from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.finance import CreateExpenseRequest, UpdateExpenseRequest, ExpenseResponse, FinanceOverviewResponse
from src.schemas.billing import FinanceSettingsResponse, UpdateFinanceSettingsRequest
from src.controller.finance.finance_controllers import FinanceController

router = APIRouter(prefix="/finance", tags=["Finance"])
controller = FinanceController()

# Recording/viewing individual expenses is Owner+Receptionist (per the
# user's own decision on this phase) — Doctor is excluded, same split as
# billing. The aggregate overview (revenue vs. expenses) is Owner-only —
# a step up from expense-line visibility, not just an alias for it.
_EXPENSE_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)
# Currency/exchange-rate config is a business decision, not an operational
# one — Owner-only, per the user's own explicit decision for this phase.
_OWNER_ONLY = (UserRole.OWNER,)


@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    data: CreateExpenseRequest,
    user: User = Depends(require_role(*_EXPENSE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_expense(db, user, data)


@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    user: User = Depends(require_role(*_EXPENSE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_expenses(db, user)


@router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: UUID,
    user: User = Depends(require_role(*_EXPENSE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_expense(db, user, expense_id)


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: UUID,
    data: UpdateExpenseRequest,
    user: User = Depends(require_role(*_EXPENSE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_expense(db, user, expense_id, data)


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: UUID,
    user: User = Depends(require_role(*_EXPENSE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    await controller.delete_expense(db, user, expense_id)


@router.get("/overview", response_model=FinanceOverviewResponse)
async def get_overview(
    user: User = Depends(require_role(*_EXPENSE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_overview(db, user)


@router.get("/settings", response_model=FinanceSettingsResponse)
async def get_settings(
    user: User = Depends(require_role(*_OWNER_ONLY)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_settings(db, user)


@router.patch("/settings", response_model=FinanceSettingsResponse)
async def update_settings(
    data: UpdateFinanceSettingsRequest,
    user: User = Depends(require_role(*_OWNER_ONLY)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_settings(db, user, data)
