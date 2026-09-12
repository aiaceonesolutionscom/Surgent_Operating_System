"""add content_type and extra_data to staff_messages

Revision ID: 878b01dab33a
Revises: 9eddd545454a
Create Date: 2026-09-08 17:55:31.228931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '878b01dab33a'
down_revision: Union[str, None] = '9eddd545454a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('staff_messages', sa.Column('content_type', sa.Text(), server_default='text', nullable=False))
    op.add_column('staff_messages', sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('staff_messages', 'extra_data')
    op.drop_column('staff_messages', 'content_type')
