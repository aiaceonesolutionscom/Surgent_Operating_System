"""Billing math: totals, payments and the balance that follows from them.

`total_amount`, `amount_paid` and `balance_due` are what a patient is asked
to pay, so an arithmetic slip here is a billing dispute. Two rules matter
most and are pinned below:

  * total = subtotal + tax - discount, and
  * amount_paid / balance_due are always derived from the real `Payment`
    rows, never stored, so they cannot drift out of sync with the ledger.

The terminal-status rule matters just as much: an invoice marked PAID,
CANCELLED or REFUNDED owes nothing even if its ledger is empty, which is how
invoices marked paid before the Payment ledger existed still read correctly.
"""

from decimal import Decimal

import pytest

from src.models.invoice import InvoiceStatus
from src.schemas.billing import CreateInvoiceLineItemRequest, CreateInvoiceRequest
from tests.conftest import make_patient, make_practice


def _line(description: str, quantity: int, unit_price: float):
    return CreateInvoiceLineItemRequest(
        description=description, quantity=quantity, unit_price=unit_price
    )


async def _seed_patient(db_session, name="Billing Clinic"):
    practice = make_practice(name=name)
    db_session.add(practice)
    await db_session.flush()
    patient = make_patient(practice)
    db_session.add(patient)
    await db_session.flush()
    return practice, patient


async def test_subtotal_and_total(db_session):
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)
    request = CreateInvoiceRequest(
        patient_id=patient.id,
        line_items=[
            _line("Rhinoplasty consult", 1, 150.00),
            _line("Derma filler", 2, 80.50),
        ],
        tax_amount=20.00,
        discount_amount=30.00,
    )

    invoice = await InvoiceService().create_invoice(db_session, practice.id, request)

    # 150.00 + (2 x 80.50) = 311.00
    assert float(invoice.subtotal_amount) == 311.00
    # 311.00 + 20.00 - 30.00 = 301.00
    assert float(invoice.total_amount) == 301.00


async def test_discount_larger_than_subtotal_does_not_go_negative(db_session):
    """A big discount must not create a negative amount owed to the clinic."""
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)
    request = CreateInvoiceRequest(
        patient_id=patient.id,
        line_items=[_line("Consult", 1, 100.00)],
        discount_amount=500.00,
    )

    invoice = await InvoiceService().create_invoice(db_session, practice.id, request)
    assert float(invoice.amount_paid) == 0.0
    assert invoice.balance_due == 0.0, "a fully discounted invoice owes nothing, not a negative"


async def test_partial_payment_reduces_balance(db_session):
    from src.models.invoice import PaymentMethod
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)
    service = InvoiceService()

    invoice = await service.create_invoice(
        db_session, practice.id,
        CreateInvoiceRequest(
            patient_id=patient.id,
            line_items=[_line("Breast augmentation", 1, 4000.00)],
        ),
    )
    assert float(invoice.total_amount) == 4000.00
    assert invoice.balance_due == 4000.00

    paid = await service.record_payment(
        db_session, practice.id, invoice.id, 1500.00, PaymentMethod.CASH
    )
    assert float(paid.amount_paid) == 1500.00
    assert paid.balance_due == 2500.00
    assert paid.status == InvoiceStatus.PARTIALLY_PAID

    fully = await service.record_payment(
        db_session, practice.id, invoice.id, 2500.00, PaymentMethod.CASH
    )
    assert float(fully.amount_paid) == 4000.00
    assert fully.balance_due == 0.0
    assert fully.status == InvoiceStatus.PAID


async def test_terminal_status_owes_nothing_with_empty_ledger(db_session):
    """An invoice marked paid before the Payment ledger existed still reads as settled."""
    from src.models.invoice import Invoice
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)
    invoice = Invoice(
        practice_id=practice.id,
        patient_id=patient.id,
        subtotal_amount=Decimal("500.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("500.00"),
        status=InvoiceStatus.PAID,
        currency="USD",
    )
    db_session.add(invoice)
    await db_session.flush()

    fetched = await InvoiceService().get_invoice(db_session, practice.id, invoice.id)
    assert float(fetched.amount_paid) == 0.0
    assert fetched.balance_due == 0.0, "PAID with no Payment rows must still owe nothing"


async def test_cancelled_invoice_owes_nothing(db_session):
    from src.models.invoice import Invoice
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)
    invoice = Invoice(
        practice_id=practice.id,
        patient_id=patient.id,
        subtotal_amount=Decimal("750.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("750.00"),
        status=InvoiceStatus.CANCELLED,
        currency="USD",
    )
    db_session.add(invoice)
    await db_session.flush()

    fetched = await InvoiceService().get_invoice(db_session, practice.id, invoice.id)
    assert fetched.balance_due == 0.0


async def test_invoice_creation_is_tenant_scoped(db_session):
    """A clinic must not invoice a patient belonging to another clinic."""
    from src.server.exceptions import NotFoundException
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)
    other = make_practice(name="Other Billing Clinic")
    db_session.add(other)
    await db_session.flush()

    with pytest.raises(NotFoundException):
        await InvoiceService().create_invoice(
            db_session, other.id,
            CreateInvoiceRequest(
                patient_id=patient.id, line_items=[_line("Consult", 1, 100.00)]
            ),
        )


async def test_invoice_needs_something_to_bill(db_session):
    from src.server.exceptions import AppException
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)

    with pytest.raises(AppException):
        await InvoiceService().create_invoice(
            db_session, practice.id, CreateInvoiceRequest(patient_id=patient.id)
        )


async def test_practice_invoice_totals_are_scoped(db_session):
    """Practice-level reporting must not mix another clinic's revenue."""
    from src.services.billing.invoice_services import InvoiceService

    practice, patient = await _seed_patient(db_session)
    other, other_patient = await _seed_patient(db_session, name="Other Billing Clinic")

    service = InvoiceService()
    mine = await service.create_invoice(
        db_session, practice.id,
        CreateInvoiceRequest(patient_id=patient.id, line_items=[_line("A", 1, 100.00)]),
    )
    theirs = await service.create_invoice(
        db_session, other.id,
        CreateInvoiceRequest(patient_id=other_patient.id, line_items=[_line("B", 1, 900.00)]),
    )

    mine_list = await service.list_for_practice(db_session, practice.id)
    assert [i.id for i in mine_list] == [mine.id]
    assert theirs.id not in {i.id for i in mine_list}
