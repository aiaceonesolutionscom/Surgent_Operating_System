import uuid
from datetime import datetime, date

from sqlalchemy import String, Text, Numeric, DateTime, Date, ForeignKey, func, Boolean, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    expense_type: Mapped[str] = mapped_column(String(20), nullable=False, default="expense")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="paid")
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    vendor: Mapped[str] = mapped_column(String(255), nullable=True)
    payee_name: Mapped[str] = mapped_column(String(255), nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # True for demo rows seeded into a new practice (services/demo/
    # sample_data_service.py). Every pre-existing row is real (the column was
    # added NOT NULL DEFAULT false), and "clear sample data" only ever deletes
    # rows with this flag set.
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice", back_populates="expenses")
    recorder = relationship("User")
