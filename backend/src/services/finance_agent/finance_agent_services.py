from __future__ import annotations
import json
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
)
from src.services.llm.llm_service import LLMService
from src.services.agent_costing.agent_costing_services import DEFAULT_COSTS
from src.server.exceptions import AppException, NotFoundException

FINANCE_AGENT_TYPE = "finance_agent"

_OUTSTANDING_STATUSES = [InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]

SYSTEM_PROMPT = (
    "You are the Finance & Billing agent inside a plastic surgery practice's "
    "dashboard. The user is the practice Owner or Receptionist asking about "
    "money — revenue, spending, net, outstanding invoices, what each doctor "
    "earned this month, or how much the AI agents cost. The CURRENT, real "
    "finance snapshot is provided to you below in JSON — use those numbers, "
    "never invent figures. Answer in plain language, short and direct, and "
    "quote dollar amounts exactly as given. If the user asks something the "
    "snapshot doesn't cover, say so honestly."
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

    async def ask(
        self, db: AsyncSession, practice_id: UUID, question: str, session_id: UUID | None = None
    ) -> AskFinanceAgentResponse:
        conversation = await self._get_or_create_session(db, practice_id, session_id)
        db.add(Message(conversation_id=conversation.id, role=MessageRole.STAFF, content=question))

        report = await self.build_report(db, practice_id)
        answer = self._fallback_answer(report, question)

        try:
            answer = await self.llm.chat(
                messages=[{"role": "user", "content": question}],
                system_prompt=(
                    SYSTEM_PROMPT
                    + "\n\nCurrent finance snapshot (JSON):\n"
                    + json.dumps(report.model_dump(), default=str)
                ),
                tier="low",
                max_tokens=400,
            )
        except Exception:  # LLM outage/misconfig -> deterministic answer from the same report
            pass

        db.add(Message(conversation_id=conversation.id, role=MessageRole.AGENT, content=answer))
        await db.flush()
        return AskFinanceAgentResponse(session_id=conversation.id, answer=answer)

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