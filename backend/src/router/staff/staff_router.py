from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role, get_current_practice_user
from src.models.user import User, UserRole
from src.schemas.staff import (
    InviteStaffRequest,
    InviteStaffResponse,
    UpdateStaffRequest,
    UpdateMyStaffRequest,
    StaffResponse,
)
from src.controller.staff.staff_controllers import StaffController

router = APIRouter(prefix="/staff", tags=["Staff"])
controller = StaffController()


@router.post("", response_model=InviteStaffResponse)
async def invite_staff(
    data: InviteStaffRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.invite_staff(db, user, data)


@router.get("", response_model=list[StaffResponse])
async def list_staff(
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_staff(db, user)


@router.get("/me", response_model=StaffResponse)
async def get_my_staff(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # Registered before /{staff_id} — a staff member's own profile (name,
    # role, permissions, work_schedule) used by their profile page.
    return await controller.get_my(user)


@router.patch("/me", response_model=StaffResponse)
async def update_my_staff(
    data: UpdateMyStaffRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # Self-service profile update (work_schedule only). Also before
    # /{staff_id} for the same routing reason.
    return await controller.update_my(db, user, data)


@router.patch("/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: UUID,
    data: UpdateStaffRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_staff(db, user, staff_id, data)


@router.post("/{staff_id}/resend-access", response_model=StaffResponse)
async def resend_staff_access(
    staff_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    # The Owner's "help them log back in" lever (see StaffService.resend_access's
    # docstring) — for a receptionist whose Clerk session is gone, not for
    # deactivating/reactivating (that's PATCH /{staff_id} with is_active).
    return await controller.resend_access(db, user, staff_id)
