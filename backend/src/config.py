from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "AesthetixAI"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5183"

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/aesthetixai"

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
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "aesthetixai"

    mistral_api_key: str = ""
    mistral_api_key_2: str = ""
    mistral_api_key_3: str = ""
    mistral_model: str = "mistral-small-latest"

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
    stripe_price_solo: str = ""
    stripe_price_practice: str = ""

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

    storage_backend: str = "cloudinary"
    upload_max_size_mb: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
