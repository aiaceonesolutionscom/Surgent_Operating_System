"""The demo checkout marks a signup "paid" with no payment at all. It must exist
only on a developer's machine: a deployed environment (staging included - it is
publicly reachable) answers "checkout unavailable" until Stripe is configured,
instead of handing out clinics for free."""

import pytest

from src.models.plan import Plan
from src.server.exceptions import AppException
from src.services.checkout import checkout_services as module
from src.services.checkout.checkout_services import CheckoutService


@pytest.fixture
def no_stripe(monkeypatch):
    monkeypatch.setattr(CheckoutService, "_stripe_key_configured", lambda self: False)


async def _seed_plan(db_session):
    db_session.add(Plan(tier="practice", name="Practice", price=999.0, display_order=1, is_active=True))
    await db_session.flush()


@pytest.mark.parametrize("env", ["production", "staging"])
async def test_deployed_environments_refuse_demo_checkout(db_session, no_stripe, monkeypatch, env):
    monkeypatch.setattr(module.settings, "app_env", env)
    await _seed_plan(db_session)
    with pytest.raises(AppException) as exc:
        await CheckoutService().create_checkout_session(db_session, "buyer@example.com", "practice")
    assert exc.value.status_code == 503


@pytest.mark.parametrize("env", ["production", "staging"])
async def test_deployed_environments_refuse_to_confirm_a_demo_payment(db_session, no_stripe, monkeypatch, env):
    monkeypatch.setattr(module.settings, "app_env", env)
    with pytest.raises(AppException) as exc:
        await CheckoutService().confirm_demo_payment(db_session, "demo_anything")
    assert exc.value.status_code == 403


async def test_local_development_still_gets_the_demo_flow(db_session, no_stripe, monkeypatch):
    monkeypatch.setattr(module.settings, "app_env", "development")
    await _seed_plan(db_session)
    url = await CheckoutService().create_checkout_session(db_session, "buyer@example.com", "practice")
    assert "/pricing/pay?session_id=demo_" in url
