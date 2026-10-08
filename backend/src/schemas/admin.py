from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AdminSummaryResponse(BaseModel):
    total_clinics: int
    plan_distribution: dict[str, int]
    # MRR = what ACTIVE (paying) subscriptions bill per month. Trials are not
    # revenue yet, so they are reported as pipeline instead.
    mrr: float
    trial_pipeline_mrr: float
    # This month's AI spend: tokens x provider list price, from llm_calls.
    ai_cost_month: float
    margin: float
    margin_percent: float
    cost_basis: str = "AI cost is month-to-date tokens x provider list price; MRR counts active paid subscriptions only."


# --- Super Admin platform overview (GET /admin/platform_metrics) -------------
# Every figure is read from the database. The one derived number is AI cost:
# measured tokens x the provider's list price (pricing in services/telemetry).

class ClinicStatusCounts(BaseModel):
    total: int
    active: int
    trial: int
    suspended: int
    # Switched on but with no live subscription (never subscribed / cancelled).
    unsubscribed: int = 0


class SubscriptionCounts(BaseModel):
    active: int
    past_due: int
    cancelled: int
    # cancel_at_period_end=True (still paid up until period end) — counted
    # separately from active, which it overlaps with.
    cancelling: int
    trial: int


class AiSourceUsage(BaseModel):
    source: str
    calls: int
    cost_usd: float


class AiUsageSummary(BaseModel):
    calls_total: int
    calls_month: int
    calls_24h: int
    avg_latency_ms_24h: Optional[float] = None
    p95_latency_ms_24h: Optional[float] = None
    # Share of the last 24h of provider calls that failed or were rate limited.
    error_rate_percent_24h: float
    tokens_month: int
    cost_month_usd: float
    cost_total_usd: float
    # Rows in agent_logs (what AI agents did, e.g. "reply.sent") — a different
    # thing from provider calls, shown alongside it.
    agent_actions_30d: int
    top_sources: list[AiSourceUsage] = []
    cost_basis: str = "list_price"


class SlowQueryItem(BaseModel):
    statement: str
    count: int
    max_ms: int
    avg_ms: int


class SystemHealthSummary(BaseModel):
    uptime_seconds: int
    started_at: datetime
    restarts_24h: int
    requests_24h: int
    error_rate_percent: float
    avg_response_ms_24h: Optional[float] = None
    slow_requests_24h: int
    slow_queries_24h: int
    top_slow_queries: list[SlowQueryItem] = []
    db_health_ms: Optional[float] = None
    scope_note: str = (
        "Request, error and slow-query figures cover the last 24h across all API instances; "
        "uptime is for the instance that served this request."
    )


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
    # Measured: month-to-date AI spend (tokens x list price) and what the
    # clinic's active subscription bills monthly (0 while on trial).
    patients_count: int = 0
    ai_calls_month: int = 0
    ai_cost_month: float = 0.0
    mrr: float = 0.0
    # Projected from the plan design (assumed sessions/agent/month), not measured.
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
    # Measured (see AdminPracticeListItem).
    patients_count: int = 0
    users_count: int = 0
    appointments_month: int = 0
    ai_calls_month: int = 0
    ai_cost_month: float = 0.0
    mrr: float = 0.0
    last_activity_at: Optional[datetime] = None


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
