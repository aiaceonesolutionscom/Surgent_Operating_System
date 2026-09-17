from __future__ import annotations
import logging
from uuid import UUID

from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.message import Message, MessageRole
from src.models.patient import Patient
from src.models.practice import Practice
from src.server.exceptions import NotFoundException
from src.services.channels.whatsapp_green_api import WhatsAppGreenAPI

logger = logging.getLogger("aesthetixai.conversations")

# Conversations created by a patient messaging their own doctor through the
# Patient Portal (patient_portal_services.py uses exactly this agent_type).
# They're deliberately NOT part of the unified Agent Sessions inbox — they
# read as "a message to your doctor", not AI-receptionist chatter — and get
# their own inbox (GET /conversations/patient-messages) plus the per-patient
# Communication tab instead.
PATIENT_DOCTOR_AGENT = "patient_doctor_message"


class ConversationsService:
    """Backs the dashboard's unified Agent Sessions inbox
    (frontend/src/app/dashboard/sessions/) — every method here is
    practice-scoped; callers must always pass the requesting user's own
    practice_id (see server/dependencies.py:get_current_practice_user),
    never trust one from the client."""

    async def list_conversations(
        self,
        db: AsyncSession,
        practice_id: UUID,
        status: ConversationStatus | None = None,
        channel: str | None = None,
        agent_types: list[str] | None = None,
        search: str | None = None,
        patient_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        query = (
            select(Conversation)
            .where(
                Conversation.practice_id == practice_id,
                # "Main Agent" (Command Center) sessions live in this same
                # table (see command_center_services.py) but are a staff
                # tool, not a patient conversation — they have no patient_id
                # and don't belong in this patient-facing inbox. Command
                # Center has its own dedicated history view already.
                Conversation.agent_type != "command_center",
            )
            .options(selectinload(Conversation.patient), selectinload(Conversation.messages))
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        if patient_id is not None:
            query = query.where(Conversation.patient_id == patient_id)
        else:
            # Page-wide "Agent Sessions" inbox: portal patient messages
            # ("a message to your doctor") don't belong here — they have
            # their own Patient Messages inbox and the doctor's per-patient
            # Communication tab. The per-patient filter above keeps them, so
            # the Communication tab still lists them.
            query = query.where(Conversation.agent_type != PATIENT_DOCTOR_AGENT)
        if status is not None:
            query = query.where(Conversation.status == status)
        if channel is not None:
            query = query.where(Conversation.channel == channel)
        if agent_types:
            query = query.where(Conversation.agent_type.in_(agent_types))
        if search:
            # Matches by patient name — a conversation with no linked patient
            # yet just won't match a text search, which is correct (there's
            # nothing to search on).
            pattern = f"%{search}%"
            query = query.join(Conversation.patient).where(
                or_(Patient.first_name.ilike(pattern), Patient.last_name.ilike(pattern))
            )

        result = await db.execute(query)
        return list(result.scalars().all())

    def __init__(self):
        self.patient_doctor_agent = PATIENT_DOCTOR_AGENT

    async def list_patient_messages(
        self,
        db: AsyncSession,
        practice_id: UUID,
        doctor_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversation]:
        """The dedicated Patient Messages inbox (frontend
        MessagesPage's "Patient messages" tab). Polls only conversations a
        patient sent their doctor through the portal
        (agent_type == patient_doctor_message). A Doctor sees only their own
        assigned patients' messages — `doctor_id` is their Doctor row (from
        patient_access.resolve_doctor_id), never a client-supplied value;
        Owner/Receptionist pass doctor_id=None and see every patient's
        portal messages (Owner read-only, decided at controller level)."""
        query = (
            select(Conversation)
            .where(
                Conversation.practice_id == practice_id,
                Conversation.agent_type == PATIENT_DOCTOR_AGENT,
            )
            .join(Conversation.patient)
            .options(selectinload(Conversation.patient), selectinload(Conversation.messages))
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        if doctor_id is not None:
            query = query.where(Patient.assigned_doctor_id == doctor_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_conversation(self, db: AsyncSession, practice_id: UUID, conversation_id: UUID) -> Conversation:
        query = (
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.practice_id == practice_id)
            .options(
                selectinload(Conversation.patient),
                selectinload(Conversation.messages),
            )
        )
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("Conversation not found")
        return conversation

    async def resolve_conversation(self, db: AsyncSession, practice_id: UUID, conversation_id: UUID) -> Conversation:
        conversation = await self.get_conversation(db, practice_id, conversation_id)
        conversation.status = ConversationStatus.RESOLVED
        conversation.is_active = False
        await db.flush()
        return conversation

    async def send_staff_message(
        self, db: AsyncSession, practice_id: UUID, conversation_id: UUID, body: str
    ) -> Conversation:
        """A staff member replying directly in a conversation — sends over
        the real channel (WhatsApp today) if the conversation has one, and
        pauses AI auto-replies so the AI Receptionist doesn't talk over a
        human who's already taken over. See InboundService._generate_reply's
        ai_paused check for the other half of this.

        The reply is ALWAYS saved to the conversation regardless of whether
        the real WhatsApp send succeeds — losing a staff member's typed
        message because of a transient network/API error would be worse than
        a delivery failure. But delivery outcome is no longer silently
        discarded (the old `except: pass` here meant a failed/skipped send
        looked identical to a successful one in the UI, with the patient
        never actually receiving it and no one finding out) — it's set as a
        transient (non-persisted) attribute on the returned Conversation,
        `_delivery_error`, which the controller reads and surfaces in the API
        response so the dashboard can show a real warning instead of a false
        "sent" state."""
        conversation = await self.get_conversation(db, practice_id, conversation_id)

        message = Message(conversation_id=conversation.id, role=MessageRole.STAFF, content=body, content_type="text")
        db.add(message)
        conversation.messages.append(message)

        conversation.extra_data = {**(conversation.extra_data or {}), "ai_paused": True}
        conversation.status = ConversationStatus.ACTIVE
        await db.flush()

        delivery_error: str | None = None
        if conversation.channel == ConversationChannel.WHATSAPP:
            if conversation.patient is None or not conversation.patient.phone:
                delivery_error = "No phone number on file for this patient — message saved but not sent to WhatsApp."
            else:
                practice = await db.get(Practice, practice_id)
                wa = WhatsAppGreenAPI.from_practice_settings((practice.settings if practice else None) or {})
                if wa is None:
                    delivery_error = "WhatsApp isn't connected for this practice yet (Settings → Integrations) — message saved but not sent."
                else:
                    try:
                        result = await wa.send_text(conversation.patient.phone, body)
                        # Green API returns 200 with an error payload (no idMessage)
                        # for real failures like an unauthorized/disconnected
                        # instance — swallowing that as a bare exception check
                        # alone missed exactly this case.
                        if not isinstance(result, dict) or not result.get("idMessage"):
                            delivery_error = f"WhatsApp didn't confirm delivery: {result}"
                            logger.warning("Green API send_text for conversation=%s returned no idMessage: %s", conversation.id, result)
                    except Exception as exc:
                        delivery_error = "Couldn't reach WhatsApp — message saved but not sent. Try again in a moment."
                        logger.warning("Green API send_text failed for conversation=%s: %s", conversation.id, exc)

        conversation._delivery_error = delivery_error
        return conversation

    async def toggle_ai(self, db: AsyncSession, practice_id: UUID, conversation_id: UUID, paused: bool) -> Conversation:
        conversation = await self.get_conversation(db, practice_id, conversation_id)
        conversation.extra_data = {**(conversation.extra_data or {}), "ai_paused": paused}
        await db.flush()
        return conversation

    @staticmethod
    def last_message_preview(conversation: Conversation) -> str:
        if not conversation.messages:
            return ""
        latest = max(conversation.messages, key=lambda m: m.created_at)
        return latest.content[:160]

    @staticmethod
    def patient_display_name(conversation: Conversation) -> str:
        if conversation.patient is None:
            return "Unknown"
        return f"{conversation.patient.first_name} {conversation.patient.last_name}".strip()
