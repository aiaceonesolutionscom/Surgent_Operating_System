from __future__ import annotations
import asyncio
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.message import Message, MessageRole
from src.models.patient import Patient
from src.models.practice import Practice
from src.server.exceptions import AppException, NotFoundException
from src.services.twilio.twilio_service import TwilioService
from src.services.channels.whatsapp_green_api import WhatsAppGreenAPI


class MessagingService:
    """Shared outbound-messaging path for every agent that needs to reach a
    patient (reminders, review requests, marketing offers, post-op
    follow-ups) — resolves which channel to use, sends via the real
    Twilio/WhatsApp clients, and records the send as a real
    Conversation/Message so it shows up in the dashboard's Agent Sessions
    inbox like any other conversation.

    WhatsApp sends go through WhatsAppGreenAPI (per-practice instance_id/
    api_token in Practice.settings["green_api"]) — the same integration
    already proven live for inbound messages all session — not the official
    Meta Business Cloud API class this used before, which reads
    WHATSAPP_API_TOKEN/WHATSAPP_PHONE_NUMBER_ID (still placeholders,
    per .env.example) and would silently "succeed" against Meta's real
    servers with an auth error nobody was checking for, meaning every
    automated WhatsApp send through here — appointment reminders included —
    was never actually delivering."""

    def __init__(self):
        self.twilio = TwilioService()

    async def resolve_channel(self, db: AsyncSession, practice_id: UUID, patient: Patient) -> ConversationChannel:
        # No stored channel preference exists on Patient — infer from the
        # patient's most recent conversation (how they last actually reached
        # the practice), falling back to SMS if they have a phone on file and
        # WhatsApp is unavailable to infer from. See models/patient.py.
        result = await db.execute(
            select(Conversation)
            .where(Conversation.practice_id == practice_id, Conversation.patient_id == patient.id)
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest is not None and latest.channel in (ConversationChannel.SMS, ConversationChannel.WHATSAPP, ConversationChannel.PHONE):
            return ConversationChannel.SMS if latest.channel == ConversationChannel.PHONE else latest.channel
        if patient.phone:
            return ConversationChannel.SMS
        raise AppException("No phone number or messaging channel on file for this patient")

    async def _find_or_create_conversation(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID, agent_type: str, channel: ConversationChannel
    ) -> Conversation:
        # Matched on (practice, patient, channel) ONLY — not agent_type. This
        # used to key on agent_type too, so a reminder, a billing receipt,
        # and a post-op follow-up to the SAME patient over the SAME WhatsApp
        # number each got their own separate Conversation row, and none of
        # them reused the thread InboundService already has open for that
        # patient's inbound replies (agent_type="ai_receptionist") either —
        # from the patient's side it's one WhatsApp chat; the dashboard was
        # showing it back as several unrelated ones. One row per
        # (patient, channel) is what actually matches a real WhatsApp thread.
        # A resolved thread is reused too (reactivated to ACTIVE), never
        # abandoned for a fresh one — same reasoning as
        # InboundService._find_or_create_conversation's identical fix.
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.practice_id == practice_id,
                Conversation.patient_id == patient_id,
                Conversation.channel == channel,
            )
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.status == ConversationStatus.RESOLVED:
                existing.status = ConversationStatus.ACTIVE
                await db.flush()
            return existing

        conversation = Conversation(
            practice_id=practice_id,
            patient_id=patient_id,
            agent_type=agent_type,
            channel=channel,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def send_and_log(
        self, db: AsyncSession, practice_id: UUID, patient: Patient, agent_type: str, text: str
    ) -> Message:
        channel = await self.resolve_channel(db, practice_id, patient)
        if not patient.phone:
            raise AppException("Patient has no phone number on file to message")

        try:
            if channel == ConversationChannel.WHATSAPP:
                result = await db.execute(select(Practice).where(Practice.id == practice_id))
                practice = result.scalar_one_or_none()
                ga = WhatsAppGreenAPI.from_practice_settings((practice.settings if practice else None) or {})
                if ga is None:
                    raise AppException("WhatsApp isn't connected for this practice yet")
                send_result = await ga.send_text(patient.phone, text)
                # A real successful sendMessage call returns a flat
                # {"idMessage": "..."} — see the matching fix + comment on
                # InboundService._send_reply for how this was confirmed
                # against the live API.
                if "idMessage" not in send_result:
                    raise AppException(f"WhatsApp send did not return a message id: {send_result}")
            else:
                # Twilio's SDK is synchronous (blocking network I/O) — run it
                # off the event loop rather than stalling every other
                # in-flight request.
                await asyncio.to_thread(self.twilio.send_sms, patient.phone, text)
        except AppException:
            raise
        except Exception as exc:
            raise AppException(f"Failed to send message via {channel.value}: {exc}")

        conversation = await self._find_or_create_conversation(db, practice_id, patient.id, agent_type, channel)
        message = Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=text)
        db.add(message)
        await db.flush()
        return message

    async def send_document_and_log(
        self, db: AsyncSession, practice_id: UUID, patient: Patient, agent_type: str,
        file_url: str, filename: str, caption: str,
    ) -> Message:
        # WhatsApp-only — Green API is the only channel here that can carry
        # a document (see WhatsAppGreenAPI.send_file_by_url); Twilio SMS has
        # no attachment support in this codebase. Callers (invoice receipts)
        # already send a plain-text fallback through send_and_log first, so
        # this raising for a non-WhatsApp patient is expected, not fatal.
        channel = await self.resolve_channel(db, practice_id, patient)
        if channel != ConversationChannel.WHATSAPP:
            raise AppException("Patient's channel isn't WhatsApp — can't send a document.")

        result = await db.execute(select(Practice).where(Practice.id == practice_id))
        practice = result.scalar_one_or_none()
        ga = WhatsAppGreenAPI.from_practice_settings((practice.settings if practice else None) or {})
        if ga is None:
            raise AppException("WhatsApp isn't connected for this practice yet")

        send_result = await ga.send_file_by_url(patient.phone, file_url, filename, caption)
        if "idMessage" not in send_result:
            raise AppException(f"WhatsApp file send did not return a message id: {send_result}")

        conversation = await self._find_or_create_conversation(db, practice_id, patient.id, agent_type, channel)
        message = Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=f"{caption}\n[Attached: {filename}]")
        db.add(message)
        await db.flush()
        return message
