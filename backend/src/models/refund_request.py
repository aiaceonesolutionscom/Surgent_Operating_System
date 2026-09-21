import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Numeric, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class RefundRequestedByType(str, enum.Enum):
    AI_RECEPTIONIST = "ai_receptionist"
    PATIENT_PORTAL = "patient_portal"
    STAFF = "staff"


class RefundRequestStatus(str, enum.Enum):
    # REQUESTED -> APPROVED (decision made, money not moved yet) ->
    # COMPLETED (a real reversing Payment has been recorded against the
    # invoice) is deliberately three separate steps, not two: "we've agreed
    # to refund you" and "the money has actually gone back" are different
    # moments in a real clinic (cash drawer, bank transfer, POS reversal),
    # and Finance needs to be able to tell "promised but not yet paid out"
    # (a liability) from "already paid out" (already reflected in revenue).
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RefundRequest(Base):
    """A patient wanting their money back — whether they said so to the AI
    receptionist on WhatsApp, through the patient portal, or in person to
    front desk — always lands here as a real, reviewable record instead of
    anyone (least of all the AI) just deciding it on the spot. The AI's own
    tool (see services/channels/inbound_service.py) can ONLY create one of
    these in REQUESTED status; nothing in the system lets it approve, set an
    amount, or complete one — see prompt_blocks.py's guardrails for why that
    boundary matters here specifically.

    `requested_amount` is a suggested pro-rata figure the service computes
    from session-completion state when the request is tied to a specific
    multi-session TreatmentPlanItem (see RefundService.create_request) —
    always reviewable/overridable by whoever approves it, never binding."""

    __tablename__ = "refund_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    # Nullable: an AI-raised request often can't reliably identify which
    # invoice the patient means from a WhatsApp message alone — staff
    # resolves/attaches the right invoice during review rather than the AI
    # guessing wrong. A staff- or portal-raised request usually has one from
    # the start.
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    treatment_plan_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("treatment_plan_items.id"), nullable=True
    )
    requested_by_type: Mapped[RefundRequestedByType] = mapped_column(Enum(RefundRequestedByType), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    requested_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # {"formula": "pro_rata"|"manual", "sessions_total":, "sessions_completed":,
    #  "sessions_remaining":, "item_total":, "amount_paid": ...} — the numbers
    # behind requested_amount, kept for the reviewer (and any later audit) to
    # see exactly how the suggestion was derived rather than trusting a bare
    # figure.
    calculation_basis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approved_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[RefundRequestStatus] = mapped_column(Enum(RefundRequestStatus), default=RefundRequestStatus.REQUESTED)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice")
    patient = relationship("Patient")
    invoice = relationship("Invoice")
    treatment_plan_item = relationship("TreatmentPlanItem")
    requested_by_user = relationship("User", foreign_keys=[requested_by_user_id])
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by])
