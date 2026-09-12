import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class StaffRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PendingStaffRequest(Base):
    """A receptionist's self-registration application — the exact mirror of
    PendingDoctorRequest, so front-desk staff onboard the SAME way doctors do:
    the Owner shares a practice signup link, the receptionist signs up through
    it, and an Owner reviews and approves before their account activates.

    The applicant's User row already exists by the time this is created (the
    `user.created` webhook's `staff_self_apply` branch makes it, inactive, as
    soon as Clerk sign-up completes) — this table just holds what they submit
    about themselves until an Owner decides. Approving flips the User active
    and drops the granted permissions onto User.permissions (see
    user.py / data/receptionist_permissions.py), the same as an email-invited
    receptionist used to get."""

    __tablename__ = "pending_staff_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    # One pending application per Clerk account — resubmitting updates the
    # same row rather than creating duplicates.
    clerk_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[StaffRequestStatus] = mapped_column(Enum(StaffRequestStatus), default=StaffRequestStatus.PENDING)
    rejected_reason: Mapped[str] = mapped_column(Text, nullable=True)
    # Set once approved — the User row (role RECEPTIONIST) this application
    # activated. Users have no roster table, so this is a plain reference.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    practice = relationship("Practice", back_populates="pending_staff_requests")