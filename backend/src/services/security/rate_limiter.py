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

    Fails OPEN (lets the request through) if Redis is unreachable — a rate
    limiter that itself blocks real logins when its backing store hiccups is
    a worse outcome than the brute-force risk it's guarding against. Logged
    loudly when this happens so it doesn't go unnoticed."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._client = None
        self._redis_available: bool | None = None

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

    async def check(self, key: str) -> None:
        """Raises AppException(429) if `key` has hit its attempt limit
        within the window; otherwise records this attempt."""
        if self._redis_available is False:
            return  # known outage — fail open instantly, no socket wait
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
            self._redis_available = True
        except AppException:
            raise
        except Exception:
            # Cache the outage so login doesn't eat a socket timeout on every
            # Redis op — after the first probe failure, fail open instantly.
            self._redis_available = False
            self._client = None
            logger.warning("RedisRateLimiter check failed for key=%s, failing open", key, exc_info=True)

    async def reset(self, key: str) -> None:
        """Clears attempts for `key` — call on a successful login so a
        legitimate user isn't left rate-limited by their own earlier typos."""
        if self._redis_available is False:
            return
        try:
            await self.client.delete(f"ratelimit:{key}")
            self._redis_available = True
        except Exception:
            self._redis_available = False
            logger.warning("RedisRateLimiter reset failed for key=%s", key, exc_info=True)
