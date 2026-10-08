from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.telemetry.recorder import set_current_practice
from src.models.patient import Patient, PatientLifecycleStage
from src.models.appointment import Appointment
from src.models.treatment_plan import TreatmentPlan
from src.models.conversation import Conversation
from src.models.message import Message, MessageRole
from src.services.llm.llm_service import LLMService
from src.services.messaging.messaging_service import MessagingService
from src.services.messaging.quiet_hours import MessageTiming
from src.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)

_STALE_AFTER_DAYS = 3
_RENURTURE_COOLDOWN_DAYS = 4
_MAX_NURTURES = 3
_AGENT_TYPE = "lead_nurturing"

_SYSTEM_PROMPT = (
    "You write one short, warm WhatsApp/SMS follow-up for a plastic surgery clinic reaching out to a lead who "
    "went quiet. 1-2 sentences, no pressure, no fake urgency, no repeating a full pitch — just a friendly nudge "
    "inviting them to pick the conversation back up. Never diagnose or promise specific outcomes/pricing."
)


class LeadNurturingService:
    """Re-engages leads who've gone cold instead of only ever reacting to
    them — patients stuck at INQUIRY/CONTACTED with no appointment on file,
    or CONSULT_COMPLETED with no treatment plan yet, both untouched for
    _STALE_AFTER_DAYS. Capped at _MAX_NURTURES total per patient with a
    cooldown between sends, tracked by counting this service's own past
    outbound messages (agent_type="lead_nurturing") — no new schema needed,
    mirrors PostOpFollowUpService's idempotency style but via message
    history instead of a JSONB flag list, since there's no single journal
    record a lead-stage patient already has the way a surgery does."""

    def __init__(self):
        self.llm = LLMService()
        self.messaging = MessagingService()
        self.notifications = NotificationService()

    async def check_and_send_nurtures(self, db: AsyncSession, practice_id: UUID | None = None) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_STALE_AFTER_DAYS)
        sent: list[dict] = []

        candidates = await self._find_stale_leads(db, practice_id, cutoff)
        for patient in candidates:
            if not patient.phone:
                continue
            try:
                nurture_count, last_sent_at = await self._nurture_history(db, patient.id)
            except Exception:
                logger.exception("Failed reading nurture history for patient %s", patient.id)
                continue

            if nurture_count >= _MAX_NURTURES:
                continue
            if last_sent_at and last_sent_at > datetime.now(timezone.utc) - timedelta(days=_RENURTURE_COOLDOWN_DAYS):
                continue

            try:
                set_current_practice(patient.practice_id)
                text = await self._draft_message(patient)
                # PROACTIVE: this is the clinic chasing a lead, so it respects
                # both the patient's waking hours and their market's working
                # week (SOP s11). Held messages are picked up by the next poll
                # run — the 12h cadence is what makes a hold safe.
                message = await self.messaging.send_and_log(
                    db, patient.practice_id, patient, _AGENT_TYPE, text,
                    timing=MessageTiming.PROACTIVE,
                )
            except Exception:
                logger.exception("Failed to send lead nurture for patient %s", patient.id)
                continue

            if message is None:
                # Not sent — do not notify the practice that a follow-up went out.
                continue

            await self.notifications.notify(
                db, patient.practice_id, "lead_nurture_sent",
                title=f"Lead nurture sent — {patient.first_name} {patient.last_name}",
                body=f"Follow-up #{nurture_count + 1} sent to a {patient.lifecycle_stage.value} lead.",
                resource_type="patient", resource_id=patient.id,
            )
            await db.flush()
            sent.append({"patient_id": str(patient.id), "lifecycle_stage": patient.lifecycle_stage.value, "attempt": nurture_count + 1})

        return sent

    async def _find_stale_leads(self, db: AsyncSession, practice_id: UUID | None, cutoff: datetime) -> list[Patient]:
        query = select(Patient).where(
            Patient.lifecycle_stage.in_([
                PatientLifecycleStage.INQUIRY,
                PatientLifecycleStage.CONTACTED,
                PatientLifecycleStage.CONSULT_COMPLETED,
            ]),
            Patient.updated_at < cutoff,
        )
        if practice_id is not None:
            query = query.where(Patient.practice_id == practice_id)
        result = await db.execute(query)
        patients = list(result.scalars().all())
        if not patients:
            return []

        patient_ids = [p.id for p in patients]
        apt_result = await db.execute(
            select(Appointment.patient_id).where(Appointment.patient_id.in_(patient_ids)).distinct()
        )
        has_appointment = {row[0] for row in apt_result.all()}
        plan_result = await db.execute(
            select(TreatmentPlan.patient_id).where(TreatmentPlan.patient_id.in_(patient_ids)).distinct()
        )
        has_plan = {row[0] for row in plan_result.all()}

        stale = []
        for p in patients:
            if p.lifecycle_stage == PatientLifecycleStage.CONSULT_COMPLETED:
                if p.id not in has_plan:
                    stale.append(p)
            elif p.id not in has_appointment:
                stale.append(p)
        return stale

    async def _nurture_history(self, db: AsyncSession, patient_id: UUID) -> tuple[int, datetime | None]:
        result = await db.execute(
            select(Message.created_at)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.patient_id == patient_id,
                Conversation.agent_type == _AGENT_TYPE,
                Message.role == MessageRole.AGENT,
            )
        )
        timestamps = [row[0] for row in result.all()]
        if not timestamps:
            return 0, None
        return len(timestamps), max(timestamps)

    async def _draft_message(self, patient: Patient) -> str:
        procedure = (patient.qualification or {}).get("interested_procedure") if patient.qualification else None
        context = (
            f"Lead's name: {patient.first_name}. Stage: {patient.lifecycle_stage.value}. "
            f"Interested procedure (if known): {procedure or 'not specified'}."
        )
        try:
            return await self.llm.chat(messages=[{"role": "user", "content": context}], system_prompt=_SYSTEM_PROMPT, tier="low")
        except Exception:
            logger.exception("Lead nurture LLM draft failed for patient %s — using a plain fallback message", patient.id)
            return f"Hi {patient.first_name}, just checking in — still interested in moving forward? Happy to answer any questions whenever you're ready."
