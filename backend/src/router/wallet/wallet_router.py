from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.wallet import WalletBalanceResponse, WalletTransactionResponse, CreateTopupRequest
from src.controller.billing.wallet_controllers import WalletController

router = APIRouter(prefix="/wallet", tags=["Wallet"])
controller = WalletController()

# Practice credits are a business/financial decision — Owner-only, same as
# Finance Settings (currency/exchange rate).
_OWNER_ONLY = (UserRole.OWNER,)


@router.get("", response_model=WalletBalanceResponse)
async def get_balance(
    user: User = Depends(require_role(*_OWNER_ONLY)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_balance(db, user)


@router.get("/transactions", response_model=list[WalletTransactionResponse])
async def list_transactions(
    user: User = Depends(require_role(*_OWNER_ONLY)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_transactions(db, user)


@router.post("/checkout-session")
async def create_checkout_session(
    data: CreateTopupRequest,
    user: User = Depends(require_role(*_OWNER_ONLY)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_checkout_session(db, user, data)


@router.post("/checkout-session/{session_id}/confirm", response_model=WalletBalanceResponse)
async def confirm_checkout_session(
    session_id: str,
    user: User = Depends(require_role(*_OWNER_ONLY)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.confirm_checkout_session(db, user, session_id)
