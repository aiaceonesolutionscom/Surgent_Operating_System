"""Landing-page AI chat (codenamed Aria).

A public, unauthenticated chat for the Aiaceone marketing website. Two kinds
of visitors use it, and Aria serves both from one warm persona:

1. **Patients** — a potential patient of one of the demo practices asks about
   procedures/consultations. Aria collects procedure-of-interest, name, and a
   contact, then creates a real patient lead (source "Landing Chat") exactly
   like the "Book a consultation" form does — reusing PatientsService + the
   front-desk agent slug — and pings the practice's in-app notifications plus
   a best-effort email.

2. **Clinic buyers** — someone evaluating the Aiaceone product for their own
   practice. Aria answers product/plan/integration questions, collects the
   buyer's name + work email, writes a platform-level `SalesLead` (deliberately
   NOT practice-scoped), and emails the platform sales team
   (`settings.sales_email`) so Aiaceone can follow up. Patient leads still land
   in a practice; sales leads land with Aiaceone.

Conversations persist as real web_chat conversations (agent_type
"receptionist") so even sales chats are reviewable in the dashboard.
"""

from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.conversation import Conversation, ConversationChannel
from src.models.message import Message, MessageRole
from src.models.practice import Practice
from src.models.sales_lead import SalesLead, SalesLeadSource, SalesLeadStatus
from src.schemas.patient import CreatePatientRequest
from src.server.exceptions import AppException
from src.services.llm.llm_service import LLMService
from src.services.notifications.notification_service import NotificationService
from src.services.patients.patients_services import PatientsService

FRONT_DESK_AGENT_SLUG = "receptionist"

# Codenamed "Aria" — friendly, memorable, and keeps the AI brand prefix the
# Aiaceone name starts with. See frontend/src/components/chat/LandingChat.tsx.
ASSISTANT_NAME = "Aria"

_HISTORY_LIMIT = 20
_FLOW_THRESHOLD = 3  # transcript lines before intent/booking extraction runs

ARIA_SYSTEM_PROMPT = """You are Aria, the warm, confident AI assistant for Aiaceone — the AI operating system for plastic and cosmetic surgery clinics. You are chatting on the Aiaceone marketing website, and two kinds of visitors talk to you:

PATIENTS (someone who might become a patient of one of our partner clinics):
- Answer questions about common procedures (rhinoplasty, breast augmentation, liposuction, facelift, botox/fillers, tummy tuck, etc.), what a first consultation involves, and typical recovery expectations.
- NEVER quote specific prices, financing terms, or guaranteed outcomes as fact — pricing is confirmed by the clinic's team during a consultation.
- NEVER give medical advice or diagnose. If someone describes a medical emergency, urge them to call their local emergency number immediately.
- When a patient wants to book: collect exactly three things, one question at a time: 1) the procedure or concern, 2) their full name, 3) a way to reach them (phone and/or email). Once you have all three, say their consultation request has been noted and the clinic's team will reach out to book.

CLINIC BUYERS (a clinic owner evaluating whether to buy Aiaceone for a plastic surgery practice):
- Explain the product: Aiaceone gives a practice 9 specialist AI agents across 4 areas — Front Desk & Intake (AI Receptionist, Appointment & Booking), Consultation & Screening (Lead Qualification, AI Patient Intake, Consultation Assistant), Post-Op Care & Retention (Recovery & Follow-up, Marketing & Retention) and Business & Operations (Finance & Billing, Main Command Center) — one inbox across phone, chat and WhatsApp, plus real booking, analytics, billing and recovery monitoring.
- If asked about pricing, say the Practice plan is $999/month and the Enterprise plan is custom-priced; a short sales chat is the fastest way to get exact details and a demo.
- Collect a few things, one at a time: their full name, their work email, and optionally their clinic/practice name and what they need. Once you have a name + work email, say their request has been logged and the Aiaceone team will reach out shortly. Do not keep asking.

General: keep answers warm, concise, and in plain English (1-3 short sentences). Never quote procedure prices or clinical outcomes. Answer confidently in the language the visitor writes in."""

