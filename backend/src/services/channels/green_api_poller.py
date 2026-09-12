from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from src.database import async_session_factory
from src.models.practice import Practice
from src.services.channels.inbound_service import InboundService
from src.services.channels.whatsapp_green_api import WhatsAppGreenAPI
from src.services.speech.speech_service import SpeechService
from src.services.storage.storage_service import StorageService
from sqlalchemy import select

logger = logging.getLogger(__name__)

_INTERVAL_SECONDS = 3


class GreenAPIPoller:
    """Background poller that pulls incoming WhatsApp notifications from the
    Green API queue (HTTP polling — no public webhook URL required).

    Green API keeps incoming notifications in a queue for 24h. This poller
    calls `receiveNotification` every few seconds, processes each incoming
    text message via InboundService, then acknowledges it with
    `deleteNotification` so it isn't processed twice.
    """

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        # Checked once per instance per process lifetime, not every tick —
        # this is an extra API call, and the setting doesn't change on its
        # own once fixed.
        self._webhook_checked: set[str] = set()

    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._poll(practice_id=None))]
        logger.info("Green API poller started")

    def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    async def _poll(self, practice_id=None) -> None:
        inbound = InboundService()
        while True:
            try:
                await self._tick(inbound)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Green API poller tick failed")
            await asyncio.sleep(_INTERVAL_SECONDS)

    async def _tick(self, inbound: InboundService) -> None:
        instances = await self._load_practice_instances()
        for instance_id, token in instances:
            wa = WhatsAppGreenAPI(instance_id, token)
            try:
                state = await wa.get_state()
            except Exception:
                logger.debug("Instance %s not reachable", instance_id)
                continue
            if state.get("stateInstance") != "authorized":
                continue

            if instance_id not in self._webhook_checked:
                try:
                    fixed = await wa.ensure_incoming_webhook_enabled()
                    if fixed:
                        logger.warning(
                            "Instance %s had incomingWebhook disabled (would have silently "
                            "dropped every incoming message) — enabled it now.",
                            instance_id,
                        )
                except Exception:
                    logger.exception("Failed to check/enable incomingWebhook for instance %s", instance_id)
                self._webhook_checked.add(instance_id)

            notification = await wa.receive_notification(timeout=5)
            while notification:
                receipt_id = notification.get("receiptId")
                body = notification.get("body") or {}
                try:
                    await self._process_notification(inbound, instance_id, body, wa)
                except Exception:
                    logger.exception("Failed processing notification %s", receipt_id)
                if receipt_id is not None:
                    try:
                        await wa.delete_notification(int(receipt_id))
                    except Exception:
                        logger.warning("Failed to delete notification %s", receipt_id)
                notification = await wa.receive_notification(timeout=5)

    async def _load_practice_instances(self) -> list[tuple[str, str]]:
        """Load all confirmed Green API instances from practice settings."""
        async with async_session_factory() as db:
            result = await db.execute(select(Practice))
            instances = []
            for practice in result.scalars().all():
                ga = (practice.settings or {}).get("green_api", {})
                instance_id = ga.get("instance_id")
                token = ga.get("api_token")
                if instance_id and token:
                    instances.append((instance_id, token))
            return instances

    async def _process_notification(self, inbound: InboundService, instance_id: str, body: dict, wa: WhatsAppGreenAPI) -> None:
        webhook_type = body.get("typeWebhook")
        if webhook_type != "incomingMessageReceived":
            logger.info("Received non-message webhook type: %s", webhook_type)
            return

        message_data = body.get("messageData", {})
        type_message = message_data.get("typeMessage")

        message_text = ""
        content_type = "text"
        extra_data = {}

        if type_message == "textMessage":
            message_text = message_data.get("textMessageData", {}).get("textMessage", "")

        elif type_message == "audioMessage":
            download_url = message_data.get("fileMessageData", {}).get("downloadUrl")
            if not download_url:
                logger.info("Audio message with no downloadUrl, skipping")
                return
            try:
                audio_bytes = await wa.download_file(download_url)
                # Upload audio to Cloudinary before transcription
                storage = StorageService()
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                audio_filename = f"voice_note_{ts}"
                upload_result = await storage.upload(
                    audio_bytes, audio_filename,
                    folder="voice_notes", resource_type="video"
                )
                audio_url = upload_result.get("url", "")
                # Transcribe via Deepgram (primary) or Groq (fallback)
                message_text = await SpeechService().transcribe(audio_bytes, filename="voice_note.ogg")
                content_type = "audio"
                extra_data = {
                    "audio_url": audio_url,
                    "transcription": message_text,
                    "duration_seconds": 0,
                }
            except Exception:
                logger.exception("Failed to process incoming voice note")
                return
            if not message_text.strip():
                logger.info("Voice note transcribed to empty text, skipping")
                return
            logger.info("Transcribed voice note: %s", message_text[:100])

        elif type_message == "imageMessage":
            download_url = message_data.get("fileMessageData", {}).get("downloadUrl")
            if not download_url:
                logger.info("Image message with no downloadUrl, skipping")
                return
            try:
                image_bytes = await wa.download_file(download_url)
                storage = StorageService()
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                ext = message_data.get("fileMessageData", {}).get("fileName", "image.jpg").rsplit(".", 1)[-1] or "jpg"
                image_filename = f"whatsapp_image_{ts}.{ext}"
                upload_result = await storage.upload(
                    image_bytes, image_filename,
                    folder="whatsapp_media", resource_type="image"
                )
                image_url = upload_result.get("url", "")
                caption = message_data.get("fileMessageData", {}).get("caption", "")
                message_text = caption or "[Image]"
                content_type = "image"
                extra_data = {"image_url": image_url, "filename": image_filename}
            except Exception:
                logger.exception("Failed to process incoming image")
                return

        elif type_message == "documentMessage":
            download_url = message_data.get("fileMessageData", {}).get("downloadUrl")
            if not download_url:
                logger.info("Document message with no downloadUrl, skipping")
                return
            try:
                doc_bytes = await wa.download_file(download_url)
                storage = StorageService()
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                filename = message_data.get("fileMessageData", {}).get("fileName", f"document_{ts}")
                upload_result = await storage.upload(
                    doc_bytes, filename,
                    folder="whatsapp_media", resource_type="raw"
                )
                doc_url = upload_result.get("url", "")
                caption = message_data.get("fileMessageData", {}).get("caption", "")
                message_text = caption or f"[Document: {filename}]"
                content_type = "file"
                extra_data = {"file_url": doc_url, "filename": filename}
            except Exception:
                logger.exception("Failed to process incoming document")
                return

        elif type_message == "videoMessage":
            download_url = message_data.get("fileMessageData", {}).get("downloadUrl")
            if not download_url:
                logger.info("Video message with no downloadUrl, skipping")
                return
            try:
                video_bytes = await wa.download_file(download_url)
                storage = StorageService()
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                video_filename = f"whatsapp_video_{ts}.mp4"
                upload_result = await storage.upload(
                    video_bytes, video_filename,
                    folder="whatsapp_media", resource_type="video"
                )
                video_url = upload_result.get("url", "")
                caption = message_data.get("fileMessageData", {}).get("caption", "")
                message_text = caption or "[Video]"
                content_type = "video"
                extra_data = {"video_url": video_url, "filename": video_filename}
            except Exception:
                logger.exception("Failed to process incoming video")
                return

        else:
            logger.info("Ignoring unsupported message type: %s", type_message)
            return

        sender_data = body.get("senderData", {})
        chat_id = sender_data.get("chatId", "")

        # Group chats end in "@g.us" (individuals end in "@c.us") — the
        # connected number can be a member of ordinary WhatsApp groups
        # (dev groups, course batches, whatever) that have nothing to do
        # with the clinic. Without this check, a group's long numeric chat
        # ID was being stripped of its suffix and treated as if it were a
        # patient's own phone number — creating a fake "patient" out of
        # someone else's group-chat display name, and the AI receptionist
        # would have started replying into that group. This is a hard skip,
        # not something to route anywhere.
        if chat_id.endswith("@g.us"):
            logger.info("Ignoring group chat message from %s", chat_id)
            return

        phone = (sender_data.get("sender") or "").replace("@c.us", "").replace("@g.us", "")
        sender_name = sender_data.get("senderName", "Unknown")

        if not phone or not message_text:
            return

        phone_from_chat = chat_id.replace("@c.us", "").replace("@g.us", "") if chat_id else phone

        async with async_session_factory() as db:
            result = await inbound.handle_whatsapp_message(
                db=db,
                phone_number=phone_from_chat,
                sender_name=sender_name,
                message_text=message_text,
                instance_id=instance_id,
                content_type=content_type,
                extra_data=extra_data,
            )
            await db.commit()
            logger.info(
                "WhatsApp handled: %s -> %s (sent=%s)",
                phone_from_chat,
                (result.get("reply") or "")[:50],
                result.get("sent"),
            )
