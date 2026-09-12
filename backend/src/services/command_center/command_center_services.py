from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.patient import Patient
from src.models.appointment import Appointment, AppointmentStatus
from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.message import Message, MessageRole
from src.models.recovery_journal import RecoveryJournal
from src.models.invoice import Invoice, InvoiceStatus
from src.models.subscription import SubscriptionTier
from src.services.llm.llm_service import LLMService
from src.services.practice.plan_capabilities import allows_category
from src.schemas.command_center import AskCommandCenterResponse, CommandCenterStep
from src.server.exceptions import AppException, NotFoundException

COMMAND_CENTER_AGENT_TYPE = "command_center"

# (category_id, label, description-for-the-LLM's-tool-schema) — category_id
# and label match services/practice/plan_capabilities.py's AGENT_CATEGORIES
# and frontend/src/data/agents/index.ts exactly, on purpose.
CATEGORIES: list[tuple[str, str, str]] = [
    ("front-desk", "Front Desk & Intake", "patients on file, intake status, and conversations needing staff attention"),
    ("consultation", "Consultation & Screening", "chief complaints, surgery-flagged patients, and upcoming appointments"),
    ("post-care", "Post-Op Care & Retention", "recovery journals and healing progress for patients post-surgery"),
    ("business", "Business & Operations", "pending and overdue invoices"),
]
CATEGORY_LABELS = {cid: label for cid, label, _ in CATEGORIES}


def _tool_name(category_id: str) -> str:
    return f"consult_{category_id.replace('-', '_')}"


TOOL_NAME_TO_CATEGORY = {_tool_name(cid): cid for cid, _, _ in CATEGORIES}

ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are the Main AI agent inside a plastic surgery practice's 'Command "
    "Center'. A doctor is asking you a question. You have no direct access "
    "to patient data yourself — you MUST call the relevant consult_* tool(s) "
    "to get real information from that category's sub-agent before "
    "answering. Call every tool relevant to the question; call more than one "
    "if the question spans categories. If a tool result says a category "
    "isn't included in the practice's plan, relay that honestly in your "
    "final answer instead of guessing — never invent data a tool didn't "
    "give you. Final answers must be short and direct (under 150 words), "
    "plain language, no filler."
)


