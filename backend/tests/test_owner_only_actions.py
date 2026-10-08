"""Actions that change money, the roster, or expose the audit trail are
Owner-only. Each used to accept any signed-in role of the practice, so a
receptionist could cancel the subscription or add a doctor."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.models.user import UserRole
from src.server.dependencies import get_current_practice_context, get_current_practice_user, PracticeContext
from tests.conftest import make_practice, make_user


def _as(role: UserRole):
    practice = make_practice()
    user = make_user(practice, role=role)

    async def _user():
        return user

    async def _ctx():
        return PracticeContext(user=user, practice=practice, tier=None)

    app.dependency_overrides[get_current_practice_user] = _user
    app.dependency_overrides[get_current_practice_context] = _ctx


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


OWNER_ONLY = [
    ("post", "/api/v1/billing/cancel", None),
    ("post", "/api/v1/billing/resume", None),
    ("post", "/api/v1/billing/change-plan", {"tier": "practice"}),
    ("get", "/api/v1/audit-logs", None),
    ("post", "/api/v1/leads/run-nurturing", None),
    ("post", "/api/v1/doctors", {"name": "Dr X", "email": "x@x.com"}),
]


@pytest.mark.parametrize("role", [UserRole.RECEPTIONIST, UserRole.DOCTOR, UserRole.STAFF])
@pytest.mark.parametrize("method,path,body", OWNER_ONLY)
async def test_non_owner_is_forbidden(role, method, path, body):
    _as(role)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert resp.status_code == 403, f"{role.value} reached {method.upper()} {path}: {resp.status_code}"
