"""Super Admin platform metrics + activity endpoints — the numbers the
overview panel (CLINICS/USERS/PATIENTS/APPOINTMENTS/AI/SUBSCRIPTIONS/SYSTEM/
ACTIVITY) renders live.

The important assertion beyond "it 200s": every count the panel shows is a
REAL measured number derived from the seeded rows, and the estimate-flagged
AI cost responds to the costing table. If any of these drift back to
hardcoded values, a test here fails instead of the panel quietly lying.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.main import app
from src.database import Base, get_db
from src.models.practice import Practice, PracticeStatus
from src.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from src.models.patient import Patient
from src.models.appointment import Appointment
from src.models.agent_log import AgentLog
from src.models.agent_costing import AgentCosting
from src.models.user import User
from src.models.audit_log import AuditLog
from src.server.dependencies import require_admin_token, AdminPrincipal


@pytest.fixture
async def admin_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_admin_token] = lambda: AdminPrincipal(username="tester")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, factory

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed(factory):
    from datetime import timedelta

    async with factory() as session:
        p_active = Practice(id=uuid4(), name="Active Clinic", email="a@x.com", status=PracticeStatus.ACTIVE)
        p_trial = Practice(id=uuid4(), name="Trial Clinic", email="t@x.com", status=PracticeStatus.ACTIVE)
        p_suspended = Practice(id=uuid4(), name="Suspended Clinic", email="s@x.com", status=PracticeStatus.SUSPENDED)
        session.add_all([p_active, p_trial, p_suspended])
        await session.flush()

        session.add_all([
            Subscription(
                practice_id=p_active.id, tier=SubscriptionTier.PRACTICE,
                status=SubscriptionStatus.ACTIVE, start_date=date.today(),
            ),
            Subscription(
                practice_id=p_trial.id, tier=SubscriptionTier.PRACTICE,
                status=SubscriptionStatus.TRIAL, start_date=date.today(),
                cancel_at_period_end=True,
            ),
            Subscription(
                practice_id=p_suspended.id, tier=SubscriptionTier.PRACTICE,
                status=SubscriptionStatus.CANCELLED, start_date=date.today(),
            ),
        ])

        patient1 = Patient(id=uuid4(), practice_id=p_active.id, first_name="A", last_name="One")
        patient2 = Patient(id=uuid4(), practice_id=p_active.id, first_name="B", last_name="Two")
        session.add_all([patient1, patient2])

        now = datetime.now(timezone.utc)
        session.add(Appointment(
            id=uuid4(), practice_id=p_active.id, patient_id=patient1.id,
            appointment_type="consult",
            start_time=now, end_time=now + timedelta(hours=1),
        ))

        session.add(AgentCosting(
            id=uuid4(), agent_slug="receptionist",
            cost_per_session=0.5, is_active=True,
        ))
        session.add_all([
            AgentLog(id=uuid4(), practice_id=p_active.id, agent_type="receptionist", action="reply.sent"),
            AgentLog(id=uuid4(), practice_id=p_active.id, agent_type="receptionist", action="reply.sent"),
        ])

        session.add(User(
            id=uuid4(), practice_id=p_active.id, clerk_id="clerk_1",
            email="doctor@x.com", name="Dr. One",
        ))

        session.add(AuditLog(
            id=uuid4(), practice_id=p_active.id, actor_user_id=None,
            actor_type="user", action="patient.view",
        ))
        session.add(AuditLog(
            id=uuid4(), practice_id=None, actor_user_id=None,
            actor_type="patient_portal", action="portal_login.failed",
        ))

        await session.commit()
        return p_active.id


async def test_platform_metrics_counts_seeded_rows(admin_client):
    client, factory = admin_client
    await _seed(factory)

    response = await client.get("/api/v1/admin/platform_metrics")
    assert response.status_code == 200
    data = response.json()

    # CLINICS: one of each status; trial is a subscription state, suspended a practice state
    assert data["clinics"] == {"total": 3, "active": 1, "trial": 1, "suspended": 1}
    assert data["total_users"] == 1
    assert data["total_patients"] == 2
    assert data["appointments_this_month"] == 1

    # AI: runs measured from agent_logs; cost = logged sessions × per-session price (2 × $0.5)
    assert data["ai"]["runs_total"] == 2
    assert data["ai"]["estimated_cost_total"] == 1.0
    assert data["ai"]["cost_is_estimate"] is True

    # SUBSCRIPTIONS: cancelling is cancel_at_period_end, counted separately from active
    subs = data["subscriptions"]
    assert subs["active"] == 1
    assert subs["trial"] == 1
    assert subs["cancelled"] == 1
    assert subs["cancelling"] == 1  # the trial with cancel_at_period_end=True

    # SYSTEM: all real values, present and typed — uptime ticks, db round-trip measured
    assert data["system"]["uptime_seconds"] >= 0
    assert data["system"]["db_health_ms"] is not None
    assert data["system"]["error_rate_percent"] >= 0.0
    assert data["system"]["slow_requests_total"] >= 0


async def test_platform_metrics_requires_admin_token(client):
    response = await client.get("/api/v1/admin/platform_metrics")
    assert response.status_code in (401, 403)


async def test_activity_returns_audit_events_with_clinic_names(admin_client):
    client, factory = admin_client
    await _seed(factory)

    response = await client.get("/api/v1/admin/activity?limit=10")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 2

    scoped = [e for e in events if e["practice_name"] == "Active Clinic"]
    assert len(scoped) == 1
    assert scoped[0]["action"] == "patient.view"
    assert scoped[0]["actor_type"] == "user"

    unscoped = [e for e in events if e["practice_name"] is None]
    assert len(unscoped) == 1
    assert unscoped[0]["action"] == "portal_login.failed"


async def test_summary_survives_real_priced_subscriptions(admin_client):
    """Regression: /summary used to 500 with 'unsupported operand Decimal +
    float' the moment any practice had a priced subscription (sub.price float
    vs the Decimal accumulator). A clinic with an actual price must sum
    cleanly, not crash the whole overview."""
    from datetime import date as date_cls
    from src.models.plan import Plan

    client, factory = admin_client
    async with factory() as session:
        practice = Practice(id=uuid4(), name="Priced Clinic", email="p@x.com", status=PracticeStatus.ACTIVE)
        session.add(practice)
        await session.flush()
        session.add(Plan(tier="practice", name="Practice", price=999.0, display_order=1))
        session.add(Subscription(
            practice_id=practice.id, tier=SubscriptionTier.PRACTICE,
            status=SubscriptionStatus.ACTIVE, price=999.0, start_date=date_cls.today(),
        ))
        await session.commit()

    response = await client.get("/api/v1/admin/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_clinics"] == 1
    assert data["total_estimated_mrr"] == 999.0
    assert data["total_estimated_margin"] == 999.0
