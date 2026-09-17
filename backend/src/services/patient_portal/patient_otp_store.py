from __future__ import annotations
import logging
import secrets
import time

from src.config import get_settings
from src.server.exceptions import AppException
from src.utils.phone import normalize_phone as _normalize_phone

settings = get_settings()
logger = logging.getLogger(__name__)

_TTL_SECONDS = 10 * 60
_CODE_LENGTH = 6


class PatientOtpStore:
    """Hybrid OTP store: tries Redis first, falls back to in-memory dict
    in development mode when Redis is unreachable. In production, Redis
    failure still raises an error (fail-closed for security)."""

    def __init__(self):
        self._client = None
        self._memory_store: dict[str, tuple[str, float]] = {}
        self._redis_available: bool | None = None

    @property
    def client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
            except Exception:
                logger.warning("Could not initialize Redis client")
                self._client = None
        return self._client

    def _key(self, phone: str) -> str:
        return f"patient_otp:{_normalize_phone(phone)}"

    async def generate(self, phone: str) -> str:
        code = "".join(str(secrets.randbelow(10)) for _ in range(_CODE_LENGTH))
        key = self._key(phone)

        # Try Redis first
        if self.client is not None:
            try:
                await self.client.set(key, code, ex=_TTL_SECONDS)
                self._redis_available = True
                return code
            except Exception:
                if self._redis_available is not False:
                    logger.warning("Redis unavailable, falling back to in-memory OTP store")
                self._redis_available = False

        # Fallback to in-memory (dev mode only)
        if settings.app_env == "development":
            self._memory_store[key] = (code, time.time() + _TTL_SECONDS)
            logger.debug("OTP stored in memory for phone lookup (dev mode)")
            return code

        # Production: fail closed
        raise AppException("Couldn't generate a login code right now — try again shortly.")

    async def verify(self, phone: str, code: str) -> bool:
        key = self._key(phone)

        # Try Redis first
        if self.client is not None and self._redis_available is not False:
            try:
                stored = await self.client.get(key)
                if stored is not None:
                    if secrets.compare_digest(stored, code.strip()):
                        try:
                            await self.client.delete(key)
                        except Exception:
                            logger.warning("OTP verified but failed to delete from Redis")
                        return True
                    return False
            except Exception:
                pass

        # Fallback to in-memory
        entry = self._memory_store.get(key)
        if entry is None:
            return False
        stored_code, expires_at = entry
        if time.time() > expires_at:
            del self._memory_store[key]
            return False
        if secrets.compare_digest(stored_code, code.strip()):
            del self._memory_store[key]
            return True
        return False
