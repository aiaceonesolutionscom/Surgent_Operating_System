"""add patient father name

Revision ID: a69e67899743
Revises: 1dcae23aa659
Create Date: 2026-09-20 15:49:17.956221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a69e67899743'
down_revision: Union[str, None] = '1dcae23aa659'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patients', sa.Column('father_name', sa.String(length=255), nullable=True))
    # NOTE: autogenerate also detected the same pre-existing drift excluded
    # in every prior migration this session (staff_conversations/
    # staff_messages FK naming, users.work_schedule NOT NULL) — deliberately
    # excluded here too, unrelated to this change.


def downgrade() -> None:
    op.drop_column('patients', 'father_name')
