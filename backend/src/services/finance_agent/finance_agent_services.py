from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.patient import Patient
from src.models.doctor import Doctor
from src.models.invoice import Invoice, InvoiceStatus
from src.models.expense import Expense
from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.message import Message, MessageRole
from src.schemas.finance_agent import (
    AskFinanceAgentResponse,
    FinanceAgentReport,
    FinanceAgentDoctorEarning,
    FinanceAgentAgentCost,
    FinanceAgentRecentInvoice,
    FinanceAgentStep,
)
from src.services.llm.llm_service import LLMService
from src.services.agent_costing.agent_costing_services import DEFAULT_COSTS
from src.server.exceptions import AppException, NotFoundException

FINANCE_AGENT_TYPE = "finance_agent"

_OUTSTANDING_STATUSES = [InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]

# First-pass orchestrator prompt — decides which tool(s) answer the
# question, same two-call shape as Command Center (services/command_center/):
# a fast tool-decision call, then a separate synthesis call over the actual
# results. Previously this agent always computed and dumped the ENTIRE
# report (revenue, expenses, per-doctor, AI costs, recent invoices) into
# every single question regardless of what was asked — correct but
# generic-feeling ("itna khaas nahi lagta"). Now it only pulls the slice of
# the books actually relevant to the question, like a real finance analyst
# choosing which report to run.
ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are the Finance & Billing agent inside a plastic surgery practice's "
    "dashboard. The user is the practice Owner or Receptionist asking about "
    "money. You have no numbers memorized — you MUST call the relevant "
    "get_* tool(s) to pull real figures before answering. Call every tool "
    "relevant to the question; call more than one if it spans topics (e.g. "
    "revenue AND outstanding invoices). Never invent a figure a tool didn't "
    "give you."
)

# Second-pass prompt for the synthesis call, over plain-text tool results —
# NOT the raw OpenAI tool-calling message replay (see command_center_services
# .py's _synthesis_messages docstring for why: Groq's reasoning model
# rejected that shape outright when no tools=[] was present on the follow-up
# call, and even when a mismatched system prompt is used, it can silently
# burn its whole token budget on reasoning and return nothing).
SYNTHESIS_SYSTEM_PROMPT = (
    "You are the Finance & Billing agent inside a plastic surgery practice's "
    "dashboard. You already have the real numbers you need below — do not "
    "ask for more, do not mention tools. Answer the question directly using "
    "only this data, quoting dollar amounts exactly as given. Short and "
    "direct (under 150 words), plain language, no filler."
)


