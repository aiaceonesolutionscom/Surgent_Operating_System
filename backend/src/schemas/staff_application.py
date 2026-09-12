from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SubmitStaffApplicationRequest(BaseModel):
    name: str
    email: str
    phone: str | None = None


class StaffApplicationResponse(BaseModel):
    id: UUID
    practice_id: UUID
    name: str
    email: str
    phone: str | None
    status: str
    rejected_reason: str | None
    user_id: UUID | None
    submitted_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ApproveStaffApplicationRequest(BaseModel):
    permissions: list[str] = []


class RejectStaffApplicationRequest(BaseModel):
    reason: str | None = None