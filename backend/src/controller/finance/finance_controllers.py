from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.finance import CreateExpenseRequest, UpdateExpenseRequest, ExpenseResponse, FinanceOverviewResponse
from src.schemas.billing import FinanceSettingsResponse, UpdateFinanceSettingsRequest
from src.services.finance.finance_services import FinanceService
from src.services.billing.invoice_services import InvoiceService
from src.services.audit.audit_log_service import AuditLogService


class FinanceController:
    def __init__(self):
        self.finance = FinanceService()
        self.invoices = InvoiceService()
        self.audit = AuditLogService()

    async def create_expense(self, db: AsyncSession, user: User, data: CreateExpenseRequest) -> ExpenseResponse:
        expense = await self.finance.create_expense(db, user.practice_id, user.id, data)
        await self.audit.log(
            db, user.practice_id, "user", "expense.created", actor_user_id=user.id,
            resource_type="expense", resource_id=expense.id,
        )
        return ExpenseResponse.model_validate(expense)

    async def list_expenses(self, db: AsyncSession, user: User) -> list[ExpenseResponse]:
        expenses = await self.finance.list_expenses(db, user.practice_id)
        return [ExpenseResponse.model_validate(e) for e in expenses]

    async def get_expense(self, db: AsyncSession, user: User, expense_id: UUID) -> ExpenseResponse:
        expense = await self.finance.get_expense(db, user.practice_id, expense_id)
        return ExpenseResponse.model_validate(expense)

    async def update_expense(self, db: AsyncSession, user: User, expense_id: UUID, data: UpdateExpenseRequest) -> ExpenseResponse:
        expense = await self.finance.update_expense(db, user.practice_id, expense_id, data)
        await self.audit.log(
            db, user.practice_id, "user", "expense.updated", actor_user_id=user.id,
            resource_type="expense", resource_id=expense.id,
        )
        return ExpenseResponse.model_validate(expense)

    async def delete_expense(self, db: AsyncSession, user: User, expense_id: UUID) -> None:
        await self.finance.delete_expense(db, user.practice_id, expense_id)
        await self.audit.log(
            db, user.practice_id, "user", "expense.deleted", actor_user_id=user.id,
            resource_type="expense", resource_id=expense_id,
        )

    async def get_overview(self, db: AsyncSession, user: User) -> FinanceOverviewResponse:
        return await self.finance.get_overview(db, user.practice_id)

    async def get_settings(self, db: AsyncSession, user: User) -> FinanceSettingsResponse:
        settings = await self.invoices.get_finance_settings(db, user.practice_id)
        return FinanceSettingsResponse(**settings)

    async def update_settings(self, db: AsyncSession, user: User, data: UpdateFinanceSettingsRequest) -> FinanceSettingsResponse:
        settings = await self.invoices.update_finance_settings(
            db, user.practice_id, data.base_currency, data.usd_to_pkr_rate
        )
        await self.audit.log(
            db, user.practice_id, "user", "finance_settings.updated", actor_user_id=user.id,
            resource_type="practice", resource_id=user.practice_id,
        )
        return FinanceSettingsResponse(**settings)
