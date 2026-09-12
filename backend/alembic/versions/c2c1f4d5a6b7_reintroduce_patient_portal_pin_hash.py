"""reintroduce patient portal pin hash (patient-chosen PIN)

Revision ID: c2c1f4d5a6b7
Revises: d3252a1c0aa9
Create Date: 2026-09-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2c1f4d5a6b7'
down_revision: Union[str, None] = 'd3252a1c0aa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # portal_pin_hash stores "pbkdf2_sha256$iterations$salt_b64$hash_b64" —
    # never the plaintext. The earlier scheme (migration 785aeb9feeef) stored
    # a clinic-*assigned* PIN (a shared secret staff had to generate and could
    # read); this time the patient chooses and sets their own PIN, so only the
    # salted hash ever touches the database. pin_set_at is when the patient
    # last set/changed their PIN (nullable = never set / portal still OTP-only).
    op.add_column('patients', sa.Column('portal_pin_hash', sa.String(length=255), nullable=True))
    op.add_column('patients', sa.Column('pin_set_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('patients', 'pin_set_at')
    op.drop_column('patients', 'portal_pin_hash')