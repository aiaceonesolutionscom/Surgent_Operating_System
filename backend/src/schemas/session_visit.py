from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SessionVisitResponse(BaseModel):
    id: UUID
    practice_id: UUID
    patient_id: UUID
    treatment_plan_item_id: UUID
    doctor_id: UUID | None
    appointment_id: UUID | None
    session_index: int
    status: str
    scheduled_date: datetime | None
    duration_minutes: int | None
    checklist: list
    products_used: list
    session_note: str | None
    price: float | None
    confirmed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleSessionRequest(BaseModel):
    doctor_id: UUID
    start_time: datetime
    appointment_type: str | None = None
    notify_patient: bool = True


class CompleteSessionRequest(BaseModel):
    session_note: str | None = None
    products_used: list[dict] = []
    actual_price: float | None = None


class UpdateSessionChecklistRequest(BaseModel):
    checklist: list[dict]


class CancelSessionRequest(BaseModel):
    reason: str | None = None
