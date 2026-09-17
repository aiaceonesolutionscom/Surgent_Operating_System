import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class SurgeryStatus(str, enum.Enum):
    # End-to-end status machine: booked at the front desk (scheduled), then
    # confirmed with patient + doctor (confirmed), the doctor starts the case
    # (in_progress), finishes it with the operative note (completed). Anything
    # pre-procedure can be cancelled instead.
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Surgery(Base):
    """A real surgery record — the "next major development" gap the user's
    own message flagged. Deliberately NOT a full OR-resourcing/room-conflict
    scheduler (out of reach for this month, per the plan's own "explicitly
    out of reach" note): `facility_note` is free text, not a linked Room
    model. This ships a real, working single-surgery record: who, what,
    when, pre-op checklist, implants used, and the operative note — the
    piece that was genuinely missing, not the harder resourcing problem."""

    __tablename__ = "surgeries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    procedure_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("procedures.id"), nullable=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    assistant_doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    scheduled_appointment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    # Forward link into Week 3's post-op journey — RecoveryJournal doesn't
    # write to this yet (that's Week 3 work), but the column exists now so
    # that build doesn't need a Surgery migration of its own.
    recovery_journal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_journals.id"), nullable=True)

    scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_estimate_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    anesthesia_type: Mapped[str] = mapped_column(String(100), nullable=True)
    facility_note: Mapped[str] = mapped_column(Text, nullable=True)
    # List of {item, checked, checked_by, checked_at} — the pre-op checklist
    # (consent signed, labs cleared, fasting confirmed, implants available...).
    pre_op_checklist: Mapped[list] = mapped_column(JSONB, default=list)
    # List of {type, manufacturer, lot_number, size} — implant traceability,
    # the same reasoning Week 3's inventory work cares about for batches.
    implants_used: Mapped[list] = mapped_column(JSONB, default=list)
    operative_note: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[SurgeryStatus] = mapped_column(Enum(SurgeryStatus), default=SurgeryStatus.SCHEDULED)
    # Lifecycle timestamps + who cancelled it — lets the Owner's overview (and
    # the front desk) answer "kis ne kab kya kiya" without counting on
    # updated_at alone.
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice")
    patient = relationship("Patient")
    procedure = relationship("Procedure")
    doctor = relationship("Doctor", foreign_keys=[doctor_id])
    assistant_doctor = relationship("Doctor", foreign_keys=[assistant_doctor_id])
    appointment = relationship("Appointment")
    recovery_journal = relationship("RecoveryJournal")
