from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.staff_message import (
    CreateStaffMessageRequest,
    StartConversationRequest,
    StaffContactResponse,
    StaffConversationResponse,
    StaffMessageResponse,
)
from src.services.staff_messages.staff_message_services import StaffMessageService


class StaffMessageController:
    def __init__(self):
        self.service = StaffMessageService()

    async def list_contacts(self, db: AsyncSession, user: User) -> list[StaffContactResponse]:
        return await self.service.list_contacts(db, user.practice_id, user)

    async def list_conversations(self, db: AsyncSession, user: User) -> list[StaffConversationResponse]:
        return await self.service.list_conversations(db, user.practice_id, user)

    async def start_conversation(
        self, db: AsyncSession, user: User, data: StartConversationRequest
    ) -> StaffConversationResponse:
        return await self.service.start_conversation(
            db, user.practice_id, user, data.recipient_user_id, data.body
        )

    async def list_messages(self, db: AsyncSession, user: User, conversation_id: UUID) -> list[StaffMessageResponse]:
        messages = await self.service.list_messages(db, user.practice_id, user, conversation_id)
        return [StaffMessageResponse.model_validate(m) for m in messages]

    async def send_message(
        self, db: AsyncSession, user: User, conversation_id: UUID, data: CreateStaffMessageRequest
    ) -> StaffMessageResponse:
        message = await self.service.send_message(db, user.practice_id, user, conversation_id, data.body)
        return StaffMessageResponse.model_validate(message)

    async def send_file(
        self,
        db: AsyncSession,
        user: User,
        conversation_id: UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> StaffMessageResponse:
        message = await self.service.send_file(
            db, user.practice_id, user, conversation_id, file_bytes, filename, content_type
        )
        return StaffMessageResponse.model_validate(message)