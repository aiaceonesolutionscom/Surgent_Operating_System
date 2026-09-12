from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.user import User
from src.schemas.wallet import WalletBalanceResponse, WalletTransactionResponse, CreateTopupRequest
from src.server.exceptions import AppException
from src.services.billing.wallet_services import WalletService
from src.services.billing.invoice_services import InvoiceService
from src.services.payment.payment_service import PaymentService
from src.services.audit.audit_log_service import AuditLogService

settings = get_settings()


class WalletController:
    def __init__(self):
        self.wallet = WalletService()
        self.invoices = InvoiceService()
        self.payment = PaymentService()
        self.audit = AuditLogService()

    async def get_balance(self, db: AsyncSession, user: User) -> WalletBalanceResponse:
        base_currency, _ = await self.invoices.resolve_finance_settings(db, user.practice_id)
        balance = await self.wallet.get_balance(db, user.practice_id)
        return WalletBalanceResponse(balance=balance, currency=base_currency)

    async def list_transactions(self, db: AsyncSession, user: User) -> list[WalletTransactionResponse]:
        transactions = await self.wallet.list_transactions(db, user.practice_id)
        return [WalletTransactionResponse.model_validate(t) for t in transactions]

    async def create_checkout_session(self, db: AsyncSession, user: User, data: CreateTopupRequest) -> dict:
        if not self.payment.is_configured():
            raise AppException(
                "Online card payment isn't configured yet — Stripe hasn't been connected with real API keys.",
                status_code=503,
            )
        if data.amount <= 0:
            raise AppException("Top-up amount must be greater than zero.")
        base_currency, _ = await self.invoices.resolve_finance_settings(db, user.practice_id)
        session = await self.payment.create_wallet_topup_checkout_session(
            practice_id=str(user.practice_id),
            amount=data.amount,
            currency=base_currency,
            success_url=f"{settings.frontend_url}/dashboard/finance/overview?tab=wallet&checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.frontend_url}/dashboard/finance/overview?tab=wallet&checkout=cancelled",
            customer_email=user.email,
        )
        return session

    async def confirm_checkout_session(self, db: AsyncSession, user: User, session_id: str) -> WalletBalanceResponse:
        session = await self.payment.get_checkout_session(session_id)
        if session["metadata"].get("type") != "wallet_topup" or session["metadata"].get("practice_id") != str(user.practice_id):
            raise AppException("This checkout session does not belong to this practice's wallet.")
        if session["paid"]:
            await self.wallet.record_topup(
                db, user.practice_id, session["amount_total"], session["currency"] or "USD",
                session["id"], session["payment_intent"],
            )
            await self.audit.log(
                db, user.practice_id, "user", "wallet.topup", actor_user_id=user.id,
                resource_type="wallet_transaction",
            )
        return await self.get_balance(db, user)
