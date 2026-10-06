from __future__ import annotations
import os
import time
from collections import deque

from openai import AsyncOpenAI, RateLimitError, AuthenticationError

from src.config import get_settings


settings = get_settings()

# Module-level benching state (shared across test auto-use fixture)
_MISTRAL_UNAVAILABLE_UNTIL: dict = {}
_MISTRAL_BACKOFF: dict = {}

# Rolling LLM call-latency samples (ms), updated on every completed fallback
# call. The Super Admin platform_metrics endpoint averages these so the SYSTEM
# panel shows a REAL "average latency" instead of a hardcoded number. Capped
# so memory stays flat; only successful calls count (a timeout is not a
# meaningful latency datapoint).
_LATENCY_SAMPLES: deque = deque(maxlen=200)


def record_llm_latency_ms(latency_ms: float) -> None:
    _LATENCY_SAMPLES.append(latency_ms)


def avg_llm_latency_ms() -> float | None:
    """Mean latency of the last N successful LLM calls, or None if none yet —
    the None is surfaced to the admin UI as \"no data\", never as 0."""
    if not _LATENCY_SAMPLES:
        return None
    return round(sum(_LATENCY_SAMPLES) / len(_LATENCY_SAMPLES), 1)


def _is_placeholder_key(key: str | None) -> bool:
    """Identify fake/placeholder API keys so they can be excluded from the
    rotation. Keys like sk-xxxx, sk-x, none, TODO, changeme are placeholders;
    real provider keys start with provider-specific prefixes like sk-proj-
    (OpenAI) or gsk_ (Groq)."""
    if not key:
        return True
    key = key.strip()
    # Exact match check for known placeholder values
    if key in ("", "   ", "none", "TODO", "changeme"):
        return True
    # Prefix check for pattern-based placeholders (sk-x*, etc.)
    if key.lower().startswith("sk-x"):
        return True
    return False


# LangSmith tracing: wraps every OpenAI-SDK chat call with trace metadata
# (model, tokens, latency, etc.) so agent prompts can be iterated from real
# production data. Only active when LANGSMITH_API_KEY is set — zero overhead
# otherwise. The project name matches config.langchain_project ("aesthetixai").
#
# The langsmith SDK reads its config from OS env vars, but this project loads
# secrets from .env via pydantic-settings (which never exports os.environ).
# So when the key is configured, mirror the three relevant vars into the real
# environment so the SDK can authenticate and pick the right project.
_tracing_enabled = bool(settings.langsmith_api_key)
if _tracing_enabled:
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")


