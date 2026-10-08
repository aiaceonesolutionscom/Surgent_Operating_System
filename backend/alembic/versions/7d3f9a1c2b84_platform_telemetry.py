"""platform telemetry: llm_calls, system_metric_buckets, slow_query_log

Revision ID: 7d3f9a1c2b84
Revises: m2n3p4q5r6s7
Create Date: 2026-10-09 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d3f9a1c2b84'
down_revision: Union[str, None] = 'm2n3p4q5r6s7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_calls',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('practice_id', sa.UUID(), nullable=True),
        sa.Column('source', sa.String(length=80), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('streaming', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('tokens_estimated', sa.Boolean(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_llm_calls_created_at', 'llm_calls', ['created_at'])
    op.create_index('ix_llm_calls_practice_created', 'llm_calls', ['practice_id', 'created_at'])

    op.create_table(
        'system_metric_buckets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('bucket_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('instance_id', sa.String(length=40), nullable=False),
        sa.Column('requests', sa.Integer(), nullable=False),
        sa.Column('errors_5xx', sa.Integer(), nullable=False),
        sa.Column('slow_requests', sa.Integer(), nullable=False),
        sa.Column('total_duration_ms', sa.BigInteger(), nullable=False),
        sa.Column('db_queries', sa.Integer(), nullable=False),
        sa.Column('slow_queries', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ux_system_metric_bucket_instance', 'system_metric_buckets', ['bucket_start', 'instance_id'], unique=True
    )

    op.create_table(
        'slow_query_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('statement_hash', sa.String(length=32), nullable=False),
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_slow_query_log_created_at', 'slow_query_log', ['created_at'])
    op.create_index('ix_slow_query_log_hash', 'slow_query_log', ['statement_hash'])


def downgrade() -> None:
    op.drop_index('ix_slow_query_log_hash', table_name='slow_query_log')
    op.drop_index('ix_slow_query_log_created_at', table_name='slow_query_log')
    op.drop_table('slow_query_log')
    op.drop_index('ux_system_metric_bucket_instance', table_name='system_metric_buckets')
    op.drop_table('system_metric_buckets')
    op.drop_index('ix_llm_calls_practice_created', table_name='llm_calls')
    op.drop_index('ix_llm_calls_created_at', table_name='llm_calls')
    op.drop_table('llm_calls')
