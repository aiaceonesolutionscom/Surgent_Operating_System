from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.pending_staff_request import StaffRequestStatus
from src.schemas.staff_application import (
    SubmitStaffApplicationRequest,
    StaffApplicationResponse,
    ApproveStaffApplicationRequest,
    RejectStaffApplicationRequest,
)
from src.schemas.staff import StaffResponse
from src.services.staff_applications.staff_applications_service import StaffApplicationsService


class StaffApplicationsController:
    def __init__(self):
        self.service = StaffApplicationsService()

    async def submit_application(
        self, db: AsyncSession, clerk_id: str, practice_id: UUID, data: SubmitStaffApplicationRequest
    ) -> StaffApplicationResponse:
        application = await self.service.submit_application(db, clerk_id, practice_id, data)
        return StaffApplicationResponse.model_validate(application)

    async def get_my_application(self, db: AsyncSession, clerk_id: str) -> StaffApplicationResponse:
        application = await self.service.get_my_application(db, clerk_id)
        return StaffApplicationResponse.model_validate(application)

    async def list_applications(self, db: AsyncSession, user: User, status: str | None) -> list[StaffApplicationResponse]:
        status_enum = StaffRequestStatus(status) if status else None
        applications = await self.service.list_applications(db, user.practice_id, status_enum)
        return [StaffApplicationResponse.model_validate(a) for a in applications]

    async def get_application(self, db: AsyncSession, user: User, request_id: UUID) -> StaffApplicationResponse:
        application = await self.service.get_application(db, user.practice_id, request_id)
        return StaffApplicationResponse.model_validate(application)

    async def approve_application(
        self, db: AsyncSession, user: User, request_id: UUID, data: ApproveStaffApplicationRequest
    ) -> StaffResponse:
        staff = await self.service.approve_application(db, user.practice_id, request_id, data.permissions, user.id)
        return StaffResponse.model_validate(staff)

    async def reject_application(
        self, db: AsyncSession, user: User, request_id: UUID, data: RejectStaffApplicationRequest
    ) -> StaffApplicationResponse:
        application = await self.service.reject_application(db, user.practice_id, request_id, data.reason)
        return StaffApplicationResponse.model_validate(application)

    async def delete_application(self, db: AsyncSession, user: User, request_id: UUID) -> None:
        await self.service.delete_application(db, user.practice_id, request_id)