from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.appointment import Appointment, AppointmentStatus
from src.models.doctor import Doctor
from src.models.patient import Patient
from src.services.messaging.messaging_service import MessagingService
from src.server.exceptions import NotFoundException, AppException

logger = logging.getLogger(__name__)


class AppointmentsService:
    """Every method here is practice-scoped; callers must always pass the
    requesting user's own practice_id, never trust one from the client."""

    def __init__(self):
        self.messaging = MessagingService()

    async def _notify_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID, agent_type: str, text: str) -> None:
        """Best-effort appointment-change notification — a failure here
        (no phone on file, channel misconfigured, provider outage) must
        never block the actual appointment state change staff just made,
        the same boundary Surgery.complete_surgery draws around its own
        optional inventory-consumption side effect."""
        result = await db.execute(select(Patient).where(Patient.id == patient_id))
        patient = result.scalar_one_or_none()
        if patient is None or not patient.phone:
            return
        try:
            await self.messaging.send_and_log(db, practice_id, patient, agent_type, text)
        except Exception:
            logger.exception("Failed to send %s notification for patient %s", agent_type, patient_id)

    @staticmethod
    def _with_patient_names(rows: list[tuple[Appointment, Patient]]) -> list[Appointment]:
        # Attach a transient patient_name so the response schema can surface it
        # without a migration (the column lives only on Patient).
        appointments: list[Appointment] = []
        for appointment, patient in rows:
            appointment.patient_name = f"{patient.first_name} {patient.last_name}".strip()
            appointments.append(appointment)
        return appointments

    async def list_for_doctor_user(
        self, db: AsyncSession, practice_id: UUID, user_id: UUID, patient_id: UUID | None = None
    ) -> list[Appointment]:
        result = await db.execute(
            select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id)
        )
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise NotFoundException("No doctor profile linked to this account")

        conditions = [Appointment.practice_id == practice_id, Appointment.doctor_id == doctor.id]
        if patient_id is not None:
            conditions.append(Appointment.patient_id == patient_id)
        query = (
            select(Appointment, Patient)
            .join(Patient, Patient.id == Appointment.patient_id)
            .where(and_(*conditions))
            .order_by(Appointment.start_time)
        )
        result = await db.execute(query)
        return self._with_patient_names(result.all())

    async def list_for_practice(
        self,
        db: AsyncSession,
        practice_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
        patient_id: UUID | None = None,
    ) -> list[Appointment]:
        # Practice-wide view — Owner/Receptionist see every doctor's
        # schedule, unlike list_for_doctor_user's own-schedule-only scope.
        conditions = [Appointment.practice_id == practice_id]
        if start is not None:
            conditions.append(Appointment.start_time >= start)
        if end is not None:
            conditions.append(Appointment.start_time <= end)
        if patient_id is not None:
            conditions.append(Appointment.patient_id == patient_id)

        query = (
            select(Appointment, Patient)
            .join(Patient, Patient.id == Appointment.patient_id)
            .where(and_(*conditions))
            .order_by(Appointment.start_time)
        )
        result = await db.execute(query)
        return self._with_patient_names(result.all())

    async def get_appointment(self, db: AsyncSession, practice_id: UUID, appointment_id: UUID) -> Appointment:
        result = await db.execute(
            select(Appointment).where(Appointment.id == appointment_id, Appointment.practice_id == practice_id)
        )
        appointment = result.scalar_one_or_none()
        if appointment is None:
            raise NotFoundException("Appointment not found")
        return appointment

    async def create_appointment(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patient_id: UUID,
        doctor_id: UUID | None,
        appointment_type: str,
        start_time: datetime,
        end_time: datetime,
        notes: str | None = None,
        notify_patient: bool = True,
    ) -> Appointment:
        if end_time <= start_time:
            raise AppException("Appointment end_time must be after start_time")

        patient_result = await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id)
        )
        patient = patient_result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")
        if patient.is_archived:
            raise AppException("Cannot book an appointment for an archived patient — restore them first")

        if doctor_id is not None:
            doctor_result = await db.execute(
                select(Doctor).where(Doctor.id == doctor_id, Doctor.practice_id == practice_id)
            )
            doctor = doctor_result.scalar_one_or_none()
            if doctor is None:
                raise NotFoundException("Doctor not found")
            if not doctor.is_active:
                raise AppException("This doctor is not active — reactivate them before assigning appointments")

            # Same conflict window the AI Receptionist's _find_available_doctor
            # checks before booking on WhatsApp — staff-created appointments
            # must not silently double-book a doctor either.
            conflict_result = await db.execute(
                select(Appointment).where(
                    Appointment.doctor_id == doctor_id,
                    Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
                    Appointment.start_time < end_time,
                    Appointment.end_time > start_time,
                )
            )
            if conflict_result.scalars().first() is not None:
                raise AppException("This doctor already has an appointment overlapping those times — pick a different slot")

        appointment = Appointment(
            practice_id=practice_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_type=appointment_type,
            status=AppointmentStatus.SCHEDULED,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
        )
        db.add(appointment)
        await db.flush()
        await db.refresh(appointment)

        # Staff-created bookings deserve the same confirmation the AI
        # Receptionist gives conversationally on WhatsApp. The AI path passes
        # notify_patient=False because its own reply to the patient IS the
        # confirmation — routing another automated message right behind it
        # would double-message the same person on the same channel.
        if notify_patient:
            when = start_time.strftime("%A, %B %d at %I:%M %p")
            await self._notify_patient(
                db, practice_id, patient_id, "appointment_confirmation",
                f"Your {appointment_type} appointment is confirmed for {when}. We look forward to seeing you!",
            )
        return appointment

    async def reschedule_appointment(
        self,
        db: AsyncSession,
        practice_id: UUID,
        appointment_id: UUID,
        new_start_time: datetime,
        new_end_time: datetime,
    ) -> Appointment:
        if new_end_time <= new_start_time:
            raise AppException("Appointment end_time must be after start_time")

        appointment = await self.get_appointment(db, practice_id, appointment_id)
        if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED):
            raise AppException(f"Cannot reschedule a {appointment.status.value} appointment")

        appointment.start_time = new_start_time
        appointment.end_time = new_end_time
        appointment.status = AppointmentStatus.SCHEDULED
        await db.flush()
        await db.refresh(appointment)

        when = new_start_time.strftime("%A, %B %d at %I:%M %p")
        await self._notify_patient(
            db, practice_id, appointment.patient_id, "appointment_reschedule",
            f"Your {appointment.appointment_type} appointment has been rescheduled to {when}. Reply if this doesn't work for you.",
        )
        return appointment

    async def cancel_appointment(
        self, db: AsyncSession, practice_id: UUID, appointment_id: UUID, reason: str | None = None
    ) -> Appointment:
        appointment = await self.get_appointment(db, practice_id, appointment_id)
        if appointment.status == AppointmentStatus.CANCELLED:
            return appointment

        appointment.status = AppointmentStatus.CANCELLED
        if reason:
            appointment.notes = f"{appointment.notes}\nCancelled: {reason}" if appointment.notes else f"Cancelled: {reason}"
        await db.flush()
        await db.refresh(appointment)

        when = appointment.start_time.strftime("%A, %B %d at %I:%M %p")
        await self._notify_patient(
            db, practice_id, appointment.patient_id, "appointment_cancellation",
            f"Your {appointment.appointment_type} appointment on {when} has been cancelled. Reply if you'd like to rebook.",
        )
        return appointment

    async def check_in_appointment(self, db: AsyncSession, practice_id: UUID, appointment_id: UUID) -> Appointment:
        appointment = await self.get_appointment(db, practice_id, appointment_id)
        if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
            raise AppException(f"Cannot check in a {appointment.status.value} appointment")

        appointment.status = AppointmentStatus.CHECKED_IN
        appointment.checked_in_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(appointment)
        return appointment

    async def complete_appointment(self, db: AsyncSession, practice_id: UUID, appointment_id: UUID) -> Appointment:
        appointment = await self.get_appointment(db, practice_id, appointment_id)
        if appointment.status == AppointmentStatus.COMPLETED:
            return appointment
        # The front desk UI only ever shows "Complete" for ready_for_checkout,
        # so anything else here is almost certainly a mistake (or a stale
        # page) — don't let a scheduled appointment skip the whole visit.
        if appointment.status not in (
            AppointmentStatus.WITH_DOCTOR,
            AppointmentStatus.READY_FOR_CHECKOUT,
        ):
            raise AppException(
                f"Cannot complete a {appointment.status.value} appointment — the patient must be with the doctor first"
            )

        appointment.status = AppointmentStatus.COMPLETED
        await db.flush()
        await db.refresh(appointment)
        return appointment

    async def start_with_doctor(self, db: AsyncSession, practice_id: UUID, appointment_id: UUID) -> Appointment:
        appointment = await self.get_appointment(db, practice_id, appointment_id)
        if appointment.status != AppointmentStatus.CHECKED_IN:
            raise AppException(f"Cannot move a {appointment.status.value} appointment to with-doctor — check in first")

        appointment.status = AppointmentStatus.WITH_DOCTOR
        appointment.with_doctor_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(appointment)
        return appointment

    async def mark_ready_for_checkout(self, db: AsyncSession, practice_id: UUID, appointment_id: UUID) -> Appointment:
        appointment = await self.get_appointment(db, practice_id, appointment_id)
        if appointment.status != AppointmentStatus.WITH_DOCTOR:
            raise AppException(f"Cannot move a {appointment.status.value} appointment to checkout — they must be with the doctor first")

        appointment.status = AppointmentStatus.READY_FOR_CHECKOUT
        appointment.ready_for_checkout_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(appointment)
        return appointment

    async def mark_no_show(self, db: AsyncSession, practice_id: UUID, appointment_id: UUID) -> Appointment:
        appointment = await self.get_appointment(db, practice_id, appointment_id)
        if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
            raise AppException(f"Cannot mark a {appointment.status.value} appointment as no-show")
        if appointment.checked_in_at is not None:
            raise AppException("This patient already checked in — no-show no longer applies")

        appointment.status = AppointmentStatus.NO_SHOW
        await db.flush()
        await db.refresh(appointment)
        return appointment
