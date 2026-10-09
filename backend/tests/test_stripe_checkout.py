"""Stripe's embedded payment form for the signup subscription.

What is pinned here:
* the Checkout Studio parameters reach Stripe verbatim, on the per-request
  preview API version (and nowhere else - other Stripe calls keep the account's
  own API version);
* no payment is ever simulated: without Stripe configured checkout is a 503 in
  every environment, development included;
* a paid signup's Stripe subscription is linked (and marked ACTIVE) when the
  customer's clinic is created - before this, a paying clinic stayed a TRIAL
  that no Stripe event could ever find.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from src.models.pending_signup import PendingSignup
from src.models.plan import Plan
from src.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from src.server.exceptions import AppException
from src.services.checkout import checkout_services as checkout_module
from src.services.checkout.checkout_services import CheckoutService
from src.services.checkout.provisioning_service import ProvisioningService
from src.services.payment import payment_service as payment_module
from src.services.payment.payment_service import PaymentService
from tests.conftest import make_practice


# --- the Checkout Session call -------------------------------------------------

class _FakeSession:
    id = "cs_test_123"
    client_secret = "cs_test_123_secret_abc"


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    def fake_create(**kwargs):
        seen.update(kwargs)
        return _FakeSession()

    monkeypatch.setattr(payment_module.stripe.checkout.Session, "create", staticmethod(fake_create))
    return seen


async def test_studio_parameters_are_sent_verbatim(captured):
    result = await PaymentService().create_checkout_session(
        price_id="price_abc",
        practice_id="pending-1",
        return_url="https://x.test/pricing/success?session_id={CHECKOUT_SESSION_ID}",
        customer_email="buyer@example.com",
    )

    assert result == {"session_id": "cs_test_123", "client_secret": "cs_test_123_secret_abc"}
    assert captured["stripe_version"] == "2026-03-25.dahlia; custom_checkout_payment_form_preview=v1"
    assert captured["ui_mode"] == "form"
    assert captured["mode"] == "subscription"
    assert captured["line_items"] == [{"price": "price_abc", "quantity": 1}]
    assert captured["billing_address_collection"] == "auto"
    assert captured["phone_number_collection"] == {"enabled": False}
    assert captured["automatic_tax"] == {"enabled": False}
    assert captured["payment_method_collection"] == "always"
    assert captured["submit_type"] == "auto"
    assert captured["integration_identifier"] == "custom_embedded_web_0001"
    assert captured["name_collection"] == {
        "individual": {"enabled": True, "optional": True},
        "business": {"enabled": True, "optional": True},
    }
    countries = captured["shipping_address_collection"]["allowed_countries"]
    assert len(countries) == len(set(countries)) == 230
    assert {"US", "CA", "PK", "GB"} <= set(countries)
    # this app's own wiring
    assert captured["client_reference_id"] == "pending-1"
    assert captured["customer_email"] == "buyer@example.com"
    assert captured["return_url"].endswith("{CHECKOUT_SESSION_ID}")
    # embedded modes have no hosted redirect pages
    assert "success_url" not in captured and "cancel_url" not in captured


async def test_stripe_errors_become_a_clean_503(monkeypatch):
    def boom(**_):
        raise payment_module.stripe.error.InvalidRequestError("No such price", "price")

    monkeypatch.setattr(payment_module.stripe.checkout.Session, "create", staticmethod(boom))
    with pytest.raises(AppException) as exc:
        await PaymentService().create_checkout_session("price_missing", "p", "https://x.test/r")
    assert exc.value.status_code == 503


# --- the service: no simulated payments -------------------------------------------------

async def _seed_plan(db_session, price_id="price_live_1"):
    db_session.add(
        Plan(tier="practice", name="Practice", price=999.0, display_order=1, is_active=True, stripe_price_id=price_id)
    )
    await db_session.flush()


@pytest.mark.parametrize("env", ["development", "staging", "production"])
async def test_checkout_is_unavailable_without_stripe_in_every_environment(db_session, monkeypatch, env):
    monkeypatch.setattr(checkout_module.settings, "app_env", env)
    monkeypatch.setattr(checkout_module.settings, "stripe_secret_key", "")
    await _seed_plan(db_session)
    with pytest.raises(AppException) as exc:
        await CheckoutService().create_checkout_session(db_session, "buyer@example.com", "practice")
    assert exc.value.status_code == 503
    assert (await db_session.execute(select(PendingSignup))).scalars().all() == []  # nothing recorded


async def test_plan_without_a_price_id_is_unavailable(db_session, monkeypatch):
    monkeypatch.setattr(checkout_module.settings, "stripe_secret_key", "sk_test_realish")
    await _seed_plan(db_session, price_id=None)
    with pytest.raises(AppException) as exc:
        await CheckoutService().create_checkout_session(db_session, "buyer@example.com", "practice")
    assert exc.value.status_code == 503


async def test_session_is_created_and_remembered(db_session, monkeypatch):
    monkeypatch.setattr(checkout_module.settings, "stripe_secret_key", "sk_test_realish")
    monkeypatch.setattr(checkout_module.settings, "frontend_url", "https://app.example.com")
    await _seed_plan(db_session)
    seen = {}

    async def fake_create(self, **kwargs):
        seen.update(kwargs)
        return {"session_id": "cs_test_999", "client_secret": "cs_test_999_secret"}

    monkeypatch.setattr(PaymentService, "create_checkout_session", fake_create)

    result = await CheckoutService().create_checkout_session(db_session, "buyer+tag@example.com", "practice")

    assert result == {"session_id": "cs_test_999", "client_secret": "cs_test_999_secret"}
    assert seen["price_id"] == "price_live_1"
    # Stripe substitutes the placeholder; the email is URL-encoded
    assert seen["return_url"] == (
        "https://app.example.com/pricing/success?session_id={CHECKOUT_SESSION_ID}"
        "&plan_tier=practice&email=buyer%2Btag%40example.com"
    )
    pending = (await db_session.execute(select(PendingSignup))).scalar_one()
    assert pending.stripe_session_id == "cs_test_999"
    assert str(pending.id) == seen["practice_id"]


# --- linking the paid Stripe subscription at provisioning --------------------------------

def _trial_subscription(practice):
    return Subscription(
        id=uuid.uuid4(),
        practice_id=practice.id,
        tier=SubscriptionTier.PRACTICE,
        status=SubscriptionStatus.TRIAL,
        start_date=date.today(),
        end_date=date(2099, 1, 1),
    )


def _pending(session_id):
    return PendingSignup(
        id=uuid.uuid4(),
        email="buyer@example.com",
        plan_tier="practice",
        stripe_session_id=session_id,
        completed_at=datetime.now(timezone.utc),
    )


async def test_paid_checkout_links_the_stripe_subscription_and_activates(monkeypatch):
    async def fake_lookup(self, session_id):
        assert session_id == "cs_test_paid"
        return "sub_123"

    monkeypatch.setattr(PaymentService, "get_checkout_subscription_id", fake_lookup)
    subscription = _trial_subscription(make_practice())

    await ProvisioningService()._link_stripe_subscription(subscription, _pending("cs_test_paid"))

    assert subscription.stripe_subscription_id == "sub_123"
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.end_date is None


@pytest.mark.parametrize("session_id", [None, "", "demo_old_session"])
async def test_nothing_to_link_without_a_real_stripe_session(monkeypatch, session_id):
    async def must_not_be_called(self, _):
        raise AssertionError("Stripe should not be contacted")

    monkeypatch.setattr(PaymentService, "get_checkout_subscription_id", must_not_be_called)
    subscription = _trial_subscription(make_practice())
    await ProvisioningService()._link_stripe_subscription(subscription, _pending(session_id))
    assert subscription.status == SubscriptionStatus.TRIAL
    assert subscription.stripe_subscription_id is None


async def test_a_stripe_outage_does_not_block_the_clinic_from_being_created(monkeypatch):
    async def down(self, _):
        raise AppException("Stripe unreachable")

    monkeypatch.setattr(PaymentService, "get_checkout_subscription_id", down)
    subscription = _trial_subscription(make_practice())
    await ProvisioningService()._link_stripe_subscription(subscription, _pending("cs_test_x"))
    assert subscription.status == SubscriptionStatus.TRIAL
