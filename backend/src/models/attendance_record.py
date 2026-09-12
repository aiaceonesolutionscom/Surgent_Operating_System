import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class AttendanceRecord(Base):
    """Professional daily attendance — one record per practice user per
    calendar day (UTC).

    A single row per (user, day) with an explicit `work_date` (day/month
    queries are trivial), separate check-in / check-out timestamps, and
    `worked_minutes` computed once at check-out. Doctors carry both `user_id`
    (the login subject, the universal lookup key) and `doctor_id` (their
    roster row); receptionists have only `user_id`. Whether a row is "in" or
    "out" is derived from `check_out_at`, not stored.

    Absence is simply *no row* that day — the owner's team view joins every
    active staff member against that day's records, so "who is missing"
    shows up explicitly instead of being an empty query result.
    """

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("user_id", "work_date", name="uq_attendance_user_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    # Receptionists have no Doctor row, so user_id is the universal subject;
    # doctors additionally carry their roster doctor_id.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    worked_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    practice = relationship("Practice", back_populates="attendance_records")
    user = relationship("User", back_populates="attendance_records")
    doctor = relationship("Doctor", back_populates="attendance_records")