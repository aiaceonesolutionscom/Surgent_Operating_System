from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.checkout import CheckoutSessionRequest, CheckoutSessionResponse, CheckoutSessionStatusResponse
from src.controller.checkout.checkout_controllers import CheckoutController

# Deliberately no auth dependency — a Pricing-page visitor starting checkout
# has no Clerk session yet (that's the whole point of PendingSignup).
router = APIRouter(prefix="/checkout", tags=["Checkout"])
controller = CheckoutController()


@router.post("/create-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_checkout_session(db, body.email, body.plan_tier)


@router.get("/session/{session_id}", response_model=CheckoutSessionStatusResponse)
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    # Also no auth — /pricing/success polls this before the customer has a
    # Clerk account yet.
    return await controller.get_session_status(db, session_id)
