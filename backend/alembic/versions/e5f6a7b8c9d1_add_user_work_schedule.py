"""add user work schedule

Adds a reusable weekly schedule (JSONB) to users so receptionists (who have
no roster row like Doctor) can record which weekdays they work and at what
times. Doctors keep using Doctor.working_hours (same {"mon":[{"start","end"}]}
shape); this column mirrors it for User-backed roles.

Revision ID: e5f6a7b8c9d1
Revises: f1e2d3c4b5a7
Create Date: 2026-09-10 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d1"
down_revision: Union[str, None] = "f1e2d3c4b5a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("work_schedule", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "work_schedule")