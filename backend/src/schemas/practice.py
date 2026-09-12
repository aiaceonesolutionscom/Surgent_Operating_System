from __future__ import annotations
from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PracticeMeResponse(BaseModel):
    id: UUID
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    timezone: str
    plan_tier: str
    subscription_status: str
    role: str
    # Only meaningful when role == "doctor" or "receptionist" — the granted
    # permission keys from data/doctor_permissions.py (models/doctor.py's
    # `permissions` column) or data/receptionist_permissions.py
    # (models/user.py's `permissions` column) respectively. Empty for Owner.
    permissions: list[str] = []


class UpdatePracticeRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None


class ClaimPlanRequest(BaseModel):
    session_id: str


class ClaimPlanResponse(BaseModel):
    practice_id: UUID
    plan_tier: str


class DoctorSignupCodeResponse(BaseModel):
    code: str
    signup_url: str


class ValidateDoctorCodeResponse(BaseModel):
    valid: bool
    practice_id: Optional[UUID] = None
    practice_name: Optional[str] = None


class UpdateGreenApiSettingsRequest(BaseModel):
    instance_id: str
    api_token: str


class GreenApiSettingsResponse(BaseModel):
    connected: bool
    instance_id: Optional[str] = None
    state: Optional[str] = None  # Green API's own getStateInstance value (e.g. "authorized")
    error: Optional[str] = None


class MetaSettingsResponse(BaseModel):
    configured: bool  # platform-level: is a real Facebook App set up at all
    connected: bool  # practice-level: has THIS practice authorized it
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    ig_business_id: Optional[str] = None


class MetaConnectUrlResponse(BaseModel):
    url: str
    state: str


class MetaCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class SubmitOrgRequestRequest(BaseModel):
    org_name: str


class OrgRequestResponse(BaseModel):
    id: UUID
    email: str
    org_name: Optional[str] = None
    status: str  # PendingSignup.request_status.value — "pending" | "approved" | "rejected"
    rejected_reason: Optional[str] = None

    @classmethod
    def from_model(cls, pending) -> "OrgRequestResponse":
        return cls(
            id=pending.id,
            email=pending.email,
            org_name=pending.org_name,
            status=pending.request_status.value if pending.request_status else "pending",
            rejected_reason=pending.rejected_reason,
        )
