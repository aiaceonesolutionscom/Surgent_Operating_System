from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.server.dependencies import PracticeContext
from src.models.conversation import Conversation
from src.models.message import MessageRole
from src.schemas.command_center import (
    AskCommandCenterRequest,
    AskCommandCenterResponse,
    CommandCenterMessage,
    CommandCenterSessionSummary,
    CommandCenterSessionDetail,
)
from src.services.command_center.command_center_services import CommandCenterService


def _title_for(conversation: Conversation) -> str:
    staff_messages = sorted(
        (m for m in conversation.messages if m.role == MessageRole.STAFF), key=lambda m: m.created_at
    )
    if not staff_messages:
        return "New conversation"
    first = staff_messages[0].content.strip()
    return first[:60] + ("…" if len(first) > 60 else "")


class CommandCenterController:
    def __init__(self):
        self.service = CommandCenterService()

    async def ask(self, db: AsyncSession, ctx: PracticeContext, data: AskCommandCenterRequest) -> AskCommandCenterResponse:
        return await self.service.ask(db, ctx.practice.id, ctx.tier, data.question, data.session_id)

    def ask_stream(self, db: AsyncSession, ctx: PracticeContext, data: AskCommandCenterRequest):
        return self.service.ask_stream(db, ctx.practice.id, ctx.tier, data.question, data.session_id)

    async def list_sessions(self, db: AsyncSession, ctx: PracticeContext) -> list[CommandCenterSessionSummary]:
        conversations = await self.service.list_sessions(db, ctx.practice.id)
        return [CommandCenterSessionSummary(id=c.id, title=_title_for(c), updated_at=c.updated_at) for c in conversations]

    async def get_session(self, db: AsyncSession, ctx: PracticeContext, session_id: UUID) -> CommandCenterSessionDetail:
        conversation = await self.service.get_session(db, ctx.practice.id, session_id)
        messages = sorted(conversation.messages, key=lambda m: m.created_at)
        return CommandCenterSessionDetail(
            id=conversation.id,
            title=_title_for(conversation),
            messages=[
                CommandCenterMessage(
                    role="staff" if m.role == MessageRole.STAFF else "agent",
                    content=m.content,
                    steps=(m.extra_data or {}).get("steps", []),
                    created_at=m.created_at,
                )
                for m in messages
            ],
        )
