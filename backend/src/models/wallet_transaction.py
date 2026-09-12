import uuid
from datetime import datetime

from sqlalchemy import String, Text, Numeric, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

import enum


class WalletTransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class WalletTransaction(Base):
    """A practice's prepaid credits ledger — Owner tops up via Stripe (see
    PaymentService.create_wallet_topup_checkout_session). Tracking-only for
    now: nothing in the codebase deducts from this balance yet (AI agent /
    WhatsApp / SMS usage costs are tracked separately via AgentCosting /
    AgentLog) — this is purely a top-up-and-view ledger, same shape as
    Payment for invoices. Balance is always derived by summing COMPLETED
    rows (WalletService.get_balance), never stored, so it can't drift."""

    __tablename__ = "wallet_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    status: Mapped[WalletTransactionStatus] = mapped_column(Enum(WalletTransactionStatus), default=WalletTransactionStatus.PENDING)
    stripe_checkout_session_id: Mapped[str] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice")