class CommandCenterService:
    """Orchestrates the doctor-facing 'AI Command Center': a Main agent
    (LLM with function-calling) delegates to one of 4 category sub-agents,
    each of which runs a real, practice-scoped DB query — never LLM-generated
    SQL, for safety. Category access follows the practice's plan tier via
    plan_capabilities.allows_category(), the same enforcement mirror
    server/dependencies.py's require_agent_category() already uses."""

    def __init__(self):
        self.llm = LLMService()

    def _tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": _tool_name(cid),
                    "description": f"Consult the {label} agent for real data about {desc}.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
            for cid, label, desc in CATEGORIES
        ]

    async def _get_or_create_session(self, db: AsyncSession, practice_id: UUID, session_id: UUID | None) -> Conversation:
        if session_id is not None:
            result = await db.execute(
                select(Conversation).where(Conversation.id == session_id, Conversation.practice_id == practice_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                raise NotFoundException("Command Center session not found")
            return conversation

        conversation = Conversation(
            practice_id=practice_id,
            agent_type=COMMAND_CENTER_AGENT_TYPE,
            channel=ConversationChannel.WEB_CHAT,
            status=ConversationStatus.ACTIVE,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def ask(
        self, db: AsyncSession, practice_id: UUID, tier: SubscriptionTier, question: str, session_id: UUID | None = None
    ) -> AskCommandCenterResponse:
        conversation = await self._get_or_create_session(db, practice_id, session_id)
        db.add(Message(conversation_id=conversation.id, role=MessageRole.STAFF, content=question))

        try:
            first = await self.llm.chat_with_tools(
                messages=[{"role": "user", "content": question}],
                tools=self._tools(),
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                tier="low",
                max_tokens=400,
            )
        except Exception as exc:  # LLM outage/misconfig shouldn't 500 the whole page
            raise AppException(f"The AI Command Center is temporarily unavailable: {exc}", status_code=503)

        tool_calls = first.get("tool_calls") or []
        if not tool_calls:
            answer = first.get("content") or "I couldn't find anything relevant to answer that."
            db.add(Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=answer, extra_data={"steps": []}))
            await db.flush()
            return AskCommandCenterResponse(session_id=conversation.id, steps=[], answer=answer)

        steps: list[CommandCenterStep] = []
        tool_result_messages: list[dict] = []

        for tc in tool_calls:
            category_id = TOOL_NAME_TO_CATEGORY.get(tc.function.name)
            if category_id is None:
                continue
            label = CATEGORY_LABELS[category_id]

            if not allows_category(tier, category_id):
                summary = f"Not available — {label} isn't included in the {tier.value} plan."
                steps.append(CommandCenterStep(category_id=category_id, category_label=label, status="locked", summary=summary))
            else:
                summary = await self._dispatch(db, category_id, practice_id)
                steps.append(CommandCenterStep(category_id=category_id, category_label=label, status="consulted", summary=summary))

            tool_result_messages.append({"role": "tool", "tool_call_id": tc.id, "content": summary})

        assistant_message = {
            "role": "assistant",
            "content": first.get("content") or None,
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        }

        try:
            answer = await self.llm.chat(
                messages=[{"role": "user", "content": question}, assistant_message, *tool_result_messages],
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                tier="low",
                max_tokens=400,
            )
        except Exception as exc:
            raise AppException(f"The AI Command Center is temporarily unavailable: {exc}", status_code=503)

        db.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.AGENT,
                content=answer,
                extra_data={"steps": [s.model_dump() for s in steps]},
            )
        )
        await db.flush()

        return AskCommandCenterResponse(session_id=conversation.id, steps=steps, answer=answer)

    async def _dispatch(self, db: AsyncSession, category_id: str, practice_id: UUID) -> str:
        handler = {
            "front-desk": self._handle_front_desk,
            "consultation": self._handle_consultation,
            "post-care": self._handle_post_care,
            "business": self._handle_business,
        }[category_id]
        return await handler(db, practice_id)

    async def _handle_front_desk(self, db: AsyncSession, practice_id: UUID) -> str:
        result = await db.execute(
            select(Patient).where(Patient.practice_id == practice_id).order_by(desc(Patient.created_at)).limit(5)
        )
        patients = list(result.scalars().all())
        attention_result = await db.execute(
            select(func.count()).select_from(Conversation).where(
                Conversation.practice_id == practice_id, Conversation.status == ConversationStatus.NEEDS_ATTENTION
            )
        )
        attention_count = attention_result.scalar_one()
        if not patients:
            return f"No patients on file yet. {attention_count} conversations currently need staff attention."
        names = ", ".join(f"{p.first_name} {p.last_name}" for p in patients)
        return f"{len(patients)} most recent patients: {names}. {attention_count} conversations currently need staff attention."

    async def _handle_consultation(self, db: AsyncSession, practice_id: UUID) -> str:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Patient)
            .where(Patient.practice_id == practice_id, Patient.chief_complaint.isnot(None))
            .order_by(desc(Patient.created_at))
            .limit(5)
        )
        patients = list(result.scalars().all())
        appt_result = await db.execute(
            select(Appointment)
            .where(
                Appointment.practice_id == practice_id,
                Appointment.start_time >= now,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
            )
            .order_by(Appointment.start_time)
            .limit(5)
        )
        appointments = list(appt_result.scalars().all())
        surgery_count_result = await db.execute(
            select(func.count()).select_from(Patient).where(Patient.practice_id == practice_id, Patient.needs_surgery.is_(True))
        )
        surgery_count = surgery_count_result.scalar_one()

        parts = []
        if patients:
            lines = "; ".join(f"{p.first_name} {p.last_name}: {p.chief_complaint}" for p in patients)
            parts.append(f"Recent chief complaints on file: {lines}")
        if appointments:
            parts.append(f"{len(appointments)} upcoming appointments scheduled.")
        if surgery_count:
            parts.append(f"{surgery_count} patients flagged as needing surgery.")
        return " ".join(parts) if parts else "No consultation records (chief complaints), upcoming appointments, or surgery-flagged patients on file yet."

    async def _handle_post_care(self, db: AsyncSession, practice_id: UUID) -> str:
        result = await db.execute(
            select(RecoveryJournal)
            .join(Patient, RecoveryJournal.patient_id == Patient.id)
            .where(Patient.practice_id == practice_id)
            .order_by(desc(RecoveryJournal.updated_at))
            .limit(5)
        )
        journals = list(result.scalars().all())
        if not journals:
            return "No recovery journals on file yet."
        scored = [j.healing_score for j in journals if j.healing_score is not None]
        avg_note = f" Average healing score {sum(scored) / len(scored):.0f}." if scored else ""
        return f"{len(journals)} active recovery journals on file.{avg_note}"

    async def list_sessions(self, db: AsyncSession, practice_id: UUID) -> list[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.practice_id == practice_id, Conversation.agent_type == COMMAND_CENTER_AGENT_TYPE)
            .options(selectinload(Conversation.messages))
            .order_by(desc(Conversation.updated_at))
        )
        return list(result.scalars().all())

    async def get_session(self, db: AsyncSession, practice_id: UUID, session_id: UUID) -> Conversation:
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.id == session_id,
                Conversation.practice_id == practice_id,
                Conversation.agent_type == COMMAND_CENTER_AGENT_TYPE,
            )
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("Command Center session not found")
        return conversation

    async def _handle_business(self, db: AsyncSession, practice_id: UUID) -> str:
        result = await db.execute(
            select(Invoice).where(
                Invoice.practice_id == practice_id, Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE])
            )
        )
        invoices = list(result.scalars().all())
        if not invoices:
            return "No pending or overdue invoices on file yet."
        total = sum(float(inv.total_amount) for inv in invoices)
        return f"{len(invoices)} pending/overdue invoices totaling ${total:,.2f}."
