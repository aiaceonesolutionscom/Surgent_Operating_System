"""Rate limiting must survive a Redis outage.

It used to fail open for the life of the process after a single failed probe:
one blip at 3am and admin login / OTP / PIN attempts were unlimited until the
next deploy."""

import time

import pytest

from src.server.exceptions import AppException
from src.services.security.rate_limiter import RedisRateLimiter


class _DeadRedis:
    def pipeline(self):
        raise ConnectionError("redis is down")

    async def delete(self, *_):
        raise ConnectionError("redis is down")


def _limiter(max_attempts=3):
    limiter = RedisRateLimiter(max_attempts=max_attempts, window_seconds=60)
    limiter._client = _DeadRedis()
    return limiter


async def test_outage_does_not_switch_limiting_off():
    limiter = _limiter(max_attempts=3)
    for _ in range(3):
        await limiter.check("1.2.3.4:admin")
    with pytest.raises(AppException) as exc:
        await limiter.check("1.2.3.4:admin")
    assert exc.value.status_code == 429


async def test_limits_are_per_key():
    limiter = _limiter(max_attempts=1)
    await limiter.check("a")
    await limiter.check("b")
    with pytest.raises(AppException):
        await limiter.check("a")


async def test_reset_clears_the_local_counter():
    limiter = _limiter(max_attempts=1)
    await limiter.check("a")
    await limiter.reset("a")
    await limiter.check("a")  # would have been the second attempt


async def test_redis_is_probed_again_after_the_pause():
    limiter = _limiter()
    await limiter.check("a")
    assert limiter._retry_redis_at > time.monotonic()  # outage remembered
    limiter._retry_redis_at = 0.0  # pause elapsed
    calls = []

    class _Pipe:
        def zremrangebyscore(self, *a): calls.append("zrem")
        def zcard(self, *a): calls.append("zcard")
        async def execute(self): return [0, 0]

    class _Recovered:
        def pipeline(self): return _Pipe()
        async def zadd(self, *a, **k): calls.append("zadd")
        async def expire(self, *a): calls.append("expire")

    limiter._client = _Recovered()
    await limiter.check("a")
    assert "zadd" in calls  # went back to Redis instead of staying local forever
