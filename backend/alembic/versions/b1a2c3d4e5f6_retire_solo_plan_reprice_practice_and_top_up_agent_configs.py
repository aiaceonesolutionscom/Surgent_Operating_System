"""retire solo plan reprice practice to 999 and top up agent configs

Revision ID: b1a2c3d4e5f6
Revises: 6becd117ec3f
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, None] = '6becd117ec3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The final consolidated 9-agent roster — mirrors seed_data.py AGENT_TYPES.
AGENT_SLUGS = [
    'receptionist',
    'appointment_reminder',
    'lead_qualification',
    'patient_intake',
    'consultation_assistant',
    'post_op_recovery',
    'marketing_retention',
    'finance_agent',
    'main_agent',
]

FOUR_CATEGORIES = ['front-desk', 'consultation', 'post-care', 'business']

PRACTICE_FEATURES = [
    'All 9 agents pre-configured',
    'Front desk, consultation, recovery & retention agents',
    'Finance agent — monthly revenue, outstanding and agent cost',
    'WhatsApp, Instagram & website chat channels',
    'Multilingual support',
    'Analytics dashboard',
    'Priority onboarding & support',
]

ENTERPRISE_FEATURES = [
    'Everything in Practice',
    'Custom plan — priced for your operation',
    'Multi-location orchestration',
    'Custom integrations & EHR',
    'BAA & dedicated success manager',
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Retire the Solo plan; reprice Practice -> $999; fix the copy to match
    #    the 9-agent catalog (no surgery category, no "All 31 agents").
    conn.execute(text("UPDATE plans SET is_active = false, price = NULL WHERE tier = 'SOLO'"))
    conn.execute(
        text(
            "UPDATE plans SET price = 999.00, "
            "tagline = 'The whole AI front office for a growing clinic', "
            "features = :features, agent_categories = :cats, "
            "highlight = true, display_order = 0 WHERE tier = 'PRACTICE'"
        ),
        {'features': json.dumps(PRACTICE_FEATURES), 'cats': json.dumps(FOUR_CATEGORIES)},
    )
    conn.execute(
        text(
            "UPDATE plans SET tagline = 'For groups & multi-location brands', "
            "features = :features, agent_categories = :cats, "
            "is_custom_pricing = true, display_order = 1 WHERE tier = 'ENTERPRISE'"
        ),
        {'features': json.dumps(ENTERPRISE_FEATURES), 'cats': json.dumps(FOUR_CATEGORIES)},
    )

    # 2) Solo subscriptions collapsed into Practice (the enum value stays so
    #    postgres enum retype isn't needed; new signups can't pick solo).
    conn.execute(
        text(
            "UPDATE subscriptions SET tier = 'PRACTICE', price = 999.00 "
            "WHERE tier = 'SOLO' AND (price IS NULL OR price <= 690)"
        )
    )
    conn.execute(text("UPDATE subscriptions SET tier = 'PRACTICE' WHERE tier = 'SOLO'"))

    # 3) Top-up: make sure every practice has an agent_config row for each of
    #    the 9 live slugs so the Agent settings page + gating have something to
    #    read. No-op for slugs already present (unique constraint).
    slugs_sql = ", ".join("('" + s + "')" for s in AGENT_SLUGS)
    conn.execute(
        text(
            "INSERT INTO agent_configs (id, practice_id, agent_type, enabled, config, created_at, updated_at) "
            "SELECT gen_random_uuid(), p.id, a.agent_type, true, '{}'::jsonb, now(), now() "
            "FROM practices p "
            f"CROSS JOIN (VALUES {slugs_sql}) AS a(agent_type) "
            "ON CONFLICT (practice_id, agent_type) DO NOTHING"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE plans SET price = NULL, is_active = true WHERE tier = 'SOLO'"
        )
    )
    conn.execute(
        text(
            "UPDATE plans SET price = 1690.00, "
            "tagline = 'For growing multi-surgeon clinics', "
            "features = '[\"Everything in Solo\",\"Full consultation & surgery agents\","
            "\"Post-surgery care & recovery suite\",\"All social channels connected\","
            "\"Analytics dashboard\",\"Priority onboarding & support\"]'::jsonb, "
            "agent_categories = '[\"front-desk\",\"consultation\",\"surgery\",\"post-care\"]'::jsonb, "
            "highlight = true, display_order = 1 WHERE tier = 'PRACTICE'"
        )
    )
    conn.execute(
        text(
            "UPDATE plans SET "
            "features = '[\"Everything in Practice\",\"All 31 agents, fully configured\","
            "\"Multi-location orchestration\",\"Custom integrations & EHR\","
            "\"BAA & dedicated success manager\"]'::jsonb, "
            "agent_categories = '[\"front-desk\",\"consultation\",\"surgery\",\"post-care\",\"business\"]'::jsonb, "
            "display_order = 2 WHERE tier = 'ENTERPRISE'"
        )
    )
    # Solo subscriptions cannot be restored (tier/price already overwritten).
    conn.execute(
        text(
            "DELETE FROM agent_configs WHERE agent_type IN "
            "('receptionist','appointment_reminder','lead_qualification','patient_intake',"
            "'consultation_assistant','post_op_recovery','marketing_retention',"
            "'finance_agent','main_agent') AND config = '{}'::jsonb "
            "AND created_at >= now() - interval '1 day'"
        )
    )