from __future__ import annotations
import logging
import time

import redis.asyncio as redis

from src.config import get_settings
from src.server.exceptions import AppException

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """Shared, Redis-backed rate limiter — replaces the per-process
    in-memory limiter this project started with (each worker process would
    otherwise track its own separate attempt counts, so a limit of 5 could
    actually allow 5×N attempts across N workers). Uses a sorted set per key,
    scored by attempt timestamp, so a precise "in the last window_seconds"
    cutoff can be enforced via ZREMRANGEBYSCORE — a plain INCR+EXPIRE counter
    would reset its whole window on the first hit after expiry, letting a
    fresh burst straight through right at the boundary.

    If Redis is unreachable the limiter does not block real logins, but it
    does NOT switch protection off either: it falls back to a per-process
    sliding window (weaker - each instance counts separately - but a
    brute-force attempt still hits a wall), and probes Redis again after a
    short pause so it recovers on its own once Redis is back. Logged loudly
    when this happens so it doesn't go unnoticed."""

    _RETRY_REDIS_AFTER_SECONDS = 30
    _LOCAL_MAX_KEYS = 10_000

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._client = None
        self._retry_redis_at = 0.0  # monotonic time before which Redis is not tried
        self._local: dict[str, list[float]] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        return self._client

    def _check_local(self, key: str) -> None:
        now = time.time()
        hits = [t for t in self._local.get(key, []) if t > now - self.window_seconds]
        if len(hits) >= self.max_attempts:
            self._local[key] = hits
            raise AppException("Too many attempts — try again in a few minutes.", status_code=429)
        hits.append(now)
        self._local[key] = hits
        if len(self._local) > self._LOCAL_MAX_KEYS:
            cutoff = now - self.window_seconds
            self._local = {k: v for k, v in self._local.items() if v and v[-1] > cutoff}

    async def check(self, key: str) -> None:
        """Raises AppException(429) if `key` has hit its attempt limit
        within the window; otherwise records this attempt."""
        if time.monotonic() < self._retry_redis_at:
            self._check_local(key)  # known outage - no socket wait, but still limited
            return
        full_key = f"ratelimit:{key}"
        try:
            now = time.time()
            cutoff = now - self.window_seconds
            pipe = self.client.pipeline()
            pipe.zremrangebyscore(full_key, 0, cutoff)
            pipe.zcard(full_key)
            _, count = await pipe.execute()
            if count >= self.max_attempts:
                raise AppException("Too many attempts — try again in a few minutes.", status_code=429)
            await self.client.zadd(full_key, {f"{now}": now})
            await self.client.expire(full_key, self.window_seconds)
        except AppException:
            raise
        except Exception:
            # Remember the outage so every login doesn't eat a socket timeout,
            # then retry Redis after a pause.
            self._retry_redis_at = time.monotonic() + self._RETRY_REDIS_AFTER_SECONDS
            self._client = None
            logger.warning("RedisRateLimiter check failed for key=%s, using the in-process limiter", key, exc_info=True)
            self._check_local(key)

    async def reset(self, key: str) -> None:
        """Clears attempts for `key` — call on a successful login so a
        legitimate user isn't left rate-limited by their own earlier typos."""
        self._local.pop(key, None)
        if time.monotonic() < self._retry_redis_at:
            return
        try:
            await self.client.delete(f"ratelimit:{key}")
        except Exception:
            self._retry_redis_at = time.monotonic() + self._RETRY_REDIS_AFTER_SECONDS
            self._client = None
            logger.warning("RedisRateLimiter reset failed for key=%s", key, exc_info=True)
