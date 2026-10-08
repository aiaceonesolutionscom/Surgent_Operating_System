from __future__ import annotations
import os
import time

from openai import AsyncOpenAI, RateLimitError, AuthenticationError

from src.config import get_settings
from src.services.llm.tracing import configure_langsmith_env
from src.services.telemetry import recorder as telemetry


settings = get_settings()

# Module-level benching state (shared across test auto-use fixture)
_MISTRAL_UNAVAILABLE_UNTIL: dict = {}
_MISTRAL_BACKOFF: dict = {}

# A rate-limited Mistral key sits out its cooldown instead of being retried on
# every call (each retry is a failed HTTP round trip before a working provider
# is reached). Repeated 429s lengthen the cooldown up to the cap; a rejected
# key (revoked / wrong) is benched far longer since waiting won't fix it.
_RATE_LIMIT_COOLDOWN_SECONDS = 60
_RATE_LIMIT_MAX_COOLDOWN_SECONDS = 300
_AUTH_FAILURE_COOLDOWN_SECONDS = 3600

def _approx_tokens(text: str) -> int:
    """Rough token count (~4 characters each) for providers/streams that don't
    return a usage block. Flagged as an estimate wherever it is stored."""
    return max(1, len(text) // 4)


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
# production data. Only active when LANGSMITH_API_KEY is set and tracing has
# not been explicitly switched off - zero overhead otherwise. The env wiring
# (key, tracing flag, per-environment project name) lives in tracing.py, which
# derives the project instead of trusting a hand-set one: a stale project name
# must never route production traces into a development project.
_tracing_enabled = configure_langsmith_env()


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
        """The OpenAI client, or None when no real OPENAI_API_KEY is configured.
        AsyncOpenAI("") raises at construction, which used to blow up every
        candidate list before Groq/Mistral were even tried - so a deployment
        with only Groq/Mistral keys could not answer a single message."""
        if _is_placeholder_key(settings.openai_api_key):
            return None
        if self._openai_client is None:
            self._openai_client = _maybe_wrap(AsyncOpenAI(api_key=settings.openai_api_key))
        return self._openai_client

    @property
    def _mistral_by_label(self) -> dict:
        """Every configured Mistral key's client, keyed by a non-secret label
        (mistral-1, mistral-2, ...) — the label is what bench state and logs
        use, so a key never ends up in a dict key or a log line."""
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
            self._mistral_clients = {
                f"mistral-{i}": _maybe_wrap(AsyncOpenAI(api_key=key, base_url=self.MISTRAL_BASE_URL))
                for i, key in enumerate(keys, start=1)
            }
        return self._mistral_clients

    def _usable_mistral(self) -> list[tuple[str, object]]:
        """(label, client) for each Mistral key that isn't sitting out a cooldown."""
        now = time.monotonic()
        return [
            (label, client)
            for label, client in self._mistral_by_label.items()
            if _MISTRAL_UNAVAILABLE_UNTIL.get(label, 0) <= now
        ]

    @property
    def mistral_clients(self) -> list:
        return [client for _, client in self._usable_mistral()]

    @property
    def _has_usable_provider(self) -> bool:
        """False only when no provider could possibly answer: every Mistral
        key benched or absent, no Groq key, and OpenAI still a placeholder."""
        return bool(
            self.mistral_clients
            or self.groq_client is not None
            or not _is_placeholder_key(settings.openai_api_key)
        )

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

    def _provider_for(self, client) -> str:
        if client is self._groq_client:
            return "groq"
        if any(client is c for c in (self._mistral_clients or {}).values()):
            return "mistral"
        return "openai"

    async def _create(self, client, model, **kwargs):
        """Every provider request in this service goes through here, so each
        one — success, rate limit or failure, streamed or not — is recorded
        for the Super Admin AI figures (latency, tokens, list-price cost).
        Recording only appends to an in-memory buffer; it can't slow or fail
        the request."""
        provider = self._provider_for(client)
        source = telemetry.infer_source()
        streaming = bool(kwargs.get("stream"))
        started = time.monotonic()
        try:
            response = await client.chat.completions.create(model=model, **kwargs)
        except Exception as exc:
            telemetry.record_llm_call(
                provider=provider, model=model, source=source, streaming=streaming,
                status="rate_limited" if isinstance(exc, RateLimitError) else "error",
                latency_ms=(time.monotonic() - started) * 1000,
            )
            raise

        if streaming:
            return self._metered_stream(response, provider, model, source, started, kwargs.get("messages") or [])

        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        estimated = prompt_tokens is None or completion_tokens is None
        if estimated:
            prompt_tokens = _approx_tokens(str(kwargs.get("messages") or ""))
            text = response.choices[0].message.content or "" if response.choices else ""
            completion_tokens = _approx_tokens(text)
        telemetry.record_llm_call(
            provider=provider, model=model, source=source, streaming=False, status="ok",
            latency_ms=(time.monotonic() - started) * 1000,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, tokens_estimated=estimated,
        )
        return response

    async def _metered_stream(self, stream, provider, model, source, started, messages):
        """Pass chunks straight through, recording the call once the stream
        ends (or the consumer stops reading). Uses the provider's usage block
        when a chunk carries one, otherwise a characters/4 estimate."""
        usage = None
        chars = 0
        failed = False
        try:
            async for chunk in stream:
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None and getattr(chunk_usage, "prompt_tokens", None) is not None:
                    usage = chunk_usage
                if chunk.choices:
                    chars += len(chunk.choices[0].delta.content or "")
                yield chunk
        except Exception:
            failed = True
            raise
        finally:
            estimated = usage is None
            telemetry.record_llm_call(
                provider=provider, model=model, source=source, streaming=True,
                status="error" if failed else "ok",
                latency_ms=(time.monotonic() - started) * 1000,
                prompt_tokens=usage.prompt_tokens if usage else _approx_tokens(str(messages)),
                completion_tokens=usage.completion_tokens if usage else max(1, chars // 4) if chars else 0,
                tokens_estimated=estimated,
            )

    @staticmethod
    def _bench(label: str, error: Exception) -> None:
        """Take a failing Mistral key out of rotation for a cooldown."""
        now = time.monotonic()
        if isinstance(error, AuthenticationError):
            _MISTRAL_UNAVAILABLE_UNTIL[label] = now + _AUTH_FAILURE_COOLDOWN_SECONDS
            return
        cooldown = min(
            _MISTRAL_BACKOFF.get(label, 0) + _RATE_LIMIT_COOLDOWN_SECONDS,
            _RATE_LIMIT_MAX_COOLDOWN_SECONDS,
        )
        _MISTRAL_BACKOFF[label] = cooldown
        _MISTRAL_UNAVAILABLE_UNTIL[label] = now + cooldown

    async def _call_with_fallback(self, call):
        """Runs `call(client, model)` against each Mistral key that is not
        benched, in turn. A rate-limited or rejected key is benched (see
        `_bench`) and the next one is tried; once Mistral is exhausted Groq
        is tried (free tier, fast, not prone to the same rate-limit wall),
        then OpenAI — but only if its key is real, since a placeholder key is
        a guaranteed 401. Raises the last provider error if everything
        fails, rather than silently swallowing it."""
        if not self._has_usable_provider:
            raise RuntimeError(
                "no Mistral API keys configured and no Groq fallback — every Mistral key is "
                "missing or cooling down, GROQ_API_KEY is unset and OPENAI_API_KEY is a placeholder"
            )

        last_error: Exception | None = None
        for label, client in self._usable_mistral():
            try:
                return await call(client, self.mistral_model)
            except (RateLimitError, AuthenticationError) as e:
                last_error = e
                self._bench(label, e)
                continue
        if self.groq_client is not None:
            try:
                return await call(self.groq_client, self.groq_model)
            except Exception as e:
                last_error = e
        if self.openai_client is not None:
            try:
                return await call(self.openai_client, self.openai_model)
            except Exception:
                if last_error is not None:
                    raise last_error
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("no LLM provider produced a reply")

    def _client_and_model(self, tier: str):
        # Matches the tiered strategy documented in system.md: low-stakes
        # traffic (FAQ, translation, general chat) rides Mistral's free tier;
        # high/critical-stakes traffic (risk assessment, payments, clinical
        # notes) always goes straight to OpenAI. Kept for callers that only
        # need a single client (not the multi-key fallback in chat()/
        # chat_with_tools()).
        if tier == "low" and self.mistral_clients:
            return self.mistral_clients[0], self.mistral_model
        if self.openai_client is not None:
            return self.openai_client, self.openai_model
        # No OpenAI key: use whichever configured provider is available.
        if self.groq_client is not None:
            return self.groq_client, self.groq_model
        if self.mistral_clients:
            return self.mistral_clients[0], self.mistral_model
        raise RuntimeError("no LLM provider is configured")

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
            response = await self._create(
                client, model,
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
        if self.openai_client is not None:
            candidates.append((self.openai_client, self.openai_model))

        last_error: Exception | None = None
        for client, model in candidates:
            yielded_anything = False
            try:
                stream = await self._create(
                    client, model, messages=full_messages, temperature=0.7, max_tokens=max_tokens, stream=True,
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
            response = await self._create(
                client, model,
                messages=full_messages,
                temperature=0.7,
                max_tokens=max_tokens,
                **kwargs,
                **self._extra_kwargs_for(client),
            )
            return response.choices[0].message.content or ""

        if tier == "low" or self.openai_client is None:
            # Low-stakes traffic rides the free providers; and without an OpenAI
            # key, "high" traffic has nowhere else to go than the same chain.
            # (_call_with_fallback raises a clear error if nothing is usable.)
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
        if self.openai_client is not None:
            candidates.append(self.openai_client)

        tool_kwargs = {"tools": tools, "tool_choice": "none"} if tools else {}

        last_error: Exception | None = None
        for client in candidates:
            model = self.mistral_model if client in self.mistral_clients else (
                self.groq_model if client is self.groq_client else self.openai_model
            )
            yielded_anything = False
            try:
                stream = await self._create(
                    client, model, messages=full_messages, temperature=0.7, max_tokens=max_tokens, stream=True,
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
            response = await self._create(
                client, model,
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

        if tier == "low" or self.openai_client is None:
            # Low-stakes traffic rides the free providers; and without an OpenAI
            # key, "high" traffic has nowhere else to go than the same chain.
            # (_call_with_fallback raises a clear error if nothing is usable.)
            return await self._call_with_fallback(call)
        return await call(self.openai_client, self.openai_model)
