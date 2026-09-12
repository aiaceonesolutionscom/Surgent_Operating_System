from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus, Payment, PaymentMethod
from src.models.patient import Patient
from src.models.practice import Practice
from src.models.treatment_plan import TreatmentPlan, TreatmentPlanItem, TreatmentPlanStatus
from src.schemas.billing import CreateInvoiceRequest, UpdateInvoiceRequest
from src.server.exceptions import NotFoundException, AppException
from src.services.notifications.notification_service import NotificationService

# Only these two currencies are supported this month — a manually-set,
# Owner-editable rate in Practice.settings["finance"], no external FX API
# (explicit user decision, see the Finance plan). Anything else falls back
# to the practice's own base currency with no conversion attempted.
_SUPPORTED_CURRENCIES = ("USD", "PKR")


class InvoiceService:
    """Patient billing — an invoice is either raised ad-hoc (caller supplies
    line items directly) or generated from a treatment plan's items (caller
    supplies `treatment_plan_id` with no explicit items). Every method is
    practice-scoped."""

    def __init__(self):
        self.notifications = NotificationService()

    async def _resolve_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> Patient:
        result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id))
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")
        return patient

    async def resolve_finance_settings(self, db: AsyncSession, practice_id: UUID) -> tuple[str, float | None]:
        result = await db.execute(select(Practice).where(Practice.id == practice_id))
        practice = result.scalar_one_or_none()
        finance = (((practice.settings or {}) if practice else {}) or {}).get("finance") or {}
        base_currency = finance.get("base_currency") or "USD"
        rate = finance.get("usd_to_pkr_rate")
        return base_currency, (float(rate) if rate is not None else None)

    async def _resolve_invoice_currency(
        self, db: AsyncSession, practice_id: UUID, requested_currency: str | None
    ) -> tuple[str, float | None]:
        base_currency, usd_to_pkr_rate = await self.resolve_finance_settings(db, practice_id)
        currency = (requested_currency or base_currency).upper()
        if currency == base_currency:
            return currency, None
        if currency not in _SUPPORTED_CURRENCIES or base_currency not in _SUPPORTED_CURRENCIES:
            return currency, None
        if usd_to_pkr_rate is None:
            raise AppException(
                f"No {base_currency}-to-{currency} exchange rate is set for this practice yet -- "
                "an Owner needs to set it in Finance Settings before billing in another currency."
            )
        # Snapshotted onto the invoice at creation time — a later change to
        # the practice's rate must never retroactively reprice an
        # already-issued invoice (same reasoning as consent template
        # versioning).
        if currency == "PKR" and base_currency == "USD":
            return currency, usd_to_pkr_rate
        if currency == "USD" and base_currency == "PKR":
            return currency, 1 / usd_to_pkr_rate
        return currency, None

    async def get_finance_settings(self, db: AsyncSession, practice_id: UUID) -> dict:
        base_currency, usd_to_pkr_rate = await self.resolve_finance_settings(db, practice_id)
        return {"base_currency": base_currency, "usd_to_pkr_rate": usd_to_pkr_rate}

    async def update_finance_settings(
        self, db: AsyncSession, practice_id: UUID, base_currency: str | None, usd_to_pkr_rate: float | None
    ) -> dict:
        result = await db.execute(select(Practice).where(Practice.id == practice_id))
        practice = result.scalar_one_or_none()
        if practice is None:
            raise NotFoundException("Practice not found")
        finance = dict((practice.settings or {}).get("finance") or {})
        if base_currency is not None:
            finance["base_currency"] = base_currency.upper()
        if usd_to_pkr_rate is not None:
            if usd_to_pkr_rate <= 0:
                raise AppException("Exchange rate must be greater than zero.")
            finance["usd_to_pkr_rate"] = usd_to_pkr_rate
        # settings is a JSONB dict column — reassign (not mutate in place) so
        # SQLAlchemy actually detects the change, same pattern already used
        # for Practice.settings["doctor_signup_code"].
        practice.settings = {**(practice.settings or {}), "finance": finance}
        await db.flush()
        return await self.get_finance_settings(db, practice_id)

    async def _lines_from_treatment_plan(
        self, db: AsyncSession, practice_id: UUID, treatment_plan_id: UUID
    ) -> list[InvoiceLineItem]:
        query = (
            select(TreatmentPlan)
            .options(selectinload(TreatmentPlan.items).selectinload(TreatmentPlanItem.procedure))
            .where(TreatmentPlan.id == treatment_plan_id, TreatmentPlan.practice_id == practice_id)
        )
        result = await db.execute(query)
        plan = result.scalar_one_or_none()
        if plan is None:
            raise NotFoundException("Treatment plan not found")
        if plan.status not in (TreatmentPlanStatus.ACCEPTED, TreatmentPlanStatus.COMPLETED):
            raise AppException(
                "This treatment plan hasn't been accepted by the doctor yet — "
                "it needs to be Accepted or Completed before it can be invoiced."
            )
        if not plan.items:
            raise AppException("This treatment plan has no items to invoice.")

        lines = []
        for item in plan.items:
            price = item.actual_price if item.actual_price is not None else item.estimated_price
            if price is None:
                price = item.procedure.base_price
            if price is None:
                raise AppException(f"'{item.procedure.name}' has no price set — add one before invoicing.")
            lines.append(
                InvoiceLineItem(
                    treatment_plan_item_id=item.id,
                    description=item.procedure.name,
                    quantity=1,
                    unit_price=price,
                )
            )
        return lines

    async def create_invoice(self, db: AsyncSession, practice_id: UUID, data: CreateInvoiceRequest) -> Invoice:
        await self._resolve_patient(db, practice_id, data.patient_id)

        if data.line_items:
            lines = [
                InvoiceLineItem(
                    treatment_plan_item_id=li.treatment_plan_item_id,
                    description=li.description,
                    quantity=li.quantity,
                    unit_price=li.unit_price,
                )
                for li in data.line_items
            ]
        elif data.treatment_plan_id:
            lines = await self._lines_from_treatment_plan(db, practice_id, data.treatment_plan_id)
        else:
            raise AppException("An invoice needs at least one line item or a treatment plan to bill from.")

        currency, exchange_rate = await self._resolve_invoice_currency(db, practice_id, data.currency)

        subtotal = sum(line.quantity * float(line.unit_price) for line in lines)
        total = subtotal + data.tax_amount - data.discount_amount

        invoice = Invoice(
            practice_id=practice_id,
            patient_id=data.patient_id,
            appointment_id=data.appointment_id,
            treatment_plan_id=data.treatment_plan_id,
            subtotal_amount=subtotal,
            tax_amount=data.tax_amount,
            discount_amount=data.discount_amount,
            total_amount=total,
            currency=currency,
            exchange_rate_to_base=exchange_rate,
            due_date=data.due_date,
            line_items=lines,
        )
        db.add(invoice)
        await db.flush()
        return await self.get_invoice(db, practice_id, invoice.id)

    def _attach_computed(self, invoices: list[Invoice]) -> None:
        # Transient attributes, not mapped columns — same pattern as
        # Patient.has_upcoming_appointment. amount_paid/balance_due are
        # always derived from the real Payment rows, never stored, so they
        # can never drift out of sync with the ledger.
        for invoice in invoices:
            paid = sum(float(p.amount) for p in invoice.payments)
            invoice.amount_paid = paid
            # PAID/CANCELLED/REFUNDED are terminal "nothing further owed"
            # states regardless of ledger completeness — this also covers
            # invoices marked paid the old way (a plain status PATCH, before
            # the Payment ledger existed) that have zero real Payment rows;
            # without this they'd show a nonzero balance despite being paid.
            if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED):
                invoice.balance_due = 0
            else:
                invoice.balance_due = max(float(invoice.total_amount) - paid, 0)

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[Invoice]:
        query = (
            select(Invoice)
            .options(selectinload(Invoice.line_items), selectinload(Invoice.payments))
            .where(Invoice.practice_id == practice_id, Invoice.patient_id == patient_id)
            .order_by(Invoice.created_at.desc())
            # Without this, an Invoice already in the session's identity map
            # (e.g. just created earlier this request) keeps its stale,
            # already-loaded `payments` collection instead of picking up
            # rows written since — amount_paid/balance_due would silently
            # read as 0 right after a payment was just recorded.
            .execution_options(populate_existing=True)
        )
        result = await db.execute(query)
        invoices = list(result.scalars().all())
        self._attach_computed(invoices)
        return invoices

    async def list_for_practice(
        self, db: AsyncSession, practice_id: UUID, status: InvoiceStatus | None = None
    ) -> list[Invoice]:
        query = (
            select(Invoice)
            .options(selectinload(Invoice.line_items), selectinload(Invoice.payments))
            .where(Invoice.practice_id == practice_id)
            .execution_options(populate_existing=True)
        )
        if status is not None:
            query = query.where(Invoice.status == status)
        query = query.order_by(Invoice.created_at.desc())
        result = await db.execute(query)
        invoices = list(result.scalars().all())
        self._attach_computed(invoices)
        return invoices

    async def get_invoice(self, db: AsyncSession, practice_id: UUID, invoice_id: UUID) -> Invoice:
        query = (
            select(Invoice)
            .options(selectinload(Invoice.line_items), selectinload(Invoice.payments))
            .where(Invoice.id == invoice_id, Invoice.practice_id == practice_id)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(query)
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise NotFoundException("Invoice not found")
        self._attach_computed([invoice])
        return invoice

    async def update_invoice(
        self, db: AsyncSession, practice_id: UUID, invoice_id: UUID, data: UpdateInvoiceRequest
    ) -> Invoice:
        invoice = await self.get_invoice(db, practice_id, invoice_id)
        fields = data.model_dump(exclude_unset=True)

        if "status" in fields:
            new_status = InvoiceStatus(fields["status"])
            fields["status"] = new_status
            # First transition into PAID stamps paid_at — flipping status
            # back and forth doesn't keep re-stamping it.
            if new_status == InvoiceStatus.PAID and invoice.paid_at is None:
                fields["paid_at"] = datetime.now(timezone.utc)
                await self.notifications.notify(
                    db, practice_id, "payment_received",
                    title=f"Payment received — ${float(invoice.total_amount):,.2f}",
                    body=f"Invoice #{str(invoice.id)[:8]} was marked paid.",
                    resource_type="invoice", resource_id=invoice.id,
                )

        for field, value in fields.items():
            setattr(invoice, field, value)

        # tax/discount edits change what's owed — total_amount is a snapshot,
        # not a computed column, so it needs recomputing here.
        if "tax_amount" in fields or "discount_amount" in fields:
            invoice.total_amount = float(invoice.subtotal_amount) + float(invoice.tax_amount) - float(invoice.discount_amount)

        await db.flush()
        return await self.get_invoice(db, practice_id, invoice_id)

    async def record_payment(
        self,
        db: AsyncSession,
        practice_id: UUID,
        invoice_id: UUID,
        amount: float,
        method: PaymentMethod,
        recorded_by: UUID | None = None,
        notes: str | None = None,
        stripe_checkout_session_id: str | None = None,
        stripe_payment_intent_id: str | None = None,
    ) -> Invoice:
        invoice = await self.get_invoice(db, practice_id, invoice_id)
        if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED):
            raise AppException(f"Can't record a payment against a {invoice.status.value} invoice.")
        if amount <= 0:
            raise AppException("Payment amount must be greater than zero.")

        payment = Payment(
            practice_id=practice_id,
            invoice_id=invoice.id,
            amount=amount,
            currency=invoice.currency,
            method=method,
            recorded_by=recorded_by,
            notes=notes,
            stripe_checkout_session_id=stripe_checkout_session_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
        )
        db.add(payment)
        await db.flush()

        total_paid = invoice.amount_paid + amount
        was_paid_before = invoice.status == InvoiceStatus.PAID
        if total_paid >= float(invoice.total_amount):
            invoice.status = InvoiceStatus.PAID
            if invoice.paid_at is None:
                invoice.paid_at = datetime.now(timezone.utc)
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        await db.flush()

        if invoice.status == InvoiceStatus.PAID and not was_paid_before:
            await self.notifications.notify(
                db, practice_id, "payment_received",
                title=f"Payment received — {invoice.currency} {float(invoice.total_amount):,.2f}",
                body=f"Invoice #{str(invoice.id)[:8]} is now fully paid.",
                resource_type="invoice", resource_id=invoice.id,
            )

        return await self.get_invoice(db, practice_id, invoice_id)

    async def list_payments_for_invoice(self, db: AsyncSession, practice_id: UUID, invoice_id: UUID) -> list[Payment]:
        invoice = await self.get_invoice(db, practice_id, invoice_id)
        return list(invoice.payments)
