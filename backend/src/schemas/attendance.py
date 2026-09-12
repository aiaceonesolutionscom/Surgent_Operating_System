from __future__ import annotations
from typing import Literal

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class AttendanceRecordResponse(BaseModel):
    id: UUID
    practice_id: UUID
    user_id: UUID
    doctor_id: UUID | None
    work_date: date
    check_in_at: datetime
    check_out_at: datetime | None
    worked_minutes: int | None
    status: Literal["checked_in", "checked_out"]

    model_config = {"from_attributes": True}


class TeamPresenceItem(BaseModel):
    """One active staff member and their state for a single day."""

    user_id: UUID | None
    name: str
    role: Literal["doctor", "receptionist"]
    doctor_id: UUID | None
    status: Literal["checked_in", "checked_out", "absent"]
    check_in_at: datetime | None
    check_out_at: datetime | None
    worked_minutes: int | None
    # Derived from the member's weekly schedule (Doctor.working_hours /
    # User.work_schedule) for the checked date.
    scheduled_today: bool = False
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    late_minutes: int | None = None


class AttendanceDayRecord(BaseModel):
    work_date: date
    check_in_at: datetime
    check_out_at: datetime | None
    worked_minutes: int | None
    late_minutes: int | None = None


class TeamMonthMember(BaseModel):
    user_id: UUID | None
    name: str
    role: Literal["doctor", "receptionist"]
    doctor_id: UUID | None
    records: list[AttendanceDayRecord]
    present_days: int
    total_minutes: int


class TeamMonthResponse(BaseModel):
    month: str
    members: list[TeamMonthMember]