from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CreateRefundRequestRequest(BaseModel):
    """Staff- or portal-raised refund request — the AI receptionist never
    calls this endpoint directly (it goes through its own tool in
    inbound_service.py, which fills in requested_by_type itself)."""
    patient_id: UUID
    invoice_id: UUID | None = None
    treatment_plan_item_id: UUID | None = None
    reason: str | None = None


class ReviewRefundRequestRequest(BaseModel):
    approved_amount: float | None = None
    review_notes: str | None = None


class RejectRefundRequestRequest(BaseModel):
    review_notes: str | None = None


class RefundRequestResponse(BaseModel):
    id: UUID
    practice_id: UUID
    patient_id: UUID
    invoice_id: UUID | None
    treatment_plan_item_id: UUID | None
    requested_by_type: str
    requested_by_user_id: UUID | None
    reason: str | None
    requested_amount: float | None
    calculation_basis: dict | None
    approved_amount: float | None
    status: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
