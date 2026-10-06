"""LangSmith tracing structure for the agentic features.

Why this module exists
----------------------
`LLMService` wraps every OpenAI-SDK client with `langsmith.wrappers.wrap_openai`,
which on its own produces *flat, sibling* LLM spans: no parent run, no tags, no
feature attribution. Twelve distinct features (lead qualification, patient
intake, triage, ...) all landed in one undifferentiated pile, and a single
global `LANGCHAIN_PROJECT` meant one project for the whole app.

The fix is a two-layer hierarchy, which is what this module provides:

    leads                    <- domain run   (@traced_domain)
      lead_qualification     <- feature run  (@traced_feature)
        llm call             <- auto-parented by wrap_openai
        llm call

Layering it this way (rather than one LangSmith project per feature) keeps
cross-feature rollups possible: total LLM cost, latency and error rate for a
whole environment are still one query, while each feature stays individually
filterable by tag.

How the nesting actually works
------------------------------
Verified against the installed langsmith 0.8.9:

  * `langsmith.traceable` creates the run and stores it in a ContextVar, so
    anything invoked inside it (our `wrap_openai` calls) is auto-parented.
  * A run created inside a `tracing_context` merges the context's tags and
    metadata onto itself -- langsmith/run_helpers.py merges
    `outer_tags = _context._TAGS.get()` into `self.tags`. So the LLM leaf runs
    pick up `domain:`/`feature:` on their own.

Consequence worth knowing: we deliberately do NOT pass tags through
`extra_body={"langsmith_extra": ...}`. That escape hatch exists, but Groq and
Mistral are OpenAI-SDK-compatible endpoints and some reject unknown body
fields with a 400 -- and this repo already uses `extra_body` for Groq's
`reasoning_effort` (see LLMService._extra_kwargs_for). Letting LangSmith's own
context propagation do the work means zero provider-facing risk.

Privacy note
------------
Tracing is ON in this codebase and real prompts carry patient data (names,
complaints, intake answers). That is a deliberate, accepted decision, and it is
a precondition that a signed BAA/DPA with LangChain Inc. exists before
production. We add only non-identifying metadata of our own (domain, feature,
provider, model tier, practice_id) and never widen what the prompt already
contains.
"""
from __future__ import annotations

import functools
import inspect
import logging
import os
from contextvars import ContextVar
from typing import Any, Callable

from src.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# The innermost (domain, feature) pair currently executing. Lets llm_service
# and debug endpoints report where a call came from without re-deriving it.
_CURRENT: ContextVar[tuple[str, str] | None] = ContextVar(
    "langsmith_current_feature", default=None
)

_warned_wrap_failure = False
_warned_traceable_failure = False


# langsmith.utils.tracing_is_enabled() resolves its flag as
# get_env_var("TRACING_V2", default=get_env_var("TRACING", default="")) and
# get_env_var() searches ("LANGSMITH", "LANGCHAIN") in that order. These tuples
# mirror that resolution so an operator's explicit setting is honoured instead
# of being silently overridden.
_TRACING_FLAG_KEYS = ("TRACING_V2", "TRACING")
_TRACING_NAMESPACES = ("LANGSMITH", "LANGCHAIN")
_TRACING_FALSE = frozenset({"false", "0", "no", "off"})


def _env_tracing_flag() -> str | None:
    """Raw configured tracing flag, lowercased, or None if unset.

    Replicates langsmith's own lookup order (TRACING_V2 before TRACING, and
    LANGSMITH_* before LANGCHAIN_*) so this module cannot disagree with the SDK
    about whether tracing is on.
    """
    for key in _TRACING_FLAG_KEYS:
        for namespace in _TRACING_NAMESPACES:
            raw = os.environ.get(f"{namespace}_{key}", "").strip()
            if raw:
                return raw.lower()
    return None


def _has_key() -> bool:
    return bool(settings.langsmith_api_key)


def tracing_enabled() -> bool:
    """True when LangSmith tracing will actually produce runs.

    Every decorator in this module short-circuits on this, so an unconfigured
    deployment keeps the same zero-overhead behaviour it had before tracing was
    added.

    Two conditions, not one. A key alone is not enough: the langsmith SDK
    independently gates on its tracing env flag, and a `traceable`-wrapped
    function whose flag is off returns normally and records nothing. Gating only
    on the key produced the worst failure mode available -- decorators that
    looked installed, cost nothing, and silently recorded nothing.
    """
    if not _has_key():
        return False
    return _env_tracing_flag() not in _TRACING_FALSE


