"""Production config validation — what must block a boot, and what must not.

`Settings.validate_production()` is the last gate before the app serves real
patient data in production, so the distinction it draws is the important part:

* **errors** refuse to boot. Each one is a case where the app would start,
  look healthy, and still be insecure or quietly broken — a dev JWT secret, a
  wildcard CORS origin with credentials on, a Stripe *test* key. Booting is the
  worst outcome, hence the hard failure.
* **warnings** only log. They cover integrations the product can degrade
  around (no Sentry DSN, no transactional email yet). A deploy that is
  otherwise correct must not be held up by a missing analytics key.

Both halves are asserted here. A validator that is only tested for the
failures will quietly grow over-strict rules that block legitimate deploys,
and one tested only for the happy path will rot into a no-op.
"""

import logging
import os

import pytest

from src.config import Settings

# A complete, valid production baseline. Every case below overrides exactly one
# thing, so a failure points at the check under test rather than at whatever
# else happened to be unset.
BASE = {
    "app_env": "production",
    "debug": False,
    "admin_password": "a-real-password",
    "admin_jwt_secret": "k" * 48,
    "patient_portal_jwt_secret": "p" * 48,
    "database_url": "postgresql+asyncpg://user:strongpw@db.internal:5432/aesthetixai",
    "clerk_secret_key": "sk_live_x",
    "clerk_publishable_key": "pk_live_x",
    "platform_admin_emails": "ops@aiaceone.dev",
    "frontend_url": "https://aiaceone.com",
    "sentry_dsn": "https://key@o1.ingest.sentry.io/2",
    "stripe_secret_key": "",
    "stripe_webhook_secret": "",
    "resend_api_key": "re_x",
    "cloudinary_cloud_name": "c",
    "cloudinary_api_key": "k",
    "cloudinary_api_secret": "s",
    "openai_api_key": "sk-x",
    # A valid production baseline must include a LangSmith key: tracing is
    # mandatory in production, so a baseline without one would make every
    # other test in this file fail on an unrelated check and bury the signal.
    "langsmith_api_key": "lsv2_x",
}

VALID_CORS = "https://aiaceone.com"


def _settings(**overrides) -> Settings:
    # _env_file=None keeps a developer's local .env out of it, so these results
    # depend only on what each case sets.
    return Settings(_env_file=None, **{**BASE, **overrides})


def _errors(**overrides) -> list[str]:
    with pytest.raises(RuntimeError) as exc:
        _settings(**overrides).validate_production()
    return [line.strip("- ") for line in str(exc.value).splitlines()[1:]]


def _assert_blocked(needle: str, **overrides) -> None:
    errors = _errors(**overrides)
    assert any(needle.lower() in e.lower() for e in errors), (
        f"expected an error mentioning {needle!r}, got: {errors}"
    )


@pytest.fixture(autouse=True)
def _clean_cors_env(monkeypatch):
    """Each case sets CORS_ORIGINS itself; this keeps one case from leaking into the next."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", VALID_CORS)


@pytest.fixture(autouse=True)
def _clean_langsmith_env(monkeypatch):
    """Clear LangSmith env vars before each case.

    `src.services.llm.tracing` mirrors the settings into os.environ at import
    time, which is what the SDK reads. Those are process-global writes, so
    without this the derived *development* project name leaks into a
    production case and trips the "hand-set project mixes environments" error
    -- a failure that has nothing to do with the setting under test. The
    LangSmith cases below set the vars they need explicitly.
    """
    for key in list(os.environ):
        if key.startswith(("LANGSMITH_", "LANGCHAIN_")):
            monkeypatch.delenv(key, raising=False)


# --- the happy path ----------------------------------------------------------

def test_fully_configured_production_boots():
    _settings().validate_production()


@pytest.mark.parametrize("env", ["development", "staging", "test", ""])
def test_non_production_is_never_validated(env):
    """Every one of these would be blocked if the check leaked outside production."""
    Settings(_env_file=None, app_env=env, debug=True, admin_password="Aceone").validate_production()


# --- credentials -------------------------------------------------------------

def test_debug_must_be_off():
    _assert_blocked("DEBUG", debug=True)


def test_default_admin_password_blocked():
    _assert_blocked("ADMIN_PASSWORD", admin_password="Aceone")


@pytest.mark.parametrize(
    "field,default",
    [
        ("admin_jwt_secret", "aiaceone-admin-jwt-dev-secret-change-in-production"),
        ("patient_portal_jwt_secret", "aiaceone-patient-portal-jwt-dev-secret-change-in-production"),
    ],
)
def test_default_jwt_secrets_blocked(field, default):
    _assert_blocked(field, **{field: default})


@pytest.mark.parametrize(
    "field", ["admin_jwt_secret", "patient_portal_jwt_secret"]
)
def test_short_jwt_secret_blocked(field):
    """A short secret is brute-forceable even when it isn't the shipped default."""
    _assert_blocked("at least 32", **{field: "s" * 12})


