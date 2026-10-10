import logging
import os
from functools import lru_cache

from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

logger = logging.getLogger("aesthetixai")

_TRACING_OFF_VALUES = {"false", "0", "no", "off"}
_DEFAULT_ADMIN_JWT_SECRET = "aiaceone-admin-jwt-dev-secret-change-in-production"
_DEFAULT_PORTAL_JWT_SECRET = "aiaceone-patient-portal-jwt-dev-secret-change-in-production"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class Settings(BaseSettings):
    app_name: str = "AesthetixAI"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5183"

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/aesthetixai"
    # Optional separate URL for `alembic upgrade`. On Neon the app connects
    # through the pooled (pgbouncer) endpoint but migrations need the direct
    # one - DDL and session-level settings don't survive transaction pooling.
    migration_database_url: str = ""

    # Comma-separated browser origins allowed to call this API, e.g.
    # "https://app.example.com,https://www.example.com". Required in
    # production (see validate_production); empty falls back to the local
    # dev origins elsewhere.
    cors_origins: str = ""

    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwks_url: str = ""
    clerk_webhook_secret: str = ""

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # LangSmith observability (extras user added to .env). pydantic-settings
    # rejects unknown env keys, so these are declared fields — and they feed
    # nothing until LLMService wires them in, they just stop a stray
    # LANGSMITH_API_KEY/LANGCHAIN_API_KEY from crashing settings at boot.
    langsmith_api_key: str = ""
    langsmith_tracing_v2: bool = False
    langsmith_project_prefix: str = "aesthetixai"
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = False
    # Hand-set LangSmith project names. Empty on purpose: the project is
    # DERIVED per environment (services/llm/tracing.py:project_name), and
    # validate_production refuses a pinned name that points elsewhere.
    langchain_project: str = ""
    langsmith_project: str = ""

    mistral_api_key: str = ""
    mistral_api_key_2: str = ""
    mistral_api_key_3: str = ""
    mistral_api_key_4: str = ""
    mistral_model: str = "mistral-small-latest"

    # Sentry error tracking. Empty = disabled (local dev boots without it).
    # DSN is not a secret token — it's safe in clients too (frontend uses its
    # own project DSN via VITE_SENTRY_DSN). Only initialized when set.
    sentry_dsn: str = ""

    # Groq's chat-completions endpoint is also OpenAI-SDK compatible (same
    # pattern as Mistral above, different base_url) — used as the fallback
    # tier between Mistral (rate-limit-prone free tier) and OpenAI (a real
    # key isn't configured yet), since Groq's free tier is fast and has
    # generous limits. See LLMService._call_with_fallback.
    groq_api_key: str = ""
    groq_model: str = "gpt-oss-120b"

    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"

    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    whatsapp_api_token: str = ""
    whatsapp_phone_number_id: str = ""

    # GREEN-API (green-api.com) — unofficial WhatsApp API
    # Each practice stores its own instance_id + api_token in Practice.settings
    # under the "green_api" key.  These env vars are only for the platform-level
    # default instance (used by the demo seed / testing).
    green_api_instance_id: str = ""
    green_api_token: str = ""
    # Shared secret for the push-style WhatsApp webhook
    # (POST /ai-receptionist/inbound/whatsapp). Configure the same value as the
    # instance's `webhookUrlToken` in Green API, which then sends it back as
    # `Authorization: Bearer <secret>`. Unset = the endpoint refuses everything
    # outside development (the poller path needs no webhook at all).
    green_api_webhook_secret: str = ""

    instagram_api_token: str = ""

    # Meta (Instagram/Facebook) OAuth — ONE registered Facebook App for the
    # whole platform (Aiaceone team registers this once, like Stripe's
    # secret key), not per-practice. Each practice then authorizes THIS app
    # via OAuth to connect their own Page/IG Business account — see
    # services/channels/meta_service.py. Placeholder until a real Facebook
    # App exists; MetaService.is_configured() gates every code path on this,
    # same pattern as CheckoutService._stripe_key_configured().
    meta_app_id: str = ""
    meta_app_secret: str = ""

    sendgrid_api_key: str = ""
    email_from: str = "noreply@aesthetixai.com"

    # Landing-page AI chat (Aria) sales lead destination — platform-sales
    # team, NOT a practice. When a website visitor is a clinic buyer (not a
    # patient) and Aria captures their email, a SalesLead is written and this
    # address is emailed so the Aiaceone sales team can follow up. Point this
    # at your real sales inbox in production (.env: SALES_EMAIL=...). When
    # empty, effective_sales_email falls back to the first platform admin
    # email so buyer leads still reach the Aiaceone team out of the box.
    sales_email: str = ""

    @property
    def effective_sales_email(self) -> str | None:
        if self.sales_email.strip():
            return self.sales_email.strip()
        first = self.platform_admin_emails.strip().split(",")[0].strip()
        return first or None

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # The subscription's Stripe Price is not configured here: it lives on the
    # Plan row (Plan.stripe_price_id) so each plan carries its own price.

    # Comma-separated bootstrap allowlist — a Clerk user whose verified email
    # appears here gets User.is_platform_admin flipped to True on their next
    # login (see server/dependencies.py). This is only the bootstrap path:
    # once at least one platform admin exists, further admins are promoted
    # from the admin panel itself, not by editing this list.
    platform_admin_emails: str = ""

    # Standalone admin login (POST /api/v1/admin/auth/login) — a plain
    # username/password + JWT, deliberately independent of Clerk so the
    # platform admin panel doesn't require a Clerk account at all. Override
    # both in production; these are the defaults for local/dev use.
    admin_username: str = "admin"
    admin_password: str = "Aceone"
    admin_jwt_secret: str = "aiaceone-admin-jwt-dev-secret-change-in-production"
    admin_jwt_expires_minutes: int = 60 * 24 * 7  # 7 days

    # Patient Portal login (ID + PIN) — deliberately separate from Clerk
    # (patients aren't staff, Clerk's pricing model is per-staff-MAU) and
    # from admin_jwt_secret above (a leaked patient-portal secret should
    # never also compromise the admin panel). Shorter-lived than the admin
    # token since it's PIN-based, not a verified-email login.
    patient_portal_jwt_secret: str = "aiaceone-patient-portal-jwt-dev-secret-change-in-production"
    patient_portal_jwt_expires_minutes: int = 60 * 24  # 24 hours

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    redis_url: str = "redis://localhost:6379"

    # Demo data (flagged is_sample, one-click removable by the Owner) loaded
    # into a clinic when a Super Admin approves its free signup, so the new
    # owner lands on a populated dashboard. Paid signups never get it. Turn
    # off to start every approved clinic empty.
    seed_sample_data_on_approval: bool = True

    storage_backend: str = "cloudinary"
    upload_max_size_mb: int = 10

    # extra="ignore": a stale key left in a .env file (e.g. the retired
    # STRIPE_PRICE_* variables) must not stop the app from booting.
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    def validate_production(self) -> None:
        """Refuse to boot in production on a config that would start, look
        healthy and still be insecure or quietly broken (dev JWT secret,
        wildcard CORS with credentials on, Stripe/Clerk test keys, a
        localhost database...). Every problem is reported at once so a deploy
        isn't a fix-one-restart-repeat loop. Integrations the product can
        degrade around only log a warning. Outside production nothing is
        checked - local dev must boot on defaults."""
        if self.app_env != "production":
            return

        errors: list[str] = []
        warnings: list[str] = []

        if self.debug:
            errors.append("DEBUG must be false in production (it enables Swagger docs and SQL logging)")

        # --- credentials -----------------------------------------------------
        if self.admin_password == "Aceone":
            errors.append("ADMIN_PASSWORD must be changed from default in production")
        for name, value, default in (
            ("ADMIN_JWT_SECRET", self.admin_jwt_secret, _DEFAULT_ADMIN_JWT_SECRET),
            ("PATIENT_PORTAL_JWT_SECRET", self.patient_portal_jwt_secret, _DEFAULT_PORTAL_JWT_SECRET),
        ):
            if value == default:
                errors.append(f"{name} must be changed from default in production")
            elif len(value) < 32:
                errors.append(f"{name} must be at least 32 characters")
        if self.admin_jwt_secret == self.patient_portal_jwt_secret:
            errors.append(
                "ADMIN_JWT_SECRET and PATIENT_PORTAL_JWT_SECRET must differ "
                "(a leaked patient token must not unlock the admin panel)"
            )

        # --- database --------------------------------------------------------
        try:
            db_url = make_url(self.database_url)
            if db_url.get_backend_name() == "sqlite":
                errors.append("DATABASE_URL is sqlite - production needs a hosted Postgres")
            elif (db_url.host or "") in _LOCAL_HOSTS or not db_url.host:
                errors.append("DATABASE_URL points at localhost - production needs a hosted Postgres")
        except Exception:
            errors.append("DATABASE_URL is not a valid database URL")

        # --- auth ------------------------------------------------------------
        for name, value, live_prefix, test_prefix in (
            ("CLERK_SECRET_KEY", self.clerk_secret_key, "sk_live_", "sk_test_"),
            ("CLERK_PUBLISHABLE_KEY", self.clerk_publishable_key, "pk_live_", "pk_test_"),
        ):
            if not value:
                errors.append(f"{name} is required in production")
            elif value.startswith(test_prefix):
                # A test key authenticates against Clerk's test tenant, so
                # every real user 404s: the app boots and simply has no users.
                errors.append(f"{name} is a test key - production needs a {live_prefix}... key")

        # --- CORS ------------------------------------------------------------
        origins = self.cors_origin_list
        if not origins:
            errors.append(
                "CORS_ORIGINS is empty - set it to the deployed frontend origin(s), "
                "otherwise the browser rejects every API call"
            )
        for origin in origins:
            host = origin.split("://", 1)[-1].split("/")[0].split(":")[0]
            if origin == "*":
                errors.append("CORS_ORIGINS must not be '*' (credentials are enabled)")
            elif host in _LOCAL_HOSTS:
                errors.append(f"CORS_ORIGINS trusts localhost ({origin})")
            elif origin.startswith("http://"):
                errors.append(f"CORS_ORIGINS contains a plain http origin ({origin})")

        # --- billing ---------------------------------------------------------
        if self.stripe_secret_key:
            if "xxxx" in self.stripe_secret_key:
                errors.append("STRIPE_SECRET_KEY appears to be a placeholder")
            elif self.stripe_secret_key.startswith("sk_test_"):
                errors.append("STRIPE_SECRET_KEY is not a live key (sk_test_...)")
            if not self.stripe_webhook_secret:
                errors.append("STRIPE_WEBHOOK_SECRET is required when STRIPE_SECRET_KEY is set")
        if self.stripe_webhook_secret and "xxxx" in self.stripe_webhook_secret:
            errors.append("STRIPE_WEBHOOK_SECRET appears to be a placeholder")

        # --- frontend --------------------------------------------------------
        frontend_host = self.frontend_url.split("://", 1)[-1].split("/")[0].split(":")[0]
        if frontend_host in _LOCAL_HOSTS:
            errors.append(f"FRONTEND_URL points at localhost ({self.frontend_url})")
        elif self.frontend_url.startswith("http://"):
            errors.append(f"FRONTEND_URL uses plain http ({self.frontend_url})")

        # --- LangSmith: where production PHI goes ----------------------------
        # Tracing ships full prompts (which carry patient data) to a third
        # party, so it is either deliberately on or deliberately off - never
        # silently missing. Only an explicit false counts as a decision; an
        # unset flag does not (the pydantic default can't tell the two apart,
        # hence the raw environment + "was it explicitly set" check).
        if not self._tracing_explicitly_disabled():
            if not self.langsmith_api_key:
                errors.append(
                    "LANGSMITH_API_KEY is empty - tracing is mandatory in production; set a key, "
                    "or set LANGSMITH_TRACING_V2=false to opt out explicitly"
                )
            else:
                warnings.append(
                    "LangSmith tracing is ON in production: full prompts, which can contain patient "
                    "data, are sent to LangChain Inc. Make sure a BAA/DPA is signed before real patient "
                    "data flows, or set LANGSMITH_TRACING_V2=false."
                )
        derived_project = f"{(self.langsmith_project_prefix or self.app_name).strip()}-production"
        for env_name, pinned in (("LANGCHAIN_PROJECT", self.langchain_project), ("LANGSMITH_PROJECT", self.langsmith_project)):
            if pinned and pinned != derived_project:
                errors.append(
                    f"{env_name}={pinned!r} pins the LangSmith project by hand - production traces must "
                    f"derive to {derived_project!r}; unset it"
                )

        if errors:
            raise RuntimeError("Production config validation failed:\n- " + "\n- ".join(errors))

        # --- degradable integrations: warn, never block ----------------------
        if not self.platform_admin_emails.strip():
            warnings.append("PLATFORM_ADMIN_EMAILS is empty - no bootstrap platform admin")
        if not self.sentry_dsn:
            warnings.append("SENTRY_DSN is empty - production errors will not be reported")
        if not (self.resend_api_key or self.sendgrid_api_key):
            warnings.append("No email provider configured (RESEND_API_KEY / SENDGRID_API_KEY) - emails will not send")
        if not (self.openai_api_key or self.mistral_api_key or self.groq_api_key):
            warnings.append("No LLM API key configured - every AI feature will fail")
        if not (self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret):
            warnings.append("Cloudinary credentials are incomplete - photo/document uploads will fail")
        redis_host = self.redis_url.split("://", 1)[-1].rsplit("@", 1)[-1].split(":")[0].split("/")[0]
        if redis_host in _LOCAL_HOSTS:
            warnings.append(
                "REDIS_URL points at localhost - rate limiting is off and patient OTP login cannot work without a hosted Redis"
            )
        for message in warnings:
            logger.warning("Production config: %s", message)

    def _tracing_explicitly_disabled(self) -> bool:
        for key in ("LANGSMITH_TRACING_V2", "LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"):
            if os.environ.get(key, "").strip().lower() in _TRACING_OFF_VALUES:
                return True
        # Set to false in .env / by keyword rather than the process environment.
        return any(
            name in self.model_fields_set and not getattr(self, name)
            for name in ("langsmith_tracing_v2", "langchain_tracing_v2")
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
