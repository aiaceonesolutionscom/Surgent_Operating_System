from __future__ import annotations

import httpx

from src.config import get_settings

settings = get_settings()


class WhatsAppGreenAPI:
    """Wrapper for GREEN-API (green-api.com) — unofficial WhatsApp API.
    Each practice gets its own instance (idInstance + apiTokenInstance)
    stored in Practice.settings under the key "green_api".  This class
    only handles send/receive — the webhook router orchestrates the
    inbound flow (LLM reply, conversation persistence, etc.)."""

    def __init__(self, instance_id: str, api_token: str):
        self.instance_id = instance_id
        self.api_token = api_token
        self.base_url = f"https://api.green-api.com/waInstance{instance_id}"

    @classmethod
    def from_practice_settings(cls, practice_settings: dict) -> "WhatsAppGreenAPI | None":
        """Build an instance from Practice.settings JSONB.
        Returns None if Green API is not configured for this practice."""
        ga = practice_settings.get("green_api", {})
        instance_id = ga.get("instance_id")
        api_token = ga.get("api_token")
        if not instance_id or not api_token:
            return None
        return cls(instance_id=instance_id, api_token=api_token)

    async def send_text(self, phone_number: str, message: str) -> dict:
        """Send a text message.  phone_number should be in国际 format
        without + or @c.us (e.g. '923468063112')."""
        chat_id = f"{phone_number}@c.us" if "@c.us" not in phone_number else phone_number
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/sendMessage/{self.api_token}",
                json={
                    "chatId": chat_id,
                    "message": message,
                },
            )
            return resp.json()

    async def send_file_by_url(self, phone_number: str, file_url: str, filename: str, caption: str | None = None) -> dict:
        """Send a document (PDF receipt/invoice, etc.) by public URL —
        Green API's sendFileByUrl, sibling to send_text above. The file has
        to already be hosted somewhere Green API's servers can fetch it
        (Cloudinary, via StorageService) — there's no raw-bytes upload
        endpoint on the free/basic Green API tier."""
        chat_id = f"{phone_number}@c.us" if "@c.us" not in phone_number else phone_number
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/sendFileByUrl/{self.api_token}",
                json={
                    "chatId": chat_id,
                    "urlFile": file_url,
                    "fileName": filename,
                    "caption": caption or "",
                },
            )
            return resp.json()

    async def get_state(self) -> dict:
        """Check instance connection status (authorized / notAuthorized / etc.)."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/getStateInstance/{self.api_token}",
            )
            return resp.json()

    async def download_file(self, url: str) -> bytes:
        """Download a media file (image, audio, etc.) from an incoming message."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            return resp.content

    async def receive_notification(self, timeout: int = 5) -> dict | None:
        """Pull one incoming notification from the queue (polling, no webhook needed).
        Returns {"receiptId": ..., "body": {...}} or None if the queue is empty."""
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            resp = await client.get(
                f"{self.base_url}/receiveNotification/{self.api_token}",
                params={"receiveTimeout": timeout},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data:
                return None
            return data

    async def delete_notification(self, receipt_id: int) -> bool:
        """Acknowledge + remove a processed notification from the queue.

        Green API takes receiptId as a path segment on a DELETE request —
        NOT a query param on GET (confirmed against the real API: the query-
        param form 404s with "Cannot GET ...deleteNotification/<token>?receiptId=1").
        Getting this wrong meant every notification was silently
        never actually deleted, so the SAME incoming message got redelivered
        and reprocessed on every poll forever — a real, previously-unnoticed
        bug that duplicates every incoming WhatsApp message indefinitely."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(f"{self.base_url}/deleteNotification/{self.api_token}/{receipt_id}")
            return resp.status_code == 200

    async def ensure_incoming_webhook_enabled(self) -> bool:
        """Green API instances default to `incomingWebhook: no` — with that
        off, incoming messages never reach the notification queue at all
        (receiveNotification just comes back empty forever, silently, no
        error anywhere). There's no connection-setup UI yet — instances are
        wired up by hand — so nothing has ever turned this on. Called once
        per instance by the poller instead. Returns True if it had to change
        anything (so the caller can log that clearly)."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.base_url}/getSettings/{self.api_token}")
            if resp.status_code != 200:
                return False
            if resp.json().get("incomingWebhook") == "yes":
                return False
            await client.post(f"{self.base_url}/setSettings/{self.api_token}", json={"incomingWebhook": "yes"})
            return True

    async def get_avatar(self, phone_number: str) -> tuple[str | None, bool]:
        """Fetch the avatar URL for a contact.

        Returns (url_or_none, definitive) — `definitive` is False when the
        call itself failed (e.g. Green API's free-tier getAvatar quota is a
        low monthly count and gets exhausted fast), so the caller knows not
        to permanently cache a "no photo" result for what was actually just
        a failed check. `definitive=True` with url=None means Green API
        genuinely answered "this contact has no photo," which IS safe to
        cache — it won't change between checks."""
        chat_id = f"{phone_number}@c.us" if "@c.us" not in phone_number else phone_number
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/getAvatar/{self.api_token}",
                params={"chatId": chat_id},
            )
            if resp.status_code != 200:
                return None, False
            data = resp.json()
            return (data.get("urlAvatar") or data.get("avatar")), True
