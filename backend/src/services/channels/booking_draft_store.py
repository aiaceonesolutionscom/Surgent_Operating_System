from __future__ import annotations
import json
import logging
from uuid import UUID

import redis.asyncio as redis

from src.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class BookingDraftStore:
    """Redis-backed scratch state for an in-progress WhatsApp booking
    conversation — whichever of date/time/appointment_type have been
    collected so far. Without this, each turn's system prompt made the LLM
    re-derive "what do we already know" from the raw message history, which
    is exactly where a live conversation went wrong: a patient's "may in the
    evening" got misread as the month, and an already-confirmed time got
    re-asked for after an unrelated turn. Reading the draft back and putting
    it in the prompt as plain structured fields removes that guesswork.

    Expires on its own (2 days) so an abandoned booking attempt doesn't
    linger in Redis forever — it isn't meant to be durable state, just a
    short-lived scratchpad for one back-and-forth."""

    _TTL_SECONDS = 60 * 60 * 24 * 2

    def __init__(self):
        self._client = None

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

    def _key(self, conversation_id: UUID | str) -> str:
        return f"booking_draft:{conversation_id}"

    async def get(self, conversation_id: UUID | str) -> dict:
        # Redis is a nice-to-have here, not a hard dependency of the booking
        # flow — if it's unreachable, degrade to "no draft known yet"
        # instead of breaking the AI reply entirely.
        try:
            raw = await self.client.get(self._key(conversation_id))
            return json.loads(raw) if raw else {}
        except Exception:
            logger.warning("BookingDraftStore.get failed, continuing without draft state", exc_info=True)
            return {}

    async def merge(self, conversation_id: UUID | str, **fields: str | None) -> dict:
        """Merges non-empty fields into the stored draft and returns the
        resulting draft."""
        try:
            current = await self.get(conversation_id)
            for k, v in fields.items():
                if v:
                    current[k] = v
            await self.client.set(self._key(conversation_id), json.dumps(current), ex=self._TTL_SECONDS)
            return current
        except Exception:
            logger.warning("BookingDraftStore.merge failed, continuing without persisting draft", exc_info=True)
            return {k: v for k, v in fields.items() if v}

    async def clear(self, conversation_id: UUID | str) -> None:
        try:
            await self.client.delete(self._key(conversation_id))
        except Exception:
            logger.warning("BookingDraftStore.clear failed", exc_info=True)

    async def clear_field(self, conversation_id: UUID | str, field: str) -> dict:
        try:
            current = await self.get(conversation_id)
            current.pop(field, None)
            await self.client.set(self._key(conversation_id), json.dumps(current), ex=self._TTL_SECONDS)
            return current
        except Exception:
            logger.warning("BookingDraftStore.clear_field failed", exc_info=True)
            return {}
