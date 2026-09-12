from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.billing import CreateInvoiceRequest, UpdateInvoiceRequest, InvoiceResponse, RecordPaymentRequest, PaymentResponse
from src.controller.billing.billing_controllers import BillingController

router = APIRouter(prefix="/invoices", tags=["Billing"])
controller = BillingController()

# Billing is the clinic's financial workspace — Owner/Receptionist only,
# both view and manage. Doctor is deliberately excluded even from viewing
# (Patient Management redesign): a doctor's job is the clinical workspace,
# not invoice amounts/payment status — matches billing_router's own access
# matrix ("View Full Billing ❌" for Doctor). If a doctor ever needs a
# narrower operational signal (e.g. "has this treatment plan been billed"),
# that's a new, deliberately minimal endpoint — not broader access here.
_VIEW_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)
_MANAGE_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)


@router.post("", response_model=InvoiceResponse)
async def create_invoice(
    data: CreateInvoiceRequest,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_invoice(db, user, data)


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    patient_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    if patient_id is not None:
        return await controller.list_invoices_for_patient(db, user, patient_id)
    return await controller.list_invoices_for_practice(db, user, status)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_invoice(db, user, invoice_id)


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    data: UpdateInvoiceRequest,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_invoice(db, user, invoice_id, data)


@router.post("/{invoice_id}/payments", response_model=InvoiceResponse)
async def record_payment(
    invoice_id: UUID,
    data: RecordPaymentRequest,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.record_payment(db, user, invoice_id, data)


@router.get("/{invoice_id}/payments", response_model=list[PaymentResponse])
async def list_payments(
    invoice_id: UUID,
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_payments(db, user, invoice_id)


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: UUID,
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    pdf_bytes = await controller.get_invoice_pdf(db, user, invoice_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="invoice-{str(invoice_id)[:8]}.pdf"'},
    )


@router.post("/{invoice_id}/checkout-session")
async def create_checkout_session(
    invoice_id: UUID,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_checkout_session(db, user, invoice_id)


@router.post("/{invoice_id}/checkout-session/{session_id}/confirm", response_model=InvoiceResponse)
async def confirm_checkout_session(
    invoice_id: UUID,
    session_id: str,
    user: User = Depends(require_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.confirm_checkout_session(db, user, invoice_id, session_id)
