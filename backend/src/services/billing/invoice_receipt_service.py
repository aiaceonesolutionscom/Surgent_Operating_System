from __future__ import annotations
import base64
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.invoice import Invoice
from src.models.practice import Practice
from src.models.treatment_plan import TreatmentPlan
from src.services.billing.invoice_pdf_service import generate_invoice_pdf
from src.services.patients.patients_services import PatientsService
from src.services.messaging.messaging_service import MessagingService
from src.services.email.resend_service import ResendService
from src.services.storage.storage_service import StorageService

logger = logging.getLogger("aesthetixai.billing")


class InvoiceReceiptService:
    """Real, patient-facing receipt delivery — generates the actual PDF
    invoice/receipt (see invoice_pdf_service) and sends it over WhatsApp
    (as a document) and email (as an attachment), on top of the existing
    plain-text confirmation. Shared by every path that can result in a
    payment being recorded: the manual "record payment" endpoint, the
    Stripe checkout confirm endpoint, and the Stripe webhook — so a real
    receipt goes out the moment a payment is genuinely accepted, no matter
    which of those three fired.

    Deliberately fire-and-forget end to end: a missing phone/email, an
    unconnected WhatsApp instance, or a provider hiccup must never undo or
    block the payment that was already committed."""

    def __init__(self):
        self.patients = PatientsService()
        self.messaging = MessagingService()
        self.email = ResendService()
        self.storage = StorageService()

    async def resolve_doctor(self, db: AsyncSession, invoice: Invoice):
        if not invoice.treatment_plan_id:
            return None
        result = await db.execute(
            select(TreatmentPlan)
            .options(selectinload(TreatmentPlan.doctor))
            .where(TreatmentPlan.id == invoice.treatment_plan_id)
        )
        plan = result.scalar_one_or_none()
        return plan.doctor if plan else None

    async def send_receipt_best_effort(self, db: AsyncSession, practice_id: UUID, invoice: Invoice, amount: float) -> None:
        try:
            patient = await self.patients.get_patient(db, practice_id, invoice.patient_id)
            practice_result = await db.execute(select(Practice).where(Practice.id == practice_id))
            practice = practice_result.scalar_one_or_none()
            if practice is None:
                return
            doctor = await self.resolve_doctor(db, invoice)
            pdf_bytes = generate_invoice_pdf(invoice, patient, practice, doctor)
        except Exception as exc:
            logger.info("Could not build receipt PDF for invoice %s: %s", invoice.id, exc)
            return

        caption = (
            f"Receipt — Invoice #{str(invoice.id)[:8]}\n"
            f"Amount paid: {invoice.currency} {amount:,.2f}\n"
            f"Balance due: {invoice.currency} {invoice.balance_due:,.2f}\n"
            f"Thank you!"
        )
        filename = f"invoice-{str(invoice.id)[:8]}.pdf"

        # Plain-text confirmation always attempted first (works over SMS
        # too, not just WhatsApp) — the PDF document is a bonus on top.
        try:
            await self.messaging.send_and_log(db, practice_id, patient, "billing_receipt", caption)
        except Exception as exc:
            logger.info("Receipt text not sent for invoice %s: %s", invoice.id, exc)

        try:
            upload = await self.storage.upload(pdf_bytes, f"invoice-{invoice.id}", folder="invoices", resource_type="raw")
            await self.messaging.send_document_and_log(
                db, practice_id, patient, "billing_receipt", upload["url"], filename, caption
            )
        except Exception as exc:
            logger.info("Receipt PDF not sent via WhatsApp for invoice %s: %s", invoice.id, exc)

        if patient.email:
            html = (
                f"<p>Receipt — Invoice #{str(invoice.id)[:8]}</p>"
                f"<p>Amount paid: {invoice.currency} {amount:,.2f}<br/>"
                f"Balance due: {invoice.currency} {invoice.balance_due:,.2f}</p>"
                f"<p>Your invoice is attached.</p><p>Thank you!</p>"
            )
            try:
                await self.email.send(
                    patient.email, "Your payment receipt", html,
                    attachments=[{"filename": filename, "content_base64": base64.b64encode(pdf_bytes).decode("ascii")}],
                )
            except Exception as exc:
                logger.info("Receipt email not sent for invoice %s: %s", invoice.id, exc)
