from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.checkout import CheckoutSessionResponse, CheckoutSessionStatusResponse
from src.services.checkout.checkout_services import CheckoutService


class CheckoutController:
    def __init__(self):
        self.service = CheckoutService()

    async def create_checkout_session(self, db: AsyncSession, email: str | None, plan_tier: str) -> CheckoutSessionResponse:
        session = await self.service.create_checkout_session(db, email, plan_tier)
        return CheckoutSessionResponse(**session)

    async def get_session_status(self, db: AsyncSession, session_id: str) -> CheckoutSessionStatusResponse:
        status = await self.service.get_session_status(db, session_id)
        return CheckoutSessionStatusResponse(**status)
