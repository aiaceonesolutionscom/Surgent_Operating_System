"""Write-behind persistence for platform telemetry.

Everything the Super Admin overview shows about AI usage and API health comes
from rows this module writes. The request path only appends to in-memory
buffers (free, can't fail); a background task flushes them to Postgres in
batches. If a flush fails the batch is put back and retried, so a database
blip delays telemetry instead of dropping it or breaking a user's request.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select

from src.models.platform_telemetry import LlmCall, SlowQueryLog, SystemMetricBucket
from src.server import runtime_metrics
from src.services.telemetry.pricing import estimate_cost_usd

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_SECONDS = 30
_MAX_BUFFERED_LLM_CALLS = 5000
_RETENTION_CHECK_EVERY_SECONDS = 3600

# The clinic the current request / task is acting for. Set once by the practice
# auth dependency (and by the WhatsApp / nurturing flows) so LLM calls made
# anywhere underneath are attributed without threading practice_id through
# every service signature.
current_practice_id: ContextVar[UUID | None] = ContextVar("telemetry_practice_id", default=None)

_llm_buffer: list[dict] = []


def set_current_practice(practice_id: UUID | None) -> None:
    current_practice_id.set(practice_id)


def infer_source() -> str:
    """Name the feature that triggered an LLM call: the first caller frame in
    `src.services.<package>` outside llm/telemetry. Derived from the import
    path rather than a hand-kept map, so it can't go stale when a service
    moves or a new one is added."""
    frame = sys._getframe(1)
    for _ in range(40):
        if frame is None:
            break
        name = frame.f_globals.get("__name__", "")
        parts = name.split(".")
        if len(parts) > 2 and parts[0] == "src" and parts[1] == "services" and parts[2] not in ("llm", "telemetry"):
            return parts[2]
        frame = frame.f_back
    return "unknown"


def record_llm_call(
    *,
    provider: str,
    model: str,
    source: str,
    streaming: bool,
    status: str,
    latency_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    tokens_estimated: bool = False,
) -> None:
    # Telemetry must never be able to fail the LLM call it is describing —
    # an odd provider response (missing/garbled usage) is dropped, not raised.
    try:
        if len(_llm_buffer) >= _MAX_BUFFERED_LLM_CALLS:
            return
        prompt_tokens = int(prompt_tokens)
        completion_tokens = int(completion_tokens)
        _llm_buffer.append({
            "practice_id": current_practice_id.get(),
            "source": source,
            "provider": provider,
            "model": model,
            "streaming": streaming,
            "status": status,
            "latency_ms": int(latency_ms),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "tokens_estimated": tokens_estimated,
            "cost_usd": estimate_cost_usd(provider, model, prompt_tokens, completion_tokens) if status == "ok" else 0,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        logger.debug("Dropped an unrecordable LLM call", exc_info=True)


def _hour_bucket(now: datetime) -> datetime:
    return now.replace(minute=0, second=0, microsecond=0)


async def flush(session_factory=None) -> None:
    """Write everything buffered since the last flush. Safe to call at any
    time; a no-op when there is nothing worth writing."""
    if session_factory is None:
        from src.database import async_session_factory as session_factory

    deltas, slow = runtime_metrics.drain()
    global _llm_buffer
    llm_rows, _llm_buffer = _llm_buffer, []

    # db_queries alone doesn't justify a write: the pollers query constantly,
    # and writing about them would wake an auto-suspending database for ever.
    if not (llm_rows or slow or deltas["requests"]):
        runtime_metrics.restore(deltas, [])
        return

    try:
        async with session_factory() as db:
            if llm_rows:
                db.add_all([LlmCall(**row) for row in llm_rows])
            if slow:
                db.add_all([SlowQueryLog(**row) for row in slow])

            bucket_start = _hour_bucket(datetime.now(timezone.utc))
            bucket = (
                await db.execute(
                    select(SystemMetricBucket).where(
                        SystemMetricBucket.bucket_start == bucket_start,
                        SystemMetricBucket.instance_id == runtime_metrics.INSTANCE_ID,
                    )
                )
            ).scalar_one_or_none()
            if bucket is None:
                bucket = SystemMetricBucket(
                    bucket_start=bucket_start,
                    instance_id=runtime_metrics.INSTANCE_ID,
                    started_at=runtime_metrics.STARTED_AT,
                    requests=0, errors_5xx=0, slow_requests=0,
                    total_duration_ms=0, db_queries=0, slow_queries=0,
                )
                db.add(bucket)
            bucket.requests += deltas["requests"]
            bucket.errors_5xx += deltas["errors_5xx"]
            bucket.slow_requests += deltas["slow_requests"]
            bucket.total_duration_ms += deltas["total_duration_ms"]
            bucket.db_queries += deltas["db_queries"]
            bucket.slow_queries += deltas["slow_queries"]
            await db.commit()
    except Exception:
        logger.warning("Telemetry flush failed; batch kept for retry", exc_info=True)
        runtime_metrics.restore(deltas, slow)
        _llm_buffer[:0] = llm_rows[: max(0, _MAX_BUFFERED_LLM_CALLS - len(_llm_buffer))]


async def purge_old_rows(session_factory=None) -> None:
    """Keep the high-churn tables bounded. LLM calls are kept (small, and the
    cost history is the point); slow-query samples and hourly request
    buckets only matter for recent windows."""
    if session_factory is None:
        from src.database import async_session_factory as session_factory
    now = datetime.now(timezone.utc)
    async with session_factory() as db:
        await db.execute(delete(SlowQueryLog).where(SlowQueryLog.created_at < now - timedelta(days=14)))
        await db.execute(delete(SystemMetricBucket).where(SystemMetricBucket.bucket_start < now - timedelta(days=35)))
        await db.commit()


async def run_flusher() -> None:
    """Background loop started from the app lifespan. Cancelling it performs
    one last flush so a clean shutdown/redeploy doesn't lose the final batch."""
    last_purge = 0.0
    loop = asyncio.get_running_loop()
    try:
        while True:
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
            await flush()
            if loop.time() - last_purge > _RETENTION_CHECK_EVERY_SECONDS:
                last_purge = loop.time()
                try:
                    await purge_old_rows()
                except Exception:
                    logger.warning("Telemetry purge failed", exc_info=True)
    except asyncio.CancelledError:
        try:
            await asyncio.wait_for(flush(), timeout=5)
        except Exception:
            logger.warning("Final telemetry flush failed", exc_info=True)
        raise
