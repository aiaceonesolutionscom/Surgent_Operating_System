"""Add trial_period_days to Plan model

Revision ID: a930d35d9464
Revises: a69e67899743
Create Date: 2026-09-25 18:27:48.821200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a930d35d9464'
down_revision: Union[str, None] = 'a69e67899743'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('plans', sa.Column('trial_period_days', sa.Integer(), nullable=False, server_default='14'))


def downgrade() -> None:
    op.drop_column('plans', 'trial_period_days')