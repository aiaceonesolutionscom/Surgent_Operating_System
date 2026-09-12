from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.attendance_record import AttendanceRecord
from src.models.doctor import Doctor
from src.models.practice import Practice
from src.models.user import User, UserRole
from src.server.exceptions import AppException

_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _month_bounds(month: str) -> tuple[date, date]:
    """[start, end) for a 'YYYY-MM' string."""
    year_str, month_str = month.split("-")
    year, mon = int(year_str), int(month_str)
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _weekday_key(day: date) -> str:
    """'mon'..'sun' for a date — matches the Doctor.working_hours / User.work_schedule keys."""
    return _WEEKDAY_KEYS[day.weekday()]


def _parse_hm(value: str) -> time | None:
    try:
        hour_str, minute_str = value.split(":")
        return time(int(hour_str), int(minute_str))
    except (ValueError, AttributeError):
        return None


def _expected_times(schedule: dict | None, day: date) -> tuple[str | None, str | None]:
    """Earliest start / latest end across a weekday's shift ranges, as
    'HH:MM' strings. (None, None) on an off day / empty schedule."""
    if not schedule:
        return None, None
    entries = schedule.get(_weekday_key(day))
    if not entries:
        return None, None
    starts = [_parse_hm(e.get("start", "")) for e in entries if isinstance(e, dict)]
    ends = [_parse_hm(e.get("end", "")) for e in entries if isinstance(e, dict)]
    starts = [s for s in starts if s is not None]
    ends = [e for e in ends if e is not None]
    if not starts:
        return None, None
    start = min(starts)
    end = max(ends) if ends else None
    return start.strftime("%H:%M"), end.strftime("%H:%M") if end else None


