import stripe

from src.config import get_settings
from src.server.exceptions import AppException

settings = get_settings()

stripe.api_key = settings.stripe_secret_key


class PaymentService:
    def is_configured(self) -> bool:
        # Same "xxxx" placeholder convention as CheckoutService._stripe_key_configured.
        return bool(settings.stripe_secret_key) and "xxxx" not in settings.stripe_secret_key

    async def get_checkout_session(self, session_id: str) -> dict:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as exc:
            raise AppException(f"Could not retrieve checkout session: {exc}") from exc
        return {
            "id": session.id,
            "paid": session.payment_status == "paid",
            "payment_intent": session.payment_intent,
            "metadata": dict(session.metadata or {}),
            "amount_total": (session.amount_total or 0) / 100,
            "currency": (session.currency or "").upper(),
        }

    async def create_checkout_session(
        self,
        price_id: str,
        practice_id: str,
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
    ) -> dict:
        kwargs = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "client_reference_id": practice_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_email:
            # Pricing-page checkouts happen before a practice/user record
            # exists (see PendingSignup) — Stripe still needs an email to
            # send its own receipt to and to pre-fill the Checkout page.
            kwargs["customer_email"] = customer_email
        try:
            session = stripe.checkout.Session.create(**kwargs)
        except stripe.error.StripeError as exc:
            # Placeholder STRIPE_SECRET_KEY/STRIPE_PRICE_* in .env until real
            # ones are set — a clean 503 instead of a raw 500 so this reads
            # as "not configured yet", not an unexpected server crash.
            raise AppException(
                "Payment processing isn't configured yet — Stripe hasn't been connected with real API keys.",
                status_code=503,
            ) from exc
        return {"session_id": session.id, "url": session.url}

    async def create_invoice_checkout_session(
        self,
        invoice_id: str,
        amount: float,
        currency: str,
        description: str,
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
    ) -> dict:
        # Unlike create_checkout_session above (fixed price_id, subscription
        # mode), an invoice's amount is dynamic per-patient — Stripe's
        # inline price_data is the mechanism for a one-off "mode=payment"
        # charge with no pre-registered Price object. metadata (not
        # client_reference_id, already used for PendingSignup lookups)
        # distinguishes this from a SaaS-signup session in the shared
        # /webhooks/stripe handler.
        kwargs = {
            "mode": "payment",
            "line_items": [{
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": round(amount * 100),
                    "product_data": {"name": description},
                },
                "quantity": 1,
            }],
            "metadata": {"invoice_id": invoice_id, "type": "invoice_payment"},
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_email:
            kwargs["customer_email"] = customer_email
        try:
            session = stripe.checkout.Session.create(**kwargs)
        except stripe.error.StripeError as exc:
            raise AppException(
                "Payment processing isn't configured yet — Stripe hasn't been connected with real API keys.",
                status_code=503,
            ) from exc
        return {"session_id": session.id, "url": session.url}

    async def create_wallet_topup_checkout_session(
        self,
        practice_id: str,
        amount: float,
        currency: str,
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
    ) -> dict:
        # Same one-off "mode=payment" shape as create_invoice_checkout_session
        # — metadata identifies this as a wallet top-up (not an invoice
        # payment or a SaaS signup) to the shared /webhooks/stripe handler.
        kwargs = {
            "mode": "payment",
            "line_items": [{
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": round(amount * 100),
                    "product_data": {"name": "Account credits top-up"},
                },
                "quantity": 1,
            }],
            "metadata": {"practice_id": practice_id, "type": "wallet_topup"},
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_email:
            kwargs["customer_email"] = customer_email
        try:
            session = stripe.checkout.Session.create(**kwargs)
        except stripe.error.StripeError as exc:
            raise AppException(
                "Payment processing isn't configured yet — Stripe hasn't been connected with real API keys.",
                status_code=503,
            ) from exc
        return {"session_id": session.id, "url": session.url}

    async def cancel_subscription(self, stripe_subscription_id: str) -> dict:
        subscription = stripe.Subscription.modify(stripe_subscription_id, cancel_at_period_end=True)
        return {"status": subscription.status, "current_period_end": subscription.current_period_end}
