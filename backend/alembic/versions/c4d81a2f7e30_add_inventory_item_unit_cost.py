"""add inventory_items.unit_cost

The InventoryItem model has carried `unit_cost` for per-item valuation
(on_hand_quantity * unit_cost -> total_value), and it was previously added
straight to developer databases by backend/scripts/add_unit_cost.py. That
script was never a migration, so a fresh database built with
`alembic upgrade head` produced an `inventory_items` table WITHOUT the
column and every inventory query failed against it.

nullable=True matches the model (unit_cost is optional - it's only known
once the practice records what it pays for a SKU).

The add_column is guarded because existing developer databases already got
this column from backend/scripts/add_unit_cost.py, which was never stamped
into alembic_version. Without the guard, deploying to any such database
fails with "column unit_cost of relation inventory_items already exists",
and with a plain add_column the same failure blocks the deploy that this
migration exists to enable. A fresh database takes the add_column path; a
database that already has it just records the new revision.

Revision ID: c4d81a2f7e30
Revises: 060faedfe923
Create Date: 2026-09-27 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d81a2f7e30'
down_revision: Union[str, None] = '060faedfe923'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_unit_cost() -> bool:
    """True when inventory_items.unit_cost is already present."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'inventory_items' not in inspector.get_table_names():
        return False
    return 'unit_cost' in {c['name'] for c in inspector.get_columns('inventory_items')}


def upgrade() -> None:
    if _has_unit_cost():
        return
    op.add_column(
        'inventory_items',
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=True),
    )


def downgrade() -> None:
    if not _has_unit_cost():
        return
    op.drop_column('inventory_items', 'unit_cost')
