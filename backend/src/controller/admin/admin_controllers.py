from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from src.models.sales_lead import SalesLead
from src.schemas.admin import (
    AdminSummaryResponse,
    AdminPracticeListItem,
    AdminPracticeDetailResponse,
    AgentCostBreakdownItem,
    UpdateSubscriptionRequest,
    CreatePracticeRequest,
    UpdatePracticeRequest,
    AdminUserResponse,
    UpdateAdminUserRequest,
    AdminMeResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    SalesLeadResponse,
    OrgRequestListItem,
    RejectOrgRequestRequest,
    ApproveOrgRequestRequest,
)
from src.schemas.plan import PlanResponse, PlanCreateRequest, PlanUpdateRequest
from src.services.admin.admin_services import AdminService
from src.services.admin.plan_services import PlanService
from src.services.admin import admin_auth_service
from src.services.security.rate_limiter import RedisRateLimiter
from src.server.dependencies import AdminPrincipal
from src.server.exceptions import NotFoundException, UnauthorizedException

# A single hardcoded platform-owner account (see admin_auth_service.py) is
# still a real credential reachable over the network — same class of risk
# as the Patient Portal PIN login, so it gets the same treatment.
admin_login_rate_limiter = RedisRateLimiter(max_attempts=5, window_seconds=15 * 60)


