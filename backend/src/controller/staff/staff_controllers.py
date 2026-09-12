from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.staff import (
    InviteStaffRequest,
    InviteStaffResponse,
    UpdateStaffRequest,
    UpdateMyStaffRequest,
    StaffResponse,
)
from src.services.staff.staff_services import StaffService


class StaffController:
    def __init__(self):
        self.service = StaffService()

    async def invite_staff(self, db: AsyncSession, user: User, data: InviteStaffRequest) -> InviteStaffResponse:
        result = await self.service.invite_staff(db, user.practice_id, data.email, data.permissions)
        return InviteStaffResponse(**result)

    async def list_staff(self, db: AsyncSession, user: User) -> list[StaffResponse]:
        staff = await self.service.list_staff(db, user.practice_id)
        return [StaffResponse.model_validate(s) for s in staff]

    async def update_staff(self, db: AsyncSession, user: User, staff_id: UUID, data: UpdateStaffRequest) -> StaffResponse:
        staff = await self.service.update_staff(db, user.practice_id, staff_id, data.permissions, data.is_active)
        return StaffResponse.model_validate(staff)

    async def resend_access(self, db: AsyncSession, user: User, staff_id: UUID) -> StaffResponse:
        staff = await self.service.resend_access(db, user.practice_id, staff_id)
        return StaffResponse.model_validate(staff)

    async def get_my(self, user: User) -> StaffResponse:
        return StaffResponse.model_validate(user)

    async def update_my(self, db: AsyncSession, user: User, data: UpdateMyStaffRequest) -> StaffResponse:
        user = await self.service.update_my(db, user, data.work_schedule, data.phone)
        return StaffResponse.model_validate(user)
