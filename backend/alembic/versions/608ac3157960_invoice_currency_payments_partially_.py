"""invoice currency, payments, partially_paid status

Revision ID: 608ac3157960
Revises: 740dd822657e
Create Date: 2026-09-08 16:09:38.754121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '608ac3157960'
down_revision: Union[str, None] = '740dd822657e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate doesn't detect new labels on an existing PG enum type —
    # same gotcha this project has hit before (see
    # a2d1b15d44a7_front_desk_status_and_waitlist.py). Member NAME, not
    # lowercase .value.
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'PARTIALLY_PAID'")

    op.create_table('payments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('method', sa.Enum('CASH', 'CARD_MANUAL', 'BANK_TRANSFER', 'STRIPE', 'OTHER', name='paymentmethod'), nullable=False),
    sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=True),
    sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
    sa.Column('recorded_by', sa.UUID(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
    sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_invoice_id'), 'payments', ['invoice_id'], unique=False)
    op.add_column('invoices', sa.Column('currency', sa.String(length=3), server_default='USD', nullable=False))
    op.add_column('invoices', sa.Column('exchange_rate_to_base', sa.Numeric(precision=12, scale=6), nullable=True))
    # Unrelated staff_conversations/staff_messages FK-naming drift that
    # autogenerate also picked up here was deliberately stripped out — see
    # 740dd822657e for the same call.


def downgrade() -> None:
    op.drop_column('invoices', 'exchange_rate_to_base')
    op.drop_column('invoices', 'currency')
    op.drop_index(op.f('ix_payments_invoice_id'), table_name='payments')
    op.drop_table('payments')
    # No ALTER TYPE ... DROP VALUE in Postgres — PARTIALLY_PAID stays; see
    # a2d1b15d44a7's own downgrade note for the same situation.