def project_name() -> str:
    """One LangSmith project per environment, derived -- never hand-set.

    Deriving it matters: a stale `LANGCHAIN_PROJECT` in .env previously pinned
    every environment to a single auto-generated project, so development
    traffic and production traffic (real PHI) were indistinguishable in one
    place. `validate_production` additionally refuses to boot a production
    deployment whose derived project is not the production one.
    """
    prefix = (settings.langsmith_project_prefix or settings.app_name).strip()
    env = (settings.app_env or "development").strip().lower()
    return f"{prefix}-{env}"


def configure_langsmith_env() -> bool:
    """Mirror the LangSmith settings into os.environ and return availability.

    The langsmith SDK reads its configuration from OS env vars, but this
    project loads secrets from .env through pydantic-settings, which never
    exports to os.environ. So the SDK would otherwise find no key and silently
    trace nothing.

    Both the current `LANGSMITH_*` and the legacy `LANGCHAIN_*` spellings are
    written. That is not redundancy for its own sake: `get_env_var` searches
    LANGSMITH before LANGCHAIN, so setting only the legacy name leaves a stale
    `LANGSMITH_PROJECT` or `LANGSMITH_TRACING_V2` in the host environment free
    to outrank us. Writing both, with plain assignment, leaves no such gap.

    An explicit operator opt-out is respected and not overwritten -- this is
    the switch someone reaches for when they need to stop tracing without
    unsetting the key.
    """
    if not _has_key():
        return False

    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key

    if _env_tracing_flag() in _TRACING_FALSE:
        logger.warning(
            "LangSmith tracing is explicitly disabled via the tracing env flag "
            "while a LangSmith key is configured; no runs will be recorded. "
            "Unset LANGSMITH_TRACING_V2 (or set it to 'true') to re-enable."
        )
        return False

    for key in _TRACING_FLAG_KEYS:
        for namespace in _TRACING_NAMESPACES:
            os.environ[f"{namespace}_{key}"] = "true"

    # Hard assignment, not setdefault: a leftover LANGCHAIN_PROJECT in the shell
    # must not be able to redirect production PHI into a development project.
    derived = project_name()
    os.environ["LANGSMITH_PROJECT"] = derived
    os.environ["LANGCHAIN_PROJECT"] = derived
    return True


def current_feature() -> tuple[str, str] | None:
    """(domain, feature) currently executing, or None outside any traced call."""
    return _CURRENT.get()


_configured = False


def _ensure_configured() -> None:
    """Run the os.environ mirror once, before anything tries to trace.

    The langsmith SDK is gated on OS env vars, and `@traced_feature` is now
    spread across a dozen service modules that have no reason to import
    `llm_service`. Relying on `llm_service` to set the env on the way past meant
    that importing this module on its own -- a script, a test, a future worker
    entry point -- produced decorators that recorded nothing while appearing to
    work. Calling it here removes that ordering dependency.
    """
    global _configured
    if _configured:
        return
    _configured = True
    configure_langsmith_env()


def _tags(domain: str, feature: str) -> list[str]:
    return [f"domain:{domain}", f"feature:{feature}"]


def _snake(name: str) -> str:
    """LeadQualificationService -> lead_qualification_service (tags stay tidy)."""
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _metadata(domain: str, feature: str, extra: dict | None) -> dict:
    md: dict[str, Any] = {"domain": domain, "feature": feature}
    if extra:
        md.update(extra)
    return md


def _resolve_domain(instance: Any, declared: str | None) -> str:
    """Class-level domain wins over the decorator argument."""
    cls_domain = getattr(type(instance), "_traced_domain", None)
    if cls_domain:
        return str(cls_domain)
    if declared:
        return declared
    return "unassigned"


def _build_decorator(
    run_name: str,
    tags: list[str],
    metadata: dict,
    run_type: str,
) -> Callable:
    """Return langsmith's traceable decorator, or a no-op passthrough.

    The no-op path is deliberate: if langsmith cannot be imported, or its
    version is incompatible, we must not take the application down with us --
    but we also must not fail *silently*, which is exactly what the previous
    `except Exception: return client` did. A missing import there meant tracing
    quietly disappeared and nothing in the logs said so.
    """
    global _warned_traceable_failure
    _ensure_configured()
    try:
        from langsmith import traceable

        return traceable(
            name=run_name,
            tags=tags,
            metadata=metadata,
            project_name=project_name(),
            run_type=run_type,
        )
    except Exception:  # pragma: no cover - depends on installed langsmith
        if not _warned_traceable_failure:
            _warned_traceable_failure = True
            logger.warning(
                "LangSmith tracing is configured but langsmith.traceable could "
                "not be loaded, so no agent runs will be traced. Traces will be "
                "missing without any other symptom. Check the langsmith "
                "install rather than assuming the project is just empty.",
                exc_info=True,
            )

        def _passthrough(fn):
            return fn

        return _passthrough


