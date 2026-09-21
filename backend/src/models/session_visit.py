import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer, Numeric, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class SessionVisitStatus(str, enum.Enum):
    # Mirrors Surgery's own status machine (see models/surgery.py) —
    # PLANNED is the one extra state: a session exists (as part of a
    # multi-visit TreatmentPlanItem) before anyone has picked a date for it,
    # which Surgery never needed since a surgery always has a scheduled_date
    # from creation.
    PLANNED = "planned"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class SessionVisit(Base):
    """One real visit within a (possibly multi-visit) TreatmentPlanItem —
    "session 2 of 6" for a laser-hair-removal course, or the single session
    of a one-visit Botox item. Generalizes Surgery's own pattern (status
    machine, checklist, lifecycle timestamps) to every procedure, not just
    major operations: a Botox/filler/laser visit gets the same real
    pre-visit checklist and completion record a surgery does, scaled down
    (no anesthesia/assistant-surgeon/implant-traceability fields that don't
    apply outside the OR).

    Session count and completion state are what a refund's pro-rata
    calculation reads (see RefundService) — "2 of 6 sessions done" is what
    makes "refund the other 4" a real, defensible number instead of a guess."""

    __tablename__ = "session_visits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    treatment_plan_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("treatment_plan_items.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    # 1-based position within the parent item's sessions_total — "session
    # 2 of 6" is session_index=2 against TreatmentPlanItem.sessions_total=6.
    session_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SessionVisitStatus] = mapped_column(Enum(SessionVisitStatus), default=SessionVisitStatus.PLANNED)
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # List of {item, checked, checked_by, checked_at} — seeded from
    # Procedure.default_checklist when this session is created.
    checklist: Mapped[list] = mapped_column(JSONB, default=list)
    # List of {name, quantity, unit, inventory_item_id} — the generic,
    # non-implant version of Surgery.implants_used (Botox units, filler ml,
    # a numbing-cream tube). inventory_item_id is optional; only entries
    # naming a real catalog item get consumed from stock on completion.
    products_used: Mapped[list] = mapped_column(JSONB, default=list)
    session_note: Mapped[str] = mapped_column(Text, nullable=True)
    # Per-session price — defaults to the parent item's estimated_price
    # divided across sessions_total when the session is created, editable
    # afterward. This is what a refund's pro-rata math actually sums, not a
    # guess re-derived from the item every time.
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice")
    patient = relationship("Patient")
    treatment_plan_item = relationship("TreatmentPlanItem", back_populates="session_visits")
    doctor = relationship("Doctor")
    appointment = relationship("Appointment")