# --- database ----------------------------------------------------------------

@pytest.mark.parametrize(
    "url,needle",
    [
        ("postgresql+asyncpg://u:p@localhost:5432/app", "localhost"),
        ("postgresql+asyncpg://u:p@127.0.0.1:5432/app", "localhost"),
        ("sqlite:///./app.db", "sqlite"),
    ],
)
def test_unusable_database_url_blocked(url, needle):
    _assert_blocked(needle, database_url=url)


# --- auth --------------------------------------------------------------------

@pytest.mark.parametrize(
    "field,value,needle",
    [
        ("clerk_secret_key", "", "CLERK_SECRET_KEY is required"),
        ("clerk_secret_key", "sk_test_abc", "sk_live_"),
        ("clerk_publishable_key", "", "CLERK_PUBLISHABLE_KEY is required"),
        ("clerk_publishable_key", "pk_test_abc", "pk_live_"),
    ],
)
def test_clerk_keys_must_be_live(field, value, needle):
    """A test key would authenticate against Clerk's test tenant, so every
    real user 404s — the app boots and simply has no users."""
    _assert_blocked(needle, **{field: value})


# --- CORS --------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,needle",
    [
        ("", "CORS_ORIGINS is empty"),
        ("*", "must not be '*'"),
        ("http://aiaceone.com", "plain http"),
        ("https://aiaceone.com,http://localhost:5173", "trusts localhost"),
    ],
)
def test_bad_cors_origins_blocked(monkeypatch, value, needle):
    monkeypatch.setenv("CORS_ORIGINS", value)
    _assert_blocked(needle)


