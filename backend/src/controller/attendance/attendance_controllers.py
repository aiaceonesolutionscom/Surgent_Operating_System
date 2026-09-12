from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.attendance_record import AttendanceRecord
from src.schemas.attendance import (
    AttendanceRecordResponse,
    TeamMonthResponse,
    TeamPresenceItem,
)
from src.services.attendance.attendance_service import AttendanceService


def _record_response(record: AttendanceRecord) -> AttendanceRecordResponse:
    return AttendanceRecordResponse(
        id=record.id,
        practice_id=record.practice_id,
        user_id=record.user_id,
        doctor_id=record.doctor_id,
        work_date=record.work_date,
        check_in_at=record.check_in_at,
        check_out_at=record.check_out_at,
        worked_minutes=record.worked_minutes,
        status="checked_out" if record.check_out_at is not None else "checked_in",
    )


class AttendanceController:
    def __init__(self):
        self.service = AttendanceService()

    async def check_in(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> AttendanceRecordResponse:
        record = await self.service.check_in(db, practice_id, user_id)
        return _record_response(record)

    async def check_out(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> AttendanceRecordResponse:
        record = await self.service.check_out(db, practice_id, user_id)
        return _record_response(record)

    async def list_my_attendance(
        self, db: AsyncSession, user, month: str | None
    ) -> list[AttendanceRecordResponse]:
        records = await self.service.list_my_attendance(db, user.practice_id, user.id, month)
        return [_record_response(r) for r in records]

    async def list_team(self, db: AsyncSession, user, day: date | None) -> list[TeamPresenceItem]:
        items = await self.service.list_team_today(db, user.practice_id, day)
        return [TeamPresenceItem.model_validate(i) for i in items]

    async def list_team_month(self, db: AsyncSession, user, month: str) -> TeamMonthResponse:
        data = await self.service.list_team_month(db, user.practice_id, month)
        return TeamMonthResponse.model_validate(data)