def _layered(
    dom: str, feature: str, tags: list[str], metadata: dict, run_type: str
) -> list[Callable]:
    """Return the run decorators for one call, outermost first.

    This is where the two-layer hierarchy is actually built:

        leads                <- domain run
          lead_qualification <- feature run
            llm calls        <- auto-parented by wrap_openai

    The domain run is created here, per call, rather than by the class-level
    `@traced_domain`. That decorator runs once at import time and cannot know
    when a feature is invoked, so it can only record the domain name; a run
    only means anything if it exists on the timeline of an actual request.

    The domain layer is omitted when it would be pure noise -- a top-level
    function passed to `@traced_domain` traces as a single run, because nesting
    a run named `leads` around a run also named `leads` is a duplicate that
    costs a click in the LangSmith UI and teaches the reader nothing.
    """
    decorators: list[Callable] = []
    if dom and dom != feature:
        # No tags on the domain run. langsmith propagates a parent's tags onto
        # its children, so tagging the parent `domain:leads` *and* declaring it
        # on the feature run yields `domain:leads, domain:leads, feature:x` on
        # every leaf -- which then makes a `tag:"domain:leads"` filter match
        # twice per run and quietly inflates any count built on it. The run name
        # is the domain; the metadata carries it for querying.
        decorators.append(
            _build_decorator(
                run_name=dom,
                tags=[],
                metadata={"domain": dom},
                run_type="chain",
            )
        )
    decorators.append(
        _build_decorator(
            run_name=feature,
            tags=tags,
            metadata=metadata,
            run_type=run_type,
        )
    )
    return decorators


def _apply_layers(decorators: list[Callable], fn: Callable) -> Callable:
    """Wrap fn in every decorator, outermost first.

    `traceable` stashes the run tree in a ContextVar as it enters, so applying
    the domain decorator outside the feature decorator nests the two runs
    rather than running them side by side.
    """
    for decorator in reversed(decorators):
        fn = decorator(fn)
    return fn


def _wrap(run_name, domain, feature, run_type, extra_metadata, get_domain):
    """Shared body for both decorators: bind a run onto a function/method.

    Works for sync functions, coroutines and async generators, and for methods
    and plain functions, because the `self`/domain lookup is deferred to call
    time rather than decoration time.

    Async generators (the four `*_stream` agent entry points) get a different
    treatment on purpose. `traceable` has to drive a generator to completion to
    close its run, which means buffering every streamed token before the caller
    sees the first one -- unacceptable for voice chat, where first-token
    latency *is* the product. Those use `tracing_context` instead: it sets the
    project/tags/metadata contextvars and returns immediately, so streaming is
    untouched. The trade-off is explicit rather than accidental -- the LLM leaf
    runs inside a stream are tagged and land in the right project, but the
    domain and feature runs are not created as parent spans, because a span
    that cannot be closed without buffering is not worth the latency cost. This
    is the one place the hierarchy is shallower than the diagram at the top of
    the module, and it is a deliberate choice, not an oversight.
    """

    def decorator(fn):
        def _resolve(instance):
            dom = get_domain(instance)
            return _tags(dom, feature), _metadata(dom, feature, extra_metadata), dom

        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def agen_inner(*args, **kwargs):
                if not tracing_enabled():
                    async for item in fn(*args, **kwargs):
                        yield item
                    return
                instance = args[0] if args else None
                tags, metadata, dom = _resolve(instance)
                try:
                    from langsmith import tracing_context
                except Exception:  # pragma: no cover - depends on langsmith
                    global _warned_traceable_failure
                    if not _warned_traceable_failure:
                        _warned_traceable_failure = True
                        logger.warning(
                            "langsmith.tracing_context is unavailable, so streamed "
                            "agent calls will run untagged.",
                            exc_info=True,
                        )
                    async for item in fn(*args, **kwargs):
                        yield item
                    return
                token = _CURRENT.set((dom, feature))
                try:
                    # `tracing_context` is a *sync* context manager even inside
                    # async code -- `async with` raises TypeError here.
                    with tracing_context(
                        project_name=project_name(),
                        tags=tags,
                        metadata=metadata,
                    ):
                        async for item in fn(*args, **kwargs):
                            yield item
                finally:
                    _CURRENT.reset(token)

            return agen_inner

        @functools.wraps(fn)
        async def async_inner(*args, **kwargs):
            if not tracing_enabled():
                return await fn(*args, **kwargs)
            instance = args[0] if args else None
            tags, metadata, dom = _resolve(instance)

            async def _call():
                token = _CURRENT.set((dom, feature))
                try:
                    return await fn(*args, **kwargs)
                finally:
                    _CURRENT.reset(token)

            return await _apply_layers(
                _layered(dom, feature, tags, metadata, run_type), _call
            )()

        @functools.wraps(fn)
        def sync_inner(*args, **kwargs):
            if not tracing_enabled():
                return fn(*args, **kwargs)
            instance = args[0] if args else None
            tags, metadata, dom = _resolve(instance)

            def _call():
                token = _CURRENT.set((dom, feature))
                try:
                    return fn(*args, **kwargs)
                finally:
                    _CURRENT.reset(token)

            return _apply_layers(
                _layered(dom, feature, tags, metadata, run_type), _call
            )()

        return async_inner if inspect.iscoroutinefunction(fn) else sync_inner

    return decorator


