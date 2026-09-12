from __future__ import annotations

import io
import logging

import httpx
from openai import AsyncOpenAI

from src.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SpeechService:
    """Speech-to-text with Deepgram Nova-3 as primary and Groq Whisper as
    fallback. Deepgram is faster (<300ms) and more accurate on noisy phone
    audio; Groq Whisper is free and works as a reliable backup.

    Used for: WhatsApp voice note transcription, doctor voice-dictation,
    and any future voice message handling.
    """

    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self):
        self._groq_client = None

    @property
    def groq_client(self):
        if self._groq_client is None:
            self._groq_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=self.GROQ_BASE_URL)
        return self._groq_client

    @property
    def is_configured(self) -> bool:
        return bool(settings.deepgram_api_key or settings.groq_api_key)

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav", language: str | None = None) -> str:
        """Transcribes audio to text. Tries Deepgram first, falls back to
        Groq Whisper. `filename`'s extension hints the format to the API."""
        if settings.deepgram_api_key:
            try:
                return await self._transcribe_deepgram(audio_bytes, filename, language)
            except Exception:
                logger.exception("Deepgram transcription failed, falling back to Groq")

        if settings.groq_api_key:
            return await self._transcribe_groq(audio_bytes, filename, language)

        logger.error("No STT provider configured (neither DEEPGRAM_API_KEY nor GROQ_API_KEY)")
        return ""

    async def _transcribe_deepgram(
        self, audio_bytes: bytes, filename: str, language: str | None = None
    ) -> str:
        """Transcribe via Deepgram Nova-3 REST API."""
        # Detect content type from filename extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
        content_type_map = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "opus": "audio/ogg",
            "m4a": "audio/mp4",
            "webm": "audio/webm",
            "mp4": "audio/mp4",
        }
        content_type = content_type_map.get(ext, "audio/wav")

        params = {
            "model": settings.deepgram_model or "nova-3",
            "smart_format": "true",
            "diarize": "false",
        }
        if language:
            params["language"] = language

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": content_type,
                },
                params=params,
                content=audio_bytes,
            )
            resp.raise_for_status()
            data = resp.json()

        alternatives = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [])
        if alternatives:
            return alternatives[0].get("transcript", "")
        return ""

    async def _transcribe_groq(
        self, audio_bytes: bytes, filename: str, language: str | None = None
    ) -> str:
        """Transcribe via Groq's hosted Whisper endpoint."""
        response = await self.groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=(filename, audio_bytes),
            language=language,
        )
        return response.text
