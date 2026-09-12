from __future__ import annotations
from openai import AsyncOpenAI, RateLimitError

from src.config import get_settings

settings = get_settings()


class LLMService:
    # Mistral's and Groq's chat completions endpoints are both OpenAI-SDK
    # compatible, so this reuses the same client class pointed at different
    # base_urls instead of adding new SDK dependencies.
    MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self):
        self._openai_client = None
        self._mistral_clients = None
        self._groq_client = None
        self.openai_model = settings.openai_model
        self.mistral_model = settings.mistral_model
        self.groq_model = settings.groq_model

    @property
    def openai_client(self):
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    @property
    def mistral_clients(self) -> list:
        # Free-tier Mistral rate limits are tight enough to hit during
        # normal dev/testing — several separate free accounts' keys are
        # tried in order on a 429 before ever falling back to Groq/OpenAI.
        if self._mistral_clients is None:
            keys = [k for k in (settings.mistral_api_key, settings.mistral_api_key_2, settings.mistral_api_key_3) if k]
            self._mistral_clients = [
                AsyncOpenAI(api_key=key, base_url=self.MISTRAL_BASE_URL) for key in keys
            ]
        return self._mistral_clients

    @property
    def groq_client(self):
        if self._groq_client is None and settings.groq_api_key:
            self._groq_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=self.GROQ_BASE_URL)
        return self._groq_client

    async def _call_with_fallback(self, call):
        """Runs `call(client, model)` against each configured Mistral key in
        turn, falling through to the next only on a rate limit. Once every
        Mistral key is exhausted, tries Groq (free tier, fast, not prone to
        the same rate-limit wall as Mistral's) before finally trying OpenAI
        (a real key isn't configured yet, so this last leg mostly stays
        theoretical until it is). Raises the last error if everything fails,
        rather than silently swallowing it."""
        last_error: Exception | None = None
        for client in self.mistral_clients:
            try:
                return await call(client, self.mistral_model)
            except RateLimitError as e:
                last_error = e
                continue
        if self.groq_client is not None:
            try:
                return await call(self.groq_client, self.groq_model)
            except Exception as e:
                last_error = e
        try:
            return await call(self.openai_client, self.openai_model)
        except Exception:
            if last_error is not None:
                raise last_error
            raise

    def _client_and_model(self, tier: str):
        # Matches the tiered strategy documented in system.md: low-stakes
        # traffic (FAQ, translation, general chat) rides Mistral's free tier;
        # high/critical-stakes traffic (risk assessment, payments, clinical
        # notes) always goes straight to OpenAI. Kept for callers that only
        # need a single client (not the multi-key fallback in chat()/
        # chat_with_tools()).
        if tier == "low" and self.mistral_clients:
            return self.mistral_clients[0], self.mistral_model
        return self.openai_client, self.openai_model

    async def chat(
        self, messages: list[dict], system_prompt: str | None = None, tier: str = "high", json_mode: bool = False, max_tokens: int = 1024
    ) -> str:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        async def call(client, model):
            kwargs = {}
            if json_mode:
                # Mistral, Groq, and OpenAI all support this OpenAI-shaped
                # param — constrains the model to emit valid JSON instead of
                # trusting a prompt instruction alone, which a small/free
                # model can and does drift from under load.
                kwargs["response_format"] = {"type": "json_object"}
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                temperature=0.7,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content or ""

        if tier == "low" and self.mistral_clients:
            return await self._call_with_fallback(call)
        return await call(self.openai_client, self.openai_model)

    async def chat_with_tools(
        self, messages: list[dict], tools: list[dict], system_prompt: str | None = None, tier: str = "high", max_tokens: int = 1024
    ) -> dict:
        # Originally OpenAI-only (bookings/escalations are always high-stakes).
        # The Command Center orchestrator (services/command_center/) also
        # needs tool-calling but for low-stakes read-only queries, so this now
        # accepts the same `tier` routing chat() uses — tier="low" runs on
        # Mistral (OpenAI-compatible tool-calling) while a real OPENAI_API_KEY
        # is still a placeholder; switches automatically once that key is real.
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        async def call(client, model):
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                tools=tools,
                temperature=0.7,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            return {
                "content": choice.message.content or "",
                "tool_calls": choice.message.tool_calls,
            }

        if tier == "low" and self.mistral_clients:
            return await self._call_with_fallback(call)
        return await call(self.openai_client, self.openai_model)
