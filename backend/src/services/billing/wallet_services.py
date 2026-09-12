from __future__ import annotations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.wallet_transaction import WalletTransaction, WalletTransactionStatus
from src.server.exceptions import AppException


class WalletService:
    """Practice-level prepaid credits — Owner tops up via Stripe
    (WalletTransaction rows, status COMPLETED once Stripe confirms).
    Tracking-only for now: nothing deducts from this balance yet (a
    deliberate scope decision — see WalletTransaction's own docstring).
    Balance is always derived from the ledger, never stored, matching
    Invoice.amount_paid's own reasoning."""

    async def get_balance(self, db: AsyncSession, practice_id: UUID) -> float:
        result = await db.execute(
            select(WalletTransaction).where(
                WalletTransaction.practice_id == practice_id,
                WalletTransaction.status == WalletTransactionStatus.COMPLETED,
            )
        )
        return sum(float(t.amount) for t in result.scalars().all())

    async def list_transactions(self, db: AsyncSession, practice_id: UUID) -> list[WalletTransaction]:
        result = await db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.practice_id == practice_id)
            .order_by(WalletTransaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def record_topup(
        self,
        db: AsyncSession,
        practice_id: UUID,
        amount: float,
        currency: str,
        stripe_checkout_session_id: str,
        stripe_payment_intent_id: str | None,
    ) -> WalletTransaction:
        # Idempotent on the Stripe session id — the webhook and the
        # frontend's confirm-after-redirect call can both race to record
        # the same top-up.
        existing = await db.execute(
            select(WalletTransaction).where(
                WalletTransaction.practice_id == practice_id,
                WalletTransaction.stripe_checkout_session_id == stripe_checkout_session_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return row

        if amount <= 0:
            raise AppException("Top-up amount must be greater than zero.")

        transaction = WalletTransaction(
            practice_id=practice_id,
            amount=amount,
            currency=currency,
            status=WalletTransactionStatus.COMPLETED,
            stripe_checkout_session_id=stripe_checkout_session_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            description="Stripe top-up",
        )
        db.add(transaction)
        await db.flush()
        return transaction