def test_empty_cors_origins_blocked(monkeypatch):
    """The failure this exists for: with a localhost-only origin list the real
    deployed domain is rejected, so the API works from curl and is dead in the
    browser."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    _assert_blocked("CORS_ORIGINS is empty")


# --- billing -----------------------------------------------------------------

def test_stripe_test_key_blocked():
    _assert_blocked(
        "not a live key", stripe_secret_key="sk_test_abc", stripe_webhook_secret="whsec_abc"
    )


def test_stripe_live_key_without_webhook_secret_blocked():
    _assert_blocked(
        "STRIPE_WEBHOOK_SECRET is required", stripe_secret_key="sk_live_abc"
    )


def test_absent_stripe_is_allowed():
    """Billing can be switched on after the first deploy; a live key is not a
    prerequisite for running the product."""
    _settings(stripe_secret_key="", stripe_webhook_secret="").validate_production()


# --- frontend URL ------------------------------------------------------------

@pytest.mark.parametrize(
    "url,needle",
    [
        ("http://aiaceone.com", "plain http"),
        ("http://localhost:5183", "localhost"),
    ],
)
def test_bad_frontend_url_blocked(url, needle):
    _assert_blocked(needle, frontend_url=url)


# --- LangSmith: where production PHI goes ------------------------------------
#
# These matter more than the other production checks, because a mistake here
# does not fail loudly -- it succeeds and files real patient data somewhere
# nobody is looking. The project name is derived, not configured, precisely so
# that cannot happen by accident.


def test_langsmith_key_is_required_in_production():
    _assert_blocked("LANGSMITH_API_KEY is empty", langsmith_api_key="")


def test_langsmith_can_be_disabled_explicitly(monkeypatch):
    """A deliberate opt-out is allowed. A missing key is not.

    Both look identical to the validator unless the flag is read raw from the
    environment, because the pydantic default cannot distinguish "unset" from
    "deliberately false".
    """
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    Settings(_env_file=None, **{**BASE, "langsmith_api_key": ""}).validate_production()


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE"])
def test_langsmith_opt_out_spellings_all_honoured(monkeypatch, value):
    monkeypatch.setenv("LANGSMITH_TRACING_V2", value)
    Settings(_env_file=None, **{**BASE, "langsmith_api_key": ""}).validate_production()


def test_langsmith_opt_out_recognised_in_legacy_namespace(monkeypatch):
    """The opt-out must be found however it was spelled.

    langsmith reads LANGSMITH_TRACING_V2 before LANGCHAIN_TRACING_V2, so a
    validator that only checks the legacy name would refuse to boot a
    deployment that had deliberately switched tracing off the current way.
    """
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    Settings(_env_file=None, **{**BASE, "langsmith_api_key": ""}).validate_production()


def test_unset_tracing_flag_does_not_satisfy_the_requirement():
    """Unset is not a decision. Only an explicit false is."""
    _assert_blocked("LANGSMITH_API_KEY is empty", langsmith_api_key="")


def test_langsmith_key_warns_about_baa_absence():
    """A production deploy with tracing on must say so in the boot log.

    A handler is attached to the `aesthetixai` logger directly rather than
    using caplog, because caplog captures through the root logger and
    `aesthetixai` has `propagate = False` -- so caplog sees nothing here, and
    worse, the assertion would silently stop testing anything.
    """
    logger = logging.getLogger("aesthetixai")
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            captured.append(record.getMessage())

    handler = _Capture()
    previous_level = logger.level
    previous_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        Settings(_env_file=None, **BASE).validate_production()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    assert any("BAA/DPA" in message for message in captured), captured


@pytest.mark.parametrize(
    "field,value",
    [
        ("langchain_project", "some-old-project"),
        ("langsmith_project", "aesthetixai-development"),
    ],
)
def test_pinned_project_name_blocked_in_production(field, value):
    """A hand-set project name is refused, in either namespace.

    This is the check that stops production and development patient data
    landing in one shared project. Both spellings are tested because
    langsmith reads LANGSMITH_PROJECT first, so validating only the legacy
    name would leave the one that actually wins unchecked.
    """
    _assert_blocked("derive to", **{field: value})


def test_matching_production_project_name_is_accepted():
    """The guard must allow the name it derives to, or it blocks every deploy."""
    Settings(
        _env_file=None, **{**BASE, "langchain_project": "aesthetixai-production"}
    ).validate_production()


# --- degradable integrations: warnings, never blocks -------------------------

@pytest.mark.parametrize(
    "label,overrides",
    [
        ("no platform admin emails", {"platform_admin_emails": ""}),
        ("no sentry dsn", {"sentry_dsn": ""}),
        ("no email provider", {"resend_api_key": "", "sendgrid_api_key": ""}),
        ("no llm key", {"openai_api_key": "", "mistral_api_key": "", "groq_api_key": ""}),
        (
            "no cloudinary credentials",
            {"cloudinary_cloud_name": "", "cloudinary_api_key": "", "cloudinary_api_secret": ""},
        ),
    ],
)
def test_missing_optional_integration_still_boots(label, overrides):
    _settings(**overrides).validate_production()


def test_every_error_is_reported_at_once():
    """All problems surface in one boot failure, not one restart per mistake."""
    errors = _errors(debug=True, admin_password="Aceone", clerk_secret_key="")
    joined = " | ".join(errors).lower()
    assert "debug" in joined
    assert "admin_password" in joined
    assert "clerk_secret_key" in joined
