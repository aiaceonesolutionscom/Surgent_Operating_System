"""make users.work_schedule NOT NULL

`User.work_schedule` is typed `Mapped[dict]` and the write path in
`StaffService.update_my` coerces every value to a dict
(`work_schedule if isinstance(work_schedule, dict) else {}`), so "no
schedule" is already represented as `{}` and no code path can produce
NULL. But the column was originally created nullable and nothing ever
tightened it, so the database and the model disagreed: `alembic check`
reported `modify_nullable` on every run.

That disagreement is not cosmetic. The type says `dict` while the column
permits NULL, so any code that trusts the annotation and does
`user.work_schedule["mon"]` raises TypeError on a NULL row rather than
failing loudly, and the six existing NULL rows are exactly that trap.
(`attendance_service.py` happens to read it as `u.work_schedule or {}`,
which is why the bug stayed invisible.)

The backfill turns NULL into `{}` -- the same value the service would have
written for "no schedule", so no information is lost -- and the
alter_column then matches the model, which makes `alembic check` clean
apart from PostgreSQL's foreign-key ordering noise.

Guarded because the backfill has to be conditional on the column existing
and still being nullable: a database that was already corrected by hand, or
built from a future migration that supersedes this one, must not fail on
"column work_schedule of relation users is already not-null".

Revision ID: d3e5f8a71c94
Revises: c4d81a2f7e30
Create Date: 2026-09-27 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'd3e5f8a71c94'
down_revision: Union[str, None] = 'c4d81a2f7e30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _work_schedule_state() -> str:
    """'missing', 'nullable' or 'not-null' for users.work_schedule."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'users' not in inspector.get_table_names():
        return 'missing'
    for column in inspector.get_columns('users'):
        if column['name'] == 'work_schedule':
            return 'nullable' if column['nullable'] else 'not-null'
    return 'missing'


def upgrade() -> None:
    if _work_schedule_state() != 'nullable':
        return
    op.execute("UPDATE users SET work_schedule = '{}'::jsonb WHERE work_schedule IS NULL")
    op.alter_column(
        'users',
        'work_schedule',
        existing_type=JSONB(astext_type=sa.Text()),
        nullable=False,
    )


def downgrade() -> None:
    if _work_schedule_state() != 'not-null':
        return
    op.alter_column(
        'users',
        'work_schedule',
        existing_type=JSONB(astext_type=sa.Text()),
        nullable=True,
    )
