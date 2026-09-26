"""Add demo_form/book_consultation sources and SLA deadline to SalesLead

Revision ID: 060faedfe923
Revises: 2260ede5e824
Create Date: 2026-09-25 18:42:26.510989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '060faedfe923'
down_revision: Union[str, None] = '2260ede5e824'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sales_leads', sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('sales_leads', 'sla_deadline')