def _minutes_late(check_in_at: datetime, practice_tz: ZoneInfo | None, expected_start: str | None) -> int | None:
    """Minutes the check-in landed after the scheduled start, else None
    (off day, no schedule, or on time)."""
    if not expected_start or check_in_at is None:
        return None
    if practice_tz is None:
        return None
    try:
        local = check_in_at.astimezone(practice_tz)
        expected = _parse_hm(expected_start)
        if expected is None:
            return None
        expected_dt = local.replace(hour=expected.hour, minute=expected.minute, second=0, microsecond=0)
        delta = (local - expected_dt).total_seconds()
        return int(delta // 60) if delta > 0 else None
    except (ValueError, OverflowError):
        return None


def _zone(practice: Practice) -> ZoneInfo | None:
    tz_name = (practice.timezone or "UTC") if practice else "UTC"
    try:
        return ZoneInfo(tz_name)
    except (ValueError, OSError):
        return None


def _elapsed_minutes(record: AttendanceRecord | None, now: datetime) -> int | None:
    if record is None:
        return None
    if record.worked_minutes is not None:
        return record.worked_minutes
    if record.check_out_at is None and record.check_in_at is not None:
        return max(1, int((now - record.check_in_at).total_seconds() // 60))
    return record.worked_minutes


class AttendanceService:
    """Daily check-in / check-out for every practice user, plus owner-facing
    team presence and monthly records.

    Model: one AttendanceRecord per (user, work_date) — checked in = row with
    check_out_at NULL, checked out = row with check_out_at set and worked
    minutes tallied, absent = no row that day. The team views always start
    from "who works here" (active doctors + receptionists) and join this
    day's records, so absence shows up explicitly instead of being an empty
    query result.

    Every roster member carries their recurring weekly schedule (doctors:
    Doctor.working_hours; receptionists: User.work_schedule) so the owner sees
    who was *supposed* to be on duty, which days are off days, and how late
    someone actually checked in.
    """

    async def _doctor_for_user(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> Doctor | None:
        result = await db.execute(
            select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def check_in(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> AttendanceRecord:
        now = _now()
        day = now.date()
        existing = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.practice_id == practice_id,
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.work_date == day,
            )
        )
        if existing.scalars().first() is not None:
            raise AppException("Already checked in today")

        doctor = await self._doctor_for_user(db, practice_id, user_id)
        record = AttendanceRecord(
            practice_id=practice_id,
            user_id=user_id,
            doctor_id=doctor.id if doctor is not None else None,
            work_date=day,
            check_in_at=now,
            worked_minutes=None,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record

    async def check_out(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> AttendanceRecord:
        result = await db.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.practice_id == practice_id,
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.check_out_at.is_(None),
            )
            .order_by(AttendanceRecord.check_in_at.desc())
        )
        record = result.scalars().first()
        if record is None:
            raise AppException("Not checked in")

        record.check_out_at = _now()
        span = record.check_out_at - record.check_in_at
        record.worked_minutes = max(1, int(span.total_seconds() // 60))
        await db.flush()
        await db.refresh(record)
        return record

    async def list_my_attendance(
        self, db: AsyncSession, practice_id: UUID, user_id: UUID, month: str | None = None
    ) -> list[AttendanceRecord]:
        query = (
            select(AttendanceRecord)
            .where(
                AttendanceRecord.practice_id == practice_id,
                AttendanceRecord.user_id == user_id,
            )
            .order_by(AttendanceRecord.work_date.desc(), AttendanceRecord.check_in_at.desc())
        )
        if month:
            start, end = _month_bounds(month)
            query = query.where(
                AttendanceRecord.work_date >= start,
                AttendanceRecord.work_date < end,
            )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def _load_practice(self, db: AsyncSession, practice_id: UUID) -> Practice | None:
        return await db.get(Practice, practice_id)

    async def _staff_roster(self, db: AsyncSession, practice_id: UUID) -> list[dict]:
        """Active clinic staff: doctors (from the roster) + receptionists
        (User rows). Returns [{user_id, name, role, doctor_id, schedule}]
        where schedule is the member's recurring weekly working_hours dict."""
        items: list[dict] = []
        doctors = (
            (await db.execute(select(Doctor).where(Doctor.practice_id == practice_id, Doctor.is_active.is_(True))))
            .scalars()
            .all()
        )
        for d in doctors:
            # Doctor.user_id should always be set once the invitee signs up,
            # but if it's ever missing (invited doctor who completed Clerk
            # signup under a slightly different link), attendance recorded
            # under their User row would silently never surface on this roster
            # entry — the owner would see "absent" despite a real check-in.
            # Backfill the link by matching a DOCTOR-role User on email.
            linked_user_id = d.user_id
            if linked_user_id is None and d.email:
                match = (
                    await db.execute(
                        select(User.id)
                        .where(
                            User.practice_id == practice_id,
                            User.role == UserRole.DOCTOR,
                            User.email.ilike(d.email.strip()),
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if match is not None:
                    linked_user_id = match
            items.append(
                {
                    "user_id": linked_user_id,
                    "name": d.name,
                    "role": "doctor",
                    "doctor_id": d.id,
                    "schedule": d.working_hours or {},
                }
            )

        receptionists = (
            (
                await db.execute(
                    select(User).where(
                        User.practice_id == practice_id,
                        User.role == UserRole.RECEPTIONIST,
                        User.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for u in receptionists:
            items.append(
                {
                    "user_id": u.id,
                    "name": u.name,
                    "role": "receptionist",
                    "doctor_id": None,
                    "schedule": u.work_schedule or {},
                }
            )
        return items

    async def _day_records(self, db: AsyncSession, practice_id: UUID, day: date, user_ids: list[UUID]) -> dict:
        if not user_ids:
            return {}
        result = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.practice_id == practice_id,
                AttendanceRecord.work_date == day,
                AttendanceRecord.user_id.in_(user_ids),
            )
        )
        return {r.user_id: r for r in result.scalars().all()}

    async def list_team_today(
        self, db: AsyncSession, practice_id: UUID, day: date | None = None
    ) -> list[dict]:
        day = day or _now().date()
        practice = await self._load_practice(db, practice_id)
        zone = _zone(practice)
        roster = await self._staff_roster(db, practice_id)
        by_user = await self._day_records(
            db, practice_id, day, [s["user_id"] for s in roster if s["user_id"]]
        )
        items = []
        for s in roster:
            record = by_user.get(s["user_id"])
            expected_start, expected_end = _expected_times(s["schedule"], day)
            if record is None:
                status = "absent"
            elif record.check_out_at is None:
                status = "checked_in"
            else:
                status = "checked_out"
            items.append(
                {
                    "user_id": s["user_id"],
                    "name": s["name"],
                    "role": s["role"],
                    "doctor_id": s["doctor_id"],
                    "status": status,
                    "check_in_at": record.check_in_at if record else None,
                    "check_out_at": record.check_out_at if record else None,
                    "worked_minutes": _elapsed_minutes(record, _now()) if record else None,
                    "scheduled_today": expected_start is not None,
                    "scheduled_start": expected_start,
                    "scheduled_end": expected_end,
                    "late_minutes": (
                        _minutes_late(record.check_in_at, zone, expected_start)
                        if record is not None and status == "checked_in"
                        else None
                    ),
                }
            )
        return items

    async def list_team_month(
        self, db: AsyncSession, practice_id: UUID, month: str
    ) -> dict:
        start, end = _month_bounds(month)
        practice = await self._load_practice(db, practice_id)
        zone = _zone(practice)
        now = _now()
        roster = await self._staff_roster(db, practice_id)
        ids = [s["user_id"] for s in roster if s["user_id"]]
        grouped: dict[UUID, list[AttendanceRecord]] = {}
        if ids:
            result = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.practice_id == practice_id,
                    AttendanceRecord.work_date >= start,
                    AttendanceRecord.work_date < end,
                    AttendanceRecord.user_id.in_(ids),
                )
            )
            for r in result.scalars().all():
                grouped.setdefault(r.user_id, []).append(r)

        members = []
        for s in roster:
            records = grouped.get(s["user_id"]) or []
            # In-progress (checked in, not yet out) days count toward
            # presence — previously they were dropped here, so a doctor who
            # checked in but was still on duty vanished from the owner's
            # monthly view entirely.
            records.sort(key=lambda r: r.work_date)
            member_records = []
            for r in records:
                expected_start_value, _ = _expected_times(s["schedule"], r.work_date)
                member_records.append(
                    {
                        "work_date": r.work_date,
                        "check_in_at": r.check_in_at,
                        "check_out_at": r.check_out_at,
                        "worked_minutes": _elapsed_minutes(r, now),
                        "late_minutes": _minutes_late(r.check_in_at, zone, expected_start_value),
                    }
                )
            members.append(
                {
                    "user_id": s["user_id"],
                    "name": s["name"],
                    "role": s["role"],
                    "doctor_id": s["doctor_id"],
                    "records": member_records,
                    "present_days": len(member_records),
                    "total_minutes": sum((m["worked_minutes"] or 0) for m in member_records),
                }
            )
        return {"month": month, "members": members}