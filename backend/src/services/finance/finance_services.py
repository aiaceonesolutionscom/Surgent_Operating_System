from __future__ import annotations
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.expense import Expense
from src.models.invoice import Invoice, InvoiceStatus, Payment
from src.models.treatment_plan import TreatmentPlanItem
from src.models.refund_request import RefundRequest, RefundRequestStatus
from src.schemas.finance import CreateExpenseRequest, UpdateExpenseRequest, FinanceOverviewResponse
from src.server.exceptions import NotFoundException
from src.services.clinical.session_visit_services import session_progress


class FinanceService:
    """Expense tracking + a real revenue-vs-expense overview. Every method
    is practice-scoped. Overview counts revenue as PAID invoices only —
    pending/overdue invoices aren't money in hand yet."""

    async def create_expense(self, db: AsyncSession, practice_id: UUID, user_id: UUID, data: CreateExpenseRequest) -> Expense:
        import datetime as dt
        expense = Expense(
            practice_id=practice_id,
            expense_type=data.expense_type,
            status=data.status,
            category=data.category,
            amount=data.amount,
            vendor=data.vendor,
            payee_name=data.payee_name,
            expense_date=data.expense_date,
            notes=data.notes,
            paid_at=(dt.datetime.now(dt.timezone.utc) if data.status == "paid" else None),
            recorded_by=user_id,
        )
        db.add(expense)
        await db.flush()
        await db.refresh(expense)
        return expense

    async def list_expenses(self, db: AsyncSession, practice_id: UUID) -> list[Expense]:
        query = select(Expense).where(Expense.practice_id == practice_id).order_by(Expense.expense_date.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_expense(self, db: AsyncSession, practice_id: UUID, expense_id: UUID) -> Expense:
        query = select(Expense).where(Expense.id == expense_id, Expense.practice_id == practice_id)
        result = await db.execute(query)
        expense = result.scalar_one_or_none()
        if expense is None:
            raise NotFoundException("Expense not found")
        return expense

    async def update_expense(self, db: AsyncSession, practice_id: UUID, expense_id: UUID, data: UpdateExpenseRequest) -> Expense:
        expense = await self.get_expense(db, practice_id, expense_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(expense, field, value)
        await db.flush()
        await db.refresh(expense)
        return expense

    async def delete_expense(self, db: AsyncSession, practice_id: UUID, expense_id: UUID) -> None:
        expense = await self.get_expense(db, practice_id, expense_id)
        await db.delete(expense)
        await db.flush()

    async def get_overview(self, db: AsyncSession, practice_id: UUID) -> FinanceOverviewResponse:
        total_revenue, invoice_count = (
            await db.execute(
                select(func.coalesce(func.sum(Invoice.total_amount), 0), func.count())
                .where(Invoice.practice_id == practice_id, Invoice.status == InvoiceStatus.PAID)
            )
        ).one()
        total_expenses, expense_count = (
            await db.execute(
                select(func.coalesce(func.sum(Expense.amount), 0), func.count())
                # Demo expenses are placeholder rows, not spend: counting them
                # would show a new clinic a fabricated burn rate.
                .where(Expense.practice_id == practice_id, Expense.is_sample.is_(False))
            )
        ).one()

        total_revenue = float(total_revenue)
        total_expenses = float(total_expenses)

        # Refunds are recorded as negative Payment rows (see
        # InvoiceService.record_refund) — sum of their absolute value is
        # real cash paid back out, which total_revenue above never reflects
        # on its own (it only ever reads Invoice.total_amount, unaffected by
        # a later refund).
        total_refunds = float(
            (
                await db.execute(
                    select(func.coalesce(-func.sum(Payment.amount), 0)).where(
                        Payment.practice_id == practice_id, Payment.amount < 0
                    )
                )
            ).scalar_one()
        )

        pending_refund_requests_count, pending_refund_liability = (
            await db.execute(
                select(
                    func.count(),
                    func.coalesce(
                        func.sum(func.coalesce(RefundRequest.approved_amount, RefundRequest.requested_amount, 0)), 0
                    ),
                ).where(
                    RefundRequest.practice_id == practice_id,
                    RefundRequest.status.in_([RefundRequestStatus.REQUESTED, RefundRequestStatus.APPROVED]),
                )
            )
        ).one()

        deferred_revenue = await self._compute_deferred_revenue(db, practice_id)

        return FinanceOverviewResponse(
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net=total_revenue - total_expenses,
            invoice_count=invoice_count,
            expense_count=expense_count,
            total_refunds=total_refunds,
            net_revenue_after_refunds=total_revenue - total_refunds,
            pending_refund_requests_count=pending_refund_requests_count,
            pending_refund_liability=float(pending_refund_liability),
            deferred_revenue=deferred_revenue,
        )

    async def _compute_deferred_revenue(self, db: AsyncSession, practice_id: UUID) -> float:
        """Money already collected for a multi-session treatment that isn't
        fully delivered yet — the accrual-accounting figure this project's
        previously pure-cash-basis Finance view never had. An estimate, not
        a ledger entry: prorates each invoice line's own paid share by that
        item's undelivered session fraction (see
        SessionVisitService/session_progress), computed in Python rather
        than one large SQL join for clarity — bounded by a practice's own
        invoice volume, which is small at this scale."""
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.line_items), selectinload(Invoice.payments))
            .where(
                Invoice.practice_id == practice_id,
                Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]),
                Invoice.treatment_plan_id.isnot(None),
            )
        )
        invoices = list(result.scalars().all())
        if not invoices:
            return 0.0

        item_ids = {
            li.treatment_plan_item_id
            for invoice in invoices
            for li in invoice.line_items
            if li.treatment_plan_item_id is not None
        }
        if not item_ids:
            return 0.0

        items_result = await db.execute(
            select(TreatmentPlanItem)
            .options(selectinload(TreatmentPlanItem.session_visits))
            .where(TreatmentPlanItem.id.in_(item_ids))
        )
        items_by_id = {item.id: item for item in items_result.scalars().all()}

        deferred = 0.0
        for invoice in invoices:
            paid = sum(float(p.amount) for p in invoice.payments)
            total = float(invoice.total_amount)
            if paid <= 0 or total <= 0:
                continue
            paid_fraction = min(paid / total, 1.0)
            for li in invoice.line_items:
                item = items_by_id.get(li.treatment_plan_item_id)
                if item is None:
                    continue
                progress = session_progress(item)
                if progress["sessions_total"] <= 1 or progress["sessions_remaining"] <= 0:
                    continue
                undelivered_fraction = progress["sessions_remaining"] / progress["sessions_total"]
                line_total = float(li.unit_price) * li.quantity
                deferred += line_total * paid_fraction * undelivered_fraction

        return round(deferred, 2)
