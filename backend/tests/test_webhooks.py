"""Webhook authenticity and the Stripe subscription lifecycle.

Two bugs these pin, both invisible until a real provider called in:

* The Clerk (Svix) signature check built the wrong signed payload and never
  base64-decoded the secret, so every GENUINE webhook was rejected - while an
  unset secret skipped verification entirely, letting anyone forge one.
* The subscription / invoice handlers used `Subscription` and
  `SubscriptionStatus` without importing them: every such Stripe event raised
  NameError and returned 500, so a clinic's billing status never updated.
"""

import base64
import hashlib
import hmac
import time
from datetime import date
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.database import Base, get_db
from src.main import app
from src.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from src.router.v1.webhooks import webhook_router as hooks
from tests.conftest import make_practice

SECRET_BYTES = b"super-secret-signing-key-1234567"
SECRET = "whsec_" + base64.b64encode(SECRET_BYTES).decode()


def _svix_headers(body: bytes, *, msg_id="msg_1", timestamp=None, secret_bytes=SECRET_BYTES) -> dict:
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signed = f"{msg_id}.{timestamp}.".encode() + body
    signature = base64.b64encode(hmac.new(secret_bytes, signed, hashlib.sha256).digest()).decode()
    return {"svix-id": msg_id, "svix-timestamp": timestamp, "svix-signature": f"v1,{signature}"}


# --- Clerk / Svix signature --------------------------------------------------

def test_genuine_svix_signature_is_accepted():
    body = b'{"type":"user.created"}'
    h = _svix_headers(body)
    assert hooks._verify_clerk_signature(body, h["svix-id"], h["svix-timestamp"], h["svix-signature"], SECRET)


def test_second_signature_in_header_is_enough():
    """Svix sends several space-separated signatures during key rotation."""
    body = b"{}"
    h = _svix_headers(body)
    rotated = "v1,AAAA " + h["svix-signature"]
    assert hooks._verify_clerk_signature(body, h["svix-id"], h["svix-timestamp"], rotated, SECRET)


def test_tampered_body_is_rejected():
    h = _svix_headers(b'{"type":"user.created"}')
    assert not hooks._verify_clerk_signature(
        b'{"type":"user.deleted"}', h["svix-id"], h["svix-timestamp"], h["svix-signature"], SECRET
    )


def test_wrong_secret_is_rejected():
    body = b"{}"
    h = _svix_headers(body, secret_bytes=b"some-other-secret-entirely-0000000")
    assert not hooks._verify_clerk_signature(body, h["svix-id"], h["svix-timestamp"], h["svix-signature"], SECRET)


def test_replayed_old_request_is_rejected():
    body = b"{}"
    h = _svix_headers(body, timestamp=int(time.time()) - 3600)
    assert not hooks._verify_clerk_signature(body, h["svix-id"], h["svix-timestamp"], h["svix-signature"], SECRET)


def test_missing_headers_or_secret_never_verify():
    assert not hooks._verify_clerk_signature(b"{}", "", "", "", SECRET)
    assert not hooks._verify_clerk_signature(b"{}", "id", str(int(time.time())), "v1,xx", "")


# --- endpoints ---------------------------------------------------------------

