from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date


class CreateExpenseRequest(BaseModel):
    expense_type: str = "expense"  # "expense" | "refund" | "salary"
    status: str = "paid"           # "paid" | "pending"
    category: str
    amount: float
    vendor: str | None = None
    payee_name: str | None = None  # staff name for salary payments
    expense_date: date
    notes: str | None = None


class UpdateExpenseRequest(BaseModel):
    expense_type: str | None = None
    status: str | None = None
    category: str | None = None
    amount: float | None = None
    vendor: str | None = None
    payee_name: str | None = None
    expense_date: date | None = None
    notes: str | None = None
    paid_at: datetime | None = None


class ExpenseResponse(BaseModel):
    id: UUID
    practice_id: UUID
    expense_type: str
    status: str
    category: str
    amount: float
    vendor: str | None
    payee_name: str | None
    expense_date: date
    notes: str | None
    paid_at: datetime | None
    recorded_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FinanceOverviewResponse(BaseModel):
    # Real sums, not estimates — $0 with zero counts is a true (not
    # fabricated) value, unlike AnalyticsService.get_overview_summary()'s
    # revenue_estimate, which needs a None/"not enough data" state because
    # it's inferring from possibly-incomplete data. The frontend uses
    # invoice_count/expense_count to decide whether to show an empty state.
    total_revenue: float
    total_expenses: float
    net: float
    invoice_count: int
    expense_count: int
    # --- Accountant's view additions (refunds + deferred revenue) --------
    # Actual cash paid back out — sum of every completed refund (negative
    # Payment rows). total_revenue above (PAID invoices' total_amount) does
    # NOT move when a refund happens later, so it overstates what the clinic
    # actually kept — net_revenue_after_refunds is the corrected figure.
    total_refunds: float = 0
    net_revenue_after_refunds: float = 0
    # Requests sitting at REQUESTED or APPROVED (money not moved yet) — a
    # liability the clinic may still owe back, not yet reflected above.
    pending_refund_requests_count: int = 0
    pending_refund_liability: float = 0
    # Money already collected (PAID/PARTIALLY_PAID invoices) for
    # multi-session treatment-plan items whose sessions aren't all delivered
    # yet — collected but not yet earned, the standard accrual-accounting
    # concept this practice-management cash view didn't have before. An
    # estimate: it prorates each such line item's paid share by
    # sessions_remaining/sessions_total.
    deferred_revenue: float = 0
