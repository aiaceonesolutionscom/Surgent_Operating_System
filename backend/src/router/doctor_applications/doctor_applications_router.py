from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import (
    get_current_user_record,
    get_current_practice_user,
    require_role,
    resolve_self_apply_practice_id,
)
from src.models.user import User, UserRole
from src.schemas.doctor_application import (
    SubmitDoctorApplicationRequest,
    DoctorApplicationResponse,
    ApproveDoctorApplicationRequest,
    RejectDoctorApplicationRequest,
    UploadResponse,
)
from src.schemas.doctor import DoctorResponse
from src.controller.doctor_applications.doctor_applications_controllers import DoctorApplicationsController

router = APIRouter(prefix="/doctor-applications", tags=["Doctor Applications"])
controller = DoctorApplicationsController()


@router.post("/me/upload", response_model=UploadResponse)
async def upload_application_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user_record),
):
    file_bytes = await file.read()
    return await controller.upload_file(user.practice_id, file_bytes, file.filename)


@router.put("/me", response_model=DoctorApplicationResponse)
async def submit_my_application(
    data: SubmitDoctorApplicationRequest,
    user: User = Depends(get_current_user_record),
    db: AsyncSession = Depends(get_db),
):
    # The applicant's own User row can hold a stale practice_id (from an
    # earlier relink bug) that hidden the application from the intended
    # Owner's Doctor Requests list. Re-resolve from Clerk metadata and heal
    # at submit time so the request lands on the practice that approved their
    # signup code.
    practice_id = await resolve_self_apply_practice_id(db, user)
    return await controller.submit_application(db, user.clerk_id, practice_id, data)


@router.get("/me", response_model=DoctorApplicationResponse)
async def get_my_application(
    user: User = Depends(get_current_user_record),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_my_application(db, user.clerk_id)


@router.get("", response_model=list[DoctorApplicationResponse])
async def list_applications(
    status: str | None = Query(default=None),
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_applications(db, user, status)


@router.get("/{request_id}", response_model=DoctorApplicationResponse)
async def get_application(
    request_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_application(db, user, request_id)


@router.post("/{request_id}/approve", response_model=DoctorResponse)
async def approve_application(
    request_id: UUID,
    data: ApproveDoctorApplicationRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.approve_application(db, user, request_id, data)


@router.post("/{request_id}/reject", response_model=DoctorApplicationResponse)
async def reject_application(
    request_id: UUID,
    data: RejectDoctorApplicationRequest,
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
