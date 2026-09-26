"""Convert SOLO plan to hidden 3-day free trial

Revision ID: 2260ede5e824
Revises: a930d35d9464
Create Date: 2026-09-25 18:28:48.819295

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '2260ede5e824'
down_revision: Union[str, None] = 'a930d35d9464'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update SOLO plan to be a hidden 3-day free trial (Super Admin only)
    # Not shown in checkout, not in marketing, only grantable via Super Admin panel
    plans_table = sa.table(
        'plans',
        sa.column('tier', postgresql.ENUM('SOLO', 'PRACTICE', 'ENTERPRISE', 'CUSTOM', name='subscriptiontier', create_type=False)),
        sa.column('name', sa.String()),
        sa.column('tagline', sa.String()),
        sa.column('price', sa.Numeric()),
        sa.column('billing_period', sa.String()),
        sa.column('is_custom_pricing', sa.Boolean()),
        sa.column('features', postgresql.JSONB()),
        sa.column('agent_categories', postgresql.JSONB()),
        sa.column('max_doctors', sa.Integer()),
        sa.column('max_social_channels', sa.Integer()),
        sa.column('max_locations', sa.Integer()),
        sa.column('has_analytics', sa.Boolean()),
        sa.column('trial_period_days', sa.Integer()),
        sa.column('is_active', sa.Boolean()),
        sa.column('highlight', sa.Boolean()),
        sa.column('display_order', sa.Integer()),
    )
    op.execute(
        plans_table.update()
        .where(plans_table.c.tier == 'SOLO')
        .values(
            name='Free Trial (3 Days)',
            tagline='Hidden Super Admin trial — not for public checkout',
            price=0,
            billing_period='monthly',
            is_custom_pricing=True,
            features=[
                'Full platform access for 3 days',
                'All 9 agents enabled',
                'Auto-expires after 3 days',
                'Revocable by Super Admin at any time',
            ],
            agent_categories=['front-desk', 'consultation', 'post-care', 'business'],
            max_doctors=2,
            max_social_channels=2,
            max_locations=1,
            has_analytics=True,
            trial_period_days=3,
            is_active=True,
            highlight=False,
            display_order=-1,  # Hidden from normal listings
        )
    )


def downgrade() -> None:
    # Restore SOLO plan to original state
    plans_table = sa.table(
        'plans',
        sa.column('tier', postgresql.ENUM('SOLO', 'PRACTICE', 'ENTERPRISE', 'CUSTOM', name='subscriptiontier', create_type=False)),
        sa.column('name', sa.String()),
        sa.column('tagline', sa.String()),
        sa.column('price', sa.Numeric()),
        sa.column('billing_period', sa.String()),
        sa.column('is_custom_pricing', sa.Boolean()),
        sa.column('features', postgresql.JSONB()),
        sa.column('agent_categories', postgresql.JSONB()),
        sa.column('max_doctors', sa.Integer()),
        sa.column('max_social_channels', sa.Integer()),
        sa.column('max_locations', sa.Integer()),
        sa.column('has_analytics', sa.Boolean()),
        sa.column('trial_period_days', sa.Integer()),
        sa.column('is_active', sa.Boolean()),
        sa.column('highlight', sa.Boolean()),
        sa.column('display_order', sa.Integer()),
    )
    op.execute(
        plans_table.update()
        .where(plans_table.c.tier == 'SOLO')
        .values(
            name='Solo',
            tagline='For single-surgeon practices',
            price=690,
            billing_period='monthly',
            is_custom_pricing=False,
            features=[
                'Front desk & intake agents', 'Booking, reminders & rescheduling',
                '1 connected social channel', 'Multilingual support', 'Email support',
            ],
            agent_categories=['front-desk'],
            max_doctors=1,
            max_social_channels=1,
            max_locations=1,
            has_analytics=False,
            trial_period_days=14,
            is_active=True,
            highlight=False,
            display_order=0,
        )
    )