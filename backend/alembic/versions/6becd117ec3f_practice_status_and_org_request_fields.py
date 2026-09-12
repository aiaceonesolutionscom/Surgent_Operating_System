"""practice status and org request fields

Revision ID: 6becd117ec3f
Revises: a3b4c5d6e7f8
Create Date: 2026-09-12 14:25:18.523384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6becd117ec3f'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    org_request_status_enum = sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='orgrequeststatus')
    practice_status_enum = sa.Enum('PENDING_APPROVAL', 'ACTIVE', 'SUSPENDED', name='practicestatus')
    # op.add_column doesn't create the backing Postgres ENUM TYPE itself
    # (that's normally a side effect of Table.create's metadata event, which
    # doesn't run here) — create both explicitly first, or the ALTER TABLE
    # below fails with "type does not exist".
    org_request_status_enum.create(bind, checkfirst=True)
    practice_status_enum.create(bind, checkfirst=True)

    op.add_column('pending_signups', sa.Column('clerk_id', sa.String(length=255), nullable=True))
    op.add_column('pending_signups', sa.Column('org_name', sa.String(length=255), nullable=True))
    op.add_column('pending_signups', sa.Column('request_status', org_request_status_enum, nullable=True))
    op.add_column('pending_signups', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pending_signups', sa.Column('rejected_reason', sa.String(length=500), nullable=True))
    # plan_tier used to be required (every row was a paid checkout) — the new
    # free org-request path never sets it, so it must become optional.
    op.alter_column('pending_signups', 'plan_tier',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
    # server_default backfills every existing Practice row to ACTIVE in the
    # same statement that adds the column — no separate UPDATE needed, and no
    # existing customer is ever locked out by this migration.
    op.add_column('practices', sa.Column(
        'status',
        practice_status_enum,
        nullable=False,
        server_default='ACTIVE',
    ))


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_column('practices', 'status')
    op.alter_column('pending_signups', 'plan_tier',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
    op.drop_column('pending_signups', 'rejected_reason')
    op.drop_column('pending_signups', 'reviewed_at')
    op.drop_column('pending_signups', 'request_status')
    op.drop_column('pending_signups', 'org_name')
    op.drop_column('pending_signups', 'clerk_id')
    sa.Enum(name='practicestatus').drop(bind, checkfirst=True)
    sa.Enum(name='orgrequeststatus').drop(bind, checkfirst=True)
