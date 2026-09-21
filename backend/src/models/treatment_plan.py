import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Numeric, Integer, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class TreatmentPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TreatmentPlanItemStatus(str, enum.Enum):
    PLANNED = "planned"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    consultation_note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consultation_notes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TreatmentPlanStatus] = mapped_column(Enum(TreatmentPlanStatus), default=TreatmentPlanStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship(
        "TreatmentPlanItem", back_populates="treatment_plan", cascade="all, delete-orphan",
        order_by="TreatmentPlanItem.phase_order",
    )
    practice = relationship("Practice", back_populates="treatment_plans")
    patient = relationship("Patient")
    doctor = relationship("Doctor")


class TreatmentPlanItem(Base):
    __tablename__ = "treatment_plan_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"), nullable=False)
    procedure_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("procedures.id"), nullable=False)
    phase_order: Mapped[int] = mapped_column(Integer, default=0)
    estimated_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[TreatmentPlanItemStatus] = mapped_column(Enum(TreatmentPlanItemStatus), default=TreatmentPlanItemStatus.PLANNED)
    # How many visits this specific item takes for this specific patient —
    # seeded from Procedure.default_session_count when the item is created,
    # editable afterward (a doctor may decide a patient needs 8 laser
    # sessions instead of the usual 6). 1 = the pre-existing single-visit
    # behavior; every item created before this field existed reads as 1.
    # The real per-visit records live in `session_visits` below — this is
    # just the target count sessions are measured against.
    sessions_total: Mapped[int] = mapped_column(Integer, default=1)
    # Set once this item is actually booked/performed — folded onto the item
    # itself rather than a separate "performed procedure" table, per the
    # roadmap's own sequencing note. For a multi-session item this points at
    # the LATEST session's appointment as a convenience; the authoritative
    # per-visit history is `session_visits`.
    scheduled_appointment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    treatment_plan = relationship("TreatmentPlan", back_populates="items")
    procedure = relationship("Procedure")
    session_visits = relationship(
        "SessionVisit", back_populates="treatment_plan_item", cascade="all, delete-orphan",
        order_by="SessionVisit.session_index",
    )
