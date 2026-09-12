from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.plan import Plan
from src.models.subscription import SubscriptionTier
from src.services.practice.plan_capabilities import (
    AGENT_CATEGORIES,
    TIER_CATEGORIES,
    TIER_LIMITS,
)

# DB-first reads of plan capabilities/pricing, with the hardcoded
# plan_capabilities.py dicts kept as a defensive fallback (only used if no
# Plan row exists for a tier — e.g. a fresh DB before the seed migration, or
# CUSTOM, which has no seeded Plan row today). This is what makes an admin's
# edit in the Plan management screen actually change what a practice is
# gated on, not just what's displayed — every call site that used to read
# plan_capabilities.py directly (server/dependencies.py) now goes through here.


class PlanService:
    @staticmethod
    def _normalize(tier: SubscriptionTier) -> SubscriptionTier:
        # Solo was retired (migration b1a2c3d4e5f6): every solo subscription
        # became practice. A stale solo tier must resolve to the Practice plan,
        # NOT the deactivated SOLO Plan row still in the table.
        return SubscriptionTier.PRACTICE if tier == SubscriptionTier.SOLO else tier

    async def get_plan_by_tier(self, db: AsyncSession, tier: SubscriptionTier | str) -> Plan | None:
        if isinstance(tier, str):
            tier = SubscriptionTier(tier)
        result = await db.execute(select(Plan).where(Plan.tier == self._normalize(tier)))
        return result.scalar_one_or_none()

    async def list_plans(self, db: AsyncSession, include_inactive: bool = True) -> list[Plan]:
        stmt = select(Plan).order_by(Plan.display_order)
        if not include_inactive:
            stmt = stmt.where(Plan.is_active.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_plan(self, db: AsyncSession, plan_id) -> Plan | None:
        result = await db.execute(select(Plan).where(Plan.id == plan_id))
        return result.scalar_one_or_none()

    async def create_plan(self, db: AsyncSession, **fields) -> Plan:
        plan = Plan(**fields)
        db.add(plan)
        await db.flush()
        # created_at/updated_at are server-computed (onupdate=func.now()) —
        # flush() expires them regardless of the session's expire_on_commit
        # setting, so the next attribute access would otherwise try a lazy
        # SELECT outside proper async context (MissingGreenlet). Refresh here
        # so callers (e.g. PlanResponse.from_model) can read them safely.
        await db.refresh(plan)
        return plan

    async def update_plan(self, db: AsyncSession, plan: Plan, **fields) -> Plan:
        for key, value in fields.items():
            if value is not None:
                setattr(plan, key, value)
        await db.flush()
        await db.refresh(plan)
        return plan

    async def allowed_categories(self, db: AsyncSession, tier: SubscriptionTier) -> list[str]:
        plan = await self.get_plan_by_tier(db, tier)
        if plan is not None:
            return plan.agent_categories
        return TIER_CATEGORIES.get(tier, TIER_CATEGORIES[SubscriptionTier.PRACTICE])

    async def allowed_agent_slugs(self, db: AsyncSession, tier: SubscriptionTier) -> set[str]:
        categories = await self.allowed_categories(db, tier)
        return {slug for cat in categories for slug in AGENT_CATEGORIES.get(cat, [])}

    async def allows_category(self, db: AsyncSession, tier: SubscriptionTier, category_id: str) -> bool:
        return category_id in await self.allowed_categories(db, tier)

    async def allows_agent(self, db: AsyncSession, tier: SubscriptionTier, agent_slug: str) -> bool:
        return agent_slug in await self.allowed_agent_slugs(db, tier)

    async def has_analytics(self, db: AsyncSession, tier: SubscriptionTier) -> bool:
        plan = await self.get_plan_by_tier(db, tier)
        if plan is not None:
            return plan.has_analytics
        return tier in (SubscriptionTier.PRACTICE, SubscriptionTier.ENTERPRISE, SubscriptionTier.CUSTOM)

    async def limits_for(self, db: AsyncSession, tier: SubscriptionTier) -> dict[str, float]:
        plan = await self.get_plan_by_tier(db, tier)
        if plan is not None:
            return {
                "max_doctors": plan.max_doctors if plan.max_doctors is not None else float("inf"),
                "max_social_channels": plan.max_social_channels if plan.max_social_channels is not None else float("inf"),
                "max_locations": plan.max_locations if plan.max_locations is not None else float("inf"),
            }
        return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.PRACTICE])
