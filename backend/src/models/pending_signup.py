import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base

# NOTE(read before touching): the Stripe webhook (checkout.session.completed)
# still only stamps `completed_at` here, NOT a `Subscription`/`Practice` row —
# Subscription.practice_id is NOT NULL and no Practice exists yet at webhook
# time (Stripe fires this server-side, before the customer has ever created a
# Clerk account). Provisioning happens at claim time instead, once a real
# Clerk identity exists — see services/checkout/provisioning_service.py and
# router/practice/practice_router.py's POST /practice/claim.
#
# This same row shape is ALSO reused for the free "new organization request"
# path (plain /sign-up, no plan chosen yet — see webhook_router.py's
# user.created else-branch and services/practice/org_request_service.py).
# That path never touches Stripe at all: `stripe_session_id` stays NULL, and
# `request_status` carries its own pending/approved/rejected lifecycle
# instead of `completed_at`/Stripe's payment signal. The two flows are told
# apart by `stripe_session_id IS NULL` (org request) vs NOT NULL (paid
# checkout) rather than a new table, since every other field
# (email/practice_id/claimed_at/claimed_by_clerk_id) already means the exact
# same thing in both.


class OrgRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PendingSignup(Base):
    """A Pricing-page checkout, from Stripe payment through to claiming a
    real account. `completed_at` is set by the Stripe webhook (payment
    succeeded). `claimed_at`/`claimed_by_clerk_id`/`practice_id` are set by
    POST /practice/claim once the customer has created a Clerk account and
    provisioning has run — see provisioning_service.py.

    For the free org-request path (see the module docstring above),
    `clerk_id`/`org_name`/`request_status` are what matter instead."""

    __tablename__ = "pending_signups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_tier: Mapped[str] = mapped_column(String(50), nullable=True)
    stripe_session_id: Mapped[str] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by_clerk_id: Mapped[str] = mapped_column(String(255), nullable=True)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- org-request-only fields (NULL for a normal paid checkout row) ---
    clerk_id: Mapped[str] = mapped_column(String(255), nullable=True)
    org_name: Mapped[str] = mapped_column(String(255), nullable=True)
    request_status: Mapped[OrgRequestStatus] = mapped_column(Enum(OrgRequestStatus), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str] = mapped_column(String(500), nullable=True)
