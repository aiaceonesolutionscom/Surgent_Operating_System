"""patient additional phones

Revision ID: d3252a1c0aa9
Revises: 878b01dab33a
Create Date: 2026-09-08 18:55:53.570899

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd3252a1c0aa9'
down_revision: Union[str, None] = '878b01dab33a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'patients',
        sa.Column('additional_phones', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    )
    # Unrelated staff_conversations/staff_messages FK-naming drift that
    # autogenerate also picked up here was deliberately stripped out — see
    # 740dd822657e, 608ac3157960 and 9eddd545454a for the same call.


def downgrade() -> None:
    op.drop_column('patients', 'additional_phones')
