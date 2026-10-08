"""Process-local request / query counters feeding the Super Admin SYSTEM panel.

This module only *counts*, in memory, with no I/O — it runs on every request
and every SQL statement, so it has to be free. Persistence lives in
services/telemetry/recorder.py: a background task drains the counters here as
deltas every few seconds and adds them to `system_metric_buckets`, which is
what the admin panel's 24h error rate / slow counts are computed from. That is
why those figures survive a restart and add up across API instances; only the
"uptime" figure is inherently per-process.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from datetime import datetime, timezone

# Random per boot: a restart appears as a new instance in the persisted rows,
# which is how the panel counts restarts.
INSTANCE_ID = uuid.uuid4().hex[:12]
STARTED_AT = datetime.now(timezone.utc)
_MONO_START = time.monotonic()

# A request / statement slower than this is counted as "slow".
SLOW_REQUEST_MS = 500.0
SLOW_QUERY_MS = 300.0
# Cap on distinct slow statements kept between two flushes, so a pathological
# burst can't grow memory without bound.
_MAX_SLOW_BUFFER = 200

# Lifetime (since boot) counters — what snapshot() reports.
_requests_total = 0
_errors_total = 0
_slow_requests = 0

# Deltas since the last drain(), written to the DB by the flusher.
_delta = {"requests": 0, "errors_5xx": 0, "slow_requests": 0, "total_duration_ms": 0, "db_queries": 0, "slow_queries": 0}
_slow_query_buffer: list[dict] = []


def record_request(duration_ms: float, status: int | None) -> None:
    """Called once per completed HTTP request by AuditLogMiddleware."""
    global _requests_total, _errors_total, _slow_requests
    _requests_total += 1
    _delta["requests"] += 1
    _delta["total_duration_ms"] += int(duration_ms)
    if status is not None and status >= 500:
        _errors_total += 1
        _delta["errors_5xx"] += 1
    if duration_ms >= SLOW_REQUEST_MS:
        _slow_requests += 1
        _delta["slow_requests"] += 1


_PARAM_RE = re.compile(r"\$\d+")
_IN_LIST_RE = re.compile(r"\(\?(?:, ?\?)+\)")


def normalize_statement(statement: str) -> str:
    """Collapse whitespace and bind-parameter placeholders so the same query
    shape hashes identically however many values it was called with."""
    flat = " ".join(statement.split())
    flat = _PARAM_RE.sub("?", flat)
    flat = _IN_LIST_RE.sub("(?, ...)", flat)
    return flat[:1500]


def record_query(duration_ms: float, statement: str) -> None:
    """Called after every SQL statement by the engine event listener."""
    _delta["db_queries"] += 1
    if duration_ms < SLOW_QUERY_MS:
        return
    _delta["slow_queries"] += 1
    if len(_slow_query_buffer) >= _MAX_SLOW_BUFFER:
        return
    normalized = normalize_statement(statement)
    _slow_query_buffer.append({
        "statement_hash": hashlib.md5(normalized.encode()).hexdigest(),
        "statement": normalized,
        "duration_ms": int(duration_ms),
    })


def install_query_timing(sync_engine) -> None:
    """Time every SQL statement on `sync_engine` (an AsyncEngine's
    `.sync_engine`). Registered once from database.py."""
    from sqlalchemy import event

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("_q_start", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get("_q_start")
        if starts:
            record_query((time.perf_counter() - starts.pop()) * 1000, statement)


def drain() -> tuple[dict, list[dict]]:
    """Hand the flusher everything counted since the last drain and reset."""
    global _slow_query_buffer
    deltas = dict(_delta)
    for key in _delta:
        _delta[key] = 0
    slow, _slow_query_buffer = _slow_query_buffer, []
    return deltas, slow


def restore(deltas: dict, slow: list[dict]) -> None:
    """Put a drained batch back when the DB write failed, so nothing is lost."""
    for key, value in deltas.items():
        _delta[key] = _delta.get(key, 0) + value
    _slow_query_buffer[:0] = slow[: max(0, _MAX_SLOW_BUFFER - len(_slow_query_buffer))]


def pending() -> dict:
    """Counts recorded since the last flush (not yet in the database)."""
    return dict(_delta)


def uptime_seconds() -> int:
    return round(time.monotonic() - _MONO_START)


def snapshot() -> dict:
    """This process's own view since boot (uptime, lifetime counters)."""
    return {
        "uptime_seconds": uptime_seconds(),
        "requests_total": _requests_total,
        "errors_5xx_total": _errors_total,
        "error_rate_percent": round((_errors_total / _requests_total * 100), 2) if _requests_total else 0.0,
        "slow_requests_total": _slow_requests,
    }
