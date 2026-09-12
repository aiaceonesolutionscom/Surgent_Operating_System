from __future__ import annotations
import json
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.message import Message, MessageRole
from src.models.practice import Practice, PracticeStatus
from src.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from src.models.pending_signup import PendingSignup, OrgRequestStatus
from src.schemas.super_agent import AskSuperAgentResponse
from src.services.admin.admin_services import AdminService
from src.services.llm.llm_service import LLMService
from src.server.exceptions import NotFoundException

SUPER_AGENT_TYPE = "super_agent"
SUPER_AGENT_SLUG = "super_agent"

SYSTEM_PROMPT = (
    "You are the Aiaceone platform-level Super Agent, used ONLY by the "
    "Aiaceone team in the Super Admin panel. The user asks business "
    "questions about the whole platform — how many clinics are live, the "
    "plan mix, estimated MRR/cost/margin, which clinics are on which tier, "
    "or the pending-approval queue. The CURRENT platform snapshot is in "
    "JSON below — answer from those numbers only, never invent figures. Be "
    "brief and direct (under 150 words): a short answer and, where useful, "
    "a 2-5 line bullet list. If the question asks something the snapshot "
    "doesn't cover, say so in one line."
)


class SuperAgentService:
    """The platform-owner OPPOSITE of a clinic agent: one LLM-backed agent
    that answers questions across ALL practices. Admin-only surface
    (require_admin_token), never seeded per clinic, never spoken to by
    practices. Numbers come from a real snapshot of the practices/plans/
    subscriptions/pending-signups tables — not LLM-guessed."""

    def __init__(self):
        self.llm = LLMService()
        self.admin_service = AdminService()

    async def build_snapshot(self, db: AsyncSession) -> dict:
        practices = (await db.execute(select(Practice))).scalars().all()
        subs = (await db.execute(select(Subscription))).scalars().all()
        active_subs: dict[UUID, Subscription] = {}
        for s in subs:
            if s.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
                continue
            if s.practice_id not in active_subs or s.created_at > active_subs[s.practice_id].created_at:
                active_subs[s.practice_id] = s

        tier_counts: dict[str, int] = {}
        for s in active_subs.values():
            tier_counts[s.tier.value] = tier_counts.get(s.tier.value, 0) + 1

        pending_count = (
            await db.execute(
                select(PendingSignup).where(PendingSignup.request_status == OrgRequestStatus.PENDING)
            )
        ).scalars()
        pending_list = list(pending_count)

        summary = await self.admin_service.platform_summary(db)
        return {
            "total_practices": len(practices),
            "active_practices": sum(1 for p in practices if p.status == PracticeStatus.ACTIVE),
            "suspended_practices": sum(1 for p in practices if p.status == PracticeStatus.SUSPENDED),
            "plan_distribution": tier_counts,
            "total_estimated_mrr": summary["total_estimated_mrr"],
            "total_estimated_cost": summary["total_estimated_cost"],
            "total_estimated_margin": summary["total_estimated_margin"],
            "pending_org_requests": len(pending_list),
            "pending_org_request_emails": [p.email for p in pending_list[:10]],
        }

    @staticmethod
    def _fallback_answer(snapshot: dict, question: str) -> str:
        q = question.lower()
        if any(k in q for k in ["pending", "org request", "approval", "approve", "signup"]):
            emails = snapshot["pending_org_requests"] and "\n  - " + "\n  - ".join(snapshot["pending_org_request_emails"])
            return (
                f"{snapshot['pending_org_requests']} organization request{'s' if snapshot['pending_org_requests'] != 1 else ''} pending approval.{emails or ''}"
            )
        if any(k in q for k in ["revenue", "mrr", "marg", "earning", "paid"]):
            return (
                f"Estimated MRR ${snapshot['total_estimated_mrr']:,.0f}, cost ${snapshot['total_estimated_cost']:,.0f}, "
                f"margin ${snapshot['total_estimated_margin']:,.0f} across {snapshot['total_practices']} practices (assumed 150 sessions/agent/month)."
            )
        if any(k in q for k in ["clinic", "practice", "active", "customer", "how many"]):
            return (
                f"{snapshot['total_practices']} practices total — {snapshot['active_practices']} active, "
                f"{snapshot['suspended_practices']} suspended. Plan mix: "
                + ", ".join(f"{k} {v}" for k, v in snapshot["plan_distribution"].items())
                or "(no active subscriptions)"
            )
        return (
            f"{snapshot['total_practices']} practices ({snapshot['active_practices']} active), "
            f"{snapshot['pending_org_requests']} org requests pending, estimated MRR "
            f"${snapshot['total_estimated_mrr']:,.0f}. Ask me about the plan mix, MRR, or the approval queue."
        )

    async def ask(self, db: AsyncSession, question: str, session_id: UUID | None = None) -> AskSuperAgentResponse:
        conversation = await self._get_or_create_session(db, session_id)
        db.add(Message(conversation_id=conversation.id, role=MessageRole.STAFF, content=question))

        snapshot = await self.build_snapshot(db)
        answer = self._fallback_answer(snapshot, question)

        try:
            answer = await self.llm.chat(
                messages=[{"role": "user", "content": question}],
                system_prompt=(
                    SYSTEM_PROMPT + "\n\nCurrent platform snapshot (JSON):\n" + json.dumps(snapshot, default=str)
                ),
                tier="low",
                max_tokens=400,
            )
        except Exception:
            pass  # deterministic fallback above stays

        db.add(Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=answer))
        await db.flush()
        return AskSuperAgentResponse(session_id=conversation.id, answer=answer)

    async def _get_or_create_session(self, db: AsyncSession, session_id: UUID | None) -> Conversation:
        if session_id is not None:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == session_id, Conversation.agent_type == SUPER_AGENT_TYPE
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                raise NotFoundException("Super Agent session not found")
            return conversation

        conversation = Conversation(
            practice_id=None,
            agent_type=SUPER_AGENT_TYPE,
            channel=ConversationChannel.WEB_CHAT,
            status=ConversationStatus.ACTIVE,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def list_sessions(self, db: AsyncSession) -> list[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.agent_type == SUPER_AGENT_TYPE)
            .options(selectinload(Conversation.messages))
            .order_by(desc(Conversation.updated_at))
        )
        return list(result.scalars().all())

    async def get_session(self, db: AsyncSession, session_id: UUID) -> Conversation:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == session_id, Conversation.agent_type == SUPER_AGENT_TYPE)
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("Super Agent session not found")
        return conversation