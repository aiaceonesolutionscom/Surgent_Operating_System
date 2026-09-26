from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.pending_signup import PendingSignup
from src.models.subscription import SubscriptionTier
from src.services.payment.payment_service import PaymentService
from src.services.admin.plan_services import PlanService
from src.server.exceptions import AppException, NotFoundException

settings = get_settings()


class CheckoutService:
    def __init__(self):
        self.payment = PaymentService()
        self.plans = PlanService()

    def _stripe_key_configured(self) -> bool:
        # backend/.env ships a literal "xxxx" placeholder until a real key is
        # added — see .env.example. Once a real sk_ key is set this flips
        # false-positive-free.
        return bool(settings.stripe_secret_key) and "xxxx" not in settings.stripe_secret_key

    def _plan_stripe_ready(self, plan) -> bool:
        return bool(plan.stripe_price_id) and "xxxx" not in plan.stripe_price_id

    async def create_checkout_session(self, db: AsyncSession, email: str, plan_tier: str) -> str:
        try:
            tier = SubscriptionTier(plan_tier)
        except ValueError:
            raise AppException(f"Unknown or unsupported plan tier: {plan_tier}")

        # DB-backed lookup (models/plan.py) — an admin editing this plan's
        # price/stripe_price_id in the admin panel changes what checkout
        # actually charges, with no code change or deploy required.
        # Use _normalize_for_checkout so SOLO (hidden trial) maps to PRACTICE
        plan = await self.plans.get_plan_by_tier(db, self.plans._normalize_for_checkout(tier))
        if plan is None or not plan.is_active:
            raise AppException(f"Unknown or unsupported plan tier: {plan_tier}")
        if plan.is_custom_pricing:
            raise AppException(f"The {plan.name} plan requires contacting sales — it isn't self-serve checkout.")

        pending = PendingSignup(id=uuid.uuid4(), email=email, plan_tier=plan_tier)
        db.add(pending)
        await db.flush()

        if not (self._stripe_key_configured() and self._plan_stripe_ready(plan)):
            return await self._demo_checkout(db, pending, plan_tier, email)

        session = await self.payment.create_checkout_session(
            price_id=plan.stripe_price_id,
            practice_id=str(pending.id),  # client_reference_id — see PendingSignup's docstring
            # plan_tier/email are static values known before redirect (not
            # Stripe template fields) — carried so /pricing/success can show
            # the right plan immediately without an extra round trip.
            success_url=f"{settings.frontend_url}/pricing/success?session_id={{CHECKOUT_SESSION_ID}}&plan_tier={plan_tier}&email={email}",
            cancel_url=f"{settings.frontend_url}/pricing/cancel",
            customer_email=email,
        )
        pending.stripe_session_id = session["session_id"]
        await db.flush()
        return session["url"]

    async def _demo_checkout(self, db: AsyncSession, pending: PendingSignup, plan_tier: str, email: str) -> str:
        # DEMO MODE — no real Stripe key configured yet (backend/.env's
        # STRIPE_SECRET_KEY is still an "xxxx" placeholder) or this specific
        # Plan row has no stripe_price_id set (see models/plan.py, editable
        # from the admin panel). Does NOT mark the signup paid here —
        # redirects to our own Stripe-Checkout-styled demo payment page
        # instead (frontend app/onboarding/DemoPaymentPage.tsx), which is
        # what calls confirm_demo_payment() below on "Pay". This is a
        # deliberate, explicit decision for pre-launch demoing (a real
        # card-entry-shaped step, not a skip-straight-to-success shortcut),
        # not a security bypass on a live product — _stripe_key_configured()
        # + _plan_stripe_ready() automatically stop matching (and this whole
        # branch stops firing) the moment a real key + price id are set;
        # nothing else needs to change.
        pending.stripe_session_id = f"demo_{pending.id}"
        await db.flush()
        return f"{settings.frontend_url}/pricing/pay?session_id={pending.stripe_session_id}&plan_tier={plan_tier}&email={email}"

    async def confirm_demo_payment(self, db: AsyncSession, session_id: str) -> dict:
        if self._stripe_key_configured():
            # Real Stripe is connected — this endpoint must never be usable
            # to fake a payment once real charges are possible.
            raise AppException("Demo payment confirmation is disabled once real Stripe keys are configured.", status_code=403)

        result = await db.execute(select(PendingSignup).where(PendingSignup.stripe_session_id == session_id))
        pending = result.scalar_one_or_none()
        if pending is None:
            raise NotFoundException("No checkout session found for that id.")

        if pending.completed_at is None:
            pending.completed_at = datetime.now(timezone.utc)
            await db.flush()

        return {"paid": True, "plan_tier": pending.plan_tier, "email": pending.email, "claimed": pending.claimed_at is not None}

    async def get_session_status(self, db: AsyncSession, session_id: str) -> dict:
        result = await db.execute(select(PendingSignup).where(PendingSignup.stripe_session_id == session_id))
        pending = result.scalar_one_or_none()
        if pending is None:
            raise NotFoundException("No checkout session found for that id.")
        return {
            "paid": pending.completed_at is not None,
            "plan_tier": pending.plan_tier,
            "email": pending.email,
            "claimed": pending.claimed_at is not None,
        }
