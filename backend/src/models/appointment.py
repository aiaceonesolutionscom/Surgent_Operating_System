import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, func, Boolean, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

import enum


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    # The two middle front-desk stages that were missing — before this, a
    # checked-in patient jumped straight to "completed" with no way to
    # reflect that they were actually with the doctor, or done clinically
    # but still waiting on billing/checkout at the front desk.
    WITH_DOCTOR = "with_doctor"
    READY_FOR_CHECKOUT = "ready_for_checkout"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    appointment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set by the front desk's check-in action (see appointments_services.py's
    # check_in_appointment) — null until then. Drives the waiting room's sort
    # order (earliest-checked-in-first).
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # Mirror checked_in_at's pattern for the two new middle stages — lets the
    # Doctor's waiting-room widget sort by "been with me since" and the
    # front desk show how long someone's been waiting on checkout/billing.
    with_doctor_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_for_checkout_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    # True for demo rows seeded into a new practice (services/demo/
    # sample_data_service.py). Every pre-existing row is real (the column was
    # added NOT NULL DEFAULT false), and "clear sample data" only ever deletes
    # rows with this flag set.
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
