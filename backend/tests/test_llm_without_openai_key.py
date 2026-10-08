"""A deployment that has Groq / Mistral keys but NO OpenAI key must still answer.

`AsyncOpenAI(api_key="")` raises at construction. The candidate lists used to
build the OpenAI client unconditionally, so every chat and every stream died
with "Missing credentials ... OPENAI_API_KEY" before Groq was even tried - the
site's AI chat was dead on arrival with only a Groq key configured."""

from types import SimpleNamespace

import pytest

from src.services.llm import llm_service as mod
from src.services.llm.llm_service import LLMService


@pytest.fixture(autouse=True)
def _no_openai_key(monkeypatch):
    monkeypatch.setattr(mod.settings, "openai_api_key", "")
    mod._MISTRAL_UNAVAILABLE_UNTIL.clear()
    mod._MISTRAL_BACKOFF.clear()


def _reply(text):
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
    )


class _FakeGroq:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            async def gen():
                for piece in ("Hel", "lo"):
                    yield SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content=piece))])
            return gen()
        return _reply("hello from groq")


def _service(groq=True):
    service = LLMService()
    service._mistral_clients = {}
    service._groq_client = _FakeGroq() if groq else None
    return service


def test_openai_client_is_none_not_a_crash():
    assert LLMService().openai_client is None


async def test_streaming_reaches_groq_without_an_openai_key():
    service = _service()
    pieces = [p async for p in service.chat_stream([{"role": "user", "content": "hi"}], tier="high")]
    assert "".join(pieces) == "Hello"


async def test_fast_streaming_reaches_groq_without_an_openai_key():
    service = _service()
    pieces = [p async for p in service.chat_fast_stream([{"role": "user", "content": "hi"}])]
    assert "".join(pieces) == "Hello"


@pytest.mark.parametrize("tier", ["low", "high"])
async def test_chat_uses_groq_for_every_tier_without_an_openai_key(tier):
    service = _service()
    assert await service.chat([{"role": "user", "content": "hi"}], tier=tier) == "hello from groq"


async def test_with_no_provider_at_all_the_error_says_so(monkeypatch):
    service = _service(groq=False)
    monkeypatch.setattr(mod.settings, "groq_api_key", "")
    with pytest.raises(RuntimeError, match="no Mistral API keys configured and no Groq fallback"):
        await service.chat([{"role": "user", "content": "hi"}], tier="high")
