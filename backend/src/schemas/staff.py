from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class InviteStaffRequest(BaseModel):
    email: str
    permissions: list[str] = []


class InviteStaffResponse(BaseModel):
    email: str
    permissions: list[str]


class UpdateStaffRequest(BaseModel):
    permissions: list[str] | None = None
    is_active: bool | None = None


class UpdateMyStaffRequest(BaseModel):
    """A staff member updating their own profile — the recurring weekly work
    schedule and their phone number are self-service; name/email/role stay
    Owner-owned."""

    work_schedule: dict | None = None
    phone: str | None = None


class StaffResponse(BaseModel):
    id: UUID
    practice_id: UUID
    email: str
    name: str | None
    phone: str | None = None
    role: str
    permissions: list[str]
    is_active: bool
    # Optional: pre-migration rows / users who never saved a schedule have a
    # NULL column — coerce to {} rather than crash StaffResponse validation.
    work_schedule: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
