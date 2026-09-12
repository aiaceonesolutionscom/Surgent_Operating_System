"""wallet transactions

Revision ID: 9eddd545454a
Revises: 608ac3157960
Create Date: 2026-09-08 16:48:28.308212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9eddd545454a'
down_revision: Union[str, None] = '608ac3157960'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('wallet_transactions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('practice_id', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='USD', nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'COMPLETED', 'FAILED', name='wallettransactionstatus'), nullable=False),
    sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=True),
    sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wallet_transactions_practice_id'), 'wallet_transactions', ['practice_id'], unique=False)
    # Unrelated staff_conversations/staff_messages FK-naming drift that
    # autogenerate also picked up here was deliberately stripped out — see
    # 740dd822657e and 608ac3157960 for the same call.


def downgrade() -> None:
    op.drop_index(op.f('ix_wallet_transactions_practice_id'), table_name='wallet_transactions')
    op.drop_table('wallet_transactions')
