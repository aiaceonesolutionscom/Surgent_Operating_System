from __future__ import annotations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.patient import Patient
from src.services.appointments.appointments_services import AppointmentsService
from src.services.messaging.messaging_service import MessagingService
from src.services.messaging.quiet_hours import (
    MessageTiming,
    evaluate_patient_timing,
    format_for_patient,
    load_practice,
    resolve_patient_timing_context,
)
from src.services.agent_log.agent_log_service import AgentLogService
from src.server.exceptions import NotFoundException


class ReminderService:
    """Automated outbound appointment reminders — a real, standing incremental
    capability over the human Receptionist workflow (nobody has to remember
    to text patients manually). Logged as `agent_type=\"ai_receptionist\"`.

    Two things the SOP is explicit about, and this service used to get both
    wrong (it formatted the appointment in raw UTC and sent whenever it was
    called):

    * the time is stated in the **patient's** local zone, with the clinic's
      alongside it (s9.1, s12) — time-zone confusion is the single biggest
      cause of international no-shows;
    * the send respects their 09:00-21:00 window (s11). Inside a staff
      member's own working day the patient may well be asleep on the other
      side of the world, so a held reminder is reported back with the time it
      *will* go out rather than silently dropped.
    """

    def __init__(self):
        self.appointments = AppointmentsService()
        self.messaging = MessagingService()
        self.agent_log = AgentLogService()

    async def send_reminder(self, db: AsyncSession, practice_id: UUID, appointment_id: UUID, performed_by: str) -> dict:
        appointment = await self.appointments.get_appointment(db, practice_id, appointment_id)

        result = await db.execute(select(Patient).where(Patient.id == appointment.patient_id))
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found for this appointment")

        practice = await load_practice(db, practice_id)
        patient_timezone = "UTC"
        clinic_timezone = (practice.timezone if practice else None) or "UTC"
        if practice is not None:
            patient_timezone = (await resolve_patient_timing_context(db, practice, patient)).timezone

        # Checked here as well as inside MessagingService so the callers (and the
        # dashboard) get the reason and the next allowed time, not just a None.
        decision = await evaluate_patient_timing(db, practice_id, patient, MessageTiming.REMINDER)
        if not decision.allowed:
            await self.agent_log.log(
                db, practice_id, agent_type="ai_receptionist", action="reminder_held_quiet_hours",
                details={"appointment_id": str(appointment.id), "patient_id": str(patient.id), **decision.as_log_details()},
                performed_by=performed_by,
            )
            return {
                "appointment_id": str(appointment.id),
                "message_id": "",
                "sent": False,
                "held_until": decision.next_allowed_label,
                "hold_reason": decision.reason,
            }

        when = format_for_patient(appointment.start_time, patient_timezone, clinic_timezone)
        text = (
            f"Hi {patient.first_name}, this is a reminder for your {appointment.appointment_type} "
            f"appointment on {when}. Reply if you need to reschedule."
        )

        message = await self.messaging.send_and_log(
            db, practice_id, patient, "appointment_reminder", text, timing=MessageTiming.REMINDER
        )
        if message is None:
            # Held by the gate inside MessagingService (e.g. the boundary minute
            # moved between the two checks) — same honest response as above.
            return {
                "appointment_id": str(appointment.id),
                "message_id": "",
                "sent": False,
                "held_until": decision.next_allowed_label,
                "hold_reason": decision.reason,
            }

        await self.agent_log.log(
            db, practice_id, agent_type="ai_receptionist", action="reminder_sent",
            details={
                "appointment_id": str(appointment.id),
                "patient_id": str(patient.id),
                "patient_timezone": patient_timezone,
            },
            performed_by=performed_by,
        )
        return {"appointment_id": str(appointment.id), "message_id": str(message.id), "sent": True}
