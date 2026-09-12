from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.pending_doctor_request import DoctorRequestStatus
from src.schemas.doctor_application import (
    SubmitDoctorApplicationRequest,
    DoctorApplicationResponse,
    ApproveDoctorApplicationRequest,
    RejectDoctorApplicationRequest,
    UploadResponse,
)
from src.schemas.doctor import DoctorResponse
from src.services.doctor_applications.doctor_applications_service import DoctorApplicationsService


class DoctorApplicationsController:
    def __init__(self):
        self.service = DoctorApplicationsService()

    async def upload_file(self, practice_id: UUID, file_bytes: bytes, filename: str) -> UploadResponse:
        result = await self.service.upload_file(practice_id, file_bytes, filename)
        return UploadResponse(url=result["url"], name=filename)

    async def submit_application(
        self, db: AsyncSession, clerk_id: str, practice_id: UUID, data: SubmitDoctorApplicationRequest
    ) -> DoctorApplicationResponse:
        application = await self.service.submit_application(db, clerk_id, practice_id, data)
        return DoctorApplicationResponse.model_validate(application)

    async def get_my_application(self, db: AsyncSession, clerk_id: str) -> DoctorApplicationResponse:
        application = await self.service.get_my_application(db, clerk_id)
        return DoctorApplicationResponse.model_validate(application)

    async def list_applications(self, db: AsyncSession, user: User, status: str | None) -> list[DoctorApplicationResponse]:
        status_enum = DoctorRequestStatus(status) if status else None
        applications = await self.service.list_applications(db, user.practice_id, status_enum)
        return [DoctorApplicationResponse.model_validate(a) for a in applications]

    async def get_application(self, db: AsyncSession, user: User, request_id: UUID) -> DoctorApplicationResponse:
        application = await self.service.get_application(db, user.practice_id, request_id)
        return DoctorApplicationResponse.model_validate(application)

    async def approve_application(
        self, db: AsyncSession, user: User, request_id: UUID, data: ApproveDoctorApplicationRequest
    ) -> DoctorResponse:
        doctor = await self.service.approve_application(db, user.practice_id, request_id, data.permissions, user.id)
        return DoctorResponse.model_validate(doctor)

    async def reject_application(
        self, db: AsyncSession, user: User, request_id: UUID, data: RejectDoctorApplicationRequest
    ) -> DoctorApplicationResponse:
        application = await self.service.reject_application(db, user.practice_id, request_id, data.reason)
        return DoctorApplicationResponse.model_validate(application)

    async def delete_application(self, db: AsyncSession, user: User, request_id: UUID) -> None:
        await self.service.delete_application(db, user.practice_id, request_id)