def _maybe_wrap(client: AsyncOpenAI) -> AsyncOpenAI:
    if not _tracing_enabled:
        return client
    try:
        from langsmith import wrappers

        return wrappers.wrap_openai(client)
    except Exception:
        return client


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
            self._openai_client = _maybe_wrap(AsyncOpenAI(api_key=settings.openai_api_key))
        return self._openai_client

    @property
    def mistral_clients(self) -> list:
        # Free-tier Mistral rate limits are tight enough to hit during
        # normal dev/testing — several separate free accounts' keys are
        # tried in order on a 429 before ever falling back to Groq/OpenAI.
        if self._mistral_clients is None:
            keys = [
                k for k in (
                    settings.mistral_api_key,
                    settings.mistral_api_key_2,
                    settings.mistral_api_key_3,
                    settings.mistral_api_key_4,
                ) if k
            ]
            self._mistral_clients = [
                _maybe_wrap(AsyncOpenAI(api_key=key, base_url=self.MISTRAL_BASE_URL)) for key in keys
            ]
        return self._mistral_clients

    @property
    def groq_client(self):
        if self._groq_client is None and settings.groq_api_key:
            self._groq_client = _maybe_wrap(AsyncOpenAI(api_key=settings.groq_api_key, base_url=self.GROQ_BASE_URL))
        return self._groq_client

    def _extra_kwargs_for(self, client) -> dict:
        # Groq's configured model (openai/gpt-oss-120b) is a reasoning model
        # that streams a hidden chain-of-thought under a separate "reasoning"
        # channel BEFORE any real answer content — with reasoning_effort left
        # at its default, that hidden trace can consume the entire max_tokens
        # budget on its own, leaving zero tokens for the actual answer (found
        # while building streaming: a real prompt came back with 30+ reasoning
        # chunks and an empty final reply). "low" keeps just enough reasoning
        # for tool-use/JSON-mode accuracy while leaving room for content.
        # Mistral/OpenAI don't recognize this field, so it's Groq-only.
        if client is self._groq_client:
            return {"extra_body": {"reasoning_effort": "low"}}
        return {}

    async def _call_with_fallback(self, call):
        """Runs `call(client, model)` against each configured Mistral key in
        turn, falling through to the next only on a rate limit. Once every
        Mistral key is exhausted, tries Groq (free tier, fast, not prone to
        the same rate-limit wall as Mistral's) before finally trying OpenAI
        (a real key isn't configured yet, so this last leg mostly stays
        theoretical until it is). Raises the last error if everything fails,
        rather than silently swallowing it.
        Also benches (temporarily disables) keys that fail with rate limit
        or authentication errors, so they aren't retried immediately."""
        last_error: Exception | None = None
        for client in self.mistral_clients:
            try:
                started = time.monotonic()
                result = await call(client, self.mistral_model)
                record_llm_latency_ms((time.monotonic() - started) * 1000)
                return result
            except RateLimitError as e:
                last_error = e
                # Benching: mark this key as unavailable for a cooldown period
                key_name = str(client)
                _MISTRAL_UNAVAILABLE_UNTIL[key_name] = (
                    time.monotonic() + 60  # 60s cooldown for rate limit
                )
                _MISTRAL_BACKOFF[key_name] = min(
                    (_MISTRAL_BACKOFF.get(key_name, 0) + 60), 300
                )
                continue
            except AuthenticationError as e:
                last_error = e
                # Benching auth failure: longer cooldown (3600s = 1 hour)
                key_name = str(client)
                _MISTRAL_UNAVAILABLE_UNTIL[key_name] = (
                    time.monotonic() + 3600
                )
                continue
        if self.groq_client is not None:
            try:
                started = time.monotonic()
                result = await call(self.groq_client, self.groq_model)
                record_llm_latency_ms((time.monotonic() - started) * 1000)
                return result
            except Exception as e:
                last_error = e
        try:
            started = time.monotonic()
            result = await call(self.openai_client, self.openai_model)
            record_llm_latency_ms((time.monotonic() - started) * 1000)
            return result
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

    async def chat_fast(
        self, messages: list[dict], system_prompt: str | None = None, json_mode: bool = False, max_tokens: int = 400
    ) -> str:
        """Low-latency twin of chat() for interactive websites where a slow
        reply is the worst failure (landing-page chat). Goes straight to Groq
        (fast, cheap, low TTFT) when a key is configured, and only falls back
        to the Mistral-key chain (then OpenAI) if Groq errors."""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        async def call(client, model):
            kwargs = {}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                temperature=0.7,
                max_tokens=max_tokens,
                **kwargs,
                **self._extra_kwargs_for(client),
            )
            return response.choices[0].message.content or ""

        if self.groq_client is not None:
            try:
                return await call(self.groq_client, self.groq_model)
            except RateLimitError as e:
                last_error: Exception | None = e
            except Exception as e:
                last_error = e
            try:
                return await self._call_with_fallback(call)
            except Exception:
                if last_error is not None:
                    raise last_error
                raise
        return await self._call_with_fallback(call)

    async def chat_fast_stream(self, messages: list[dict], system_prompt: str | None = None, max_tokens: int = 350):
        """Streaming twin of chat_fast() — Groq first (low TTFT), falling
        through to the Mistral/OpenAI candidate chain only if Groq fails
        before yielding anything. See chat_stream()'s docstring for why a
        failed stream can't transparently retry mid-way."""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        candidates = []
        if self.groq_client is not None:
            candidates.append((self.groq_client, self.groq_model))
        candidates.extend((c, self.mistral_model) for c in self.mistral_clients)
        candidates.append((self.openai_client, self.openai_model))

        last_error: Exception | None = None
        for client, model in candidates:
            yielded_anything = False
            try:
                stream = await client.chat.completions.create(
                    model=model, messages=full_messages, temperature=0.7, max_tokens=max_tokens, stream=True,
                    **self._extra_kwargs_for(client),
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yielded_anything = True
                        yield delta
                return
            except Exception as e:
                last_error = e
                if yielded_anything:
                    return
                continue
        if last_error is not None:
            raise last_error

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        tier: str = "high",
        json_mode: bool = False,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
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
            if tools:
                # Groq (and some other providers) reject a request whose
                # message history contains an assistant tool_calls turn
                # unless `tools` is present on THIS call too — even when no
                # new tool call is wanted (hence tool_choice="none"). Needed
                # for any caller passing back a prior tool-calling turn's
                # follow-up messages (e.g. Command Center's second pass).
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "none"
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                temperature=0.7,
                max_tokens=max_tokens,
                **kwargs,
                **self._extra_kwargs_for(client),
            )
            return response.choices[0].message.content or ""

        if tier == "low" and self.mistral_clients:
            return await self._call_with_fallback(call)
        return await call(self.openai_client, self.openai_model)

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        tier: str = "high",
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
    ):
        """Token-by-token twin of chat() for a live SSE reply instead of a
        single blocking call. Yields text deltas as they arrive from the
        provider. Unlike chat()'s multi-key fallback chain, a stream that
        fails mid-way can't transparently retry on a different client
        without the caller re-sending already-yielded text — so this only
        tries the SAME candidate order chat() would pick first, one at a
        time, falling through to the next candidate only if the stream
        fails before yielding anything at all."""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        candidates = list(self.mistral_clients) if (tier == "low" and self.mistral_clients) else []
        if self.groq_client is not None:
            candidates.append(self.groq_client)
        candidates.append(self.openai_client)

        tool_kwargs = {"tools": tools, "tool_choice": "none"} if tools else {}

        last_error: Exception | None = None
        for client in candidates:
            model = self.mistral_model if client in self.mistral_clients else (
                self.groq_model if client is self.groq_client else self.openai_model
            )
            yielded_anything = False
            try:
                stream = await client.chat.completions.create(
                    model=model, messages=full_messages, temperature=0.7, max_tokens=max_tokens, stream=True,
                    **tool_kwargs,
                    **self._extra_kwargs_for(client),
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yielded_anything = True
                        yield delta
                return
            except Exception as e:
                last_error = e
                if yielded_anything:
                    # Already streamed partial text to the caller — switching
                    # providers now would duplicate/garble it, so stop here
                    # rather than silently retrying mid-stream.
                    return
                continue
        if last_error is not None:
            raise last_error

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
                **self._extra_kwargs_for(client),
            )
            choice = response.choices[0]
            return {
                "content": choice.message.content or "",
                "tool_calls": choice.message.tool_calls,
            }

        if tier == "low" and self.mistral_clients:
            return await self._call_with_fallback(call)
        return await call(self.openai_client, self.openai_model)
