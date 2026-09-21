from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.models.refund_request import RefundRequestStatus
from src.schemas.refund_request import (
    RefundRequestResponse, CreateRefundRequestRequest, ReviewRefundRequestRequest, RejectRefundRequestRequest,
)
from src.controller.refunds.refunds_controllers import RefundsController

router = APIRouter(prefix="/refund-requests", tags=["Refund Requests"])
controller = RefundsController()

# Same split billing_router.py already uses — front desk runs money day to
# day, Owner has full visibility/override. Deliberately NOT open to Doctor:
# per the roadmap decision, refund approval is Owner/Receptionist territory,
# same as the actual send/sign/void consent workflow being Owner/
# Receptionist-only while a Doctor gets one narrow clinical action instead.
_VIEW_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)
_MANAGE_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)


@router.post("", response_model=RefundRequestResponse)
async def create_refund_request(
    data: CreateRefundRequestRequest,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create(db, user, data)


@router.get("", response_model=list[RefundRequestResponse])
async def list_refund_requests(
    status: RefundRequestStatus | None = Query(default=None),
    patient_id: UUID | None = Query(default=None),
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    if patient_id is not None:
        return await controller.list_for_patient(db, user, patient_id)
    return await controller.list_for_practice(db, user, status)


@router.get("/{request_id}", response_model=RefundRequestResponse)
async def get_refund_request(
    request_id: UUID,
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get(db, user, request_id)


@router.post("/{request_id}/approve", response_model=RefundRequestResponse)
async def approve_refund_request(
    request_id: UUID,
    data: ReviewRefundRequestRequest,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.approve(db, user, request_id, data)


@router.post("/{request_id}/reject", response_model=RefundRequestResponse)
async def reject_refund_request(
    request_id: UUID,
    data: RejectRefundRequestRequest,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.reject(db, user, request_id, data)


@router.post("/{request_id}/complete", response_model=RefundRequestResponse)
async def complete_refund_request(
    request_id: UUID,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.complete(db, user, request_id)