class FinanceAgentService:
    """The Finance Agent: builds a real, practice-scoped report from the
    Invoices/Expenses/Patient/Doctor/AI-costing tables and answers natural
    language questions with the LLM given those numbers in context. If the
    LLM is unavailable (placeholder keys / outage) it falls back to a
    keyword-driven answer built from the same report, so the feature never
    hard-errors."""

    def __init__(self):
        self.llm = LLMService()

    async def build_report(self, db: AsyncSession, practice_id: UUID) -> FinanceAgentReport:
        invoice_rows = (
            await db.execute(select(Invoice).where(Invoice.practice_id == practice_id))
        ).scalars().all()

        total_revenue = sum(float(i.total_amount) for i in invoice_rows if i.status == InvoiceStatus.PAID)
        outstanding = sum(float(i.total_amount) for i in invoice_rows if i.status in _OUTSTANDING_STATUSES)
        invoice_count = len(invoice_rows)

        expense_rows = (
            await db.execute(select(Expense).where(Expense.practice_id == practice_id))
        ).scalars().all()
        total_expenses = sum(float(e.amount) for e in expense_rows)
        expense_count = len(expense_rows)

        patient_rows = {
            p.id: p
            for p in (
                await db.execute(select(Patient).where(Patient.practice_id == practice_id))
            ).scalars().all()
        }
        doctor_rows = {
            d.id: d
            for d in (
                await db.execute(select(Doctor).where(Doctor.practice_id == practice_id))
            ).scalars().all()
        }

        earnings_by_doctor: dict[str, list[float]] = {}
        for i in invoice_rows:
            if i.status != InvoiceStatus.PAID:
                continue
            patient = patient_rows.get(i.patient_id)
            doctor = doctor_rows.get(patient.assigned_doctor_id) if patient and patient.assigned_doctor_id else None
            name = doctor.name if doctor else ("Unassigned" if not patient or not patient.assigned_doctor_id else "Unknown")
            earnings_by_doctor.setdefault(name, []).append(float(i.total_amount))

        per_doctor = sorted(
            [
                FinanceAgentDoctorEarning(
                    doctor_name=name, total_earned=sum(amounts), invoices_paid=len(amounts)
                )
                for name, amounts in earnings_by_doctor.items()
            ],
            key=lambda r: r.total_earned,
            reverse=True,
        )

        conversation_rows = (
            await db.execute(
                select(Conversation.agent_type, Conversation.id).where(Conversation.practice_id == practice_id)
            )
        ).all()
        counts: dict[str, int] = {}
        for agent_type, _ in conversation_rows:
            counts[agent_type] = counts.get(agent_type, 0) + 1
        per_agent_cost = [
            FinanceAgentAgentCost(
                agent_slug=slug,
                sessions=count,
                estimated_cost=round(count * DEFAULT_COSTS.get(slug, 0.10), 2),
            )
            for slug, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

        recent_paid = [i for i in invoice_rows if i.status == InvoiceStatus.PAID][-5:]
        recent_invoices = [
            FinanceAgentRecentInvoice(
                patient_name=(
                    f"{patient_rows[i.patient_id].first_name} {patient_rows[i.patient_id].last_name}"
                    if i.patient_id in patient_rows
                    else "Unknown patient"
                ),
                status=i.status.value,
                amount=float(i.total_amount),
            )
            for i in recent_paid
        ]

        now = datetime.now(timezone.utc)
        return FinanceAgentReport(
            total_revenue=round(total_revenue, 2),
            total_expenses=round(total_expenses, 2),
            net=round(total_revenue - total_expenses, 2),
            outstanding=round(outstanding, 2),
            invoice_count=invoice_count,
            expense_count=expense_count,
            month_label=now.strftime("%B %Y"),
            per_doctor=per_doctor,
            per_agent_cost=per_agent_cost,
            recent_invoices=recent_invoices,
        )

    @staticmethod
    def _fallback_answer(report: FinanceAgentReport, question: str) -> str:
        q = question.lower()
        if any(k in q for k in ["doctor", "earn", "earned", "kitne paise", "commission", "kis kisi", "kisko"]):
            if not report.per_doctor:
                return "No paid invoices are assigned to a doctor yet — nothing to report per doctor this month."
            lines = [
                f"{d.doctor_name}: ${d.total_earned:,.2f} ({d.invoices_paid} paid invoice{'s' if d.invoices_paid != 1 else ''})"
                for d in report.per_doctor
            ]
            return "This month's earnings per doctor:\n" + "\n".join(lines)
        if any(k in q for k in ["outstanding", "pending", "owe", "owed", "unpaid"]):
            return (
                f"${report.outstanding:,.2f} is currently outstanding across pending, partially paid and overdue "
                f"invoices ({report.invoice_count} invoices on file total)."
            )
        if any(k in q for k in ["expense", "spend", "spending", "kharcha", "cost"]):
            return f"Spending this {report.month_label}: ${report.total_expenses:,.2f} across {report.expense_count} recorded payments. Net for the period: ${report.net:,.2f}."
        if any(k in q for k in ["agent", "ai cost", "ai spend", "sessions"]):
            if not report.per_agent_cost:
                return "No agent sessions recorded yet — AI cost estimates will appear as conversations happen."
            lines = [
                f"{a.agent_slug}: {a.sessions} sessions, ~${a.estimated_cost:,.2f}" for a in report.per_agent_cost
            ]
            return "Estimated AI cost this month:\n" + "\n".join(lines)
        return (
            f"{report.month_label}: revenue ${report.total_revenue:,.2f} (paid invoices), spending "
            f"${report.total_expenses:,.2f}, net ${report.net:,.2f}, and ${report.outstanding:,.2f} outstanding. "
            f"Ask me about a specific doctor's earnings, outstanding invoices, or AI agent costs."
        )

    async def _get_or_create_session(self, db: AsyncSession, practice_id: UUID, session_id: UUID | None) -> Conversation:
        if session_id is not None:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == session_id,
                    Conversation.practice_id == practice_id,
                    Conversation.agent_type == FINANCE_AGENT_TYPE,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                raise NotFoundException("Finance Agent session not found")
            return conversation

        conversation = Conversation(
            practice_id=practice_id,
            agent_type=FINANCE_AGENT_TYPE,
            channel=ConversationChannel.WEB_CHAT,
            status=ConversationStatus.ACTIVE,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    # --- tool schema + dispatch ---------------------------------------------
    # Each tool pulls one targeted slice of the same build_report() rather
    # than the whole thing — the LLM picks which one(s) are relevant, so a
    # "what's outstanding" question no longer drags per-doctor/AI-cost data
    # into context (or into what the frontend reveals as "consulted") that
    # has nothing to do with what was asked.
    _TOOL_DEFS: list[tuple[str, str, str]] = [
        ("get_revenue_expense_summary", "Revenue & Spending", "this month's total revenue, expenses, and net"),
        ("get_outstanding_invoices", "Outstanding Invoices", "pending/partially-paid/overdue invoices and their total"),
        ("get_doctor_earnings", "Doctor Earnings", "how much each doctor earned this month from paid invoices"),
        ("get_agent_ai_costs", "AI Agent Costs", "estimated AI usage cost per agent this month"),
        ("get_recent_paid_invoices", "Recent Paid Invoices", "the most recently paid invoices"),
    ]
    _TOOL_LABELS = {name: label for name, label, _ in _TOOL_DEFS}

    def _tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {"name": name, "description": f"Get {desc}.", "parameters": {"type": "object", "properties": {}, "required": []}},
            }
            for name, _, desc in self._TOOL_DEFS
        ]

    @staticmethod
    def _dispatch_tool(name: str, report: FinanceAgentReport) -> str:
        if name == "get_revenue_expense_summary":
            return (
                f"{report.month_label}: revenue ${report.total_revenue:,.2f} (paid invoices), spending "
                f"${report.total_expenses:,.2f}, net ${report.net:,.2f}."
            )
        if name == "get_outstanding_invoices":
            return (
                f"${report.outstanding:,.2f} outstanding across pending/partially-paid/overdue invoices "
                f"({report.invoice_count} invoices on file total)."
            )
        if name == "get_doctor_earnings":
            if not report.per_doctor:
                return "No paid invoices are assigned to a doctor yet — nothing to report per doctor this month."
            return "; ".join(
                f"{d.doctor_name}: ${d.total_earned:,.2f} ({d.invoices_paid} paid invoice{'s' if d.invoices_paid != 1 else ''})"
                for d in report.per_doctor
            )
        if name == "get_agent_ai_costs":
            if not report.per_agent_cost:
                return "No agent sessions recorded yet — AI cost estimates will appear as conversations happen."
            return "; ".join(f"{a.agent_slug}: {a.sessions} sessions, ~${a.estimated_cost:,.2f}" for a in report.per_agent_cost)
        if name == "get_recent_paid_invoices":
            if not report.recent_invoices:
                return "No paid invoices yet."
            return "; ".join(f"{i.patient_name}: ${i.amount:,.2f} ({i.status})" for i in report.recent_invoices)
        return "Unknown tool."

    @staticmethod
    def _synthesis_messages(question: str, steps: list[FinanceAgentStep]) -> list[dict]:
        context = "\n".join(f"- {s.tool_label}: {s.summary}" for s in steps) or "No matching finance data was found."
        return [{"role": "user", "content": f"{question}\n\nReal finance data pulled from the practice's books:\n{context}"}]

    async def ask(
        self, db: AsyncSession, practice_id: UUID, question: str, session_id: UUID | None = None
    ) -> AskFinanceAgentResponse:
        conversation = await self._get_or_create_session(db, practice_id, session_id)
        db.add(Message(conversation_id=conversation.id, role=MessageRole.STAFF, content=question))

        report = await self.build_report(db, practice_id)

        try:
            first = await self.llm.chat_with_tools(
                messages=[{"role": "user", "content": question}],
                tools=self._tools(),
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                tier="low",
                max_tokens=300,
            )
            tool_calls = first.get("tool_calls") or []
            if not tool_calls:
                answer = first.get("content") or self._fallback_answer(report, question)
                steps: list[FinanceAgentStep] = []
            else:
                steps = [
                    FinanceAgentStep(tool_label=self._TOOL_LABELS.get(tc.function.name, tc.function.name), summary=self._dispatch_tool(tc.function.name, report))
                    for tc in tool_calls
                    if tc.function.name in self._TOOL_LABELS
                ]
                answer = await self.llm.chat(
                    messages=self._synthesis_messages(question, steps),
                    system_prompt=SYNTHESIS_SYSTEM_PROMPT,
                    tier="low",
                    max_tokens=400,
                )
        except Exception:  # LLM outage/misconfig -> deterministic answer from the same report
            answer = self._fallback_answer(report, question)
            steps = []

        db.add(Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=answer, extra_data={"steps": [s.model_dump() for s in steps]}))
        await db.flush()
        return AskFinanceAgentResponse(session_id=conversation.id, answer=answer, steps=steps)

    async def ask_stream(self, db: AsyncSession, practice_id: UUID, question: str, session_id: UUID | None = None):
        """SSE twin of ask() — same "step" reveal + token streaming pattern
        as Command Center's ask_stream (see command_center_services.py)."""
        conversation = await self._get_or_create_session(db, practice_id, session_id)
        db.add(Message(conversation_id=conversation.id, role=MessageRole.STAFF, content=question))
        await db.flush()

        report = await self.build_report(db, practice_id)

        try:
            first = await self.llm.chat_with_tools(
                messages=[{"role": "user", "content": question}],
                tools=self._tools(),
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                tier="low",
                max_tokens=300,
            )
        except Exception as exc:
            yield {"type": "error", "message": f"The Finance Agent is temporarily unavailable: {exc}"}
            return

        tool_calls = first.get("tool_calls") or []
        if not tool_calls:
            answer = first.get("content") or self._fallback_answer(report, question)
            for ch in answer:
                yield {"type": "chunk", "text": ch}
            db.add(Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=answer, extra_data={"steps": []}))
            await db.commit()
            yield {"type": "done", "session_id": str(conversation.id), "steps": []}
            return

        steps: list[FinanceAgentStep] = []
        for tc in tool_calls:
            if tc.function.name not in self._TOOL_LABELS:
                continue
            step = FinanceAgentStep(tool_label=self._TOOL_LABELS[tc.function.name], summary=self._dispatch_tool(tc.function.name, report))
            steps.append(step)
            yield {"type": "step", "step": step.model_dump()}

        chunks: list[str] = []
        try:
            async for delta in self.llm.chat_stream(
                messages=self._synthesis_messages(question, steps),
                system_prompt=SYNTHESIS_SYSTEM_PROMPT,
                tier="low",
                max_tokens=400,
            ):
                chunks.append(delta)
                yield {"type": "chunk", "text": delta}
        except Exception as exc:
            yield {"type": "error", "message": f"The Finance Agent is temporarily unavailable: {exc}"}
            return

        answer = "".join(chunks) or self._fallback_answer(report, question)
        db.add(Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=answer, extra_data={"steps": [s.model_dump() for s in steps]}))
        await db.commit()
        yield {"type": "done", "session_id": str(conversation.id), "steps": [s.model_dump() for s in steps]}

    async def list_sessions(self, db: AsyncSession, practice_id: UUID) -> list[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.practice_id == practice_id, Conversation.agent_type == FINANCE_AGENT_TYPE)
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
                Conversation.agent_type == FINANCE_AGENT_TYPE,
            )
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("Finance Agent session not found")
        return conversation