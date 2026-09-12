from __future__ import annotations
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.practice import Practice
from src.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from src.models.user import User


class PracticeService:
    async def active_subscription_for(self, db: AsyncSession, practice_id) -> Subscription | None:
        # Practice.subscriptions has no "current" convenience accessor — a
        # practice can accumulate historical rows (cancelled, expired), so
        # pick the most recent non-cancelled/expired one explicitly rather
        # than trusting list order.
        result = await db.execute(
            select(Subscription)
            .where(Subscription.practice_id == practice_id)
            .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]))
            .order_by(Subscription.created_at.desc())
        )
        return result.scalars().first()

    async def tier_for(self, db: AsyncSession, practice_id) -> SubscriptionTier:
        sub = await self.active_subscription_for(db, practice_id)
        return sub.tier if sub else SubscriptionTier.PRACTICE

    async def get_practice(self, db: AsyncSession, practice_id) -> Practice | None:
        result = await db.execute(select(Practice).where(Practice.id == practice_id))
        return result.scalar_one_or_none()

    async def update_practice(self, db: AsyncSession, practice: Practice, **fields) -> Practice:
        for key, value in fields.items():
            if value is not None:
                setattr(practice, key, value)
        await db.flush()
        return practice

    async def get_or_create_doctor_signup_code(self, db: AsyncSession, practice: Practice) -> str:
        code = (practice.settings or {}).get("doctor_signup_code")
        if code:
            return code
        return await self.regenerate_doctor_signup_code(db, practice)

    async def regenerate_doctor_signup_code(self, db: AsyncSession, practice: Practice) -> str:
        code = secrets.token_hex(6)
        practice.settings = {**(practice.settings or {}), "doctor_signup_code": code}
        await db.flush()
        return code

    async def resolve_doctor_signup_code(self, db: AsyncSession, code: str) -> Practice | None:
        # No index on a JSONB key — practice counts are small (this is a
        # per-practice admin tool, not a hot path), so a full scan filtering
        # in Python is fine rather than adding a dedicated column/index.
        result = await db.execute(select(Practice))
        for practice in result.scalars().all():
            if (practice.settings or {}).get("doctor_signup_code") == code:
                return practice
        return None

    async def get_or_create_staff_signup_code(self, db: AsyncSession, practice: Practice) -> str:
        code = (practice.settings or {}).get("staff_signup_code")
        if code:
            return code
        return await self.regenerate_staff_signup_code(db, practice)

    async def regenerate_staff_signup_code(self, db: AsyncSession, practice: Practice) -> str:
        code = secrets.token_hex(6)
        practice.settings = {**(practice.settings or {}), "staff_signup_code": code}
        await db.flush()
        return code

    async def resolve_staff_signup_code(self, db: AsyncSession, code: str) -> Practice | None:
        result = await db.execute(select(Practice))
        for practice in result.scalars().all():
            if (practice.settings or {}).get("staff_signup_code") == code:
                return practice
        return None

    # --- Green API (WhatsApp) self-connect — Phase 6 -------------------------
    # Consumption side (WhatsAppGreenAPI.from_practice_settings, green_api_poller)
    # already reads Practice.settings["green_api"] and was never touched here —
    # this is only the entry side, previously hand-seeded via scripts/seed_demo_practice.py.

    def get_green_api_config(self, practice: Practice) -> dict | None:
        ga = (practice.settings or {}).get("green_api")
        if not ga or not ga.get("instance_id") or not ga.get("api_token"):
            return None
        return ga

    async def set_green_api_config(self, db: AsyncSession, practice: Practice, instance_id: str, api_token: str) -> Practice:
        practice.settings = {**(practice.settings or {}), "green_api": {"instance_id": instance_id, "api_token": api_token}}
        await db.flush()
        return practice

    async def disconnect_green_api(self, db: AsyncSession, practice: Practice) -> Practice:
        settings = dict(practice.settings or {})
        settings.pop("green_api", None)
        practice.settings = settings
        await db.flush()
        return practice

    # --- Meta (Instagram/Facebook) self-connect — Phase 7 --------------------
    # Same Practice.settings["meta"] shape convention as green_api above.

    def get_meta_config(self, practice: Practice) -> dict | None:
        meta = (practice.settings or {}).get("meta")
        if not meta or not meta.get("page_id") or not meta.get("page_access_token"):
            return None
        return meta

    async def set_meta_config(self, db: AsyncSession, practice: Practice, page_id: str, page_name: str, page_access_token: str, ig_business_id: str | None) -> Practice:
        practice.settings = {
            **(practice.settings or {}),
            "meta": {
                "page_id": page_id,
                "page_name": page_name,
                "page_access_token": page_access_token,
                "ig_business_id": ig_business_id,
            },
        }
        await db.flush()
        return practice

    async def disconnect_meta(self, db: AsyncSession, practice: Practice) -> Practice:
        settings = dict(practice.settings or {})
        settings.pop("meta", None)
        practice.settings = settings
        await db.flush()
        return practice
