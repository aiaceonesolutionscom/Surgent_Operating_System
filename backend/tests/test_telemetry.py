"""Persisted platform telemetry: LLM call metering, request/slow-query counters,
and the write-behind flush that makes the Super Admin figures survive restarts.

No network and no real provider: the "client" is a stand-in that returns
OpenAI-shaped responses, so what is under test is our own bookkeeping.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import RateLimitError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.database import Base
from src.models.platform_telemetry import LlmCall, SlowQueryLog, SystemMetricBucket
from src.server import runtime_metrics
from src.services.llm.llm_service import LLMService
from src.services.telemetry import recorder
from src.services.telemetry.pricing import estimate_cost_usd


@pytest.fixture(autouse=True)
def _clean_buffers():
    """Telemetry buffers are module-level by design (they are process-wide),
    so every test starts and ends with them empty."""
    runtime_metrics.drain()
    recorder._llm_buffer.clear()
    yield
    runtime_metrics.drain()
    recorder._llm_buffer.clear()
    recorder.current_practice_id.set(None)


@pytest.fixture
async def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _response(prompt_tokens=120, completion_tokens=30, text="hello"):
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
    )


class _FakeClient:
    """Stands in for an AsyncOpenAI client."""

    def __init__(self, outcome):
        self._outcome = outcome
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


# --- pricing -----------------------------------------------------------------

def test_cost_is_tokens_times_list_price():
    # 1M input + 1M output of gpt-oss-120b = $0.15 + $0.60
    assert estimate_cost_usd("groq", "openai/gpt-oss-120b", 1_000_000, 1_000_000) == Decimal("0.750000")


def test_unlisted_model_is_costed_at_provider_default_not_free():
    assert estimate_cost_usd("openai", "some-new-model", 1_000_000, 0) == Decimal("2.500000")


# --- runtime counters --------------------------------------------------------

def test_request_counters_feed_the_flush_deltas():
    runtime_metrics.record_request(40, 200)
    runtime_metrics.record_request(900, 200)   # slow
    runtime_metrics.record_request(10, 503)    # error
    deltas, _ = runtime_metrics.drain()
    assert deltas["requests"] == 3
    assert deltas["errors_5xx"] == 1
    assert deltas["slow_requests"] == 1
    assert deltas["total_duration_ms"] == 950
    # drained: the next drain starts from zero
    assert runtime_metrics.drain()[0]["requests"] == 0


def test_slow_queries_are_normalised_so_one_shape_hashes_once():
    runtime_metrics.record_query(450, "SELECT *\n  FROM patients WHERE id IN ($1, $2, $3)")
    runtime_metrics.record_query(500, "SELECT * FROM patients WHERE id IN ($1, $2, $3, $4, $5)")
    runtime_metrics.record_query(5, "SELECT 1")  # fast: counted, not logged
    deltas, slow = runtime_metrics.drain()
    assert deltas["db_queries"] == 3
    assert deltas["slow_queries"] == 2
    assert len(slow) == 2
    assert slow[0]["statement_hash"] == slow[1]["statement_hash"]
    assert slow[0]["statement"] == "SELECT * FROM patients WHERE id IN (?, ...)"


def test_restore_puts_a_failed_batch_back():
    runtime_metrics.record_request(10, 200)
    deltas, slow = runtime_metrics.drain()
    runtime_metrics.restore(deltas, slow)
    assert runtime_metrics.pending()["requests"] == 1


# --- LLM metering ------------------------------------------------------------

async def test_successful_call_records_usage_latency_and_cost():
    llm = LLMService()
    client = _FakeClient(_response(prompt_tokens=1_000_000, completion_tokens=1_000_000))
    recorder.set_current_practice(uuid4())

    await llm._create(client, "gpt-oss-120b", messages=[{"role": "user", "content": "hi"}])

    (row,) = recorder._llm_buffer
    assert row["status"] == "ok"
    assert row["prompt_tokens"] == 1_000_000
    assert row["cost_usd"] == Decimal("0.750000")
    assert row["practice_id"] == recorder.current_practice_id.get()
    assert row["tokens_estimated"] is False


async def test_missing_usage_block_is_estimated_and_flagged():
    llm = LLMService()
    response = SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content="x" * 400))])
    await llm._create(_FakeClient(response), "mistral-small-latest", messages=[{"role": "user", "content": "hi"}])
    (row,) = recorder._llm_buffer
    assert row["tokens_estimated"] is True
    assert row["completion_tokens"] == 100


async def test_rate_limited_attempt_is_recorded_and_still_raised():
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    error = RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    llm = LLMService()

    with pytest.raises(RateLimitError):
        await llm._create(_FakeClient(error), "mistral-small-latest", messages=[])

    (row,) = recorder._llm_buffer
    assert row["status"] == "rate_limited"
    assert row["cost_usd"] == 0


async def test_streamed_call_is_recorded_once_the_stream_ends():
    class _Stream:
        def __init__(self):
            chunks = [
                SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="Hel"))]),
                SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="lo!"))]),
                SimpleNamespace(usage=SimpleNamespace(prompt_tokens=50, completion_tokens=7), choices=[]),
            ]
            self._chunks = chunks

        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for chunk in self._chunks:
                yield chunk

    llm = LLMService()
    stream = await llm._create(_FakeClient(_Stream()), "gpt-oss-120b", messages=[], stream=True)
    assert recorder._llm_buffer == []          # nothing recorded until the stream is consumed
    texts = [c.choices[0].delta.content async for c in stream if c.choices]
    assert texts == ["Hel", "lo!"]              # chunks pass through untouched

    (row,) = recorder._llm_buffer
    assert row["streaming"] is True
    assert (row["prompt_tokens"], row["completion_tokens"]) == (50, 7)
    assert row["tokens_estimated"] is False


async def test_recording_never_breaks_the_call_it_describes():
    """A garbled usage block must not turn a good LLM answer into an error."""
    llm = LLMService()
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=object(), completion_tokens=object()),
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
    )
    result = await llm._create(_FakeClient(response), "gpt-oss-120b", messages=[])
    assert result is response
    assert recorder._llm_buffer == []


# --- flush -------------------------------------------------------------------

async def test_flush_persists_everything_and_is_additive_per_hour(factory):
    recorder.record_llm_call(provider="groq", model="gpt-oss-120b", source="x", streaming=False,
                             status="ok", latency_ms=120, prompt_tokens=10, completion_tokens=5)
    runtime_metrics.record_request(20, 200)
    runtime_metrics.record_request(700, 500)
    runtime_metrics.record_query(800, "SELECT pg_sleep(1)")

    await recorder.flush(factory)

    # a second batch in the same hour adds to the same bucket row
    runtime_metrics.record_request(30, 200)
    await recorder.flush(factory)

    async with factory() as db:
        assert len((await db.execute(select(LlmCall))).scalars().all()) == 1
        (bucket,) = (await db.execute(select(SystemMetricBucket))).scalars().all()
        assert (bucket.requests, bucket.errors_5xx, bucket.slow_requests) == (3, 1, 1)
        assert bucket.slow_queries == 1
        assert bucket.instance_id == runtime_metrics.INSTANCE_ID
        assert len((await db.execute(select(SlowQueryLog))).scalars().all()) == 1


async def test_flush_with_nothing_worth_writing_touches_no_table(factory):
    # DB queries alone (the background pollers generate these constantly)
    # must not cause writes, or an auto-suspending database never sleeps.
    runtime_metrics.record_query(2, "SELECT 1")
    await recorder.flush(factory)
    async with factory() as db:
        assert (await db.execute(select(SystemMetricBucket))).scalars().all() == []
    assert runtime_metrics.pending()["db_queries"] == 1


async def test_failed_flush_keeps_the_batch_for_retry():
    class _BrokenFactory:
        def __call__(self):
            raise ConnectionError("database unreachable")

    recorder.record_llm_call(provider="groq", model="m", source="x", streaming=False,
                             status="ok", latency_ms=1, prompt_tokens=1, completion_tokens=1)
    runtime_metrics.record_request(5, 200)

    await recorder.flush(_BrokenFactory())

    assert len(recorder._llm_buffer) == 1
    assert runtime_metrics.pending()["requests"] == 1
