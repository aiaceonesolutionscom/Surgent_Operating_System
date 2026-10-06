from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AdminSummaryResponse(BaseModel):
    total_clinics: int
    plan_distribution: dict[str, int]
    total_estimated_mrr: float
    total_estimated_cost: float
    total_estimated_margin: float
    margin_percent: float
    assumption_note: str = "Estimated — based on an assumed average of 150 sessions/agent/month, not live usage."


# --- Super Admin platform overview (GET /admin/platform_metrics) -------------
# Real counts, measured live — the ONLY intentionally estimated number is the
# AI cost total (per-session prices × logged sessions), flagged so the UI
# can't present it as a measurement.

class ClinicStatusCounts(BaseModel):
    total: int
    active: int
    trial: int
    suspended: int


class SubscriptionCounts(BaseModel):
    active: int
    past_due: int
    cancelled: int
    # cancel_at_period_end=True (still paid up until period end) — counted
    # separately from active, which it overlaps with.
    cancelling: int
    trial: int


class AiUsageSummary(BaseModel):
    runs_total: int
    avg_latency_ms: Optional[float] = None
    estimated_cost_total: float
    cost_is_estimate: bool = True


class SystemHealthSummary(BaseModel):
    uptime_seconds: int
    db_health_ms: Optional[float] = None
    error_rate_percent: float
    slow_requests_total: int
    scope_note: str = "Measured for this API process since boot."


class PlatformMetricsResponse(BaseModel):
    clinics: ClinicStatusCounts
    total_users: int
    total_patients: int
    appointments_this_month: int
    ai: AiUsageSummary
    subscriptions: SubscriptionCounts
    system: SystemHealthSummary


class ActivityEventResponse(BaseModel):
    """One recent platform-wide event for the Super Admin ACTIVITY feed —
    read from the audit_logs trail (real actions, newest first)."""
    id: UUID
    practice_id: Optional[UUID] = None
    practice_name: Optional[str] = None
    action: str
    actor_type: str
    actor_email: Optional[str] = None
    created_at: datetime


class AdminPracticeListItem(BaseModel):
    id: UUID
    name: str
    email: str
    status: str
    plan_tier: str
    subscription_status: str
    agents_enabled_count: int
    estimated_monthly_cost: float
    estimated_monthly_revenue: float
    joined_at: datetime


class AgentCostBreakdownItem(BaseModel):
    agent_slug: str
    enabled: bool
    cost_per_session: float
    estimated_monthly_cost: float


class AdminPracticeDetailResponse(BaseModel):
    id: UUID
    name: str
    email: str
    status: str
    phone: Optional[str] = None
    address: Optional[str] = None
    plan_tier: str
    subscription_status: str
    estimated_monthly_revenue: float
    estimated_monthly_cost: float
    agent_breakdown: list[AgentCostBreakdownItem]
    joined_at: datetime


class UpdateSubscriptionRequest(BaseModel):
    tier: str


class CreatePracticeRequest(BaseModel):
    name: str
    email: str
    # "practice" (default) or "enterprise" — retired "solo" is normalized away.
    plan_tier: Optional[str] = None


class UpdatePracticeRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    plan_tier: Optional[str] = None


class OrgRequestListItem(BaseModel):
    id: UUID
    email: str
    org_name: Optional[str] = None
    status: str
    created_at: datetime


class RejectOrgRequestRequest(BaseModel):
    reason: Optional[str] = None


class ApproveOrgRequestRequest(BaseModel):
    # Which plan the approved org starts on trial of — "practice" (default)
    # or "enterprise". The retired "solo" value is rejected upstream.
    plan_tier: Optional[str] = None


class AdminUserPermissionGrant(BaseModel):
    key: str
    label: str


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str] = None
    # Practice-scoped role — "owner" | "doctor" | "receptionist" | "staff"
    role: str
    practice_id: UUID
    practice_name: Optional[str] = None
    is_active: bool
    is_platform_admin: bool
    # What the user can actually reach inside their clinic: granular grants
    # exist today only for receptionists (see data/receptionist_permissions.py);
    # owner/doctor access follows from the role itself, so this stays empty
    # for them.
    permissions: list[AdminUserPermissionGrant] = []


class UpdateAdminUserRequest(BaseModel):
    is_platform_admin: bool


class AdminMeResponse(BaseModel):
    username: str
    role: str = "platform_admin"


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class SalesLeadResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    message: Optional[str] = None
    source: str
    status: str
    conversation_id: Optional[UUID] = None
    created_at: datetime


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
