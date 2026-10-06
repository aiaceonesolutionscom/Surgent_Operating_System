"""Approval-time provisioning, and the demo data it seeds.

`ProvisioningService` is what turns a Super Admin's approval into a real
Practice/User/Subscription. Two paths reach it:

  - provision_from_pending_signup  — PAID. Money changed hands via Stripe.
  - provision_from_org_request     — FREE. An admin approved a request.

Only the FREE path seeds demo data. That split is the whole point of these
tests: a prospect should open a populated dashboard, and somebody who has just
paid real money should open a real (empty) one.

The savepoint behaviour in _seed_sample_data_best_effort gets its own test
because it is the difference between "the owner clicked Load demo data and it
failed" (recoverable, they retry from Settings) and "the approval silently
didn't happen" (the admin sees success, the clinic does not exist).
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from src.models.patient import Patient
from src.models.pending_signup import OrgRequestStatus, PendingSignup
from src.models.subscription import SubscriptionTier
from src.services.checkout.provisioning_service import ProvisioningService
from tests.conftest import random_suffix


async def _sample_patient_count(db_session, practice_id):
    return (
        await db_session.execute(
            select(func.count())
            .select_from(Patient)
            .where(Patient.practice_id == practice_id, Patient.is_sample.is_(True))
        )
    ).scalar_one()


def _free_org_request(**kwargs):
    """A PendingSignup shaped like a free org-request approval.

    `request_status` + `org_name` + a NULL `stripe_session_id` is what marks a
    row as the org-request flow (see the NOTE in models/pending_signup.py).
    """
    email = f"owner-{random_suffix()}@test.local"
    defaults = {
        "id": uuid.uuid4(),
        "email": email,
        "clerk_id": f"user_{uuid.uuid4().hex[:12]}",
        "org_name": "Test Aesthetics",
        "request_status": OrgRequestStatus.PENDING,
        "stripe_session_id": None,
        "plan_tier": SubscriptionTier.PRACTICE.value,
    }
    defaults.update(kwargs)
    return PendingSignup(**defaults)


def _paid_signup(**kwargs):
    """A PendingSignup shaped like a paid Stripe checkout: a session id and a
    `completed_at` payment stamp, with the org-request fields left NULL."""
    email = f"buyer-{random_suffix()}@test.local"
    defaults = {
        "id": uuid.uuid4(),
        "email": email,
        "clerk_id": f"user_{uuid.uuid4().hex[:12]}",
        "stripe_session_id": f"cs_test_{uuid.uuid4().hex[:16]}",
        "completed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "plan_tier": SubscriptionTier.PRACTICE.value,
    }
    defaults.update(kwargs)
    return PendingSignup(**defaults)


# ------------------------------------------------------------- free path


@pytest.mark.asyncio
async def test_free_org_approval_seeds_demo_data(db_session):
    """The headline requirement: an approved free org lands on a populated
    dashboard, not an empty one."""
    pending = _free_org_request()
    db_session.add(pending)
    await db_session.flush()

    practice = await ProvisioningService().provision_from_org_request(db_session, pending)
    await db_session.flush()

    assert await _sample_patient_count(db_session, practice.id) > 0
    assert pending.practice_id == practice.id
    assert pending.claimed_at is not None


@pytest.mark.asyncio
async def test_free_org_approval_seeds_only_its_own_practice(db_session):
    """Two orgs approved in one test session must not share demo rows."""
    first = _free_org_request()
    second = _free_org_request()
    db_session.add_all([first, second])
    await db_session.flush()

    service = ProvisioningService()
    practice_a = await service.provision_from_org_request(db_session, first)
    practice_b = await service.provision_from_org_request(db_session, second)
    await db_session.flush()

    assert practice_a.id != practice_b.id
    assert await _sample_patient_count(db_session, practice_a.id) > 0
    assert await _sample_patient_count(db_session, practice_b.id) > 0


@pytest.mark.asyncio
async def test_free_org_approval_is_idempotent(db_session):
    """Re-approving must return the same practice, not duplicate it."""
    pending = _free_org_request()
    db_session.add(pending)
    await db_session.flush()

    service = ProvisioningService()
    first = await service.provision_from_org_request(db_session, pending)
    patients_after_first = await _sample_patient_count(db_session, first.id)

    second = await service.provision_from_org_request(db_session, pending)
    await db_session.flush()

    assert second.id == first.id
    assert await _sample_patient_count(db_session, first.id) == patients_after_first


# -------------------------------------------------------------- paid path


@pytest.mark.asyncio
async def test_paid_signup_does_not_seed_demo_data(db_session):
    """A paying customer must open a real, empty clinic.

    Seeding here would put fabricated patients and a fabricated burn rate in
    front of someone who has just handed over money — the exact outcome
    sample_data_service.py's rule 3 exists to prevent.
    """
    pending = _paid_signup()
    db_session.add(pending)
    await db_session.flush()

    practice = await ProvisioningService().provision_from_pending_signup(
        db_session,
        pending,
        clerk_id=pending.clerk_id,
        clerk_email=pending.email,
        clerk_name="Paid Buyer",
    )
    await db_session.flush()

    assert await _sample_patient_count(db_session, practice.id) == 0


# ----------------------------------------------------------- savepoint


@pytest.mark.asyncio
async def test_seed_failure_does_not_fail_the_approval(db_session, monkeypatch):
    """The most important test in this file.

    If seeding raised through to the caller, the approval transaction would
    roll back and the request would be left looking approved while no clinic
    existed. Instead the failure must be swallowed — and, crucially, must not
    poison the outer transaction either (which is what the SAVEPOINT is for:
    in PostgreSQL a failed statement aborts the whole transaction, so a bare
    try/except would swallow the error and then still fail on the next flush).

    The failure injected here is a REAL database error (a duplicate primary
    key), not a Python exception, and that distinction is the whole test. A
    `raise RuntimeError` in the seeder is caught and rolled back cleanly with
    or without a savepoint, so it proves nothing about PostgreSQL's
    aborted-transaction behaviour — this variant is the one that fails without
    `db.begin_nested()`.
    """
    from src.services.checkout import provisioning_service as module

    async def failing_seed(self, db, practice):
        """Insert a patient with a fixed id twice: the second insert violates the
        primary key and aborts the transaction the way a real bug would.

        Takes `self` because seed_sample_data is an instance method — omitting it
        raises a TypeError before any SQL runs, which the savepoint would
        absorb happily and the test would pass without proving anything.
        """
        for _ in range(2):
            db.add(
                Patient(
                    id=uuid.UUID("00000000-0000-0000-0000-00000000c0de"),
                    practice_id=practice.id,
                    first_name="Duplicate",
                    last_name="PrimaryKey",
                )
            )
            await db.flush()

    monkeypatch.setattr(module.SampleDataService, "seed_sample_data", failing_seed)

    pending = _free_org_request()
    db_session.add(pending)
    await db_session.flush()

    practice = await ProvisioningService().provision_from_org_request(db_session, pending)

    # The approval completed: the practice exists and the request is claimed.
    assert practice.id is not None
    assert pending.practice_id == practice.id
    assert pending.claimed_at is not None

    # The session is still usable. Without the savepoint the flush below would
    # raise "current transaction is aborted, commands ignored until end of
    # transaction block" — the savepoint is what keeps the approval alive.
    await db_session.flush()
    assert await _sample_patient_count(db_session, practice.id) == 0
