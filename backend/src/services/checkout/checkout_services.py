from __future__ import annotations
import uuid
from urllib.parse import quote

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

    async def create_checkout_session(self, db: AsyncSession, email: str, plan_tier: str) -> dict:
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

        if not (self._stripe_key_configured() and self._plan_stripe_ready(plan)):
            # No payment is ever simulated: until Stripe keys and this plan's
            # Price ID are set, checkout is simply unavailable.
            raise AppException(
                "Online checkout isn't available yet - please contact sales.", status_code=503
            )

        pending = PendingSignup(id=uuid.uuid4(), email=email, plan_tier=plan_tier)
        db.add(pending)
        await db.flush()

        # {CHECKOUT_SESSION_ID} is substituted by Stripe. plan_tier/email are
        # static values known before checkout (not Stripe fields) - carried so
        # /pricing/success can show the right plan immediately.
        return_url = (
            f"{settings.frontend_url}/pricing/success?session_id={{CHECKOUT_SESSION_ID}}"
            f"&plan_tier={plan_tier}&email={quote(email)}"
        )
        session = await self.payment.create_checkout_session(
            price_id=plan.stripe_price_id,
            practice_id=str(pending.id),  # client_reference_id - see PendingSignup's docstring
            return_url=return_url,
            customer_email=email,
        )
        pending.stripe_session_id = session["session_id"]
        await db.flush()
        return {"session_id": session["session_id"], "client_secret": session["client_secret"]}

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
