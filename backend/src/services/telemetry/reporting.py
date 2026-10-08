"""Read side of platform telemetry: the aggregates the Super Admin overview
and clinic pages render. Everything here is computed from persisted rows
(llm_calls, system_metric_buckets, slow_query_log, agent_logs), so figures are
identical across restarts and across API instances."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_log import AgentLog
from src.models.platform_telemetry import LlmCall, SlowQueryLog, SystemMetricBucket
from src.server import runtime_metrics

_P95_SAMPLE_CAP = 20_000


def month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _f(value) -> float:
    return float(value) if value is not None else 0.0


def _percentile(sorted_values: list[int], pct: float) -> float | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, round(pct / 100 * (len(sorted_values) - 1))))
    return float(sorted_values[index])


async def ai_usage_by_practice(db: AsyncSession, since: datetime) -> dict:
    """{practice_id: (calls, cost_usd)} for successful calls since `since`."""
    rows = await db.execute(
        select(LlmCall.practice_id, func.count(), func.coalesce(func.sum(LlmCall.cost_usd), 0))
        .where(LlmCall.created_at >= since, LlmCall.status == "ok", LlmCall.practice_id.is_not(None))
        .group_by(LlmCall.practice_id)
    )
    return {practice_id: (calls, Decimal(cost)) for practice_id, calls, cost in rows.all()}


async def ai_usage_summary(db: AsyncSession, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_month = month_start(now)

    calls_total, cost_total = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(LlmCall.status == "ok")
        )
    ).one()

    month_calls, month_prompt, month_completion, month_cost = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(LlmCall.prompt_tokens), 0),
                func.coalesce(func.sum(LlmCall.completion_tokens), 0),
                func.coalesce(func.sum(LlmCall.cost_usd), 0),
            ).where(LlmCall.created_at >= since_month, LlmCall.status == "ok")
        )
    ).one()

    calls_24h, failed_24h = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(case((LlmCall.status != "ok", 1), else_=0)), 0),
            ).where(LlmCall.created_at >= since_24h)
        )
    ).one()

    latencies = sorted(
        (
            await db.execute(
                select(LlmCall.latency_ms)
                .where(LlmCall.created_at >= since_24h, LlmCall.status == "ok")
                .order_by(LlmCall.created_at.desc())
                .limit(_P95_SAMPLE_CAP)
            )
        ).scalars().all()
    )
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

    top_sources = [
        {"source": source, "calls": calls, "cost_usd": _f(cost)}
        for source, calls, cost in (
            await db.execute(
                select(LlmCall.source, func.count(), func.coalesce(func.sum(LlmCall.cost_usd), 0))
                .where(LlmCall.created_at >= since_month, LlmCall.status == "ok")
                .group_by(LlmCall.source)
                .order_by(func.sum(LlmCall.cost_usd).desc(), func.count().desc())
                .limit(6)
            )
        ).all()
    ]

    agent_actions_30d = (
        await db.execute(
            select(func.count()).select_from(AgentLog).where(AgentLog.created_at >= now - timedelta(days=30))
        )
    ).scalar_one()

    return {
        "calls_total": calls_total,
        "calls_month": month_calls,
        "calls_24h": calls_24h,
        "avg_latency_ms_24h": avg_latency,
        "p95_latency_ms_24h": _percentile(latencies, 95),
        "error_rate_percent_24h": round(int(failed_24h) / calls_24h * 100, 2) if calls_24h else 0.0,
        "tokens_month": int(month_prompt) + int(month_completion),
        "cost_month_usd": _f(month_cost),
        "cost_total_usd": _f(cost_total),
        "agent_actions_30d": agent_actions_30d,
        "top_sources": top_sources,
    }


async def system_summary(db: AsyncSession, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    # Buckets are hourly, so the oldest included hour is a partial one — fine
    # for a rolling "last 24h" figure.
    window_start = since_24h.replace(minute=0, second=0, microsecond=0)

    totals = (
        await db.execute(
            select(
                func.coalesce(func.sum(SystemMetricBucket.requests), 0),
                func.coalesce(func.sum(SystemMetricBucket.errors_5xx), 0),
                func.coalesce(func.sum(SystemMetricBucket.slow_requests), 0),
                func.coalesce(func.sum(SystemMetricBucket.total_duration_ms), 0),
                func.coalesce(func.sum(SystemMetricBucket.slow_queries), 0),
            ).where(SystemMetricBucket.bucket_start >= window_start)
        )
    ).one()
    requests, errors, slow_requests, total_ms, slow_queries = (int(v) for v in totals)

    # Add what this process has counted since its last flush (< 30s), so the
    # panel never lags behind a burst of errors it is about to report.
    pending = runtime_metrics.pending()
    requests += pending["requests"]
    errors += pending["errors_5xx"]
    slow_requests += pending["slow_requests"]
    total_ms += pending["total_duration_ms"]
    slow_queries += pending["slow_queries"]

    started_instances = set(
        (
            await db.execute(
                select(SystemMetricBucket.instance_id)
                .where(SystemMetricBucket.started_at >= since_24h)
                .distinct()
            )
        ).scalars().all()
    )
    if runtime_metrics.STARTED_AT >= since_24h:
        started_instances.add(runtime_metrics.INSTANCE_ID)

    top_slow = [
        {"statement": statement, "count": count, "max_ms": int(max_ms), "avg_ms": round(float(avg_ms))}
        for statement, count, max_ms, avg_ms in (
            await db.execute(
                select(
                    func.min(SlowQueryLog.statement),
                    func.count(),
                    func.max(SlowQueryLog.duration_ms),
                    func.avg(SlowQueryLog.duration_ms),
                )
                .where(SlowQueryLog.created_at >= since_24h)
                .group_by(SlowQueryLog.statement_hash)
                .order_by(func.max(SlowQueryLog.duration_ms).desc())
                .limit(5)
            )
        ).all()
    ]

    # DB health = round-trip of one trivial statement on this request's own
    # session — real, and the endpoint 500s if the database is unreachable.
    started = time.perf_counter()
    await db.execute(text("SELECT 1"))
    db_health_ms = round((time.perf_counter() - started) * 1000, 1)

    return {
        "uptime_seconds": runtime_metrics.uptime_seconds(),
        "started_at": runtime_metrics.STARTED_AT,
        "restarts_24h": len(started_instances),
        "requests_24h": requests,
        "error_rate_percent": round(errors / requests * 100, 2) if requests else 0.0,
        "avg_response_ms_24h": round(total_ms / requests, 1) if requests else None,
        "slow_requests_24h": slow_requests,
        "slow_queries_24h": slow_queries,
        "top_slow_queries": top_slow,
        "db_health_ms": db_health_ms,
    }

