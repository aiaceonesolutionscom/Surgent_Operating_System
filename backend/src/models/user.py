import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


# Practice-scoped role (distinct from is_platform_admin below, which is
# Aiaceone-team-level). STAFF is the honest fallback for Clerk's
# `user.created` webhook (router/v1/webhooks/webhook_router.py), which has
# no signal about which real role a brand-new sign-up actually is. PATIENT
# is deliberately NOT a value here — patients are `Patient` rows, not `User`
# rows; a patient login is a separate, later problem.
class UserRole(str, enum.Enum):
    OWNER = "owner"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    STAFF = "staff"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    clerk_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.STAFF, nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Granular dashboard access for roles that don't have their own roster
    # table (unlike Doctor.permissions) — currently only meaningful for
    # role == RECEPTIONIST, set by the Owner via PATCH /staff/{id}/permissions.
    # Keys come from data/receptionist_permissions.py's static catalog.
    permissions: Mapped[list] = mapped_column(JSONB, default=list)
    # Recurring weekly work schedule for User-backed staff (receptionists) —
    # same shape as Doctor.working_hours: {"mon": [{"start": "09:00", "end":
    # "17:00"}], ...}. Set by the staff member from their own profile
    # (PATCH /staff/me); drives the Owner's attendance "who should be in,
    # who is late" view. See attendance_service.py:_staff_roster.
    work_schedule: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Platform-level (Aiaceone team), not practice-level — distinct from
    # `role` above, which only ever means something within `practice_id`.
    # Self-healed to True on login for any email in Settings.platform_admin_emails
    # (see server/dependencies.py:get_current_practice_user); editable
    # afterwards from the admin panel itself.
    is_platform_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice", back_populates="users")
    attendance_records = relationship("AttendanceRecord", back_populates="user")
