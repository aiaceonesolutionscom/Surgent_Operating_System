from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date


class CreateInvoiceLineItemRequest(BaseModel):
    treatment_plan_item_id: UUID | None = None
    description: str
    quantity: int = 1
    unit_price: float


class CreateInvoiceRequest(BaseModel):
    patient_id: UUID
    appointment_id: UUID | None = None
    # When set and no explicit `line_items` are given, the invoice's lines
    # are auto-built from this plan's items (using each item's actual price
    # if it's been performed, else its estimated price, else the procedure's
    # catalog price). Passing `line_items` always overrides this — that's
    # the "ad-hoc" path.
    treatment_plan_id: UUID | None = None
    line_items: list[CreateInvoiceLineItemRequest] = []
    tax_amount: float = 0
    discount_amount: float = 0
    due_date: date | None = None
    # Defaults to the practice's base currency when omitted.
    currency: str | None = None


class UpdateInvoiceRequest(BaseModel):
    status: str | None = None
    due_date: date | None = None
    tax_amount: float | None = None
    discount_amount: float | None = None


class InvoiceLineItemResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    treatment_plan_item_id: UUID | None
    description: str
    quantity: int
    unit_price: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecordPaymentRequest(BaseModel):
    amount: float
    method: str
    notes: str | None = None


class PaymentResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    amount: float
    currency: str
    method: str
    recorded_by: UUID | None
    notes: str | None
    paid_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: UUID
    practice_id: UUID
    patient_id: UUID
    appointment_id: UUID | None
    treatment_plan_id: UUID | None
    subtotal_amount: float
    tax_amount: float
    discount_amount: float
    total_amount: float
    status: str
    currency: str
    exchange_rate_to_base: float | None
    due_date: date | None
    paid_at: datetime | None
    line_items: list[InvoiceLineItemResponse]
    payments: list[PaymentResponse]
    # Transient, query-time-computed — see InvoiceService._attach_computed.
    amount_paid: float = 0
    balance_due: float = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FinanceSettingsResponse(BaseModel):
    base_currency: str
    usd_to_pkr_rate: float | None


class UpdateFinanceSettingsRequest(BaseModel):
    base_currency: str | None = None
    usd_to_pkr_rate: float | None = None
