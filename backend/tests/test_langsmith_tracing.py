"""LangSmith tracing structure — the parts that fail silently.

Every assertion in this file exists because the corresponding bug shipped
looking healthy. The failure mode this module was built to kill is *absence*:
a missing import, a wrong env-var name, or an opt-out that ignored the operator
produces a system that runs, logs nothing, and records nothing. A test that
only checked "the decorator is attached" would pass against every one of those
bugs, so these tests assert on the two things that actually determine whether
data reaches LangSmith:

1. `tracing_enabled()` must agree with the langsmith SDK's own opinion. The SDK
   gates on OS env vars; we gate on a settings field. Those can disagree, and
   when they do the SDK silently drops every run.
2. The derived project name must survive a stale `LANGSMITH_*` value in the
   environment. langsmith's `get_env_var` searches LANGSMITH before LANGCHAIN,
   so writing only the legacy spelling loses the precedence fight -- and the
   loser is a decision about where production PHI is stored.

Nothing here contacts LangSmith. The real-client end-to-end behaviour (nested
domain/feature/LLM runs, tag inheritance) was verified manually against
langsmith 0.8.9; asserting on it in CI would make the suite depend on a network
and an API key, and a test that fails on someone's network is a test people
learn to skip.

The `traceable` fake below is autouse precisely so that leak is impossible
rather than merely intended: an earlier draft of this file asserted on
structure while still executing the real decorator, and every test quietly
POSTed to api.smith.langchain.com. A test suite that emits telemetry is a test
suite that needs credentials to pass, and one whose failures depend on someone
else's API quota.
"""

import asyncio
import os
from unittest.mock import patch

import pytest

from src.services.llm import tracing


class _FakeTraceable:
    """Stand-in for `langsmith.traceable` that records and never sends.

    Mirrors the real signature, and preserves the wrapped function's sync or
    async nature so a test can still `await` the result. Decorating with it
    gives the module under test a real decorator to apply, which is what
    `_apply_layers` needs in order to be exercised at all.
    """

    def __init__(self):
        self.runs = []

    def __call__(self, *, name, tags, metadata, project_name, run_type):
        self.runs.append(
            {
                "name": name,
                "tags": list(tags or []),
                "metadata": dict(metadata or {}),
                "project_name": project_name,
                "run_type": run_type,
            }
        )

        def decorator(fn):
            if asyncio.iscoroutinefunction(fn):

                async def _async(*a, **k):
                    return await fn(*a, **k)

                _async.__wrapped__ = fn
                return _async

            def _sync(*a, **k):
                return fn(*a, **k)

            _sync.__wrapped__ = fn
            return _sync

        return decorator

    @property
    def names(self):
        return [r["name"] for r in self.runs]

    def by_name(self, name):
        return next(r for r in self.runs if r["name"] == name)


@pytest.fixture(autouse=True)
def fake_traceable(monkeypatch):
    """Replace the network-touching decorator for every test in this module."""
    fake = _FakeTraceable()
    import langsmith

    monkeypatch.setattr(langsmith, "traceable", fake, raising=False)
    return fake


