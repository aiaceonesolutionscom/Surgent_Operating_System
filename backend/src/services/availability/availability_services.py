from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.practice import Practice
from src.models.doctor import Doctor, DoctorAvailability
from src.models.appointment import Appointment, AppointmentStatus
from src.schemas.availability import DoctorSlotsResponse, TimeSlot
from src.server.exceptions import NotFoundException, AppException

# Booking never considers an appointment "occupied" if it was cancelled or a
# no-show — those minutes are genuinely open again.
_NON_BLOCKING_STATUSES = {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}


class AvailabilitySlotService:
    """Computes a doctor's actually-bookable time slots for a date range:
    weekly `Doctor.working_hours` (practice-local clock) minus one-off
    `DoctorAvailability` overrides (a blocked day, an extra clinic day), with
    each generated slot marked unavailable when an existing appointment
    already occupies it. This is the missing 'pick a time' surface — booking
    today just takes a raw start/end with no slot awareness, and nothing on
    the API could tell a patient OR front desk what times are even open."""

    _WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    async def get_practice_timezone(self, db: AsyncSession, practice_id: UUID) -> ZoneInfo:
        practice = await db.get(Practice, practice_id)
        name = practice.timezone if practice and practice.timezone else "UTC"
        try:
            return ZoneInfo(name)
        except Exception:
            return ZoneInfo("UTC")

    @staticmethod
    def _parse_hhmm(value: str) -> tuple[int, int]:
        hour, minute = value.split(":")
        return int(hour), int(minute)

    async def get_slots(
        self,
        db: AsyncSession,
        practice_id: UUID,
        doctor_id: UUID,
        start_date: date,
        days: int = 7,
        duration_minutes: int = 30,
    ) -> list[DoctorSlotsResponse]:
        if duration_minutes < 15 or duration_minutes > 240:
            raise AppException("duration_minutes must be between 15 and 240")
        if days < 1 or days > 31:
            raise AppException("days must be between 1 and 31")

        doctor = (
            await db.execute(select(Doctor).where(Doctor.id == doctor_id, Doctor.practice_id == practice_id))
        ).scalar_one_or_none()
        if doctor is None:
            raise NotFoundException("Doctor not found in this practice")

        tz = await self.get_practice_timezone(db, practice_id)
        end_date = start_date + timedelta(days=days)

        # The override window, in the practice-local calendar, clamped to UTC
        # for the SQL query so timezone drift can't drop a boundary override.
        window_start_local = datetime.combine(start_date, time.min, tzinfo=tz)
        window_end_local = datetime.combine(end_date, time.min, tzinfo=tz)
        override_result = await db.execute(
            select(DoctorAvailability).where(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.date >= window_start_local.astimezone(timezone.utc),
                DoctorAvailability.date < window_end_local.astimezone(timezone.utc),
            )
        )
        overrides_by_date: dict[date, DoctorAvailability] = {}
        for override in override_result.scalars().all():
            override_date = override.date
            if override_date.tzinfo is not None:
                override_date = override_date.astimezone(tz)
            overrides_by_date[override_date.date()] = override

        # Occupied windows from real appointments so each slot can be truthfully
        # marked. Statuses in _NON_BLOCKING_STATUSES free their minutes again.
        apt_result = await db.execute(
            select(Appointment.start_time, Appointment.end_time).where(
                Appointment.doctor_id == doctor_id,
                Appointment.start_time < window_end_local.astimezone(timezone.utc),
                Appointment.end_time > window_start_local.astimezone(timezone.utc),
                Appointment.status.notin_(list(_NON_BLOCKING_STATUSES)),
            )
        )
        occupied = [
            (
                start.astimezone(tz) if start.tzinfo is not None else start.replace(tzinfo=tz),
                end.astimezone(tz) if end.tzinfo is not None else end.replace(tzinfo=tz),
            )
            for start, end in apt_result.all()
        ]

        responses: list[DoctorSlotsResponse] = []
        day: date = start_date
        while day < end_date:
            slots = self._day_slots(day, tz, doctor.working_hours, overrides_by_date.get(day), duration_minutes)
            if not slots:
                day += timedelta(days=1)
                continue
            decorated = [
                TimeSlot(
                    start_time=self._as_utc(slot_start, tz),
                    end_time=self._as_utc(slot_end, tz),
                    available=not self._occupied(slot_start, slot_end, occupied),
                )
                for slot_start, slot_end in slots
            ]
            responses.append(DoctorSlotsResponse(doctor_id=doctor_id, date=day, slots=decorated))
            day += timedelta(days=1)
        return responses

    @staticmethod
    def _as_utc(value: datetime, tz: ZoneInfo) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        return value.astimezone(timezone.utc)

    def _day_slots(
        self,
        day: date,
        tz: ZoneInfo,
        working_hours: dict[str, Any] | None,
        override: DoctorAvailability | None,
        duration_minutes: int,
    ) -> list[tuple[datetime, datetime]]:
        if override is not None:
            if not override.is_available:
                return []
            ranges: list[dict[str, str]] = override.hours or []
        else:
            weekday_key = day.strftime("%a").lower()
            working = (working_hours or {}).get(weekday_key, [])
            if not working:
                return []
            ranges = working

        day_start = datetime.combine(day, time.min, tzinfo=tz)
        slots: list[tuple[datetime, datetime]] = []
        for range_def in ranges:
            try:
                start_h, start_m = self._parse_hhmm(range_def["start"])
                end_h, end_m = self._parse_hhmm(range_def["end"])
            except (KeyError, ValueError):
                continue
            cursor = day_start.replace(hour=start_h, minute=start_m)
            window_end = day_start.replace(hour=end_h, minute=end_m)
            while cursor + timedelta(minutes=duration_minutes) <= window_end:
                slots.append((cursor, cursor + timedelta(minutes=duration_minutes)))
                cursor += timedelta(minutes=duration_minutes)
        return slots

    @staticmethod
    def _occupied(
        slot_start: datetime,
        slot_end: datetime,
        occupied: list[tuple[datetime, datetime]],
    ) -> bool:
        for app_start, app_end in occupied:
            if app_start < slot_end and app_end > slot_start:
                return True
        return False