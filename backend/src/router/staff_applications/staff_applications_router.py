from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_user_record, require_role, resolve_self_apply_practice_id
from src.models.user import User, UserRole
from src.schemas.staff_application import (
    SubmitStaffApplicationRequest,
    StaffApplicationResponse,
    ApproveStaffApplicationRequest,
    RejectStaffApplicationRequest,
)
from src.schemas.staff import StaffResponse
from src.controller.staff_applications.staff_applications_controllers import StaffApplicationsController

router = APIRouter(prefix="/staff-applications", tags=["Staff Applications"])
controller = StaffApplicationsController()


@router.put("/me", response_model=StaffApplicationResponse)
async def submit_my_application(
    data: SubmitStaffApplicationRequest,
    user: User = Depends(get_current_user_record),
    db: AsyncSession = Depends(get_db),
):
    # Same submit-time healing as the doctor applications router — a stale
    # practice_id on the applicant's User row would file the receptionist
    # request where the intended Owner's Staff Requests page can't see it.
    practice_id = await resolve_self_apply_practice_id(db, user)
    return await controller.submit_application(db, user.clerk_id, practice_id, data)


@router.get("/me", response_model=StaffApplicationResponse)
async def get_my_application(
    user: User = Depends(get_current_user_record),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_my_application(db, user.clerk_id)


@router.get("", response_model=list[StaffApplicationResponse])
async def list_applications(
    status: str | None = Query(default=None),
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_applications(db, user, status)


@router.get("/{request_id}", response_model=StaffApplicationResponse)
async def get_application(
    request_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_application(db, user, request_id)


@router.post("/{request_id}/approve", response_model=StaffResponse)
async def approve_application(
    request_id: UUID,
    data: ApproveStaffApplicationRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.approve_application(db, user, request_id, data)


@router.post("/{request_id}/reject", response_model=StaffApplicationResponse)
async def reject_application(
    request_id: UUID,
    data: RejectStaffApplicationRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.reject_application(db, user, request_id, data)


@router.delete("/{request_id}", status_code=204)
async def delete_application(
    request_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    await controller.delete_application(db, user, request_id)