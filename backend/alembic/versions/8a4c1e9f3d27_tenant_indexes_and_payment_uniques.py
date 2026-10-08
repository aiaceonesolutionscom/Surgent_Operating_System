"""tenant/foreign-key indexes + payment idempotency uniques

PostgreSQL does not index foreign-key columns automatically, and almost every
query in this app filters on practice_id (or a patient/doctor/conversation id).
Without these, each list screen is a sequential scan that gets slower with
every clinic that signs up - and the slow-query panel in the Super Admin
overview is where it would first show.

The unique indexes make payment handling idempotent at the database level:
the Stripe webhook and the success-redirect can both arrive for one payment,
and a check-then-insert in application code lets both through under
concurrency. They are partial (non-NULL only) because most rows carry no
Stripe id.

Everything is IF NOT EXISTS so the migration is safe to re-run.

Revision ID: 8a4c1e9f3d27
Revises: 7d3f9a1c2b84
Create Date: 2026-10-09 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8a4c1e9f3d27"
down_revision: Union[str, None] = "7d3f9a1c2b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs that are filtered or joined on constantly.
FK_INDEXES = [
    ("agent_logs", "practice_id"),
    ("appointments", "doctor_id"),
    ("appointments", "patient_id"),
    ("appointments", "practice_id"),
    ("attendance_records", "doctor_id"),
    ("attendance_records", "practice_id"),
    ("audit_logs", "practice_id"),
    ("consent_documents", "patient_id"),
    ("consent_documents", "practice_id"),
    ("consent_templates", "practice_id"),
    ("consultation_notes", "doctor_id"),
    ("consultation_notes", "patient_id"),
    ("consultation_notes", "practice_id"),
    ("conversations", "patient_id"),
    ("conversations", "practice_id"),
    ("doctor_availability", "doctor_id"),
    ("doctor_procedures", "doctor_id"),
    ("doctor_time_blocks", "practice_id"),
    ("doctors", "practice_id"),
    ("expenses", "practice_id"),
    ("inventory_items", "practice_id"),
    ("invoices", "patient_id"),
    ("invoices", "practice_id"),
    ("messages", "conversation_id"),
    ("notifications", "practice_id"),
    ("patient_photos", "patient_id"),
    ("patients", "practice_id"),
    ("payments", "practice_id"),
    ("pending_doctor_requests", "doctor_id"),
    ("pending_doctor_requests", "practice_id"),
    ("pending_signups", "practice_id"),
    ("pending_staff_requests", "practice_id"),
    ("procedures", "practice_id"),
    ("purchase_orders", "practice_id"),
    ("recovery_journals", "patient_id"),
    ("refund_requests", "patient_id"),
    ("refund_requests", "practice_id"),
    ("review_requests", "patient_id"),
    ("review_requests", "practice_id"),
    ("session_visits", "doctor_id"),
    ("session_visits", "patient_id"),
    ("session_visits", "practice_id"),
    ("staff_messages", "practice_id"),
    ("subscriptions", "practice_id"),
    ("suppliers", "practice_id"),
    ("surgeries", "doctor_id"),
    ("surgeries", "patient_id"),
    ("surgeries", "practice_id"),
    ("treatment_plans", "doctor_id"),
    ("treatment_plans", "patient_id"),
    ("treatment_plans", "practice_id"),
    ("users", "practice_id"),
    ("visit_documents", "doctor_id"),
    ("visit_documents", "patient_id"),
    ("visit_documents", "practice_id"),
    ("waitlist_entries", "doctor_id"),
    ("waitlist_entries", "patient_id"),
    ("waitlist_entries", "practice_id"),
]

# Time-ordered per-tenant feeds (audit trail, agent activity, notifications).
COMPOSITE_INDEXES = [
    ("audit_logs", "practice_id, created_at DESC"),
    ("agent_logs", "practice_id, created_at DESC"),
    ("notifications", "practice_id, created_at DESC"),
]

# (index name, table, column) - partial unique on non-NULL Stripe identifiers.
PAYMENT_UNIQUES = [
    ("ux_payments_stripe_checkout_session", "payments", "stripe_checkout_session_id"),
    ("ux_wallet_tx_stripe_checkout_session", "wallet_transactions", "stripe_checkout_session_id"),
    ("ux_pending_signups_stripe_session", "pending_signups", "stripe_session_id"),
    ("ux_subscriptions_stripe_subscription", "subscriptions", "stripe_subscription_id"),
]


def upgrade() -> None:
    for table, column in FK_INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table} ({column})")
    for table, columns in COMPOSITE_INDEXES:
        name = f"ix_{table}_" + columns.split(" DESC")[0].replace(", ", "_")
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
    for name, table, column in PAYMENT_UNIQUES:
        op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({column}) WHERE {column} IS NOT NULL")


def downgrade() -> None:
    for name, _table, _column in PAYMENT_UNIQUES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    for table, columns in COMPOSITE_INDEXES:
        name = f"ix_{table}_" + columns.split(" DESC")[0].replace(", ", "_")
        op.execute(f"DROP INDEX IF EXISTS {name}")
    for table, column in FK_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_{column}")
