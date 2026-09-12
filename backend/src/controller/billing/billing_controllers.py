from __future__ import annotations
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.invoice import InvoiceStatus, PaymentMethod
from src.models.practice import Practice
from src.schemas.billing import (
    CreateInvoiceRequest,
    UpdateInvoiceRequest,
    InvoiceResponse,
    RecordPaymentRequest,
    PaymentResponse,
)
from src.config import get_settings
from src.server.exceptions import AppException
from src.services.billing.invoice_services import InvoiceService
from src.services.billing.invoice_receipt_service import InvoiceReceiptService
from src.services.billing.invoice_pdf_service import generate_invoice_pdf
from src.services.audit.audit_log_service import AuditLogService
from src.services.patients.patients_services import PatientsService
from src.services.payment.payment_service import PaymentService

logger = logging.getLogger("aesthetixai.billing")
settings = get_settings()


class BillingController:
    def __init__(self):
        self.invoices = InvoiceService()
        self.audit = AuditLogService()
        self.patients = PatientsService()
        self.payment = PaymentService()
        self.receipts = InvoiceReceiptService()

    async def create_invoice(self, db: AsyncSession, user: User, data: CreateInvoiceRequest) -> InvoiceResponse:
        invoice = await self.invoices.create_invoice(db, user.practice_id, data)
        await self.audit.log(
            db, user.practice_id, "user", "invoice.created", actor_user_id=user.id,
            resource_type="invoice", resource_id=invoice.id,
        )
        return InvoiceResponse.model_validate(invoice)

    async def list_invoices_for_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> list[InvoiceResponse]:
        invoices = await self.invoices.list_for_patient(db, user.practice_id, patient_id)
        return [InvoiceResponse.model_validate(i) for i in invoices]

    async def list_invoices_for_practice(self, db: AsyncSession, user: User, status: str | None) -> list[InvoiceResponse]:
        status_enum = InvoiceStatus(status) if status else None
        invoices = await self.invoices.list_for_practice(db, user.practice_id, status_enum)
        return [InvoiceResponse.model_validate(i) for i in invoices]

    async def get_invoice(self, db: AsyncSession, user: User, invoice_id: UUID) -> InvoiceResponse:
        invoice = await self.invoices.get_invoice(db, user.practice_id, invoice_id)
        return InvoiceResponse.model_validate(invoice)

    async def update_invoice(self, db: AsyncSession, user: User, invoice_id: UUID, data: UpdateInvoiceRequest) -> InvoiceResponse:
        was_paid_before = (await self.invoices.get_invoice(db, user.practice_id, invoice_id)).status == InvoiceStatus.PAID
        invoice = await self.invoices.update_invoice(db, user.practice_id, invoice_id, data)
        if invoice.status == InvoiceStatus.PAID and not was_paid_before:
            await self.audit.log(
                db, user.practice_id, "user", "invoice.marked_paid", actor_user_id=user.id,
                resource_type="invoice", resource_id=invoice.id,
            )
        return InvoiceResponse.model_validate(invoice)

    async def record_payment(
        self, db: AsyncSession, user: User, invoice_id: UUID, data: RecordPaymentRequest
    ) -> InvoiceResponse:
        try:
            method = PaymentMethod(data.method)
        except ValueError:
            raise AppException(f"Unknown payment method: {data.method}")

        invoice = await self.invoices.record_payment(
            db, user.practice_id, invoice_id, data.amount, method,
            recorded_by=user.id, notes=data.notes,
        )
        await self.audit.log(
            db, user.practice_id, "user", "invoice.payment_recorded", actor_user_id=user.id,
            resource_type="invoice", resource_id=invoice.id,
        )
        await self.receipts.send_receipt_best_effort(db, user.practice_id, invoice, data.amount)
        return InvoiceResponse.model_validate(invoice)

    async def list_payments(self, db: AsyncSession, user: User, invoice_id: UUID) -> list[PaymentResponse]:
        payments = await self.invoices.list_payments_for_invoice(db, user.practice_id, invoice_id)
        return [PaymentResponse.model_validate(p) for p in payments]

    async def create_checkout_session(self, db: AsyncSession, user: User, invoice_id: UUID) -> dict:
        if not self.payment.is_configured():
            raise AppException(
                "Online card payment isn't configured yet — Stripe hasn't been connected with real API keys.",
                status_code=503,
            )
        invoice = await self.invoices.get_invoice(db, user.practice_id, invoice_id)
        if invoice.balance_due <= 0:
            raise AppException("This invoice has no balance due.")

        patient = await self.patients.get_patient(db, user.practice_id, invoice.patient_id)
        session = await self.payment.create_invoice_checkout_session(
            invoice_id=str(invoice.id),
            amount=invoice.balance_due,
            currency=invoice.currency,
            description=f"Invoice #{str(invoice.id)[:8]}",
            success_url=f"{settings.frontend_url}/dashboard/invoices/{invoice.id}?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.frontend_url}/dashboard/invoices/{invoice.id}?checkout=cancelled",
            customer_email=patient.email,
        )
        return session

    async def confirm_checkout_session(self, db: AsyncSession, user: User, invoice_id: UUID, session_id: str) -> InvoiceResponse:
        # Robust confirmation path for local dev, where Stripe can't call
        # our webhook directly — the frontend calls this right after
        # Checkout redirects back, same shape as CheckoutService's own
        # get_session_status/_demo_checkout pattern for SaaS signups.
        session = await self.payment.get_checkout_session(session_id)
        if session["metadata"].get("invoice_id") != str(invoice_id):
            raise AppException("This checkout session does not belong to this invoice.")
        if not session["paid"]:
            invoice = await self.invoices.get_invoice(db, user.practice_id, invoice_id)
            return InvoiceResponse.model_validate(invoice)

        # Idempotent — a payment already recorded for this exact Stripe
        # session (e.g. the webhook beat us to it) is not recorded twice.
        existing = await self.invoices.list_payments_for_invoice(db, user.practice_id, invoice_id)
        if any(p.stripe_checkout_session_id == session_id for p in existing):
            invoice = await self.invoices.get_invoice(db, user.practice_id, invoice_id)
            return InvoiceResponse.model_validate(invoice)

        invoice = await self.invoices.record_payment(
            db, user.practice_id, invoice_id, session["amount_total"], PaymentMethod.STRIPE,
            stripe_checkout_session_id=session["id"], stripe_payment_intent_id=session["payment_intent"],
        )
        await self.audit.log(
            db, user.practice_id, "user", "invoice.payment_recorded", actor_user_id=user.id,
            resource_type="invoice", resource_id=invoice.id,
        )
        await self.receipts.send_receipt_best_effort(db, user.practice_id, invoice, session["amount_total"])
        return InvoiceResponse.model_validate(invoice)

    async def get_invoice_pdf(self, db: AsyncSession, user: User, invoice_id: UUID) -> bytes:
        invoice = await self.invoices.get_invoice(db, user.practice_id, invoice_id)
        patient = await self.patients.get_patient(db, user.practice_id, invoice.patient_id)
        practice = await db.get(Practice, user.practice_id)
        doctor = await self.receipts.resolve_doctor(db, invoice)
        return generate_invoice_pdf(invoice, patient, practice, doctor)