FLOW_CLASSIFIER_PROMPT = """Classify the visitor in this website chat transcript (clinic buyer vs patient).
Return STRICT JSON only — no markdown, no commentary. Shape: {"flow": "sales" or "patient"}
- "sales": the visitor works at or owns a clinic and is evaluating the software — asks about buying/signing up, pricing or plans, a demo, integrations, the AI agents product, automation for their practice, or how many staff/doctors they have.
- "patient": the visitor is a potential patient — asks about a procedure (rhinoplasty, botox, liposuction, breast surgery, tummy tuck, facelift, etc.), price/feelings about a procedure, booking a consultation with a clinic, or recovery.
- If genuinely ambiguous, prefer "patient" only when a patient-style concern or procedure is mentioned; otherwise prefer "sales"."""

BOOKING_EXTRACT_PROMPT = """You extract booking details from a website chat transcript between a patient and a receptionist assistant named Aria.
Return STRICT JSON only — no markdown fences, no commentary. Shape:
{"book_ready": true or false, "full_name": "...", "email": "...", "phone": "...", "chief_complaint": "...", "needs_surgery": true or false}

Rules:
- book_ready is true ONLY when all of these are present in the transcript: the patient's full name, at least one way to reach them (phone or email), and the procedure/concern (chief_complaint).
- Use exact values the patient gave. Leave email, phone as "" and needs_surgery as false when not provided.
- needs_surgery is true only if the patient explicitly indicates a surgical procedure (rhinoplasty, liposuction, breast surgery, tummy tuck, facelift, etc.); otherwise false."""

SALES_EXTRACT_PROMPT = """Extract sales-lead details from a website chat transcript between a clinic owner (buyer) and Aria, the Aiaceone product assistant.
Return STRICT JSON only — no markdown fences, no commentary. Shape:
{"lead_ready": true or false, "full_name": "...", "email": "...", "phone": "...", "company": "...", "message": "..."}

Rules:
- lead_ready is true ONLY when BOTH the buyer's full name AND a work email are present in the transcript.
- Use exact values the buyer gave. Leave phone, company, message as "" when not provided.
- message: one short line summarizing what the buyer is looking for (e.g. "Wants a demo and pricing for a 3-surgeon practice")."""