@pytest.fixture(autouse=True)
def _clean_tracing_state(monkeypatch):
    """Isolate every test from the developer's real .env and from each other.

    `tracing.settings` is resolved at import time, so patching the settings
    object is the only way to exercise the key-absent branch. Env vars are
    cleared because the SDK reads them straight from os.environ, and the
    one-shot config flag is reset so a test that configures tracing cannot
    decide the outcome of the next one.
    """
    for key in list(os.environ):
        if key.startswith(("LANGSMITH_", "LANGCHAIN_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(tracing, "_configured", False, raising=False)
    yield


def _with_key(monkeypatch, key="lsv2_test_key"):
    monkeypatch.setattr(tracing.settings, "langsmith_api_key", key, raising=False)
    return key


def _enabled(monkeypatch, env="development"):
    """Configure tracing the way a real deployment would, minus the network."""
    _with_key(monkeypatch)
    monkeypatch.setattr(tracing.settings, "app_env", env, raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "true")
    return monkeypatch


# --- env flag resolution -------------------------------------------------
#
# langsmith.utils.get_env_var() searches ("LANGSMITH", "LANGCHAIN") in that
# order. These tests pin that precedence, because the module has to match it
# exactly to stay in agreement with the SDK.


def test_env_flag_prefers_langsmith_namespace(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    # LANGSMITH wins in the SDK, so it must win here too -- otherwise we would
    # report "enabled" for a deployment the SDK has switched off.
    assert tracing._env_tracing_flag() == "false"


def test_env_flag_prefers_tracing_v2_over_bare_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "true")
    assert tracing._env_tracing_flag() == "true"


def test_env_flag_is_none_when_unset(monkeypatch):
    assert tracing._env_tracing_flag() is None


# --- tracing_enabled(): key AND not-opted-out ---------------------------


def test_disabled_without_key(monkeypatch):
    monkeypatch.setattr(tracing.settings, "langsmith_api_key", "", raising=False)
    assert tracing.tracing_enabled() is False


def test_enabled_with_key_and_no_flag(monkeypatch):
    _with_key(monkeypatch)
    assert tracing.tracing_enabled() is True


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE", " off "])
def test_explicit_opt_out_is_honoured(monkeypatch, value):
    """An operator who switches tracing off must actually switch it off.

    The key stays configured in this scenario, which is exactly the case a
    key-only check would wave through and the SDK would drop on the floor.
    """
    _with_key(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING_V2", value)
    assert tracing.tracing_enabled() is False


def test_configure_does_not_override_opt_out(monkeypatch):
    _with_key(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    assert tracing.configure_langsmith_env() is False
    # Still false afterwards -- the opt-out must survive configuration.
    assert os.environ.get("LANGSMITH_TRACING_V2") == "false"


def test_configure_returns_false_without_key(monkeypatch):
    monkeypatch.setattr(tracing.settings, "langsmith_api_key", "", raising=False)
    assert tracing.configure_langsmith_env() is False
    assert "LANGSMITH_PROJECT" not in os.environ


# --- env mirroring: names and precedence ---------------------------------


def test_configure_sets_both_namespaces(monkeypatch):
    """Both spellings are written, because only LANGSMITH is authoritative."""
    _with_key(monkeypatch)
    monkeypatch.setattr(tracing.settings, "app_env", "development", raising=False)
    assert tracing.configure_langsmith_env() is True
    for key in (
        "LANGSMITH_API_KEY",
        "LANGSMITH_TRACING_V2",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
    ):
        assert os.environ.get(key), f"{key} was not set"


def test_derived_project_beats_stale_langsmith_project(monkeypatch):
    """The SDK reads LANGSMITH_PROJECT first, so we must outrank it.

    This is the test that protects where production PHI lands. A stale
    LANGSMITH_PROJECT pointing at a shared project would otherwise win on
    precedence and quietly mix environments.
    """
    _with_key(monkeypatch)
    monkeypatch.setattr(tracing.settings, "app_env", "production", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", "somebody-elses-project")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "also-stale")
    tracing.configure_langsmith_env()
    assert os.environ["LANGSMITH_PROJECT"] == "aesthetixai-production"
    assert os.environ["LANGCHAIN_PROJECT"] == "aesthetixai-production"


def test_project_name_is_derived_per_environment(monkeypatch):
    monkeypatch.setattr(tracing.settings, "app_env", "production", raising=False)
    assert tracing.project_name() == "aesthetixai-production"
    monkeypatch.setattr(tracing.settings, "app_env", "development", raising=False)
    assert tracing.project_name() == "aesthetixai-development"


def test_configure_runs_once_on_import(monkeypatch):
    """Module import configures tracing on its own.

    `@traced_feature` is spread across a dozen service modules that never
    import `llm_service`, so relying on someone else to set the env left
    tracing dead for every importer that came first.
    """
    _with_key(monkeypatch)
    with patch.object(tracing, "configure_langsmith_env") as spy:
        tracing._ensure_configured()
        tracing._ensure_configured()
    assert spy.call_count == 1


# --- decorators: structure without a network ----------------------------


def test_domain_class_decorator_marks_the_class(monkeypatch):
    _with_key(monkeypatch)

    @tracing.traced_domain("leads")
    class LeadQualificationService:
        pass

    assert LeadQualificationService._traced_domain == "leads"


def test_bare_domain_decorator_derives_name_from_class(monkeypatch):
    _with_key(monkeypatch)

    @tracing.traced_domain
    class LeadQualificationService:
        pass

    # Bare usage is one call, so Python assigns the return value straight to the
    # class name; if the no-parens form were unhandled the name would vanish.
    assert LeadQualificationService._traced_domain == "lead_qualification_service"


def test_feature_decorator_returns_callable_that_preserves_result(monkeypatch):
    _enabled(monkeypatch)

    @tracing.traced_domain("leads")
    class Service:
        @tracing.traced_feature("lead_qualification")
        def qualify(self, lead_id):
            return f"qualified:{lead_id}"

    assert Service().qualify(7) == "qualified:7"


def test_feature_decorator_passes_through_when_disabled(monkeypatch, fake_traceable):
    """Disabled tracing must be a no-op: no run, and the work still happens."""
    monkeypatch.setattr(tracing.settings, "langsmith_api_key", "", raising=False)
    calls = []

    @tracing.traced_domain("leads")
    class Service:
        @tracing.traced_feature("lead_qualification")
        def qualify(self, lead_id):
            calls.append(lead_id)
            return lead_id

    assert Service().qualify(3) == 3
    assert calls == [3]
    assert fake_traceable.runs == [], "a run was created while tracing was off"


def test_current_feature_tracks_the_running_call(monkeypatch):
    _enabled(monkeypatch)
    seen = []

    @tracing.traced_domain("leads")
    class Service:
        @tracing.traced_feature("lead_qualification")
        def qualify(self):
            seen.append(tracing.current_feature())
            return "ok"

    assert tracing.current_feature() is None
    Service().qualify()
    assert seen == [("leads", "lead_qualification")]
    # ContextVar must be reset, or a later unrelated call would inherit it.
    assert tracing.current_feature() is None


def test_domain_run_is_not_duplicated_for_top_level_function(monkeypatch, fake_traceable):
    """A single-run feature must not be wrapped in a same-named parent.

    Nesting `leads` around `leads` adds a span that costs a click in the UI
    and teaches the reader nothing. `_layered` omits it.
    """
    _enabled(monkeypatch)

    @tracing.traced_domain("leads")
    def qualify():
        return "ok"

    qualify()
    assert fake_traceable.names == ["leads"]


def test_domain_layer_precedes_feature_layer(monkeypatch, fake_traceable):
    """The domain run must be built outside the feature run.

    Order is the whole point: `traceable` nests via a ContextVar, so applying
    them in the other order would produce two sibling runs and a flat trace --
    the exact bug this module was written to fix.
    """
    _enabled(monkeypatch)

    @tracing.traced_domain("leads")
    class Service:
        @tracing.traced_feature("lead_qualification")
        def qualify(self):
            return "ok"

    Service().qualify()
    assert fake_traceable.names == ["leads", "lead_qualification"]


def test_domain_layer_carries_no_tags(monkeypatch, fake_traceable):
    """Tagging the domain run would duplicate `domain:` on every descendant.

    langsmith propagates parent tags to children, so a tagged parent plus an
    explicitly tagged child yields `domain:leads, domain:leads, feature:x` on
    each leaf -- and a `tag:` filter then matches twice per run, inflating any
    count built on it.
    """
    _enabled(monkeypatch)

    @tracing.traced_domain("leads")
    class Service:
        @tracing.traced_feature("lead_qualification")
        def qualify(self):
            return "ok"

    Service().qualify()
    assert fake_traceable.by_name("leads")["tags"] == []
    assert fake_traceable.by_name("lead_qualification")["tags"] == [
        "domain:leads",
        "feature:lead_qualification",
    ]


def test_every_run_targets_the_derived_project(monkeypatch, fake_traceable):
    """Both layers must land in the derived per-environment project."""
    _enabled(monkeypatch, env="production")

    @tracing.traced_domain("leads")
    class Service:
        @tracing.traced_feature("lead_qualification")
        def qualify(self):
            return "ok"

    Service().qualify()
    assert {r["project_name"] for r in fake_traceable.runs} == {
        "aesthetixai-production"
    }


def test_streaming_entry_point_is_not_buffered(monkeypatch):
    """Async generators must yield before the run is complete.

    `traceable` has to drive a generator to completion to close its run, which
    would buffer every token and make first-token latency the sum of the whole
    response. For voice chat that is the product, so streaming uses
    `tracing_context` and must yield eagerly.
    """
    _enabled(monkeypatch)

    @tracing.traced_domain("super_agent")
    class Service:
        @tracing.traced_feature("super_agent_ask_stream")
        async def ask_stream(self):
            for token in ("a", "b", "c"):
                yield token

    async def drain():
        out = []
        async for token in Service().ask_stream():
            out.append(token)
        return out

    assert asyncio.run(drain()) == ["a", "b", "c"]


def test_shipped_services_are_all_instrumented():
    """Guard against a new agent service being added without tracing.

    A service that calls an LLM and forgets `@traced_feature` is invisible in
    LangSmith, which looks exactly like a service that stopped running. This
    test cannot know the intent of future code, but it can enforce that every
    currently-known agent surface stays covered.
    """
    from src.services.ai_receptionist import (
        emergency_triage_service,
        translation_service,
        voice_chat_service,
    )
    from src.services.channels import inbound_service
    from src.services.clinical import consultation_services
    from src.services.command_center import command_center_services
    from src.services.finance_agent import finance_agent_services
    from src.services.landing_chat import landing_chat_service
    from src.services.leads import (
        lead_nurturing_service,
        lead_qualification_service,
    )
    from src.services.patient_portal import patient_intake_service
    from src.services.super_agent import super_agent_services

    expected = {
        lead_qualification_service.LeadQualificationService: "leads",
        lead_nurturing_service.LeadNurturingService: "leads",
        patient_intake_service.PatientIntakeService: "patient_portal",
        emergency_triage_service.EmergencyTriageService: "ai_receptionist",
        translation_service.TranslationService: "ai_receptionist",
        voice_chat_service.VoiceChatService: "ai_receptionist",
        consultation_services.ConsultationService: "clinical",
        command_center_services.CommandCenterService: "command_center",
        finance_agent_services.FinanceAgentService: "finance_agent",
        landing_chat_service.LandingChatService: "landing",
        inbound_service.InboundService: "channels",
        super_agent_services.SuperAgentService: "super_agent",
    }
    for cls, domain in expected.items():
        assert getattr(cls, "_traced_domain", None) == domain, (
            f"{cls.__name__} is missing @traced_domain({domain!r})"
        )
