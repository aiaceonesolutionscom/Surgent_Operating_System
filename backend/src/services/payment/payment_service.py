import logging

import stripe

from src.config import get_settings
from src.server.exceptions import AppException

settings = get_settings()
logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key

# The embedded payment form (ui_mode "form") is a Stripe preview: it needs this
# API version AND the preview flag. It is passed PER REQUEST on the checkout
# session call only - not set globally - so every other Stripe call here
# (cancel / resume / change plan, invoice and wallet checkouts) keeps running on
# the account's own API version and response shapes.
CHECKOUT_FORM_API_VERSION = "2026-03-25.dahlia; custom_checkout_payment_form_preview=v1"

# Countries offered in the checkout form's shipping-address step, exactly as
# configured in Stripe's Checkout Studio.
CHECKOUT_SHIPPING_COUNTRIES = """
CA MX US AG AI AW BB BL BM BQ BS BZ CR CW DM DO GD GL GP GT HN HT JM KN KY LC MF MQ MS NI PA PM PR SV SX TC TT VC VG
AR BO BR BV CL CO EC FK GF GS GY PE PY SR UY VE
AD AL AT AX BA BE BG BY CH CZ DE DK EE ES FI FO FR GB GG GI GR HR HU IE IM IS IT JE LI LT LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM UA VA
AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG ER ET GA GH GM GN GQ GW IO KE KM LR LS LY MA MG ML MR MU MW MZ NA NE NG RE RW SC SH SL SN SO SS ST SZ TD TF TG TN TZ UG YT ZA ZM ZW
AE AF AM AZ BD BH BN BT CN CY GE HK ID IL IN IQ JO JP KG KH KR KW KZ LA LB LK MM MN MO MV MY NP OM PH PK QA SA SG TH TJ TL TM TR TW UZ VN YE
AU CK FJ GU KI NC NR NU NZ PF PG PN SB TK TO TV VU WF WS
""".split()


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
        return_url: str,
        customer_email: str | None = None,
    ) -> dict:
        """Create the signup subscription's Checkout Session for Stripe's
        embedded payment form: returns the `client_secret` the browser mounts
        the form with (there is no hosted URL to redirect to).

        Everything from `ui_mode` down to `integration_identifier` is the
        Checkout Studio configuration and is used verbatim; `client_reference_id`,
        `customer_email` and `return_url` are this app's own wiring."""
        kwargs = {
            "stripe_version": CHECKOUT_FORM_API_VERSION,
            # The Studio spec said "custom" for SDKs older than 21.0.0, but on
            # this API version Stripe answers 'The ui_mode value `custom` is no
            # longer supported. Use `elements` instead.' - `form` is what the
            # API accepts (verified against the live test API).
            "ui_mode": "form",
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "billing_address_collection": "auto",
            "phone_number_collection": {"enabled": False},
            "automatic_tax": {"enabled": False},
            "payment_method_collection": "always",
            "submit_type": "auto",
            "shipping_address_collection": {"allowed_countries": CHECKOUT_SHIPPING_COUNTRIES},
            "name_collection": {
                "individual": {"enabled": True, "optional": True},
                "business": {"enabled": True, "optional": True},
            },
            "integration_identifier": "custom_embedded_web_0001",
            "client_reference_id": practice_id,
            "return_url": return_url,
        }
        if customer_email:
            # Pricing-page checkouts happen before a practice/user record
            # exists (see PendingSignup) - Stripe still needs an email to
            # send its own receipt to and to pre-fill the payment form.
            kwargs["customer_email"] = customer_email
        try:
            session = stripe.checkout.Session.create(**kwargs)
        except stripe.error.StripeError as exc:
            # A placeholder / missing STRIPE_SECRET_KEY or Price ID reads as
            # "not configured yet" (a clean 503) rather than a raw 500; the
            # real reason is in the log.
            logger.warning("Stripe checkout session creation failed: %s", exc)
            raise AppException(
                "Payment processing isn't configured yet - Stripe hasn't been connected with real API keys.",
                status_code=503,
            ) from exc
        return {"session_id": session.id, "client_secret": session.client_secret}

    async def get_checkout_subscription_id(self, session_id: str) -> str | None:
        """The Stripe subscription a completed subscription-mode checkout created."""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as exc:
            raise AppException(f"Could not retrieve checkout session: {exc}") from exc
        subscription = session.subscription
        return subscription if isinstance(subscription, str) else getattr(subscription, "id", None)

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

    async def resume_subscription(self, stripe_subscription_id: str) -> dict:
        subscription = stripe.Subscription.modify(stripe_subscription_id, cancel_at_period_end=False)
        return {"status": subscription.status, "current_period_end": subscription.current_period_end}

    async def change_subscription_plan(self, stripe_subscription_id: str, new_price_id: str) -> dict:
        # Get current subscription to find the subscription item to replace
        subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        item_id = subscription["items"]["data"][0]["id"]
        # Replace the price
        subscription = stripe.Subscription.modify(
            stripe_subscription_id,
            items=[{"id": item_id, "price": new_price_id}],
            proration_behavior="create_prorations",
        )
        return {"status": subscription.status, "current_period_end": subscription.current_period_end}

    async def get_subscription(self, stripe_subscription_id: str) -> dict:
        subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "items": subscription["items"]["data"],
        }
