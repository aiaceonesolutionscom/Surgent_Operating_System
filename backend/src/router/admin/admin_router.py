from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.admin import (
    AdminSummaryResponse,
    AdminPracticeListItem,
    AdminPracticeDetailResponse,
    UpdateSubscriptionRequest,
    AdminUserResponse,
    UpdateAdminUserRequest,
    AdminMeResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    SalesLeadResponse,
    OrgRequestListItem,
    RejectOrgRequestRequest,
    ApproveOrgRequestRequest,
    CreatePracticeRequest,
    UpdatePracticeRequest,
)
from src.schemas.plan import PlanResponse, PlanCreateRequest, PlanUpdateRequest
from src.schemas.super_agent import (
    AskSuperAgentRequest, AskSuperAgentResponse,
    SuperAgentSessionSummary, SuperAgentSessionDetail,
)
from src.models.message import MessageRole
from src.controller.admin.admin_controllers import AdminController
from src.server.dependencies import require_admin_token, AdminPrincipal
from src.services.super_agent.super_agent_services import SuperAgentService

# Every route here (except /auth/login) is platform-owner-only (Aiaceone
# team), never clinic-facing — enforced by require_admin_token (a standalone
# username/password + JWT login, see services/admin/admin_auth_service.py),
# not just hidden by frontend routing.
router = APIRouter(prefix="/admin", tags=["Platform Admin"])
controller = AdminController()
super_agent_service = SuperAgentService()


@router.post("/auth/login", response_model=AdminLoginResponse)
async def login(body: AdminLoginRequest, request: Request):
    client_key = f"{request.client.host if request.client else 'unknown'}:{body.username}"
    return await controller.login(body, client_key)


@router.get("/me", response_model=AdminMeResponse)
async def get_me(admin: AdminPrincipal = Depends(require_admin_token)):
    return await controller.me(admin)


@router.get("/summary", response_model=AdminSummaryResponse)
async def get_summary(
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.summary(db)


@router.get("/practices", response_model=list[AdminPracticeListItem])
async def list_practices(
    q: Optional[str] = None,
    plan_tier: Optional[str] = None,
    sort: str = "-joined_at",
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_practices(db, q=q, plan_tier=plan_tier, sort=sort)


@router.get("/practices/{practice_id}", response_model=AdminPracticeDetailResponse)
async def get_practice(
    practice_id: UUID,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.practice_detail(db, practice_id)


@router.post("/practices", response_model=AdminPracticeDetailResponse)
async def create_practice(
    body: CreatePracticeRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Super-Admin manual practice creation — used for a sale done offline; the
    practice is created active on the chosen plan with the full 9-agent config
    (same result as an approved org request, without the signup queue)."""
    return await controller.create_practice(db, body)


@router.patch("/practices/{practice_id}", response_model=AdminPracticeDetailResponse)
async def update_practice(
    practice_id: UUID,
    body: UpdatePracticeRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Edit a practice's name/email and reassign its plan (writes the active
    subscription tier)."""
    return await controller.update_practice(db, practice_id, body)


@router.patch("/practices/{practice_id}/subscription", response_model=AdminPracticeDetailResponse)
async def update_practice_subscription(
    practice_id: UUID,
    body: UpdateSubscriptionRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_subscription(db, practice_id, body)


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_plans(db)


@router.post("/plans", response_model=PlanResponse)
async def create_plan(
    body: PlanCreateRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_plan(db, body)


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: UUID,
    body: PlanUpdateRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_plan(db, plan_id, body)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    q: Optional[str] = None,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_users(db, q=q)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: UUID,
    body: UpdateAdminUserRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_user(db, user_id, body)


@router.get("/org-requests", response_model=list[OrgRequestListItem])
async def list_org_requests(
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """The new-organization approval queue — every PENDING free /sign-up
    request (see org_request_service.py). Approving provisions a real,
    isolated Practice + Owner User; rejecting just marks the request."""
    return await controller.list_org_requests(db)


@router.post("/org-requests/{request_id}/approve", response_model=AdminPracticeDetailResponse)
async def approve_org_request(
    request_id: UUID,
    body: ApproveOrgRequestRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.approve_org_request(db, request_id, body)


@router.post("/org-requests/{request_id}/reject", status_code=204)
async def reject_org_request(
    request_id: UUID,
    body: RejectOrgRequestRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    await controller.reject_org_request(db, request_id, body)


@router.post("/practices/{practice_id}/suspend", response_model=AdminPracticeDetailResponse)
async def suspend_practice(
    practice_id: UUID,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """A Super Admin's soft 'delete' — data stays intact
    (see admin_services.py's suspend_practice docstring), the practice just
    loses dashboard access immediately (enforced in
    server/dependencies.py's get_current_practice_context)."""
    return await controller.suspend_practice(db, practice_id)


@router.post("/practices/{practice_id}/reactivate", response_model=AdminPracticeDetailResponse)
async def reactivate_practice(
    practice_id: UUID,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return await controller.reactivate_practice(db, practice_id)


@router.get("/sales-leads", response_model=list[SalesLeadResponse])
async def list_sales_leads(
    q: Optional[str] = None,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Clinic-buyer leads captured by Aria on the marketing site (platform
    sales pipeline). Aiaceone-owner only, same access rule as every /admin
    route."""
    return await controller.list_sales_leads(db, q=q)


# --- Super Agent (platform-level, Aiaceone-team only) -------------------------

def _super_title(conversation) -> str:
    staff = sorted((m for m in conversation.messages if m.role == MessageRole.STAFF), key=lambda m: m.created_at)
    if not staff:
        return "New conversation"
    first = staff[0].content.strip()
    return first[:60] + ("…" if len(first) > 60 else "")


@router.post("/super-agent/ask", response_model=AskSuperAgentResponse)
async def ask_super_agent(
    body: AskSuperAgentRequest,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """The platform-owner agent — answers questions about the whole book of
    practices (MRR, plan mix, approval queue) using live numbers."""
    return await super_agent_service.ask(db, body.question, body.session_id)


@router.get("/super-agent/sessions", response_model=list[SuperAgentSessionSummary])
async def list_super_agent_sessions(
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    return [
        SuperAgentSessionSummary(id=c.id, title=_super_title(c), updated_at=c.updated_at)
        for c in await super_agent_service.list_sessions(db)
    ]


@router.get("/super-agent/sessions/{session_id}", response_model=SuperAgentSessionDetail)
async def get_super_agent_session(
    session_id: UUID,
    admin: AdminPrincipal = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db),
):
    conversation = await super_agent_service.get_session(db, session_id)
    messages = sorted(conversation.messages, key=lambda m: m.created_at)
    return SuperAgentSessionDetail(
        id=conversation.id,
        title=_super_title(conversation),
        messages=[
            {
                "role": "staff" if m.role == MessageRole.STAFF else "agent",
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    )
