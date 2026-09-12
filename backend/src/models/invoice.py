import uuid
from datetime import datetime, date

from sqlalchemy import String, Text, Integer, Numeric, DateTime, Date, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

import enum


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD_MANUAL = "card_manual"  # POS terminal swipe recorded by staff, not through Stripe
    BANK_TRANSFER = "bank_transfer"
    STRIPE = "stripe"
    OTHER = "other"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    appointment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    # Set when the invoice was generated from a treatment plan's items —
    # nullable because an invoice can also be raised ad-hoc with no plan.
    treatment_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"), nullable=True)
    subtotal_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING)
    # The currency THIS invoice is billed in — not necessarily the
    # practice's base currency (see Practice.settings["finance"]). Every
    # amount column above (subtotal/tax/discount/total) is in this currency.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    # Snapshotted at creation time when `currency` differs from the
    # practice's base currency — "1 base-currency unit = this many
    # `currency` units" at the moment this invoice was raised. A later
    # change to the practice's exchange rate must never retroactively
    # change what an already-issued invoice is worth, same snapshot
    # reasoning as ConsentDocument's template versioning.
    exchange_rate_to_base: Mapped[float] = mapped_column(Numeric(12, 6), nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice", back_populates="invoices")
    patient = relationship("Patient", back_populates="invoices")
    treatment_plan = relationship("TreatmentPlan")
    line_items = relationship(
        "InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan",
        order_by="InvoiceLineItem.created_at",
    )
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan", order_by="Payment.paid_at")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    # Traceable back to the plan item it was billed from — nullable since
    # ad-hoc lines (a walk-in product sale, a one-off fee) have none.
    treatment_plan_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("treatment_plan_items.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    invoice = relationship("Invoice", back_populates="line_items")
    treatment_plan_item = relationship("TreatmentPlanItem")


class Payment(Base):
    """One real payment against an invoice — replaces the old binary
    paid/unpaid-only model. An invoice can have several of these (a deposit,
    then a balance payment) before it's fully PAID; recompute_status on the
    invoice sums them against total_amount to decide PENDING vs
    PARTIALLY_PAID vs PAID. Manual methods (cash/card_manual/bank_transfer)
    are staff-recorded on the spot; STRIPE rows are written by the webhook/
    confirmation flow (see services/billing/invoice_payment_services.py) —
    `recorded_by` is null for those since no staff member typed them in."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Always the invoice's own currency — a payment can't partially settle
    # an invoice in a different currency without its own conversion, which
    # this project doesn't attempt (see system_design.md's own scope notes).
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    stripe_checkout_session_id: Mapped[str] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invoice = relationship("Invoice", back_populates="payments")
    recorded_by_user = relationship("User")
