from __future__ import annotations

import secrets

import httpx

from src.config import get_settings

settings = get_settings()

GRAPH_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


class MetaService:
    """Per-practice Instagram/Facebook connect via Meta's OAuth (Facebook
    Login for Business) — the real, multi-tenant replacement for the old
    dead single-tenant instagram_service.py stub (one global token, no
    router, never wired up).

    Requires ONE registered Facebook App for the whole platform
    (settings.meta_app_id/meta_app_secret) — not something any individual
    practice Owner can supply themselves, unlike Green API. Every method
    here is a no-op / clear error until that App exists and is configured,
    exactly like CheckoutService gates on a real Stripe key. Once it is,
    each practice's Owner authorizes THIS app via the standard OAuth
    consent screen and picks their own Page/IG Business account — nothing
    else in this class changes.

    Token storage shape, once connected, mirrors WhatsAppGreenAPI's own
    Practice.settings pattern: Practice.settings["meta"] = {"page_id":...,
    "page_access_token":..., "ig_business_id":...}."""

    def is_configured(self) -> bool:
        return bool(settings.meta_app_id) and bool(settings.meta_app_secret)

    def generate_state(self) -> str:
        # CSRF guard for the OAuth redirect — the caller persists this
        # (e.g. in the user's session/short-lived DB row) and verifies it
        # matches on callback, same purpose as OAuth's `state` param anywhere.
        return secrets.token_urlsafe(24)

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        if not self.is_configured():
            raise RuntimeError("Meta integration is not configured on this platform yet.")
        scopes = "pages_show_list,pages_messaging,instagram_basic,instagram_manage_messages,pages_manage_metadata"
        return (
            f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
            f"?client_id={settings.meta_app_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&scope={scopes}"
        )

    async def exchange_code_for_user_token(self, code: str, redirect_uri: str) -> str:
        if not self.is_configured():
            raise RuntimeError("Meta integration is not configured on this platform yet.")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/oauth/access_token",
                params={
                    "client_id": settings.meta_app_id,
                    "client_secret": settings.meta_app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def list_pages(self, user_access_token: str) -> list[dict]:
        """The Pages this user manages, each with its own page access token
        and (if linked) an Instagram Business Account id — what the Owner
        picks from in the connect UI when they manage more than one Page."""
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/accounts",
                params={"access_token": user_access_token, "fields": "id,name,access_token,instagram_business_account"},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    async def subscribe_page_webhook(self, page_id: str, page_access_token: str) -> None:
        """Without this, Meta never delivers inbound DMs/comments to any
        webhook — mirrors Green API's ensure_incoming_webhook_enabled, same
        "do it once at connect time" reasoning."""
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{GRAPH_BASE}/{page_id}/subscribed_apps",
                params={
                    "access_token": page_access_token,
                    "subscribed_fields": "messages,messaging_postbacks,feed",
                },
            )