def traced_domain(name=None, *, metadata: dict | None = None):
    """Mark a service class as a tracing domain (no wrapper, just an attribute).

    Applying this to a class is the cheap half of the hierarchy: it records the
    domain name so that every `@traced_feature` method underneath can label
    itself correctly without each method having to repeat the domain string.

        @traced_domain("leads")
        class LeadQualificationService:
            @traced_feature("lead_qualification")
            async def qualify(self, lead): ...

    Applied to a function instead, it traces that function as a domain-level
    run -- useful for a top-level entry point that is itself a whole agent
    turn rather than one of several features. Used bare on a class
    (`@traced_domain`) the domain name is derived from the class name.
    """
    cls_name = _snake(name.__name__) if inspect.isclass(name) else name
    resolved = cls_name if isinstance(cls_name, str) else None

    def _apply(obj):
        if resolved is None:
            raise TypeError(
                "@traced_domain needs a name: use @traced_domain('leads') on a "
                "class, or @traced_domain('leads') on a function."
            )
        if inspect.isclass(obj):
            obj._traced_domain = resolved
            return obj
        return _wrap(
            run_name=resolved,
            domain=None,
            feature=resolved,
            run_type="chain",
            extra_metadata=metadata,
            get_domain=lambda _self, _n=resolved: _n,
        )(obj)

    # Bare usage (`@traced_domain` with no parentheses) is a single call:
    # Python evaluates `traced_domain(cls)` and assigns the *result* straight
    # to the class name, so the returned decorator is never applied. Handle it
    # here rather than handing back a closure that would silently never run.
    if name is not None and not isinstance(name, str):
        return _apply(name)

    if resolved is None:
        raise TypeError(
            "@traced_domain needs a name: use @traced_domain('leads') on a "
            "class, or @traced_domain('leads') on a function."
        )
    return _apply


def traced_feature(
    feature: str,
    *,
    domain: str | None = None,
    run_type: str = "chain",
    metadata: dict | None = None,
):
    """Trace one feature, nested under its domain, so its LLM calls hang off it.

    Unlike `@traced_domain`, this creates a real run. The domain layer comes
    from `_traced_domain` on the owning class, so the usual call site is just
    the two decorators on the class and the one method:

        @traced_domain("leads")
        class LeadQualificationService:
            @traced_feature("lead_qualification")
            async def qualify(self, lead): ...

    `domain` is only needed when there is no declaring class (module-level
    functions, scripts).
    """

    def decorator(obj):
        if inspect.isclass(obj):
            raise TypeError(
                "@traced_feature decorates a method or function, not a class. "
                "Use @traced_domain on the class."
            )
        return _wrap(
            run_name=feature,
            domain=None,
            feature=feature,
            run_type=run_type,
            extra_metadata=metadata,
            get_domain=lambda instance, _d=domain: _resolve_domain(instance, _d),
        )(obj)

    return decorator


# Mirror the settings into os.environ as soon as this module is importable, so
# that tracing works for any importer and not only for the code path that
# happens to construct an LLM client first.
_ensure_configured()
