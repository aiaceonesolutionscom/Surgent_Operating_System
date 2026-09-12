"""add patient portal one-time PIN

Adds the staff-visible, single-use clinic login PIN columns to patients:
phone + one-time PIN is now the primary patient-portal login (no OTP needed),
with the patient setting their own permanent PIN after their first login.

Revision ID: f1e2d3c4b5a7
Revises: f1e2d3c4b5a6
Create Date: 2026-09-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a7"
down_revision: Union[str, None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("portal_temp_pin", sa.String(10), nullable=True))
    op.add_column("patients", sa.Column("portal_temp_pin_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "portal_temp_pin_expires_at")
    op.drop_column("patients", "portal_temp_pin")