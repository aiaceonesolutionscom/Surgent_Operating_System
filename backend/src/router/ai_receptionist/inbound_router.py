from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import get_db
from src.server.exceptions import AppException, UnauthorizedException
from src.services.channels.inbound_service import InboundService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-receptionist/inbound", tags=["Inbound Webhooks"])
inbound = InboundService()


def _require_webhook_secret(request: Request) -> None:
    """Authenticate a push webhook. Without this, anyone who knows a clinic's
    Green API `idInstance` could inject patient messages, spend the clinic's
    LLM budget and make its WhatsApp number text arbitrary people."""
    settings = get_settings()
    secret = settings.green_api_webhook_secret
    if not secret:
        if settings.app_env == "development":
            return
        raise AppException("Inbound webhook secret is not configured", status_code=503)
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), secret.encode()):
        raise UnauthorizedException("Invalid webhook credentials")


@router.post("/whatsapp")
async def receive_whatsapp_message(request: Request) -> dict:
    """Webhook endpoint for GREEN-API incoming WhatsApp messages.

    Green API sends POST requests to this URL when a patient sends a
    WhatsApp message to the connected number.  The payload format is:

    {
        "typeWebhook": "incomingMessageReceived",
        "instanceData": {"idInstance": "...", ...},
        "senderData": {
            "chatId": "923468063112@c.us",
            "sender": "923468063112",
            "senderName": "Ahmed Khan"
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": "Hello, I want to book an appointment"}
        }
    }
    """
    _require_webhook_secret(request)
    payload = await request.json()
    webhook_type = payload.get("typeWebhook", "")

    # Only process incoming text messages
    if webhook_type != "incomingMessageReceived":
        return {"status": "ignored", "type": webhook_type}

    # Also ignore outgoing messages (we send them, no need to process)
    if webhook_type == "outgoingMessageReceived":
        return {"status": "ignored", "type": webhook_type}

    message_data = payload.get("messageData", {})
    message_type = message_data.get("typeMessage", "")

    # For now, only handle text messages
    if message_type != "textMessage":
        logger.info("Ignoring non-text message type: %s", message_type)
        return {"status": "ignored", "type": message_type}

    # Extract data
    sender_data = payload.get("senderData", {})
    instance_data = payload.get("instanceData", {})

    phone = sender_data.get("sender", "")
    sender_name = sender_data.get("senderName", "Unknown")
    chat_id = sender_data.get("chatId", "")
    message_text = message_data.get("textMessageData", {}).get("textMessage", "")
    instance_id = instance_data.get("idInstance", "")

    if not phone or not message_text:
        return {"status": "error", "detail": "Missing phone or message"}

    # Get database session
    async for db in get_db():
        try:
            result = await inbound.handle_whatsapp_message(
                db=db,
                phone_number=phone,
                sender_name=sender_name,
                message_text=message_text,
                instance_id=instance_id,
            )
            await db.commit()
            logger.info("WhatsApp message handled: %s -> %s", phone, result.get("reply", "")[:50])
            return {"status": "ok", **result}
        except Exception as e:
            await db.rollback()
            logger.exception("Error handling WhatsApp message from %s", phone)
            return {"status": "error", "detail": "Could not process the message"}

    return {"status": "error", "detail": "Database session failed"}


@router.post("/messenger")
async def receive_messenger_message(request: Request) -> dict:
    """Webhook endpoint for Facebook Messenger incoming messages.
    TODO: Implement when Facebook integration is added."""
    return {"status": "not_implemented"}


@router.post("/instagram")
async def receive_instagram_message(request: Request) -> dict:
    """Webhook endpoint for Instagram DM incoming messages.
    TODO: Implement when Instagram integration is added."""
    return {"status": "not_implemented"}


@router.get("/whatsapp/verify")
async def verify_webhook(request: Request) -> Response:
    """Webhook verification endpoint for Meta/Facebook webhooks.
    Also used by Green API for health checks."""
    return Response(content="OK", media_type="text/plain")
