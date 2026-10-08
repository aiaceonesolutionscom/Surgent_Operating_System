import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from src.main import app
from src.database import Base, get_db


# Production runs on Postgres, tests run on in-memory SQLite. These two hooks
# teach SQLite how to render the Postgres-only column types the models use
# (JSONB, UUID) so `Base.metadata.create_all` can build the real schema in a
# test. This changes only the DDL SQLite emits — the Python-side bind/result
# processors on the types still run, so UUIDs and JSON round-trip exactly as
# they do in production.
@compiles(JSONB, "sqlite")
def _jsonb_on_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PGUUID, "sqlite")
def _uuid_on_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# --- Model factories ---------------------------------------------------------
# Plain constructors (nothing is added to a session): tests add the objects
# they build and flush, so each test decides its own transaction boundaries.
# Every unique column (practice email, user clerk_id, ...) gets a random
# suffix so two objects built in one test never collide.

import uuid as _uuid

from src.models.doctor import Doctor
from src.models.patient import Patient
from src.models.practice import Practice, PracticeStatus
from src.models.user import User, UserRole


def random_suffix() -> str:
    return _uuid.uuid4().hex[:10]


def make_practice(name: str = "Test Clinic", **overrides) -> Practice:
    fields = {
        "id": _uuid.uuid4(),
        "name": name,
        "email": f"practice-{random_suffix()}@test.local",
        "status": PracticeStatus.ACTIVE,
    }
    fields.update(overrides)
    return Practice(**fields)


def make_patient(practice: Practice, first_name: str = "Pat", last_name: str = "Ient", **overrides) -> Patient:
    fields = {
        "id": _uuid.uuid4(),
        "practice_id": practice.id,
        "first_name": first_name,
        "last_name": last_name,
    }
    fields.update(overrides)
    return Patient(**fields)


def make_user(practice: Practice, role=UserRole.STAFF, **overrides) -> User:
    suffix = random_suffix()
    fields = {
        "id": _uuid.uuid4(),
        "practice_id": practice.id,
        "clerk_id": f"user_{suffix}",
        "email": f"user-{suffix}@test.local",
        "name": f"User {suffix}",
        "role": UserRole(role),
    }
    fields.update(overrides)
    return User(**fields)


def make_doctor(practice: Practice, user: User | None = None, **overrides) -> Doctor:
    suffix = random_suffix()
    fields = {
        "id": _uuid.uuid4(),
        "practice_id": practice.id,
        "user_id": user.id if user is not None else None,
        "name": user.name if (user is not None and user.name) else f"Dr. {suffix}",
        "email": user.email if user is not None else f"doctor-{suffix}@test.local",
    }
    fields.update(overrides)
    return Doctor(**fields)
