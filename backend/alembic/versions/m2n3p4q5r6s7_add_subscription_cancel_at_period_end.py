"""add subscription cancel_at_period_end

Mirror Stripe's subscription.cancel_at_period_end on the Subscription row so
the Super Admin panel can count "Cancelling" separately from "Active" instead
of showing a hardcoded number.

Revision ID: m2n3p4q5r6s7
Revises: llllllllll
Create Date: 2026-10-06 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'm2n3p4q5r6s7'
down_revision: Union[str, None] = 'llllllllll'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subscriptions',
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('subscriptions', 'cancel_at_period_end')
