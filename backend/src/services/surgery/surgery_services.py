from __future__ import annotations
from collections import Counter
from datetime import datetime, date, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.surgery import Surgery, SurgeryStatus
from src.models.patient import Patient
from src.models.doctor import Doctor, DoctorAvailability
from src.models.procedure import Procedure
from src.models.appointment import Appointment, AppointmentStatus
from src.server.exceptions import NotFoundException, AppException
from src.services.inventory.inventory_services import InventoryService

import logging

logger = logging.getLogger(__name__)

# Same boundary the availability slot engine uses — a cancelled/no-show
# appointment frees its minutes again.
_NON_BLOCKING_APPOINTMENT_STATUSES = {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
# A surgery that's already done or cancelled no longer occupies the doctor.
_NON_BLOCKING_SURGERY_STATUSES = {SurgeryStatus.COMPLETED, SurgeryStatus.CANCELLED}
_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class SurgeryService:
    """The end-to-end surgery record + the front-desk scheduling gate.

    Status machine: scheduled -> confirmed -> in_progress -> completed, with
    cancelled reachable from any pre-procedure state. The Receptionist books
    (scheduled/confirmed/reschedule/cancel) and the Doctor owns the clinical
    side (pre-op checklist / start / complete). Every booking runs the same
    doctor-availability check so a surgery is never pinned on a doctor who is
    off that day, already with a patient, or already in another case."""

    _WEEKDAY_KEYS = _WEEKDAY_KEYS

    def __init__(self):
        self.inventory = InventoryService()

    # ── reference verification -------------------------------------------------
    async def _verify_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> None:
        result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id))
        if result.scalar_one_or_none() is None:
            raise NotFoundException("Patient not found")

    async def _get_doctor(self, db: AsyncSession, practice_id: UUID, doctor_id: UUID) -> Doctor:
        result = await db.execute(select(Doctor).where(Doctor.id == doctor_id, Doctor.practice_id == practice_id))
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise NotFoundException("Doctor not found")
        return doctor

    async def _verify_doctor(self, db: AsyncSession, practice_id: UUID, doctor_id: UUID) -> None:
        await self._get_doctor(db, practice_id, doctor_id)

    async def _get_practice_timezone(self, db: AsyncSession, practice_id: UUID) -> ZoneInfo:
        from src.models.practice import Practice

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

    # ── doctor availability for a surgery window ---------------------------------
    async def check_surgery_availability(
        self,
        db: AsyncSession,
        practice_id: UUID,
        doctor_id: UUID,
        scheduled_date: datetime,
        duration_minutes: int | None,
        exclude_surgery_id: UUID | None = None,
    ) -> tuple[bool, list[str]]:
        """True only if this doctor can actually do the case at that time:
        active, working that day/time (or an override says yes), not already in
        an appointment, and not already booked as surgeon/assistant for
        another surgery. Returns human-readable reasons for every blocker so
        the front desk sees 'why not' instead of a bare false."""
        reasons: list[str] = []
        duration = max(duration_minutes or 60, 15)

        doctor = (
            await db.execute(select(Doctor).where(Doctor.id == doctor_id, Doctor.practice_id == practice_id))
        ).scalar_one_or_none()
        if doctor is None:
            return False, ["Doctor not found in this practice"]
        if not doctor.is_active:
            return False, [f"{doctor.name} is not active"]

        tz = await self._get_practice_timezone(db, practice_id)
        local = scheduled_date.astimezone(tz) if scheduled_date.tzinfo else scheduled_date.replace(tzinfo=tz)
        local_end = local + timedelta(minutes=duration)
        day = local.date()
        weekday_key = _WEEKDAY_KEYS[day.weekday()]

        # One-off override for that exact day (evaluated in the practice-local
        # calendar, same clamping the availability slot engine uses).
        override = (
            await db.execute(
                select(DoctorAvailability).where(
                    DoctorAvailability.doctor_id == doctor_id,
                    DoctorAvailability.date >= local.replace(hour=0, minute=0, second=0).astimezone(timezone.utc),
                    DoctorAvailability.date < (local.replace(hour=0, minute=0, second=0) + timedelta(days=1)).astimezone(timezone.utc),
                )
            )
        ).scalar_one_or_none()

        if override is not None:
            if not override.is_available:
                block = f"{doctor.name} is off / blocked that day"
                if override.reason:
                    block += f" ({override.reason})"
                return False, [block]
            ranges = override.hours or []
        else:
            ranges = (doctor.working_hours or {}).get(weekday_key, [])

        if not ranges:
            return False, [f"{doctor.name} has no working hours on {weekday_key.title()}"]

        # Does the whole [local, local_end) window fit inside a work range?
        window_ok = False
        for range_def in ranges:
            try:
                start_h, start_m = self._parse_hhmm(range_def["start"])
                end_h, end_m = self._parse_hhmm(range_def["end"])
            except (KeyError, ValueError):
                continue
            range_start = local.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            range_end = local.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
            if range_start <= local and local_end <= range_end:
                window_ok = True
                break
        if not window_ok:
            reasons.append(f"{doctor.name}'s {weekday_key.title()} hours don't cover {local.time().strftime('%H:%M')}–{local_end.time().strftime('%H:%M')}")

        # Overlapping appointments for this doctor (cancel/no-show free the slot).
        window_start_utc = local.astimezone(timezone.utc)
        window_end_utc = local_end.astimezone(timezone.utc)
        apt_conflicts = await db.execute(
            select(func.count()).select_from(Appointment).where(
                Appointment.doctor_id == doctor_id,
                Appointment.practice_id == practice_id,
                Appointment.start_time < window_end_utc,
                Appointment.end_time > window_start_utc,
                Appointment.status.notin_(list(_NON_BLOCKING_APPOINTMENT_STATUSES)),
            )
        )
        if apt_conflicts.scalar_one() > 0:
            reasons.append(f"{doctor.name} already has an appointment at that time")

        # Overlapping surgery — as surgeon OR assistant. A surgery occupies
        # [scheduled_date, scheduled_date + duration); cancelled/completed
        # cases release their window.
        candidate_rows = await db.execute(
            select(Surgery.id, Surgery.scheduled_date, Surgery.duration_estimate_minutes).where(
                Surgery.practice_id == practice_id,
                (Surgery.doctor_id == doctor_id) | (Surgery.assistant_doctor_id == doctor_id),
                Surgery.scheduled_date < window_end_utc + timedelta(days=1),
                Surgery.scheduled_date > window_start_utc - timedelta(days=1),
                Surgery.status.notin_(list(_NON_BLOCKING_SURGERY_STATUSES)),
                Surgery.id != exclude_surgery_id if exclude_surgery_id is not None else True,
            )
        )
        for row in candidate_rows.all():
            other_start = row.scheduled_date
            other_end = other_start + timedelta(minutes=max(row.duration_estimate_minutes or 60, 15))
            if other_start < window_end_utc and other_end > window_start_utc:
                reasons.append(f"{doctor.name} is already booked for another surgery at that time")
                break

        return (not reasons), reasons

    async def assert_doctor_available(
        self,
        db: AsyncSession,
        practice_id: UUID,
        doctor_id: UUID,
        scheduled_date: datetime,
        duration_minutes: int | None,
        exclude_surgery_id: UUID | None = None,
    ) -> None:
        available, reasons = await self.check_surgery_availability(
            db, practice_id, doctor_id, scheduled_date, duration_minutes, exclude_surgery_id
        )
        if not available:
            raise AppException("; ".join(reasons))

    # ── create / read -----------------------------------------------------------
    async def create_surgery(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patient_id: UUID,
        procedure_id: UUID | None,
        doctor_id: UUID,
        assistant_doctor_id: UUID | None,
        scheduled_appointment_id: UUID | None,
        scheduled_date: datetime,
        duration_estimate_minutes: int | None,
        anesthesia_type: str | None,
        facility_note: str | None,
        pre_op_checklist: list[dict],
    ) -> Surgery:
        await self._verify_patient(db, practice_id, patient_id)
        await self._verify_doctor(db, practice_id, doctor_id)
        if assistant_doctor_id is not None:
            await self._verify_doctor(db, practice_id, assistant_doctor_id)
        if procedure_id is not None:
            result = await db.execute(select(Procedure).where(Procedure.id == procedure_id, Procedure.practice_id == practice_id))
            if result.scalar_one_or_none() is None:
                raise NotFoundException("Procedure not found")

        # The front-desk gate: a surgery only gets pinned once the surgeon is
        # actually available at that time.
        await self.assert_doctor_available(db, practice_id, doctor_id, scheduled_date, duration_estimate_minutes)
        if assistant_doctor_id is not None:
            await self.assert_doctor_available(db, practice_id, assistant_doctor_id, scheduled_date, duration_estimate_minutes)

        # An appointment link must be real, practice-local, and for the same
        # patient — you can't pin a surgery for Furqan onto Salma's check-up.
        if scheduled_appointment_id is not None:
            appointment_result = await db.execute(
                select(Appointment).where(
                    Appointment.id == scheduled_appointment_id,
                    Appointment.practice_id == practice_id,
                )
            )
            appointment = appointment_result.scalar_one_or_none()
            if appointment is None:
                raise NotFoundException("Appointment not found")
            if appointment.patient_id != patient_id:
                raise AppException("Appointment belongs to a different patient")

        surgery = Surgery(
            practice_id=practice_id,
            patient_id=patient_id,
            procedure_id=procedure_id,
            doctor_id=doctor_id,
            assistant_doctor_id=assistant_doctor_id,
            scheduled_appointment_id=scheduled_appointment_id,
            scheduled_date=scheduled_date,
            duration_estimate_minutes=duration_estimate_minutes,
            anesthesia_type=anesthesia_type,
            facility_note=facility_note,
            pre_op_checklist=pre_op_checklist,
            status=SurgeryStatus.SCHEDULED,
        )
        db.add(surgery)
        await db.flush()
        return await self.get_surgery(db, practice_id, surgery.id)

    def _base_query(self):
        from sqlalchemy.orm import selectinload

        return (
            select(Surgery)
            .options(
                selectinload(Surgery.patient),
                selectinload(Surgery.procedure),
                selectinload(Surgery.doctor),
                selectinload(Surgery.assistant_doctor),
            )
        )

    async def list_for_practice(self, db: AsyncSession, practice_id: UUID) -> list[Surgery]:
        result = await db.execute(
            self._base_query().where(Surgery.practice_id == practice_id).order_by(Surgery.scheduled_date.desc())
        )
        return list(result.scalars().all())

    async def list_for_doctor(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> list[Surgery]:
        """The surgeries where the calling user's roster row is the surgeon —
        a Doctor's own "Meri Surgeries" list. A doctor whose roster row is
        missing (never approved / unlinked) simply has no surgeries."""
        doctor_result = await db.execute(
            select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        if doctor is None:
            return []
        result = await db.execute(
            self._base_query()
            .where(Surgery.practice_id == practice_id, Surgery.doctor_id == doctor.id)
            .order_by(Surgery.scheduled_date.desc())
        )
        return list(result.scalars().all())

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[Surgery]:
        await self._verify_patient(db, practice_id, patient_id)
        result = await db.execute(
            self._base_query()
            .where(Surgery.practice_id == practice_id, Surgery.patient_id == patient_id)
            .order_by(Surgery.scheduled_date.desc())
        )
        return list(result.scalars().all())

    async def get_surgery(self, db: AsyncSession, practice_id: UUID, surgery_id: UUID) -> Surgery:
        result = await db.execute(self._base_query().where(Surgery.id == surgery_id, Surgery.practice_id == practice_id))
        surgery = result.scalar_one_or_none()
        if surgery is None:
            raise NotFoundException("Surgery not found")
        return surgery

    # ── scheduling actions (Receptionist/Owner) ----------------------------------
    async def update_surgery(
        self,
        db: AsyncSession,
        practice_id: UUID,
        surgery_id: UUID,
        scheduled_date: datetime | None,
        duration_estimate_minutes: int | None,
        anesthesia_type: str | None,
        facility_note: str | None,
        assistant_doctor_id: UUID | None,
    ) -> Surgery:
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status in (SurgeryStatus.COMPLETED, SurgeryStatus.CANCELLED):
            raise AppException("Cannot reschedule a surgery that is already completed or cancelled")

        if scheduled_date is not None or duration_estimate_minutes is not None:
            new_date = scheduled_date if scheduled_date is not None else surgery.scheduled_date
            new_duration = duration_estimate_minutes if duration_estimate_minutes is not None else surgery.duration_estimate_minutes
            await self.assert_doctor_available(db, practice_id, surgery.doctor_id, new_date, new_duration, exclude_surgery_id=surgery_id)

        if scheduled_date is not None:
            surgery.scheduled_date = scheduled_date
        if duration_estimate_minutes is not None:
            surgery.duration_estimate_minutes = duration_estimate_minutes
        if anesthesia_type is not None:
            surgery.anesthesia_type = anesthesia_type
        if facility_note is not None:
            surgery.facility_note = facility_note
        if assistant_doctor_id is not None:
            await self._verify_doctor(db, practice_id, assistant_doctor_id)
            await self.assert_doctor_available(db, practice_id, assistant_doctor_id, surgery.scheduled_date, surgery.duration_estimate_minutes, exclude_surgery_id=surgery_id)
            surgery.assistant_doctor_id = assistant_doctor_id
        await db.flush()
        return await self.get_surgery(db, practice_id, surgery.id)

    async def confirm_surgery(self, db: AsyncSession, practice_id: UUID, surgery_id: UUID) -> Surgery:
        """The front desk's 'patient + doctor both agreed, lock it in' step.
        A SCHEDULED surgery moves to CONFIRMED, which is where the Doctor's
        'Meri Surgeries' pre-op view picks it up."""
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status != SurgeryStatus.SCHEDULED:
            raise AppException(f"Cannot confirm a {surgery.status.value} surgery")
        surgery.status = SurgeryStatus.CONFIRMED
        surgery.confirmed_at = datetime.now(timezone.utc)
        await db.flush()
        return await self.get_surgery(db, practice_id, surgery.id)

    # ── clinical actions (Doctor/Owner) ------------------------------------------
    async def update_surgery_clinical(
        self,
        db: AsyncSession,
        practice_id: UUID,
        surgery_id: UUID,
        pre_op_checklist: list[dict] | None,
        implants_used: list[dict] | None,
        operative_note: str | None,
    ) -> Surgery:
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status in (SurgeryStatus.COMPLETED, SurgeryStatus.CANCELLED):
            raise AppException("Cannot edit a surgery that is already completed or cancelled")
        if pre_op_checklist is not None:
            surgery.pre_op_checklist = pre_op_checklist
        if implants_used is not None:
            surgery.implants_used = implants_used
        if operative_note is not None:
            surgery.operative_note = operative_note
        await db.flush()
        return await self.get_surgery(db, practice_id, surgery.id)

    async def start_surgery(self, db: AsyncSession, practice_id: UUID, surgery_id: UUID) -> Surgery:
        """Doctor walks into the OR — CONFIRMED becomes IN_PROGRESS."""
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status != SurgeryStatus.CONFIRMED:
            raise AppException(f"Cannot start a {surgery.status.value} surgery — only confirmed surgeries can be started")
        surgery.status = SurgeryStatus.IN_PROGRESS
        surgery.started_at = datetime.now(timezone.utc)
        await db.flush()
        return await self.get_surgery(db, practice_id, surgery.id)

    async def complete_surgery(
        self, db: AsyncSession, practice_id: UUID, surgery_id: UUID, operative_note: str, implants_used: list[dict]
    ) -> Surgery:
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status != SurgeryStatus.IN_PROGRESS:
            raise AppException(f"Cannot complete a {surgery.status.value} surgery — start it before completing")

        surgery.status = SurgeryStatus.COMPLETED
        surgery.operative_note = operative_note
        surgery.implants_used = implants_used
        surgery.completed_at = datetime.now(timezone.utc)
        await db.flush()

        # Consume-on-completion: an implant entry that names a real
        # InventoryItem (via inventory_item_id — optional, since
        # implants_used stays free-text for anything not tracked in the
        # catalog) decrements that item's stock FEFO, same real path
        # InventoryService.consume already uses elsewhere. A missing item,
        # or not enough stock on hand, is logged and skipped rather than
        # failing the whole surgery-completion call.
        for entry in implants_used or []:
            item_id = entry.get("inventory_item_id")
            quantity = entry.get("quantity", 1)
            if not item_id:
                continue
            try:
                await self.inventory.consume(
                    db, practice_id, UUID(str(item_id)), int(quantity),
                    resource_type="surgery", resource_id=surgery.id, performed_by="system",
                )
            except Exception:
                logger.exception(
                    "Failed to consume inventory item %s (qty %s) for surgery %s — completing anyway",
                    item_id, quantity, surgery.id,
                )

        return await self.get_surgery(db, practice_id, surgery.id)

    async def cancel_surgery(
        self, db: AsyncSession, practice_id: UUID, surgery_id: UUID, reason: str
    ) -> Surgery:
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status in (SurgeryStatus.COMPLETED, SurgeryStatus.CANCELLED):
            raise AppException("Cannot cancel a surgery that is already completed or cancelled")

        surgery.status = SurgeryStatus.CANCELLED
        surgery.cancelled_at = datetime.now(timezone.utc)
        surgery.cancelled_reason = reason or None
        await db.flush()
        return await self.get_surgery(db, practice_id, surgery.id)

    # ── Owner overview ----------------------------------------------------------
    async def overview(
        self, db: AsyncSession, practice_id: UUID
    ) -> dict:
        now = datetime.now(timezone.utc)
        tz = await self._get_practice_timezone(db, practice_id)
        now_local = now.astimezone(tz)
        today_local = now_local.date()
        week_start = now_local - timedelta(days=now_local.weekday())
        week_start_utc = datetime.combine(week_start, time.min, tzinfo=tz).astimezone(timezone.utc)

        all_surgeries = await self.list_for_practice(db, practice_id)
        if not all_surgeries:
            return {
                "by_status": {},
                "today": [],
                "upcoming": [],
                "in_progress": [],
                "completed_this_week": 0,
                "per_doctor": [],
            }

        today = [
            s for s in all_surgeries
            if s.scheduled_date.astimezone(tz).date() == today_local and s.status not in (SurgeryStatus.COMPLETED, SurgeryStatus.CANCELLED)
        ]
        upcoming = sorted(
            [s for s in all_surgeries if s.scheduled_date > now and s.status in (SurgeryStatus.SCHEDULED, SurgeryStatus.CONFIRMED)],
            key=lambda s: s.scheduled_date,
        )[:10]
        in_progress = [s for s in all_surgeries if s.status == SurgeryStatus.IN_PROGRESS]
        completed_this_week = sum(1 for s in all_surgeries if s.status == SurgeryStatus.COMPLETED and s.completed_at and s.completed_at >= week_start_utc)

        by_doctor: dict[UUID, dict] = {}
        for s in all_surgeries:
            bucket = by_doctor.setdefault(s.doctor_id, {"doctor_id": s.doctor_id, "doctor_name": s.doctor.name, "scheduled": 0, "confirmed": 0, "in_progress": 0, "completed": 0, "cancelled": 0})
            key = s.status.value
            if key == "scheduled":
                bucket["scheduled"] += 1
            elif key == "confirmed":
                bucket["confirmed"] += 1
            elif key == "in_progress":
                bucket["in_progress"] += 1
            elif key == "completed":
                bucket["completed"] += 1
            elif key == "cancelled":
                bucket["cancelled"] += 1

        return {
            "by_status": dict(Counter(s.status.value for s in all_surgeries)),
            "today": today,
            "upcoming": upcoming,
            "in_progress": in_progress,
            "completed_this_week": completed_this_week,
            "per_doctor": list(by_doctor.values()),
        }