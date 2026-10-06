"""add is_sample flag for per-practice demo data

Revision ID: c7d8e9f0a1b2
Revises: d3e5f8a71c94
Create Date: 2026-10-02 18:40:11.204918

WHY
---
The free "request organization" path (see PendingSignup's org-request fields and
services/practice/org_request_service.py) lets a prospect use the whole product
without paying. But provisioning_from_org_request only ever creates a Practice,
an owner User, a trial Subscription and the 9 AgentConfig rows — it seeds no
patients, appointments, conversations or leads. So an approved owner lands on
completely EMPTY dashboards, which defeats the entire point of a free trial:
there is nothing to click, explore or judge.

Sample data must be able to be seeded per-practice AND individually removed
again ("load sample data" / "delete all sample data" in the owner's settings),
which means real and sample rows have to be distinguishable in the table. Hence
one nullable=False boolean per seedable table.

ISOLATION
---------
Only tables that carry practice_id (or hang off it) are flagged. `messages` is
deliberately NOT flagged: it has no practice_id and only a conversation_id
foreign key, and Conversation.messages cascades "all, delete-orphan" — so
deleting a sample Conversation already deletes its sample Messages with it.
Adding a second, independently-writable flag there would let the two drift.

`sales_leads` is ALSO deliberately NOT flagged. Despite the name, SalesLead is
not a clinic's patient-lead funnel — models/sales_lead.py documents it as
"Aiaceone's own pipeline, not a clinic's patient lead", it has no practice_id,
and its `source` enum is only aria_landing_chat / demo_form /
book_consultation (Aiaceone's own marketing sources). Seeding it with fake
clinic patients would silently pollute the platform's real sales funnel and
show fabricated rows to the Super-Admin. A clinic's own lead funnel is
Patient.lifecycle_stage instead, which IS practice-scoped and IS seeded.

`nullable=False, server_default=false` (same discipline as
6becd117ec3f_practice_status_and_org_request_fields) means every pre-existing
row is categorised as REAL in the very same statement that adds the column.
No UPDATE pass, and — critically — no existing customer's data is ever at risk
of being swept up by a "delete sample data" click.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'd3e5f8a71c94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table) — every one of these is practice-scoped.
SAMPLE_TABLES = [
    'patients',
    'appointments',
    'conversations',
    'inventory_items',
    'expenses',
]


def upgrade() -> None:
    for table in SAMPLE_TABLES:
        op.add_column(
            table,
            sa.Column(
                'is_sample',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    for table in reversed(SAMPLE_TABLES):
        op.drop_column(table, 'is_sample')