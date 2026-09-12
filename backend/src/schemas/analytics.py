from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID


class OverviewSummaryResponse(BaseModel):
    sessions_today: int
    needs_attention: int
    bookings_this_week: int
    # Sum of completed TreatmentPlanItems' actual/estimated price — real,
    # clinically-linked revenue, not a projection. None (not 0) when nothing
    # is completed yet, so the frontend can show an honest "not enough data"
    # state instead of a fabricated $0.
    revenue_estimate: float | None = None


class ChannelCount(BaseModel):
    channel: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class SessionAnalyticsResponse(BaseModel):
    total_conversations: int
    active_count: int
    needs_attention_count: int
    resolved_count: int
    by_channel: list[ChannelCount]
    by_category: list[CategoryCount]


# --- Reporting (Practice plan) ---

class RevenuePointResponse(BaseModel):
    """One bucket of the revenue-over-time series. `bucket` is the bucket's
    ISO-label (a day, week-start date, or month-start date depending on
    group_by). Revenue is the total of payments recorded in that bucket —
    actual cash in, not the plan-estimate figure /overview uses."""

    bucket: str
    revenue: float
    payments_count: int


class RevenueTrendResponse(BaseModel):
    total_revenue: float
    buckets: list[RevenuePointResponse]


class FunnelStage(BaseModel):
    stage: str
    count: int


class FunnelResponse(BaseModel):
    """Counts of unique patients at each milestone of the practice journey —
    inquiry (patient created) → booked → consulted → planned → operated →
    paid. Each stage counts *distinct* patients so a patient with five
    appointments still contributes one, keeping the funnel honest."""

    stages: list[FunnelStage]


class DoctorPerformanceResponse(BaseModel):
    doctor_id: UUID
    name: str
    appointment_count: int
    completed_appointments: int
    revenue: float


class ProcedureAnalyticsResponse(BaseModel):
    procedure_id: UUID
    name: str
    proposals: int
    completed: int
    revenue: float


class AppointmentAnalyticsResponse(BaseModel):
    total_appointments: int
    status_counts: dict[str, int]
    no_show_count: int
    no_show_rate: float