class AdminController:
    def __init__(self):
        self.service = AdminService()
        self.plans = PlanService()

    async def login(self, body: AdminLoginRequest, client_key: str) -> AdminLoginResponse:
        await admin_login_rate_limiter.check(client_key)
        if not admin_auth_service.authenticate(body.username, body.password):
            raise UnauthorizedException("Invalid username or password.")
        await admin_login_rate_limiter.reset(client_key)
        return AdminLoginResponse(access_token=admin_auth_service.create_admin_token())

    async def me(self, admin: AdminPrincipal) -> AdminMeResponse:
        return AdminMeResponse(username=admin.username)

    async def summary(self, db: AsyncSession) -> AdminSummaryResponse:
        data = await self.service.platform_summary(db)
        return AdminSummaryResponse(
            total_clinics=data["total_clinics"],
            plan_distribution=data["plan_distribution"],
            total_estimated_mrr=float(data["total_estimated_mrr"]),
            total_estimated_cost=float(data["total_estimated_cost"]),
            total_estimated_margin=float(data["total_estimated_margin"]),
            margin_percent=data["margin_percent"],
        )

    async def list_practices(self, db: AsyncSession, q: str | None, plan_tier: str | None, sort: str) -> list[AdminPracticeListItem]:
        rows = await self.service.list_practices(db, q=q, plan_tier=plan_tier, sort=sort)
        return [
            AdminPracticeListItem(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                status=row["status"],
                plan_tier=row["plan_tier"],
                subscription_status=row["subscription_status"],
                agents_enabled_count=row["agents_enabled_count"],
                estimated_monthly_cost=float(row["estimated_monthly_cost"]),
                estimated_monthly_revenue=float(row["estimated_monthly_revenue"]),
                joined_at=row["joined_at"],
            )
            for row in rows
        ]

    async def create_practice(self, db: AsyncSession, body: CreatePracticeRequest) -> AdminPracticeDetailResponse:
        practice = await self.service.create_practice(db, body.name, body.email, body.plan_tier)
        return await self.practice_detail(db, practice.id)

    async def update_practice(self, db: AsyncSession, practice_id, body: UpdatePracticeRequest) -> AdminPracticeDetailResponse:
        practice = await self.service.update_practice(db, practice_id, body.name, body.email, body.plan_tier)
        return await self.practice_detail(db, practice.id)

    async def practice_detail(self, db: AsyncSession, practice_id) -> AdminPracticeDetailResponse:
        data = await self.service.practice_detail(db, practice_id)
        if data is None:
            raise NotFoundException("Practice not found.")
        return AdminPracticeDetailResponse(
            id=data["id"],
            name=data["name"],
            email=data["email"],
            status=data["status"],
            phone=data["phone"],
            address=data["address"],
            plan_tier=data["plan_tier"],
            subscription_status=data["subscription_status"],
            estimated_monthly_revenue=float(data["estimated_monthly_revenue"]),
            estimated_monthly_cost=float(data["estimated_monthly_cost"]),
            agent_breakdown=[
                AgentCostBreakdownItem(
                    agent_slug=b["agent_slug"],
                    enabled=b["enabled"],
                    cost_per_session=float(b["cost_per_session"]),
                    estimated_monthly_cost=float(b["estimated_monthly_cost"]),
                )
                for b in data["agent_breakdown"]
            ],
            joined_at=data["joined_at"],
        )

    async def update_subscription(self, db: AsyncSession, practice_id, body: UpdateSubscriptionRequest) -> AdminPracticeDetailResponse:
        try:
            new_tier = SubscriptionTier(body.tier)
        except ValueError:
            raise NotFoundException(f"Unknown plan tier: {body.tier}")

        plan = await self.plans.get_plan_by_tier(db, new_tier)

        result = await db.execute(
            select(Subscription)
            .where(Subscription.practice_id == practice_id)
            .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]))
            .order_by(Subscription.created_at.desc())
        )
        sub = result.scalars().first()

        if sub is None:
            sub = Subscription(
                practice_id=practice_id,
                tier=new_tier,
                status=SubscriptionStatus.ACTIVE,
                price=plan.price if plan else None,
                start_date=date.today(),
            )
            db.add(sub)
        else:
            sub.tier = new_tier
            # Moving a clinic to a new tier updates what they're charged
            # going forward — this is an explicit admin action, not the
            # "never rewrite retroactively" concern Plan.price's docstring
            # warns about (that's about Plan edits silently drifting every
            # subscriber; this is a deliberate one-off per-practice change).
            if plan is not None and plan.price is not None:
                sub.price = plan.price

        await db.flush()
        return await self.practice_detail(db, practice_id)

    async def list_plans(self, db: AsyncSession) -> list[PlanResponse]:
        plans = await self.plans.list_plans(db)
        return [PlanResponse.from_model(p) for p in plans]

    async def create_plan(self, db: AsyncSession, body: PlanCreateRequest) -> PlanResponse:
        plan = await self.plans.create_plan(db, tier=SubscriptionTier(body.tier), **body.model_dump(exclude={"tier"}))
        return PlanResponse.from_model(plan)

    async def update_plan(self, db: AsyncSession, plan_id, body: PlanUpdateRequest) -> PlanResponse:
        plan = await self.plans.get_plan(db, plan_id)
        if plan is None:
            raise NotFoundException("Plan not found.")
        plan = await self.plans.update_plan(db, plan, **body.model_dump(exclude_unset=True, exclude_none=True))
        return PlanResponse.from_model(plan)

    async def list_users(self, db: AsyncSession, q: str | None) -> list[AdminUserResponse]:
        users = await self.service.list_users(db, q=q)
        return [AdminUserResponse.model_validate(u) for u in users]

    async def list_sales_leads(self, db: AsyncSession, q: str | None) -> list[SalesLeadResponse]:
        stmt = select(SalesLead).order_by(SalesLead.created_at.desc())
        if q:
            stmt = stmt.where(SalesLead.email.ilike(f"%{q}%") | SalesLead.full_name.ilike(f"%{q}%"))
        result = await db.execute(stmt)
        return [
            SalesLeadResponse(
                id=lead.id,
                full_name=lead.full_name,
                email=lead.email,
                phone=lead.phone,
                company=lead.company,
                message=lead.message,
                source=lead.source.value,
                status=lead.status.value,
                conversation_id=lead.conversation_id,
                created_at=lead.created_at,
            )
            for lead in result.scalars().all()
        ]

    async def update_user(self, db: AsyncSession, user_id, body: UpdateAdminUserRequest) -> AdminUserResponse:
        user = await self.service.get_user(db, user_id)
        if user is None:
            raise NotFoundException("User not found.")
        user.is_platform_admin = body.is_platform_admin
        await db.flush()
        return AdminUserResponse.model_validate(user)

    async def list_org_requests(self, db: AsyncSession) -> list[OrgRequestListItem]:
        rows = await self.service.list_pending_org_requests(db)
        return [
            OrgRequestListItem(id=r.id, email=r.email, org_name=r.org_name, status=r.request_status.value, created_at=r.created_at)
            for r in rows
        ]

    async def approve_org_request(self, db: AsyncSession, request_id: UUID, body: ApproveOrgRequestRequest) -> AdminPracticeDetailResponse:
        practice = await self.service.approve_org_request(db, request_id, plan_tier=body.plan_tier)
        return await self.practice_detail(db, practice.id)

    async def reject_org_request(self, db: AsyncSession, request_id: UUID, body: RejectOrgRequestRequest) -> None:
        await self.service.reject_org_request(db, request_id, body.reason)

    async def suspend_practice(self, db: AsyncSession, practice_id: UUID) -> AdminPracticeDetailResponse:
        await self.service.suspend_practice(db, practice_id)
        return await self.practice_detail(db, practice_id)

    async def reactivate_practice(self, db: AsyncSession, practice_id: UUID) -> AdminPracticeDetailResponse:
        await self.service.reactivate_practice(db, practice_id)
        return await self.practice_detail(db, practice_id)
