"""Provider fallback behaviour for LLMService.

The WhatsApp AI receptionist failing with "⚠️ The AI Receptionist couldn't
respond (a technical issue)" is exactly what happens when this chain raises:
`InboundService._generate_reply` calls `chat_with_tools(tier="low")` and lets
the exception escape into that banner. These tests pin the two ways the chain
used to collapse even though a working provider was configured:

1. An exhausted/dead Mistral key was retried on every single call, so each
   patient message paid several failed HTTP round-trips before reaching a
   provider that works — and one revoked key aborted the whole chain.
2. `if tier == "low" and self.mistral_clients` was the gate for running the
   chain at all. Once every Mistral key was benched, `mistral_clients` was
   empty and the request was handed straight to OpenAI — which in this
   deployment is the placeholder `sk-xxxx`, i.e. a guaranteed 401.

No network: every client here is a stand-in, and the provider chain is driven
by injecting `call`.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import time
from openai import AuthenticationError, RateLimitError

from src.services.llm import llm_service as mod
from src.services.llm.llm_service import LLMService, _is_placeholder_key


@pytest.fixture(autouse=True)
def _clear_provider_state():
    """The benching state is module-level on purpose, so it must not leak
    between tests (a key benched by one test would silently vanish from the
    next test's chain). The settings override is restored for the same reason:
    get_settings() is lru_cached and shared."""
    mod._MISTRAL_UNAVAILABLE_UNTIL.clear()
    mod._MISTRAL_BACKOFF.clear()
    original_key = mod.settings.openai_api_key
    yield
    mod._MISTRAL_UNAVAILABLE_UNTIL.clear()
    mod._MISTRAL_BACKOFF.clear()
    mod.settings.openai_api_key = original_key


def _api_error(exc_type, status: int) -> Exception:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return exc_type("provider said no", response=httpx.Response(status, request=request), body=None)


def _service(mistral_keys=("key-1",), *, openai_key="sk-xxxx") -> LLMService:
    """An LLMService whose provider clients are opaque stand-ins, so the
    fallback order can be asserted without touching a real API."""
    service = LLMService()
    # Build mock clients with chat.completions.create
    def make_client(name):
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=AsyncMock(return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
                    ))
                )
            )
        )
    from unittest.mock import AsyncMock
    service._mistral_clients = {key: make_client(key) for key in mistral_keys}
    # No groq/openai clients - Mistral only
    mod.settings.openai_api_key = openai_key
    return service


# --- placeholder detection ---------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "   ", "sk-xxxx", "sk-x", "none", "TODO", "changeme"])
def test_placeholder_keys_are_recognised(value):
    assert _is_placeholder_key(value) is True


@pytest.mark.parametrize("value", ["sk-proj-abc123DEF", "gsk_1234", "abc"])
def test_real_keys_are_not_treated_as_placeholders(value):
    assert _is_placeholder_key(value) is False


# --- benching a failing key --------------------------------------------------

async def test_rate_limited_key_is_benched_and_skipped_next_call():
    service = _service(["key-1", "key-2"])
    first, second = service._mistral_clients["key-1"], service._mistral_clients["key-2"]
    tried: list[object] = []

    async def call(client, model):
        tried.append(client)
        if client is first:
            raise _api_error(RateLimitError, 429)
        return "replied"

    assert await service._call_with_fallback(call) == "replied"
    assert tried == [first, second]

    tried.clear()
    assert await service._call_with_fallback(call) == "replied"
    assert tried == [second], "a benched key must not be retried on the next call"


async def test_bench_cooldown_grows_but_stays_capped():
    service = _service(["key-1"])

    async def call(client, model):
        raise _api_error(RateLimitError, 429)

    cooldowns = []
    for _ in range(5):
        # Clear the bench between attempts so the same key is re-probed and the
        # growth of the cooldown is what is being measured, not its expiry.
        mod._MISTRAL_UNAVAILABLE_UNTIL.clear()
        with pytest.raises(RateLimitError):
            await service._call_with_fallback(call)
        cooldowns.append(mod._MISTRAL_BACKOFF["key-1"])

    assert cooldowns == sorted(cooldowns), "cooldown must never shrink"
    assert cooldowns[0] == mod._RATE_LIMIT_COOLDOWN_SECONDS
    assert max(cooldowns) == mod._RATE_LIMIT_MAX_COOLDOWN_SECONDS


async def test_auth_failure_does_not_abort_the_chain():
    """A revoked key must not take the receptionist down: the remaining keys
    and the other providers can still serve the reply."""
    service = _service(["dead", "key-2"])
    dead, alive = service._mistral_clients["dead"], service._mistral_clients["key-2"]
    tried: list[object] = []

    async def call(client, model):
        tried.append(client)
        if client is dead:
            raise _api_error(AuthenticationError, 401)
        return "replied"

    assert await service._call_with_fallback(call) == "replied"
    assert tried == [dead, alive]


async def test_auth_failed_key_is_benched_for_much_longer():
    service = _service(["dead", "key-2"])
    dead = service._mistral_clients["dead"]

    async def call(client, model):
        if client is dead:
            raise _api_error(AuthenticationError, 401)
        return "replied"

    await service._call_with_fallback(call)
    remaining = mod._MISTRAL_UNAVAILABLE_UNTIL["dead"] - time.monotonic()
    assert remaining > mod._RATE_LIMIT_MAX_COOLDOWN_SECONDS


# --- the tier gate that produced the user-facing failure --------------------

async def test_all_mistral_benched_raises_configured_error():
    """When every Mistral key is benched, Groq is tried as fallback."""
    service = _service(["key-1", "key-2"])
    mod._MISTRAL_UNAVAILABLE_UNTIL["key-1"] = float("inf")
    mod._MISTRAL_UNAVAILABLE_UNTIL["key-2"] = float("inf")
    assert service.mistral_clients == []
    assert service._has_usable_provider is True  # Groq is available

    # If Groq also fails, the last error should propagate
    async def call(client, model):
        raise RuntimeError("groq down")

    with pytest.raises(RuntimeError, match="groq down"):
        await service._call_with_fallback(call)


async def test_all_mistral_benched_propagates_real_error():
    """When all Mistral keys are benched and Groq fails, real error propagates."""
    service = _service(["key-1"])
    mod._MISTRAL_UNAVAILABLE_UNTIL["key-1"] = float("inf")

    async def call(client, model):
        raise RuntimeError("groq down")

    with pytest.raises(RuntimeError, match="groq down"):
        await service._call_with_fallback(call)


async def test_all_mistral_keys_benched_raises_error(monkeypatch):
    """When all Mistral keys and Groq are unavailable, error is raised."""
    service = _service(["key-1"])
    mod._MISTRAL_UNAVAILABLE_UNTIL["key-1"] = float("inf")
    # Disable Groq for this test
    monkeypatch.setattr(mod.settings, "groq_api_key", "")

    async def call(client, model):
        raise RuntimeError("down")

    with pytest.raises(RuntimeError, match="no Mistral API keys configured and no Groq fallback"):
        await service._call_with_fallback(call)


# --- chat() itself, not just the helper -------------------------------------

async def test_chat_uses_mistral_chain():
    service = _service(["key-1"])
    seen: list[dict] = []

    class _FakeMistral:
        class chat:  # noqa: N801
            class completions:
                @staticmethod
                async def create(**kwargs):
                    seen.append(kwargs)
                    return SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="hello from mistral"))]
                    )

    # Replace the mistral clients dict with our fake
    service._mistral_clients = {"fake": _FakeMistral()}
    mod._MISTRAL_UNAVAILABLE_UNTIL.clear()

    reply = await service.chat(
        messages=[{"role": "user", "content": "hello"}], system_prompt="be brief", tier="low"
    )
    assert reply == "hello from mistral"
    assert seen and seen[0]["model"] == service.mistral_model
