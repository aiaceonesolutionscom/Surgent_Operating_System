from __future__ import annotations
import httpx
import jwt
from jwt import PyJWKClient

from src.config import get_settings
from src.server.exceptions import AppException

settings = get_settings()


class ClerkService:
    def __init__(self):
        self.secret_key = settings.clerk_secret_key
        self.jwks_url = settings.clerk_jwks_url
        self.base_url = "https://api.clerk.com/v1"

    async def verify_token(self, token: str) -> dict | None:
        try:
            jwks_client = PyJWKClient(self.jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=None,
                options={"verify_exp": True},
                # A few seconds of clock skew between this machine and
                # Clerk's servers is normal, not a sign of a bad token — an
                # exact iat/nbf check with zero tolerance was rejecting
                # freshly-issued, genuinely valid tokens as "not yet valid"
                # on every request (verified against real Clerk session
                # tokens, not a hypothetical).
                leeway=10,
            )

            return {
                "sub": payload.get("sub"),
                "email": payload.get("email"),
                "name": payload.get("name"),
            }
        except Exception:
            return None

    async def get_user(self, clerk_user_id: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {self.secret_key}"},
            )
            if resp.status_code == 200:
                return resp.json()
            return None

    async def find_user_by_email(self, email: str) -> dict | None:
        # Clerk's array-filter params take the bare key repeated, NOT the
        # `email_address[]` bracket form (that's silently ignored and
        # returns every user in the instance, unfiltered — verified against
        # the real API before trusting this).
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/users",
                params=[("email_address", email)],
                headers={"Authorization": f"Bearer {self.secret_key}"},
            )
            if resp.status_code == 200:
                results = resp.json()
                return results[0] if results else None
            return None

    async def create_user(self, email: str, password: str, first_name: str, last_name: str) -> dict:
        """Directly provisions a real Clerk account with an immediately-usable
        password login — for seeding dev/demo staff accounts, as opposed to
        invite_user's email-invite flow (which needs the invitee to complete
        Clerk's own sign-up UI). Backend-API-created users' emails come back
        already verified, so this account can sign in right away."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/users",
                json={
                    "email_address": [email],
                    "password": password,
                    "first_name": first_name,
                    "last_name": last_name,
                    "skip_password_checks": True,
                },
                headers={"Authorization": f"Bearer {self.secret_key}"},
            )
            if resp.status_code in (200, 201):
                return resp.json()
            detail = "Failed to create Clerk user"
            try:
                errors = resp.json().get("errors") or []
                if errors and errors[0].get("message"):
                    detail = errors[0]["message"]
            except ValueError:
                pass
            raise AppException(detail)

    async def has_pending_invitation(self, email: str) -> bool:
        """Checks Clerk for an already-outstanding (not yet accepted/revoked)
        invitation to this email — used to stop invite_staff/invite_doctor
        from firing a second invite email on a double-click or retry, since
        Clerk itself has no idempotency here and happily sends duplicates."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/invitations",
                params=[("email_address", email), ("status", "pending")],
                headers={"Authorization": f"Bearer {self.secret_key}"},
            )
            if resp.status_code == 200:
                results = resp.json()
                data = results.get("data") if isinstance(results, dict) else results
                return bool(data)
            return False

    async def invite_user(self, email: str, redirect_url: str, public_metadata: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/invitations",
                json={
                    "email_address": email,
                    "redirect_url": redirect_url,
                    "public_metadata": public_metadata,
                },
                headers={"Authorization": f"Bearer {self.secret_key}"},
            )
            if resp.status_code in (200, 201):
                return resp.json()
            # Clerk's error body carries the real, specific reason (e.g.
            # "That email address is taken." when inviting an email that
            # already has an account) — surface that instead of a generic
            # failure, same reasoning as apiFetch()'s fix on the frontend.
            detail = "Failed to send invitation"
            try:
                errors = resp.json().get("errors") or []
                if errors and errors[0].get("message"):
                    detail = errors[0]["message"]
            except ValueError:
                pass
            raise AppException(detail)
