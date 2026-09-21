import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class VisitDocumentType(str, enum.Enum):
    INTAKE_SUMMARY = "intake_summary"


class VisitDocumentGeneratedBy(str, enum.Enum):
    AI_RECEPTIONIST = "ai_receptionist"
    STAFF = "staff"
    SYSTEM = "system"


class VisitDocument(Base):
    """An auto-generated, patient-facing PDF summarizing whatever intake data
    exists for a patient (AI-receptionist-collected or patient-portal-
    collected) — the "bring this to your visit" artifact. Generation is
    best-effort and fire-and-forget (see VisitDocumentService): failures here
    must never block the appointment-booking or chat flow that triggered
    them. `sent_to_doctor_at`/`sent_to_receptionist_at` mark when an in-app
    notification was raised for staff, not a WhatsApp/email push — those two
    roles see it in-app; only the patient gets an actual message/email."""

    __tablename__ = "visit_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    document_type: Mapped[VisitDocumentType] = mapped_column(Enum(VisitDocumentType), default=VisitDocumentType.INTAKE_SUMMARY)
    # Cloudinary raw-upload URL from StorageService.upload — same pattern as
    # invoice PDFs, never stored on local disk.
    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    generated_by: Mapped[VisitDocumentGeneratedBy] = mapped_column(Enum(VisitDocumentGeneratedBy), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_to_patient_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_to_doctor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_to_receptionist_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice")
    patient = relationship("Patient", back_populates="visit_documents")
    appointment = relationship("Appointment")
    doctor = relationship("Doctor")
