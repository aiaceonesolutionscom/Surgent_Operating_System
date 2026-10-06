"""Process-local runtime telemetry for the Super Admin SYSTEM panel.

Deliberately in-process (not Redis-backed): these numbers answer "how is the
API process doing since it booted", which is the only honest question a
single-instance deployment can answer without a metrics stack. Every value is
scoped to this process since boot — the frontend labels them that way, and a
multi-instance deploy would need per-instance aggregation (or Prometheus)
before these numbers mean "the platform". Cheap, real, and never fake.
"""

from __future__ import annotations

import time

# Module import time ~= app boot time: this module is first imported by
# middleware.py, which main.py pulls in at import time, before any request.
_WALL_START = time.time()
_MONO_START = time.monotonic()

_requests_total = 0
_errors_total = 0
_slow_requests = 0

# A request slower than this counts as a "slow query" in the SYSTEM panel —
# one honest proxy for it, since per-query timings aren't collected (that
# needs pg_stat_statements or SQLAlchemy event listeners, both heavier than
# this file's job).
SLOW_REQUEST_MS = 500.0


def record_request(duration_ms: float, status: int | None) -> None:
    """Called once per completed HTTP request by AuditLogMiddleware."""
    global _requests_total, _errors_total, _slow_requests
    _requests_total += 1
    if status is not None and status >= 500:
        _errors_total += 1
    if duration_ms >= SLOW_REQUEST_MS:
        _slow_requests += 1


def snapshot() -> dict:
    """One consistent read of everything the /admin/platform_metrics
    SYSTEM block needs."""
    return {
        "uptime_seconds": round(time.time() - _WALL_START),
        "requests_total": _requests_total,
        "errors_5xx_total": _errors_total,
        # Percent of requests that 5xx'd since boot; 0 before any traffic.
        "error_rate_percent": round((_errors_total / _requests_total * 100), 2) if _requests_total else 0.0,
        "slow_requests_total": _slow_requests,
    }