@pytest.fixture
async def api(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, factory, monkeypatch
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_clerk_webhook_without_secret_is_refused_outside_development(api):
    client, _, monkeypatch = api
    monkeypatch.setattr(hooks.settings, "clerk_webhook_secret", "")
    monkeypatch.setattr(hooks.settings, "app_env", "production")
    resp = await client.post("/api/v1/webhooks/clerk", content=b'{"type":"user.created"}')
    assert resp.status_code == 503


async def test_clerk_webhook_rejects_a_bad_signature(api):
    client, _, monkeypatch = api
    monkeypatch.setattr(hooks.settings, "clerk_webhook_secret", SECRET)
    resp = await client.post(
        "/api/v1/webhooks/clerk",
        content=b'{"type":"user.created"}',
        headers={"svix-id": "m", "svix-timestamp": str(int(time.time())), "svix-signature": "v1,bogus"},
    )
    assert resp.status_code == 400


async def test_clerk_webhook_accepts_a_genuine_signature(api):
    client, _, monkeypatch = api
    monkeypatch.setattr(hooks.settings, "clerk_webhook_secret", SECRET)
    body = b'{"type":"session.created","data":{}}'
    resp = await client.post("/api/v1/webhooks/clerk", content=body, headers=_svix_headers(body))
    assert resp.status_code == 200


async def test_stripe_webhook_without_secret_is_refused(api):
    """An empty secret would make construct_event verify against an empty
    key, so a forged event signed with "" would be accepted."""
    client, _, monkeypatch = api
    monkeypatch.setattr(hooks.settings, "stripe_webhook_secret", "")
    resp = await client.post("/api/v1/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})
    assert resp.status_code == 503


async def _post_stripe_event(client, monkeypatch, event_type, obj):
    monkeypatch.setattr(hooks.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(
        hooks.stripe.Webhook,
        "construct_event",
        staticmethod(lambda **_: {"type": event_type, "data": {"object": obj}}),
    )
    return await client.post("/api/v1/webhooks/stripe", content=b"{}", headers={"stripe-signature": "x"})


async def _seed_subscription(factory, status=SubscriptionStatus.TRIAL):
    async with factory() as session:
        practice = make_practice()
        session.add(practice)
        await session.flush()
        session.add(Subscription(
            practice_id=practice.id, tier=SubscriptionTier.PRACTICE, status=status,
            start_date=date.today(), stripe_subscription_id="sub_123",
        ))
        await session.commit()
        return practice.id


async def _status_of(factory, practice_id):
    async with factory() as session:
        return (
            await session.execute(select(Subscription).where(Subscription.practice_id == practice_id))
        ).scalar_one()


@pytest.mark.parametrize(
    "stripe_status,expected",
    [("active", SubscriptionStatus.ACTIVE), ("past_due", SubscriptionStatus.PAST_DUE),
     ("canceled", SubscriptionStatus.CANCELLED), ("unpaid", SubscriptionStatus.EXPIRED)],
)
async def test_subscription_updated_event_moves_the_status(api, stripe_status, expected):
    client, factory, monkeypatch = api
    practice_id = await _seed_subscription(factory)

    resp = await _post_stripe_event(client, monkeypatch, "customer.subscription.updated", {
        "id": "sub_123", "status": stripe_status, "cancel_at_period_end": True,
        "items": {"data": [{"price": {"unit_amount": 99900}}]},
    })

    assert resp.status_code == 200
    sub = await _status_of(factory, practice_id)
    assert sub.status == expected
    assert sub.cancel_at_period_end is True
    assert float(sub.price) == 999.0


async def test_invoice_payment_failed_marks_past_due_and_paid_reactivates(api):
    client, factory, monkeypatch = api
    practice_id = await _seed_subscription(factory, SubscriptionStatus.ACTIVE)

    resp = await _post_stripe_event(client, monkeypatch, "invoice.payment_failed", {"subscription": "sub_123"})
    assert resp.status_code == 200
    assert (await _status_of(factory, practice_id)).status == SubscriptionStatus.PAST_DUE

    resp = await _post_stripe_event(client, monkeypatch, "invoice.paid", {"subscription": "sub_123", "amount_paid": 99900})
    assert resp.status_code == 200
    assert (await _status_of(factory, practice_id)).status == SubscriptionStatus.ACTIVE


async def test_subscription_deleted_event_cancels(api):
    client, factory, monkeypatch = api
    practice_id = await _seed_subscription(factory, SubscriptionStatus.ACTIVE)
    resp = await _post_stripe_event(client, monkeypatch, "customer.subscription.deleted", {"id": "sub_123"})
    assert resp.status_code == 200
    assert (await _status_of(factory, practice_id)).status == SubscriptionStatus.CANCELLED
