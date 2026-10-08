import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class LlmCall(Base):
    """One row per call to an LLM provider (Mistral / Groq / OpenAI) — the
    source of truth for the Super Admin's AI runs / latency / token / cost
    numbers. Persisted (not in-process) so the figures survive a restart and
    add up across several API instances. Written in batches by
    services/telemetry/recorder.py, never on the request path."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable on purpose: platform-level calls (the marketing-site chat, the
    # Super Agent) belong to no clinic, and a clinic deleted later must not
    # take its cost history with it.
    practice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practices.id", ondelete="SET NULL"), nullable=True
    )
    # Which feature made the call — the services/ package name that invoked
    # the LLM ("finance_agent", "command_center", "landing_chat", ...).
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="unknown")
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # "ok" | "rate_limited" | "error"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # True when the provider sent no usage block (common on streams) and the
    # token counts are a characters/4 estimate instead of a measurement.
    tokens_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # tokens × the provider's list price (services/telemetry/pricing.py) — what
    # the call would cost on a paid plan, even while the free tier bills $0.
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_llm_calls_created_at", "created_at"),
        Index("ix_llm_calls_practice_created", "practice_id", "created_at"),
    )


class SystemMetricBucket(Base):
    """Per-API-instance request counters rolled up by hour — what lets the
    Super Admin SYSTEM panel show a 24h error rate / slow-request count that
    survives restarts and covers every instance, instead of "since this
    process booted". One row per (hour, instance); the flusher adds deltas."""

    __tablename__ = "system_metric_buckets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Random per process boot, so a restart shows up as a new instance row.
    instance_id: Mapped[str] = mapped_column(String(40), nullable=False)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_5xx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slow_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    db_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slow_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ux_system_metric_bucket_instance", "bucket_start", "instance_id", unique=True),
    )


class SlowQueryLog(Base):
    """A database statement that took longer than the slow-query threshold.
    Only the SQL text is stored (SQLAlchemy sends values as bind parameters,
    which are never captured), so no patient data lands here."""

    __tablename__ = "slow_query_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_slow_query_log_created_at", "created_at"),
        Index("ix_slow_query_log_hash", "statement_hash"),
    )
