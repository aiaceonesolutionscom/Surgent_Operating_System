from __future__ import annotations
import logging
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.surgery import Surgery, SurgeryStatus
from src.models.patient import Patient
from src.models.recovery_checkin import RecoveryCheckpoint
from src.services.messaging.messaging_service import MessagingService
from src.services.messaging.quiet_hours import MessageTiming
from src.services.notifications.notification_service import NotificationService
from src.services.recovery.recovery_services import RecoveryService

logger = logging.getLogger(__name__)

# Which day-since-surgery maps to which real RecoveryCheckIn checkpoint —
# matches RecoveryService's own checkpoint set (recovery_services.py), kept
# as a local mapping rather than importing that module's private one so
# this doesn't couple to an underscore-prefixed symbol.
_CHECKPOINT_DAY_MAP: dict[int, RecoveryCheckpoint] = {
    1: RecoveryCheckpoint.DAY_1,
    3: RecoveryCheckpoint.DAY_3,
    7: RecoveryCheckpoint.DAY_7,
    14: RecoveryCheckpoint.DAY_14,
    30: RecoveryCheckpoint.MONTH_1,
}


class PostOpFollowUpService:
    """Makes the Recovery Timeline (Week 3) proactive instead of only ever
    waiting for a patient to think to check in on their own. For every
    COMPLETED surgery, on the exact day a checkpoint falls due (Day 1/3/7/14/
    1 month post-op), sends one real WhatsApp/SMS prompt via the existing
    MessagingService and logs an in-app Notification for staff — the AI's
    role here is strictly "ask," never "diagnose": the patient's actual
    reply is what gets classified by RecoveryService's existing threshold
    rules once they respond (with a real check-in via the Portal, or a
    reply a staff member logs manually), matching the project's established
    boundary that AI never makes a clinical judgment.

    Idempotent per checkpoint per journal: which checkpoints have already
    been prompted is tracked in RecoveryJournal.notes (a JSONB field that
    already existed for exactly this kind of loosely-structured flag), so
    running this check more than once on the same day — or many times over
    the following days — never sends the same prompt twice."""

    def __init__(self):
        self.messaging = MessagingService()
        self.notifications = NotificationService()
        self.recovery = RecoveryService()

    async def check_and_send_followups(self, db: AsyncSession, practice_id: UUID | None = None) -> list[dict]:
        """`practice_id=None` (the background poller's own usage) checks
        every practice; a manual staff-triggered run passes their own
        practice_id so one clinic can't trigger sends for another."""
        today = date.today()
        query = select(Surgery).where(Surgery.status == SurgeryStatus.COMPLETED)
        if practice_id is not None:
            query = query.where(Surgery.practice_id == practice_id)
        result = await db.execute(query)
        sent: list[dict] = []

        for surgery in result.scalars().all():
            if surgery.scheduled_date is None:
                continue
            days_since = (today - surgery.scheduled_date.date()).days
            checkpoint = _CHECKPOINT_DAY_MAP.get(days_since)
            if checkpoint is None:
                continue

            journal = await self.recovery.get_or_create_journal(
                db, surgery.patient_id, surgery.procedure_id, surgery.scheduled_date.date()
            )
            already_sent = checkpoint.value in (journal.notes or {}).get("followups_sent", [])
            if already_sent:
                continue

            result2 = await db.execute(select(Patient).where(Patient.id == surgery.patient_id))
            patient = result2.scalar_one_or_none()
            if patient is None or not patient.phone:
                continue

            label = checkpoint.value.replace("_", " ")
            text = (
                f"Hi {patient.first_name}, checking in on your recovery ({label} post-op). "
                "How are you feeling — any pain, swelling, or concerns? Reply here, or log a check-in on your patient portal."
            )
            try:
                # REMINDER, not PROACTIVE: a clinical check-in is expected, but it
                # still waits for the patient's own 09:00-21:00 window (SOP s11).
                message = await self.messaging.send_and_log(
                    db, surgery.practice_id, patient, "post_op_followup", text,
                    timing=MessageTiming.REMINDER,
                )
            except Exception:
                logger.exception("Failed to send post-op follow-up for surgery %s (checkpoint %s)", surgery.id, checkpoint.value)
                continue

            if message is None:
                # Held back by quiet hours — do NOT journal it as sent, so the
                # next poll run (every 6h) picks the same checkpoint up again.
                continue

            journal.notes = {
                **(journal.notes or {}),
                "followups_sent": [*(journal.notes or {}).get("followups_sent", []), checkpoint.value],
            }
            await self.notifications.notify(
                db, surgery.practice_id, "post_op_followup_sent",
                title=f"Post-op follow-up sent — {patient.first_name} {patient.last_name}",
                body=f"{label.capitalize()} check-in prompt sent.",
                resource_type="surgery", resource_id=surgery.id,
            )
            await db.flush()
            sent.append({"surgery_id": str(surgery.id), "patient_id": str(patient.id), "checkpoint": checkpoint.value})

        return sent