class LandingChatService:
    """FAQ + booking/sales-intent chat for the public website."""

    def __init__(self):
        self.llm = LLMService()
        self.patients = PatientsService()
        self.notifications = NotificationService()

    async def handle_message(
        self,
        db: AsyncSession,
        conversation_id: str | None,
        message_text: str,
        context: str | None = None,
    ) -> dict:
        result = await db.execute(select(Practice).order_by(Practice.created_at))
        practice = result.scalars().first()

        conversation = await self._find_or_create_conversation(db, practice.id if practice else None, conversation_id, context)

        db.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.PATIENT,
                content=message_text,
                content_type="text",
            )
        )

        history = await self._recent_history(db, conversation.id)
        reply = await self.llm.chat_fast(history, system_prompt=ARIA_SYSTEM_PROMPT, max_tokens=350)

        flow = conversation.extra_data.get("flow")
        booking_created = False
        lead_name: str | None = None
        sales_lead_created = False
        sales_lead_name: str | None = None

        flow = await self._classify_flow(db, conversation, flow)
        if flow:
            conversation.extra_data = {**conversation.extra_data, "flow": flow}

        if flow == "patient" and practice is not None and not conversation.extra_data.get("booking"):
            booking = await self._extract_booking(db, conversation.id)
            if booking and booking.get("book_ready"):
                patient_id, lead_name = await self._create_patient_lead(db, practice, conversation, booking)
                conversation.patient_id = patient_id
                conversation.extra_data = {**conversation.extra_data, "booking": {**booking, "patient_id": str(patient_id)}}
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.SYSTEM,
                        content=f"Patient lead created by {ASSISTANT_NAME} (landing-page chat) — {lead_name}.",
                        content_type="text",
                    )
                )
                booking_created = True

        if flow == "sales" and not conversation.extra_data.get("sales_lead"):
            sales = await self._extract_sales_lead(db, conversation.id)
            if sales and sales.get("lead_ready"):
                sales_lead_name = await self._create_sales_lead(db, conversation, sales)
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.SYSTEM,
                        content=f"Sales lead created by {ASSISTANT_NAME} (landing-page chat) — {sales_lead_name}.",
                        content_type="text",
                    )
                )
                sales_lead_created = True

        db.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.AGENT,
                content=reply,
                content_type="text",
                extra_data={"assistant": ASSISTANT_NAME},
            )
        )

        await db.commit()
        return {
            "conversation_id": str(conversation.id),
            "reply": reply,
            "flow": flow,
            "booking_created": booking_created,
            "lead_name": lead_name,
            "sales_lead_created": sales_lead_created,
            "sales_lead_name": sales_lead_name,
        }

    async def _find_or_create_conversation(
        self,
        db: AsyncSession,
        practice_id: UUID | None,
        conversation_id: str | None,
        context: str | None,
    ) -> Conversation:
        if conversation_id:
            result = await db.execute(select(Conversation).where(Conversation.id == UUID(str(conversation_id))))
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        conversation = Conversation(
            practice_id=practice_id,
            patient_id=None,
            agent_type=FRONT_DESK_AGENT_SLUG,
            channel=ConversationChannel.WEB_CHAT,
            extra_data={
                "channel": "landing_chat",
                "assistant": ASSISTANT_NAME,
                "context": context,
            },
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def _recent_history(self, db: AsyncSession, conversation_id: UUID) -> list[dict]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(_HISTORY_LIMIT)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        out = []
        for row in rows:
            role = {MessageRole.PATIENT: "user", MessageRole.AGENT: "assistant"}.get(row.role)
            if role and row.content.strip():
                out.append({"role": role, "content": row.content})
        return out

    async def _transcript(self, db: AsyncSession, conversation_id: UUID, limit: int = _HISTORY_LIMIT) -> tuple[list[str], int]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        parts = []
        for row in reversed(result.scalars().all()):
            label = {MessageRole.PATIENT: "visitor", MessageRole.AGENT: "aria"}.get(row.role)
            if label and row.content.strip():
                parts.append(f"{label}: {row.content}")
        return parts, len(parts)

    async def _extract_json(self, db: AsyncSession, conversation_id: UUID, system_prompt: str, min_parts: int) -> dict | None:
        parts, count = await self._transcript(db, conversation_id)
        if count < min_parts:
            return None
        raw = await self.llm.chat_fast(
            [{"role": "user", "content": "\n".join(parts)}],
            system_prompt=system_prompt,
            json_mode=True,
            max_tokens=300,
        )
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    async def _classify_flow(self, db: AsyncSession, conversation: Conversation, current: str | None) -> str | None:
        if current:
            return current
        data = await self._extract_json(db, conversation.id, FLOW_CLASSIFIER_PROMPT, _FLOW_THRESHOLD)
        flow = (data or {}).get("flow")
        return flow if flow in ("sales", "patient") else None

    async def _extract_booking(self, db: AsyncSession, conversation_id: UUID) -> dict | None:
        return await self._extract_json(db, conversation_id, BOOKING_EXTRACT_PROMPT, _FLOW_THRESHOLD)

    async def _extract_sales_lead(self, db: AsyncSession, conversation_id: UUID) -> dict | None:
        return await self._extract_json(db, conversation_id, SALES_EXTRACT_PROMPT, _FLOW_THRESHOLD)

    async def _create_patient_lead(
        self,
        db: AsyncSession,
        practice: Practice,
        conversation: Conversation,
        booking: dict,
    ) -> tuple[UUID, str]:
        name = str(booking.get("full_name") or "").strip()
        if not name:
            raise AppException("Booking details are incomplete — ask the visitor for their name.", status_code=400)
        parts = name.split(maxsplit=1)
        first_name = parts[0]
        last_name = parts[1].strip() if len(parts) > 1 else ""

        chief_complaint = str(booking.get("chief_complaint") or "").strip()
        if not chief_complaint and conversation.extra_data.get("context"):
            chief_complaint = str(conversation.extra_data["context"]).strip()

        patient = await self.patients.create_patient(
            db,
            practice.id,
            CreatePatientRequest(
                first_name=first_name,
                last_name=last_name,
                email=(booking.get("email") or None) and str(booking["email"]).strip() or None,
                phone=(booking.get("phone") or None) and str(booking["phone"]).strip() or None,
                chief_complaint=chief_complaint,
                needs_surgery=bool(booking.get("needs_surgery")),
                ai_agent_assigned=FRONT_DESK_AGENT_SLUG,
                source="Landing Chat",
            ),
        )
        await db.flush()

        await self.notifications.notify(
            db,
            practice.id,
            event_type="lead_new",
            title=f"Landing chat lead: {first_name}",
            body=f"{first_name} booked a consultation via Aria on the website — {chief_complaint[:120]}",
            resource_type="patient",
            resource_id=patient.id,
        )
        await self._best_effort_email(
            practice.email,
            f"New landing-page lead — {name}",
            (
                f"<h3>New consultation request from the website chatbot (Aria)</h3>"
                f"<table>{self._email_rows([('Name', name), ('Email', patient.email or '—'), ('Phone', patient.phone or '—'), ('Procedure / concern', patient.chief_complaint or '—'), ('Source', 'Landing Page Chat (Aria)')])}</table>"
                f"<p>Follow up with the patient in the Aiaceone dashboard (Front Desk / Leads).</p>"
            ),
        )
        return patient.id, patient.first_name

    async def _create_sales_lead(self, db: AsyncSession, conversation: Conversation, data: dict) -> str:
        name = str(data.get("full_name") or "").strip()
        email = str(data.get("email") or "").strip()
        if not name or not email:
            raise AppException("Sales lead is incomplete — ask the buyer for their name and email.", status_code=400)

        lead = SalesLead(
            full_name=name,
            email=email,
            phone=(data.get("phone") or None) and str(data["phone"]).strip() or None,
            company=(data.get("company") or None) and str(data["company"]).strip() or None,
            message=(data.get("message") or None) and str(data["message"]).strip() or None,
            source=SalesLeadSource.ARIA_LANDING_CHAT,
            status=SalesLeadStatus.NEW,
            conversation_id=conversation.id,
        )
        db.add(lead)
        db.flush()
        conversation.extra_data = {**conversation.extra_data, "sales_lead": {"id": str(lead.id), "full_name": name, "email": email}}

        settings = get_settings()
        await self._best_effort_email(
            settings.effective_sales_email,
            f"New Aiaceone sales lead — {name}",
            (
                f"<h3>New clinic-buyer lead from the website chat (Aria)</h3>"
                f"<table>{self._email_rows([('Name', name), ('Email', email), ('Phone', lead.phone or '—'), ('Clinic / company', lead.company or '—'), ('What they need', lead.message or '—'), ('Source', 'Aria Landing Page Chat (Aiaceone website)')])}</table>"
                f"<p>Follow up with the buyer from the platform admin panel (Sales Leads).</p>"
            ),
        )
        return name

    @staticmethod
    def _email_rows(rows: list[tuple[str, str]]) -> str:
        return "".join(f"<tr><td><strong>{k}:</strong></td><td>{v}</td></tr>" for k, v in rows)

    async def _best_effort_email(self, to: str | None, subject: str, html: str) -> None:
        """Best-effort email, Resend preferred (this deployment has a live
        Resend key via the demo-request flow), SendGrid as the fallback.
        Fully guarded and silent: email is auxiliary — the DB record (patient
        lead / SalesLead) and the chat confirmation already happened. A missing
        sales email address, an unconfigured provider, or a failed send just
        logs nothing and moves on."""
        if not to:
            return
        try:
            settings = get_settings()
            if settings.resend_api_key and settings.resend_from_email:
                from src.services.email.resend_service import ResendService  # noqa: PLC0415

                await ResendService().send(to, subject, html)
                return
            if settings.sendgrid_api_key and settings.sendgrid_api_key != "SG.xxxx":
                from src.services.email.email_service import EmailService  # noqa: PLC0415

                EmailService().send(to, subject, html_content=html)
        except Exception:
            return