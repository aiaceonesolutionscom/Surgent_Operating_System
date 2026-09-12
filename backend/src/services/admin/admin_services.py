from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.practice import Practice, PracticeStatus
from src.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from src.models.agent_config import AgentConfig
from src.models.agent_costing import AgentCosting
from src.models.user import User
from src.models.pending_signup import PendingSignup, OrgRequestStatus
from src.services.checkout.provisioning_service import ProvisioningService
from src.server.exceptions import NotFoundException, AppException

# No real per-session usage telemetry exists yet — nothing persists
# Conversation/Message rows today (see models/conversation.py), and
# AgentCosting.total_sessions is never incremented anywhere in this
# codebase. Every "cost"/"revenue" figure this service produces is
# therefore an ESTIMATE, not a measurement, and every field name/response
# is prefixed `estimated_` so the frontend can't accidentally present it
# as real. This constant is the first thing to replace once real usage
# tracking ships.
ASSUMED_MONTHLY_SESSIONS_PER_AGENT = 150


class AdminService:
    async def _agent_costing_map(self, db: AsyncSession) -> dict[str, AgentCosting]:
        result = await db.execute(select(AgentCosting))
        return {row.agent_slug: row for row in result.scalars().all()}

    async def _active_subscriptions(self, db: AsyncSession) -> dict:
        # Most-recent active/trial subscription per practice — mirrors
        # PracticeService.active_subscription_for but batched for every
        # practice in one query instead of N+1.
        result = await db.execute(
            select(Subscription)
            .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]))
            .order_by(Subscription.practice_id, Subscription.created_at.desc())
        )
        by_practice: dict = {}
        for sub in result.scalars().all():
            by_practice.setdefault(sub.practice_id, sub)  # first hit per practice_id = most recent (query is ordered)
        return by_practice

    async def _enabled_agent_counts(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(AgentConfig.practice_id, func.count())
            .where(AgentConfig.enabled.is_(True))
            .group_by(AgentConfig.practice_id)
        )
        return dict(result.all())

    def estimated_monthly_cost_for_configs(self, configs: list[AgentConfig], costing_map: dict[str, AgentCosting]) -> Decimal:
        total = Decimal("0")
        for cfg in configs:
            if not cfg.enabled:
                continue
            costing = costing_map.get(cfg.agent_type)
            if costing is None or not costing.is_active:
                continue
            total += costing.cost_per_session * ASSUMED_MONTHLY_SESSIONS_PER_AGENT
        return total

    async def list_practices(
        self,
        db: AsyncSession,
        q: str | None = None,
        plan_tier: str | None = None,
        sort: str = "-joined_at",
    ) -> list[dict]:
        stmt = select(Practice)
        if q:
            stmt = stmt.where(Practice.name.ilike(f"%{q}%"))
        stmt = stmt.order_by(Practice.created_at.desc() if sort == "-joined_at" else Practice.created_at.asc())
        practices = (await db.execute(stmt)).scalars().all()

        costing_map = await self._agent_costing_map(db)
        subs_by_practice = await self._active_subscriptions(db)
        enabled_counts = await self._enabled_agent_counts(db)

        # Per-practice agent configs, batched.
        practice_ids = [p.id for p in practices]
        configs_result = await db.execute(select(AgentConfig).where(AgentConfig.practice_id.in_(practice_ids))) if practice_ids else None
        configs_by_practice: dict = {}
        if configs_result is not None:
            for cfg in configs_result.scalars().all():
                configs_by_practice.setdefault(cfg.practice_id, []).append(cfg)

        rows = []
        for practice in practices:
            sub = subs_by_practice.get(practice.id)
            if plan_tier and (sub is None or sub.tier.value != plan_tier):
                continue
            configs = configs_by_practice.get(practice.id, [])
            cost = self.estimated_monthly_cost_for_configs(configs, costing_map)
            revenue = sub.price if (sub and sub.price is not None) else Decimal("0")
            rows.append({
                "id": practice.id,
                "name": practice.name,
                "email": practice.email,
                "status": practice.status.value,
                "plan_tier": sub.tier.value if sub else SubscriptionTier.PRACTICE.value,
                "subscription_status": sub.status.value if sub else "none",
                "agents_enabled_count": enabled_counts.get(practice.id, 0),
                "estimated_monthly_cost": cost,
                "estimated_monthly_revenue": revenue,
                "joined_at": practice.created_at,
            })
        return rows

    async def create_practice(
        self, db: AsyncSession, name: str, email: str, plan_tier: str | None = None
    ) -> Practice:
        """Super-Admin manual practice creation (no approx: from the /admin
        Clinics tab, not the paid checkout flow). Creates the Practice row +
        an active-trial Subscription on the chosen plan + the 9 agent config
        rows, so the practice is immediately visible and gated correctly."""
        name = (name or "").strip()
        email = (email or "").strip().lower()
        if not name or not email:
            raise AppException("Name and email are required.")
        existing = (await db.execute(select(Practice).where(Practice.email == email))).scalar_one_or_none()
        if existing:
            raise AppException("A practice with this email already exists.")

        tier = plan_tier or SubscriptionTier.PRACTICE.value
        if tier == SubscriptionTier.SOLO.value:
            tier = SubscriptionTier.PRACTICE.value

        practice = Practice(id=UUID(str(uuid4())), name=name, email=email, status=PracticeStatus.ACTIVE)
        db.add(practice)
        await db.flush()

        provisioning = ProvisioningService()
        subscription = await provisioning._get_or_create_subscription(db, practice, tier)
        await provisioning._seed_agent_configs(db, practice, subscription.tier)
        await db.refresh(practice)
        return practice

    async def update_practice(
        self, db: AsyncSession, practice_id, name: str | None = None, email: str | None = None, plan_tier: str | None = None
    ) -> Practice:
        practice = await db.get(Practice, practice_id)
        if practice is None:
            raise NotFoundException("Practice not found.")

        if name is not None and name.strip():
            practice.name = name.strip()
        if email is not None and email.strip():
            practice.email = email.strip().lower()

        if plan_tier:
            tier = SubscriptionTier.PRACTICE if plan_tier == SubscriptionTier.SOLO.value else SubscriptionTier(plan_tier)
            provisioning = ProvisioningService()
            subscription = await provisioning._get_or_create_subscription(db, practice, tier.value)
            if subscription.tier != tier:
                subscription.tier = tier
            await db.flush()

        await db.flush()
        await db.refresh(practice)
        return practice

    async def practice_detail(self, db: AsyncSession, practice_id) -> dict | None:
        practice = (await db.execute(select(Practice).where(Practice.id == practice_id))).scalar_one_or_none()
        if practice is None:
            return None

        sub = (
            await db.execute(
                select(Subscription)
                .where(Subscription.practice_id == practice_id)
                .order_by(Subscription.created_at.desc())
            )
        ).scalars().first()

        costing_map = await self._agent_costing_map(db)
        configs = (await db.execute(select(AgentConfig).where(AgentConfig.practice_id == practice_id))).scalars().all()

        breakdown = []
        for cfg in configs:
            costing = costing_map.get(cfg.agent_type)
            cost_per_session = costing.cost_per_session if costing else Decimal("0")
            monthly_cost = cost_per_session * ASSUMED_MONTHLY_SESSIONS_PER_AGENT if cfg.enabled and costing and costing.is_active else Decimal("0")
            breakdown.append({
                "agent_slug": cfg.agent_type,
                "enabled": cfg.enabled,
                "cost_per_session": cost_per_session,
                "estimated_monthly_cost": monthly_cost,
            })

        return {
            "id": practice.id,
            "name": practice.name,
            "email": practice.email,
            "status": practice.status.value,
            "phone": practice.phone,
            "address": practice.address,
            "plan_tier": sub.tier.value if sub else SubscriptionTier.PRACTICE.value,
            "subscription_status": sub.status.value if sub else "none",
            "estimated_monthly_revenue": sub.price if (sub and sub.price is not None) else Decimal("0"),
            "estimated_monthly_cost": self.estimated_monthly_cost_for_configs(configs, costing_map),
            "agent_breakdown": breakdown,
            "joined_at": practice.created_at,
        }

    async def platform_summary(self, db: AsyncSession) -> dict:
        rows = await self.list_practices(db)
        total_clinics = len(rows)
        plan_distribution: dict[str, int] = {}
        total_mrr = Decimal("0")
        total_cost = Decimal("0")
        for row in rows:
            plan_distribution[row["plan_tier"]] = plan_distribution.get(row["plan_tier"], 0) + 1
            total_mrr += row["estimated_monthly_revenue"]
            total_cost += row["estimated_monthly_cost"]
        margin = total_mrr - total_cost
        margin_percent = float(margin / total_mrr * 100) if total_mrr else 0.0
        return {
            "total_clinics": total_clinics,
            "plan_distribution": plan_distribution,
            "total_estimated_mrr": total_mrr,
            "total_estimated_cost": total_cost,
            "total_estimated_margin": margin,
            "margin_percent": margin_percent,
        }

    async def list_users(self, db: AsyncSession, q: str | None = None) -> list[User]:
        # Every user across every practice, searchable by email — this is
        # how a platform admin finds and promotes the next admin. Not
        # paginated yet; fine at current scale, revisit if the roster grows.
        stmt = select(User).order_by(User.created_at.desc())
        if q:
            stmt = stmt.where(User.email.ilike(f"%{q}%"))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_user(self, db: AsyncSession, user_id) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    # --- New-organization approval queue (Super Admin) ----------------------
    # These act on the SAME PendingSignup rows the free /sign-up org-request
    # path writes (see org_request_service.py) — a Super Admin reviewing
    # `request_status == PENDING` rows is the actual gate that turns a
    # genuinely new signup into a real, isolated Practice.

    async def list_pending_org_requests(self, db: AsyncSession) -> list[PendingSignup]:
        result = await db.execute(
            select(PendingSignup)
            .where(PendingSignup.request_status == OrgRequestStatus.PENDING)
            .order_by(PendingSignup.created_at.asc())
        )
        return list(result.scalars().all())

    async def _get_org_request(self, db: AsyncSession, request_id: UUID) -> PendingSignup:
        result = await db.execute(select(PendingSignup).where(PendingSignup.id == request_id))
        pending = result.scalar_one_or_none()
        if pending is None or pending.request_status is None:
            raise NotFoundException("Organization request not found.")
        return pending

    async def approve_org_request(self, db: AsyncSession, request_id: UUID, plan_tier: str | None = None) -> Practice:
        pending = await self._get_org_request(db, request_id)
        if pending.request_status != OrgRequestStatus.PENDING:
            raise AppException(f"This request is already {pending.request_status.value}.")

        practice = await ProvisioningService().provision_from_org_request(db, pending, plan_tier=plan_tier)
        pending.request_status = OrgRequestStatus.APPROVED
        pending.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        return practice

    async def reject_org_request(self, db: AsyncSession, request_id: UUID, reason: str | None) -> PendingSignup:
        pending = await self._get_org_request(db, request_id)
        if pending.request_status != OrgRequestStatus.PENDING:
            raise AppException(f"This request is already {pending.request_status.value}.")

        pending.request_status = OrgRequestStatus.REJECTED
        pending.rejected_reason = reason
        pending.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(pending)
        return pending

    # --- Soft suspend/reactivate (Super Admin's "delete an organization") --
    # Deliberately soft (per product decision — patient medical data cascades
    # off Practice, see models/practice.py's relationships) — suspend flips
    # status only, data stays intact, and get_current_practice_context
    # (server/dependencies.py) is the actual enforcement point that locks
    # every practice-scoped endpoint out the moment this flips.

    async def suspend_practice(self, db: AsyncSession, practice_id: UUID) -> Practice:
        practice = (await db.execute(select(Practice).where(Practice.id == practice_id))).scalar_one_or_none()
        if practice is None:
            raise NotFoundException("Practice not found.")
        practice.status = PracticeStatus.SUSPENDED
        await db.flush()
        await db.refresh(practice)
        return practice

    async def reactivate_practice(self, db: AsyncSession, practice_id: UUID) -> Practice:
        practice = (await db.execute(select(Practice).where(Practice.id == practice_id))).scalar_one_or_none()
        if practice is None:
            raise NotFoundException("Practice not found.")
        practice.status = PracticeStatus.ACTIVE
        await db.flush()
        await db.refresh(practice)
        return practice
