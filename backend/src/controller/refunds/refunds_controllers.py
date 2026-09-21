from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.refund_request import RefundRequestedByType, RefundRequestStatus
from src.schemas.refund_request import (
    RefundRequestResponse, CreateRefundRequestRequest, ReviewRefundRequestRequest, RejectRefundRequestRequest,
)
from src.services.billing.refund_services import RefundService


class RefundsController:
    def __init__(self):
        self.service = RefundService()

    async def create(self, db: AsyncSession, user: User, data: CreateRefundRequestRequest) -> RefundRequestResponse:
        request = await self.service.create_request(
            db, user.practice_id, data.patient_id, RefundRequestedByType.STAFF, data.reason,
            invoice_id=data.invoice_id, treatment_plan_item_id=data.treatment_plan_item_id,
            requested_by_user_id=user.id,
        )
        return RefundRequestResponse.model_validate(request)

    async def list_for_practice(self, db: AsyncSession, user: User, status: RefundRequestStatus | None) -> list[RefundRequestResponse]:
        requests = await self.service.list_for_practice(db, user.practice_id, status)
        return [RefundRequestResponse.model_validate(r) for r in requests]

    async def list_for_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> list[RefundRequestResponse]:
        requests = await self.service.list_for_patient(db, user.practice_id, patient_id)
        return [RefundRequestResponse.model_validate(r) for r in requests]

    async def get(self, db: AsyncSession, user: User, request_id: UUID) -> RefundRequestResponse:
        request = await self.service.get_request(db, user.practice_id, request_id)
        return RefundRequestResponse.model_validate(request)

    async def approve(self, db: AsyncSession, user: User, request_id: UUID, data: ReviewRefundRequestRequest) -> RefundRequestResponse:
        request = await self.service.approve_request(db, user.practice_id, request_id, user.id, data.approved_amount, data.review_notes)
        return RefundRequestResponse.model_validate(request)

    async def reject(self, db: AsyncSession, user: User, request_id: UUID, data: RejectRefundRequestRequest) -> RefundRequestResponse:
        request = await self.service.reject_request(db, user.practice_id, request_id, user.id, data.review_notes)
        return RefundRequestResponse.model_validate(request)

    async def complete(self, db: AsyncSession, user: User, request_id: UUID) -> RefundRequestResponse:
        request = await self.service.complete_request(db, user.practice_id, request_id, user.id)
        return RefundRequestResponse.model_validate(request)
