"""A Super Admin suspending a practice must lock its staff out of EVERY
practice-scoped endpoint, not only the ones that happened to resolve through
get_current_practice_context. Roughly four in five routes depend on
get_current_practice_user instead, so the suspension used to be decorative for
most of the dashboard."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.database import Base, get_db
from src.main import app
from src.models.practice import PracticeStatus
from src.models.user import UserRole
from src.server.dependencies import get_current_user
from tests.conftest import make_practice, make_user


@pytest.fixture
async def staff_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.clear()
    await engine.dispose()


async def _staff_member(factory, status):
    async with factory() as session:
        practice = make_practice(status=status)
        session.add(practice)
        await session.flush()
        user = make_user(practice, role=UserRole.OWNER)
        session.add(user)
        await session.commit()
        sub = user.clerk_id
    app.dependency_overrides[get_current_user] = lambda: {"sub": sub}


@pytest.mark.parametrize("path", ["/api/v1/patients", "/api/v1/doctors", "/api/v1/appointments"])
async def test_suspended_practice_is_locked_out(staff_client, path):
    client, factory = staff_client
    await _staff_member(factory, PracticeStatus.SUSPENDED)
    resp = await client.get(path)
    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"].lower()


async def test_active_practice_still_gets_in(staff_client):
    client, factory = staff_client
    await _staff_member(factory, PracticeStatus.ACTIVE)
    resp = await client.get("/api/v1/patients")
    assert resp.status_code == 200
