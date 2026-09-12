from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation, ConversationStatus
from src.models.user import User, UserRole
from src.schemas.conversation import ConversationListItem, ConversationDetail, MessageResponse
from src.server.exceptions import ForbiddenException, NotFoundException
from src.server.patient_access import resolve_doctor_id, verify_doctor_access
from src.services.conversations.conversations_services import ConversationsService


class ConversationsController:
    def __init__(self):
        self.service = ConversationsService()

    def _list_item(self, c: Conversation, can_reply: bool = True) -> ConversationListItem:
        extra = c.extra_data or {}
        return ConversationListItem(
            id=c.id,
            patient_id=c.patient_id,
            patient_name=self.service.patient_display_name(c),
            agent_type=c.agent_type,
            channel=c.channel.value,
            status=c.status.value,
            last_message_preview=self.service.last_message_preview(c),
            updated_at=c.updated_at,
            avatar_url=extra.get("avatar_url"),
            ai_paused=bool(extra.get("ai_paused")),
            ai_booked_appointment_id=extra.get("ai_booked_appointment_id"),
            can_reply=can_reply,
        )

    @staticmethod
    def _can_reply_for(user: User) -> bool:
        # Only the assigned doctor and the receptionist answer portal patient
        # messages. The Owner sees the whole inbox but read-only (this app's
        # never edited from the owner seat — clinical messaging is a
        # doctor/receptionist responsibility).
        return user.role != UserRole.OWNER

    async def list_conversations(
        self,
        db: AsyncSession,
        user: User,
        status: ConversationStatus | None,
        channel: str | None,
        agent_type: list[str] | None,
        search: str | None,
        patient_id: UUID | None,
        limit: int,
        offset: int,
    ) -> list[ConversationListItem]:
        if patient_id is not None:
            # Closes the gap a Doctor role would otherwise have: without
            # this, any authenticated staff member could pass an arbitrary
            # patient_id and read that patient's conversations regardless
            # of assignment. Owner/Receptionist pass through as a no-op.
            await verify_doctor_access(db, user, patient_id)
        elif user.role == UserRole.DOCTOR:
            # No patient_id at all means "browse everything" — the
            # practice-wide lead/CRM inbox, which is Owner/Receptionist
            # territory (see Sidebar.tsx's own role gate on this same
            # feature). A Doctor must always pass a specific patient_id.
            return []
        conversations = await self.service.list_conversations(
            db,
            practice_id=user.practice_id,
            status=status,
            channel=channel,
            agent_types=agent_type,
            search=search,
            patient_id=patient_id,
            limit=limit,
            offset=offset,
        )
        return [self._list_item(c) for c in conversations]

    async def get_conversation(self, db: AsyncSession, user: User, conversation_id: UUID) -> ConversationDetail:
        c = await self.service.get_conversation(db, user.practice_id, conversation_id)
        # Portal patient messages get their own access/visibility rules (own
        # doctor + receptionist; owner read-only) no matter which endpoint
        # surface reaches them — enforce the same gate here as on the
        # dedicated /patient-messages routes so a generic call can't side-step
        # the Doctor hard-restriction or the Owner read-only rule.
        if c.agent_type == self.service.patient_doctor_agent:
            return await self.get_patient_message(db, user, conversation_id)
        item = self._list_item(c)
        return ConversationDetail(
            **item.model_dump(),
            messages=[MessageResponse.model_validate(m) for m in sorted(c.messages, key=lambda m: m.created_at)],
        )

    async def resolve_conversation(self, db: AsyncSession, user: User, conversation_id: UUID) -> ConversationDetail:
        c = await self.service.get_conversation(db, user.practice_id, conversation_id)
        if c.agent_type == self.service.patient_doctor_agent:
            await self._require_can_reply(db, user, conversation_id)
        await self.service.resolve_conversation(db, user.practice_id, conversation_id)
        return await self.get_conversation(db, user, conversation_id)

    async def send_message(self, db: AsyncSession, user: User, conversation_id: UUID, body: str) -> ConversationDetail:
        c = await self.service.get_conversation(db, user.practice_id, conversation_id)
        if c.agent_type == self.service.patient_doctor_agent:
            # Owner read-only applies to portal patient messages even via the
            # generic reply route.
            await self._require_can_reply(db, user, conversation_id)
        await self.service.send_staff_message(db, user.practice_id, conversation_id, body)
        return await self.get_conversation(db, user, conversation_id)

    async def toggle_ai(self, db: AsyncSession, user: User, conversation_id: UUID, paused: bool) -> ConversationDetail:
        await self.service.toggle_ai(db, user.practice_id, conversation_id, paused)
        return await self.get_conversation(db, user, conversation_id)

    # --- Patient Messages (portal: patient → assigned doctor) ------------

    async def list_patient_messages(self, db: AsyncSession, user: User, limit: int, offset: int) -> list[ConversationListItem]:
        doctor_id = None if user.role != UserRole.DOCTOR else await resolve_doctor_id(db, user)
        conversations = await self.service.list_patient_messages(db, user.practice_id, doctor_id=doctor_id, limit=limit, offset=offset)
        can_reply = self._can_reply_for(user)
        return [self._list_item(c, can_reply=can_reply) for c in conversations]

    async def _get_patient_message(self, db: AsyncSession, user: User, conversation_id: UUID) -> Conversation:
        conversation = await self.service.get_conversation(db, user.practice_id, conversation_id)
        if conversation.agent_type != self.service.patient_doctor_agent:
            # Not a portal patient message — this surface only serves those.
            raise NotFoundException("Patient message not found")
        if conversation.patient_id is None:
            raise NotFoundException("Patient message not found")
        # Doctor hard-restriction: only their own assigned patients' messages.
        # Owner/Receptionist pass through as a no-op.
        await verify_doctor_access(db, user, conversation.patient_id)
        return conversation

    async def get_patient_message(self, db: AsyncSession, user: User, conversation_id: UUID) -> ConversationDetail:
        c = await self._get_patient_message(db, user, conversation_id)
        item = self._list_item(c, can_reply=self._can_reply_for(user))
        return ConversationDetail(
            **item.model_dump(),
            messages=[MessageResponse.model_validate(m) for m in sorted(c.messages, key=lambda m: m.created_at)],
        )

    async def _require_can_reply(self, db: AsyncSession, user: User, conversation_id: UUID) -> Conversation:
        conversation = await self._get_patient_message(db, user, conversation_id)
        if not self._can_reply_for(user):
            raise ForbiddenException("Only a doctor or the receptionist can reply to patient messages — you have read-only access")
        return conversation

    async def reply_to_patient_message(self, db: AsyncSession, user: User, conversation_id: UUID, body: str) -> ConversationDetail:
        await self.service.send_staff_message(db, user.practice_id, conversation_id, body)
        return await self.get_patient_message(db, user, conversation_id)

    async def resolve_patient_message(self, db: AsyncSession, user: User, conversation_id: UUID) -> ConversationDetail:
        await self._require_can_reply(db, user, conversation_id)
        await self.service.resolve_conversation(db, user.practice_id, conversation_id)
        return await self.get_patient_message(db, user, conversation_id)
