from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user, require_role
from src.models.user import User, UserRole
from src.schemas.attendance import AttendanceRecordResponse, TeamMonthResponse, TeamPresenceItem
from src.controller.attendance.attendance_controllers import AttendanceController

router = APIRouter(prefix="/attendance", tags=["Attendance"])
controller = AttendanceController()


@router.post("/check-in", response_model=AttendanceRecordResponse)
async def check_in(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.check_in(db, user.practice_id, user.id)


@router.post("/check-out", response_model=AttendanceRecordResponse)
async def check_out(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.check_out(db, user.practice_id, user.id)


@router.get("/me", response_model=list[AttendanceRecordResponse])
async def list_my_attendance(
    month: str | None = Query(default=None, description="YYYY-MM; defaults to the current month"),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    return await controller.list_my_attendance(db, user, month)


def _today() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/team", response_model=list[TeamPresenceItem])
async def list_team_today(
    date: date | None = Query(default=None, description="YYYY-MM-DD; defaults to today"),
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    day = date or _today()
    return await controller.list_team(db, user, day)


@router.get("/team/records", response_model=TeamMonthResponse)
async def list_team_month(
    month: str | None = Query(default=None, description="YYYY-MM; defaults to the current month"),
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    return await controller.list_team_month(db, user, month)