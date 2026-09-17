"""surgery status machine and lifecycle timestamps

Revision ID: a7b8c9d0e1f2
Revises: b1a2c3d4e5f6
Create Date: 2026-09-14 12:00:00.000000

Surgery moves from a 3-state marker (planned/completed/cancelled) to a real
end-to-end status machine: scheduled -> confirmed -> in_progress -> completed,
with cancelled reachable from any pre-procedure state. The DB enum stores the
Python member NAME (PLANNED/COMPLETED/CANCELLED today), so the old 'PLANNED'
label is renamed to 'SCHEDULED' and the two middle states are added. Lifecycle
timestamps + a cancel reason give the Owner overview and front desk the
"kis ne kab kya kiya" timeline.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block before
    # Postgres 12 (this codebase runs PG 16/18), and RENAME VALUE renames the
    # existing 'PLANNED' label in place so already-saved rows become SCHEDULED.
    op.execute("ALTER TYPE surgerystatus ADD VALUE IF NOT EXISTS 'CONFIRMED'")
    op.execute("ALTER TYPE surgerystatus ADD VALUE IF NOT EXISTS 'IN_PROGRESS'")
    op.execute("ALTER TYPE surgerystatus RENAME VALUE 'PLANNED' TO 'SCHEDULED'")

    op.add_column('surgeries', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('surgeries', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('surgeries', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('surgeries', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('surgeries', sa.Column('cancelled_reason', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('surgeries', 'cancelled_reason')
    op.drop_column('surgeries', 'cancelled_at')
    op.drop_column('surgeries', 'completed_at')
    op.drop_column('surgeries', 'started_at')
    op.drop_column('surgeries', 'confirmed_at')

    # Postgres cannot drop an enum value without rewriting the column to a
    # fresh type, so the downgrade only restores the historical label and
    # leaves CONFIRMED/IN_PROGRESS defined-but-unused on the enum type.
    op.execute("ALTER TYPE surgerystatus RENAME VALUE 'SCHEDULED' TO 'PLANNED'")