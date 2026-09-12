from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.server.dependencies import PracticeContext
from src.server.exceptions import ForbiddenException
from src.models.conversation import Conversation
from src.models.message import MessageRole
from src.models.user import UserRole
from src.schemas.finance_agent import (
    AskFinanceAgentRequest,
    AskFinanceAgentResponse,
    FinanceAgentReport,
    FinanceAgentMessage,
    FinanceAgentSessionSummary,
    FinanceAgentSessionDetail,
)
from src.services.finance_agent.finance_agent_services import FinanceAgentService

_FINANCE_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)


def _title_for(conversation: Conversation) -> str:
    staff_messages = sorted(
        (m for m in conversation.messages if m.role == MessageRole.STAFF), key=lambda m: m.created_at
    )
    if not staff_messages:
        return "New conversation"
    first = staff_messages[0].content.strip()
    return first[:60] + ("…" if len(first) > 60 else "")


class FinanceAgentController:
    def __init__(self):
        self.service = FinanceAgentService()

    @staticmethod
    def _guard(ctx: PracticeContext) -> None:
        if ctx.user.role not in _FINANCE_ROLES:
            raise ForbiddenException("Only the practice Owner or Receptionist can use the Finance Agent.")

    async def report(self, db: AsyncSession, ctx: PracticeContext) -> FinanceAgentReport:
        self._guard(ctx)
        return await self.service.build_report(db, ctx.practice.id)

    async def ask(self, db: AsyncSession, ctx: PracticeContext, data: AskFinanceAgentRequest) -> AskFinanceAgentResponse:
        self._guard(ctx)
        return await self.service.ask(db, ctx.practice.id, data.question, data.session_id)

    async def list_sessions(self, db: AsyncSession, ctx: PracticeContext) -> list[FinanceAgentSessionSummary]:
        self._guard(ctx)
        conversations = await self.service.list_sessions(db, ctx.practice.id)
        return [FinanceAgentSessionSummary(id=c.id, title=_title_for(c), updated_at=c.updated_at) for c in conversations]

    async def get_session(self, db: AsyncSession, ctx: PracticeContext, session_id: UUID) -> FinanceAgentSessionDetail:
        self._guard(ctx)
        conversation = await self.service.get_session(db, ctx.practice.id, session_id)
        messages = sorted(conversation.messages, key=lambda m: m.created_at)
        return FinanceAgentSessionDetail(
            id=conversation.id,
            title=_title_for(conversation),
            messages=[
                FinanceAgentMessage(
                    role="staff" if m.role == MessageRole.STAFF else "agent",
                    content=m.content,
                    created_at=m.created_at,
                )
                for m in messages
            ],
        )