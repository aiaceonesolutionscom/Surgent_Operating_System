import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Boolean, Numeric, Integer, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.subscription import SubscriptionTier

# The DB-backed source of truth for pricing/plan capabilities — replaces the
# hardcoded PLANS array in frontend/src/data/plans.ts and the TIER_CATEGORIES/
# TIER_LIMITS dicts in services/practice/plan_capabilities.py as the thing an
# admin actually edits. Those two files stay in the repo as seed data + an
# offline fallback (same "self-seeding on first read" convention already used
# by AgentCosting) rather than being deleted, so the app still works if the
# DB has no Plan rows yet.
#
# `price` here is the CURRENT list price shown at checkout and in the admin
# editor — distinct from Subscription.price, which is a snapshot of what a
# specific practice actually agreed to pay at signup and must NOT change
# retroactively when an admin edits a Plan's price later.


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tagline: Mapped[str] = mapped_column(String(255), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)  # null == custom/"Contact us" pricing
    billing_period: Mapped[str] = mapped_column(String(20), default="monthly")
    is_custom_pricing: Mapped[bool] = mapped_column(Boolean, default=False)
    features: Mapped[list] = mapped_column(JSONB, default=list)            # ordered display copy, e.g. ["Front desk & intake agents", ...]
    agent_categories: Mapped[list] = mapped_column(JSONB, default=list)    # e.g. ["front-desk", "consultation"]
    max_doctors: Mapped[int] = mapped_column(Integer, nullable=True)          # null == unlimited
    max_social_channels: Mapped[int] = mapped_column(Integer, nullable=True)  # null == unlimited
    max_locations: Mapped[int] = mapped_column(Integer, nullable=True)        # null == unlimited
    has_analytics: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_period_days: Mapped[int] = mapped_column(Integer, default=14)       # admin-configurable per plan
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    highlight: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Plan {self.tier.value}: {self.name} ${self.price}>"
