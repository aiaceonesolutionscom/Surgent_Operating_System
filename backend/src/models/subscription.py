import uuid
from datetime import datetime, date

from sqlalchemy import String, Numeric, DateTime, Date, ForeignKey, Enum, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

import enum


class SubscriptionTier(str, enum.Enum):
    SOLO = "solo"
    PRACTICE = "practice"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIAL = "trial"


class Subscription(Base):
    __tablename__ = "subscriptions"

    # `price` below is a SNAPSHOT of what this practice actually agreed to
    # pay at signup — it must never be silently rewritten when an admin
    # later edits Plan.price (models/plan.py) for the tier. Plan.price is
    # the current list price shown at checkout/in the admin editor; this
    # field is what a specific practice is actually billed.

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), nullable=True)
    tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier), default=SubscriptionTier.SOLO)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(default=True)
    # Mirror of Stripe's subscription.cancel_at_period_end — True the moment a
    # practice cancels (they keep access until period end), False on resume.
    # Written by the customer.subscription.updated webhook (see
    # webhook_router.py) so the Super Admin can show "Cancelling" as its own
    # subscription state instead of conflating it with active.
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice", back_populates="subscriptions")
