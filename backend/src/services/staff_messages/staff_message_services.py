from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.staff_message import StaffConversation, StaffMessage
from src.models.user import User
from src.schemas.staff_message import StaffContactResponse, StaffConversationResponse
from src.server.exceptions import NotFoundException, ForbiddenException
from src.services.cloudinary.cloudinary_service import CloudinaryService


class StaffMessageService:
    """One-to-one chat between any two active users of a practice. Threads
    are real conversations (user pairs stored canonically), so anyone on the
    team — owner, doctor, receptionist — can message anyone else. Every
    method is practice-scoped; participants are the only people who can read
    or write a conversation."""

    def __init__(self):
        self.cloudinary = CloudinaryService()

    async def _resolve_user(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> User:
        result = await db.execute(
            select(User).where(User.id == user_id, User.practice_id == practice_id, User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundException("User not found")
        return user

    async def _get_participant_conversation(
        self, db: AsyncSession, practice_id: UUID, user: User, conversation_id: UUID
    ) -> StaffConversation:
        result = await db.execute(
            select(StaffConversation).where(
                StaffConversation.id == conversation_id, StaffConversation.practice_id == practice_id
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("Conversation not found")
        if user.id not in (conversation.user_a_id, conversation.user_b_id):
            raise ForbiddenException("You can only view conversations you are part of.")
        return conversation

    async def list_contacts(self, db: AsyncSession, practice_id: UUID, user: User) -> list[StaffContactResponse]:
        """Every other active member of the practice — who you can start a
        conversation with."""
        result = await db.execute(
            select(User).where(
                User.practice_id == practice_id,
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        members = sorted(
            list(result.scalars().all()),
            key=lambda u: (u.role.value, (u.name or "").lower()),
        )
        return [
            StaffContactResponse(id=m.id, name=m.name, role=m.role.value, email=m.email)
            for m in members
        ]

    async def list_conversations(
        self, db: AsyncSession, practice_id: UUID, user: User
    ) -> list[StaffConversationResponse]:
        result = await db.execute(
            select(StaffConversation).where(
                StaffConversation.practice_id == practice_id,
                or_(
                    StaffConversation.user_a_id == user.id,
                    StaffConversation.user_b_id == user.id,
                )
            )
        )
        conversations = list(result.scalars().all())
        if not conversations:
            return []

        ids = [c.id for c in conversations]
        participant_ids = {user.id}
        for c in conversations:
            participant_ids.add(c.user_a_id)
            participant_ids.add(c.user_b_id)

        users_result = await db.execute(select(User).where(User.id.in_(participant_ids), User.practice_id == practice_id))
        users = {u.id: u for u in users_result.scalars().all()}

        counts_result = await db.execute(
            select(StaffMessage.conversation_id, func.count())
            .where(StaffMessage.conversation_id.in_(ids), StaffMessage.practice_id == practice_id)
            .group_by(StaffMessage.conversation_id)
        )
        counts = dict(counts_result.all())

        last_result = await db.execute(
            select(StaffMessage)
            .where(StaffMessage.conversation_id.in_(ids), StaffMessage.practice_id == practice_id)
            .order_by(StaffMessage.created_at.desc())
        )
        last_by_conversation: dict[UUID, StaffMessage] = {}
        for m in last_result.scalars().all():
            if m.conversation_id not in last_by_conversation:
                last_by_conversation[m.conversation_id] = m

        summaries = []
        for c in conversations:
            other_id = c.user_b_id if c.user_a_id == user.id else c.user_a_id
            other = users.get(other_id)
            last = last_by_conversation.get(c.id)
            summaries.append(
                StaffConversationResponse(
                    conversation_id=c.id,
                    recipient_id=other_id,
                    recipient_name=(other.name if other else None),
                    recipient_email=(other.email if other else ""),
                    recipient_role=(other.role.value if other else "staff"),
                    last_message_preview=(last.body[:120] if last else None),
                    last_message_at=(last.created_at if last else None),
                    message_count=counts.get(c.id, 0),
                )
            )
        summaries.sort(
            key=lambda s: (s.last_message_at is not None, s.last_message_at or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        return summaries

    async def list_messages(
        self, db: AsyncSession, practice_id: UUID, user: User, conversation_id: UUID
    ) -> list[StaffMessage]:
        conversation = await self._get_participant_conversation(db, practice_id, user, conversation_id)
        result = await db.execute(
            select(StaffMessage)
            .options(selectinload(StaffMessage.sender))
            .where(StaffMessage.conversation_id == conversation.id)
            .order_by(StaffMessage.created_at.asc())
        )
        messages = list(result.scalars().all())
        for m in messages:
            m.sender_name = m.sender.name
            m.sender_role = m.sender.role.value
            m.mine = m.sender_id == user.id
        return messages

    async def start_conversation(
        self,
        db: AsyncSession,
        practice_id: UUID,
        user: User,
        recipient_id: UUID,
        body: str | None = None,
    ) -> StaffConversationResponse:
        if recipient_id == user.id:
            raise ForbiddenException("You can't start a conversation with yourself.")
        recipient = await self._resolve_user(db, practice_id, recipient_id)

        user_a, user_b = sorted([user.id, recipient_id])
        result = await db.execute(
            select(StaffConversation).where(
                StaffConversation.practice_id == practice_id,
                StaffConversation.user_a_id == user_a,
                StaffConversation.user_b_id == user_b,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            conversation = StaffConversation(practice_id=practice_id, user_a_id=user_a, user_b_id=user_b)
            db.add(conversation)
            await db.flush()
            await db.refresh(conversation)

        if body:
            await self.send_message(db, practice_id, user, conversation.id, body)

        message_count_result = await db.execute(
            select(func.count()).select_from(StaffMessage).where(StaffMessage.conversation_id == conversation.id)
        )
        message_count = message_count_result.scalar_one()
        last_result = await db.execute(
            select(StaffMessage)
            .where(StaffMessage.conversation_id == conversation.id)
            .order_by(StaffMessage.created_at.desc())
            .limit(1)
        )
        last = last_result.scalar_one_or_none()

        return StaffConversationResponse(
            conversation_id=conversation.id,
            recipient_id=recipient.id,
            recipient_name=recipient.name,
            recipient_email=recipient.email,
            recipient_role=recipient.role.value,
            last_message_preview=(last.body[:120] if last else None),
            last_message_at=(last.created_at if last else None),
            message_count=message_count,
        )

    async def send_message(
        self, db: AsyncSession, practice_id: UUID, user: User, conversation_id: UUID, body: str
    ) -> StaffMessage:
        conversation = await self._get_participant_conversation(db, practice_id, user, conversation_id)

        message = StaffMessage(practice_id=practice_id, conversation_id=conversation.id, sender_id=user.id, body=body)
        db.add(message)
        await db.flush()
        await db.refresh(message)
        message.sender_name = user.name
        message.sender_role = user.role.value
        message.mine = True
        return message

    async def send_file(
        self,
        db: AsyncSession,
        practice_id: UUID,
        user: User,
        conversation_id: UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> StaffMessage:
        conversation = await self._get_participant_conversation(db, practice_id, user, conversation_id)

        # Determine Cloudinary resource type
        if content_type.startswith("image/"):
            resource_type = "image"
        elif content_type.startswith("video/"):
            resource_type = "video"
        elif content_type.startswith("audio/"):
            resource_type = "video"
        else:
            resource_type = "raw"

        upload_result = await self.cloudinary.upload_from_bytes(
            file_bytes, filename, folder="staff_messages", resource_type=resource_type
        )

        extra_data = {"url": upload_result["url"], "filename": filename, "mime_type": content_type}

        # Body shown in conversation preview
        body = f"📎 {filename}"

        message = StaffMessage(
            practice_id=practice_id,
            conversation_id=conversation.id,
            sender_id=user.id,
            body=body,
            content_type=content_type if content_type.startswith(("image/", "video/", "audio/")) else "file",
            extra_data=extra_data,
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)
        message.sender_name = user.name
        message.sender_role = user.role.value
        message.mine = True
        return message