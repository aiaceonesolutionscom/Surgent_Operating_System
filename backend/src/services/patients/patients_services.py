from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.patient import Patient, PatientLifecycleStage
from src.models.appointment import Appointment, AppointmentStatus
from src.models.doctor import Doctor
from src.models.conversation import Conversation, ConversationChannel
from src.models.visit_document import VisitDocumentGeneratedBy
from src.schemas.patient import CreatePatientRequest, UpdatePatientRequest, FunnelStageCount
from src.server.exceptions import NotFoundException, AppException
from src.services.visit_documents.visit_document_service import VisitDocumentService

logger = logging.getLogger(__name__)


class PatientsService:
    """Backs the dashboard's Patients page (frontend/src/app/dashboard/patients/) —
    every method here is practice-scoped; callers must always pass the
    requesting user's own practice_id (see server/dependencies.py:
    get_current_practice_user), never trust one from the client. Mirrors
    services/conversations/conversations_services.py's shape."""

    def __init__(self):
        self.visit_documents = VisitDocumentService()

    async def create_patient(self, db: AsyncSession, practice_id: UUID, data: CreatePatientRequest) -> Patient:
        assigned_doctor: Doctor | None = None
        if data.assigned_doctor_id is not None:
            doctor_result = await db.execute(
                select(Doctor).where(Doctor.id == data.assigned_doctor_id, Doctor.practice_id == practice_id)
            )
            assigned_doctor = doctor_result.scalar_one_or_none()
            if assigned_doctor is None:
                raise NotFoundException("Doctor not found")

        patient = Patient(
            practice_id=practice_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            date_of_birth=data.date_of_birth,
            chief_complaint=data.chief_complaint,
            needs_surgery=data.needs_surgery,
            ai_agent_assigned=data.ai_agent_assigned,
            agent_status="active" if data.ai_agent_assigned else "inactive",
            source=data.source,
            assigned_doctor_id=data.assigned_doctor_id,
        )
        # Every PatientProfileFields key (gender, pregnancy_status,
        # father_name, allergies, ...) a front-desk walk-in intake can set in
        # one go — same generic write update_patient already uses, so a new
        # field added there is picked up here automatically too.
        profile_fields = data.model_dump(
            exclude_unset=True,
            include={
                "gender", "additional_phones", "father_name", "pregnancy_status", "occupation",
                "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
                "regular_physician_name", "regular_physician_phone", "allergies", "surgical_history",
                "current_medications", "smoking_status", "previous_cosmetic_procedures", "referral_source",
                "preferred_language", "communication_preferences", "insurance_provider", "insurance_number",
            },
        )
        for field, value in profile_fields.items():
            setattr(patient, field, value)

        db.add(patient)
        await db.flush()

        if data.preferred_channel == "whatsapp" and data.phone:
            # Seed conversation so MessagingService.resolve_channel's "infer
            # from the most recent conversation" finds WhatsApp on the very
            # first automated send (visit document, appointment confirmation)
            # instead of falling back to SMS for a patient with no history yet.
            db.add(Conversation(
                practice_id=practice_id, patient_id=patient.id,
                agent_type="front_desk_intake", channel=ConversationChannel.WHATSAPP,
            ))
            await db.flush()

        await db.refresh(patient)
        await self._attach_appointment_flags(db, practice_id, [patient])
        await self._attach_doctor_names(db, practice_id, [patient])

        # Best-effort visit-document generation for a walk-in/front-desk
        # intake too, not just the appointment-booking and AI-receptionist
        # paths (see AppointmentsService.create_appointment and
        # InboundService) — front desk collecting a patient's full intake in
        # one go should get the same "here's your intake summary" doc
        # immediately, even when no appointment is booked yet. Never allowed
        # to fail patient creation itself.
        try:
            await self.visit_documents.generate_and_send(
                db, practice_id, patient, doctor=assigned_doctor, generated_by=VisitDocumentGeneratedBy.STAFF,
            )
        except Exception:
            logger.exception("Visit document generation failed for patient %s", patient.id)
        return patient

    async def list_patients(
        self, db: AsyncSession, practice_id: UUID, doctor_id: UUID | None = None, include_archived: bool = False
    ) -> list[Patient]:
        # doctor_id scopes to Patient.assigned_doctor_id — the Doctor
        # hard-restriction (see server/patient_access.py); the controller
        # passes this whenever the caller's role is DOCTOR, never trusting
        # the client to ask for the right doctor_id itself. Archived
        # patients are excluded by default — this is the "hidden from the
        # default list" half of archiving (see archive_patient).
        query = select(Patient).where(Patient.practice_id == practice_id)
        if not include_archived:
            query = query.where(Patient.is_archived == False)  # noqa: E712
        if doctor_id is not None:
            query = query.where(Patient.assigned_doctor_id == doctor_id)
        query = query.order_by(desc(Patient.created_at))
        result = await db.execute(query)
        patients = list(result.scalars().all())
        await self._attach_appointment_flags(db, practice_id, patients)
        await self._attach_doctor_names(db, practice_id, patients)
        return patients

    async def get_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> Patient:
        query = select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id)
        result = await db.execute(query)
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")
        await self._attach_appointment_flags(db, practice_id, [patient])
        await self._attach_doctor_names(db, practice_id, [patient])
        return patient

    async def assign_doctor(self, db: AsyncSession, practice_id: UUID, patient_id: UUID, doctor_id: UUID | None) -> Patient:
        patient = await self.get_patient(db, practice_id, patient_id)
        if doctor_id is not None:
            doctor_result = await db.execute(select(Doctor).where(Doctor.id == doctor_id, Doctor.practice_id == practice_id))
            if doctor_result.scalar_one_or_none() is None:
                raise NotFoundException("Doctor not found")
        patient.assigned_doctor_id = doctor_id
        await db.flush()
        await db.refresh(patient)
        await self._attach_appointment_flags(db, practice_id, [patient])
        await self._attach_doctor_names(db, practice_id, [patient])
        return patient

    async def archive_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID, archived_by: UUID) -> Patient:
        patient = await self.get_patient(db, practice_id, patient_id)
        if patient.is_archived:
            return patient
        patient.is_archived = True
        patient.archived_at = datetime.now(timezone.utc)
        patient.archived_by = archived_by
        # Archiving blocks portal login too (see AppointmentsService's own
        # is_archived check for the "no new appointments" half) — an
        # archived record shouldn't still be reachable through any door.
        patient.portal_enabled = False
        await db.flush()
        await db.refresh(patient)
        await self._attach_doctor_names(db, practice_id, [patient])
        return patient

    async def delete_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> None:
        """Hard delete — Owner-only, only for an already-archived patient (see
        patients_router.py). Only ORM-cascaded relations (photos,
        appointments, recovery_journals, conversations, review_requests,
        consent_documents, invoices, visit_documents — see models/patient.py)
        are removed automatically; a patient with deeper records the ORM
        doesn't cascade (treatment plans, surgeries, consultation notes,
        refund requests, session visits, waitlist entries) still can't be
        hard-deleted — the FK violation is caught below and turned into a
        clear message instead of a 500."""
        patient = await self.get_patient(db, practice_id, patient_id)
        if not patient.is_archived:
            raise AppException("Archive this patient first — only archived patients can be permanently deleted.")
        await db.delete(patient)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise AppException(
                "Can't delete this patient — they still have treatment plans, surgeries, consultation notes, "
                "refund requests, or other clinical/financial records attached. Those have to be resolved first."
            )

    async def restore_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> Patient:
        patient = await self.get_patient(db, practice_id, patient_id)
        patient.is_archived = False
        patient.archived_at = None
        patient.archived_by = None
        await db.flush()
        await db.refresh(patient)
        await self._attach_doctor_names(db, practice_id, [patient])
        return patient

    async def update_patient(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID, data: UpdatePatientRequest
    ) -> Patient:
        query = select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id)
        result = await db.execute(query)
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(patient, field, value)
        await db.flush()
        await db.refresh(patient)
        await self._attach_appointment_flags(db, practice_id, [patient])
        await self._attach_doctor_names(db, practice_id, [patient])
        return patient

    async def update_stage(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID, stage: str, lost_reason: str | None
    ) -> Patient:
        query = select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id)
        result = await db.execute(query)
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")

        try:
            new_stage = PatientLifecycleStage(stage)
        except ValueError:
            raise AppException(f"'{stage}' is not a valid funnel stage")

        patient.lifecycle_stage = new_stage
        patient.lost_reason = lost_reason if new_stage == PatientLifecycleStage.LOST else None
        await db.flush()
        await db.refresh(patient)
        await self._attach_appointment_flags(db, practice_id, [patient])
        await self._attach_doctor_names(db, practice_id, [patient])
        return patient

    async def funnel_summary(self, db: AsyncSession, practice_id: UUID) -> list[FunnelStageCount]:
        result = await db.execute(
            select(Patient.lifecycle_stage, func.count())
            .where(Patient.practice_id == practice_id)
            .group_by(Patient.lifecycle_stage)
        )
        counts = {stage.value: count for stage, count in result.all()}
        # Always return every stage, in funnel order, even at 0 — a chart
        # rendering this needs a stable shape, not just whichever stages
        # happen to have a patient in them yet.
        return [FunnelStageCount(stage=stage.value, count=counts.get(stage.value, 0)) for stage in PatientLifecycleStage]

    async def _attach_appointment_flags(self, db: AsyncSession, practice_id: UUID, patients: list[Patient]) -> None:
        # Two practice-wide queries regardless of patient count (not N+1) —
        # sets `has_upcoming_appointment`/`has_completed_appointment`/
        # `last_appointment_at`/`next_appointment_at` as plain instance
        # attributes so PatientResponse.model_validate (which reads via
        # from_attributes, not a real column) picks them up.
        if not patients:
            return
        patient_ids = [p.id for p in patients]
        now = datetime.now(timezone.utc)

        upcoming_result = await db.execute(
            select(Appointment.patient_id, func.min(Appointment.start_time))
            .where(
                Appointment.practice_id == practice_id,
                Appointment.patient_id.in_(patient_ids),
                Appointment.start_time >= now,
                Appointment.status != AppointmentStatus.CANCELLED,
            )
            .group_by(Appointment.patient_id)
        )
        next_appointment_by_id = {row[0]: row[1] for row in upcoming_result.all()}

        completed_result = await db.execute(
            select(Appointment.patient_id, func.max(Appointment.start_time))
            .where(
                Appointment.practice_id == practice_id,
                Appointment.patient_id.in_(patient_ids),
                Appointment.status == AppointmentStatus.COMPLETED,
            )
            .group_by(Appointment.patient_id)
        )
        last_appointment_by_id = {row[0]: row[1] for row in completed_result.all()}

        for patient in patients:
            patient.has_upcoming_appointment = patient.id in next_appointment_by_id
            patient.has_completed_appointment = patient.id in last_appointment_by_id
            patient.next_appointment_at = next_appointment_by_id.get(patient.id)
            patient.last_appointment_at = last_appointment_by_id.get(patient.id)

    async def _attach_doctor_names(self, db: AsyncSession, practice_id: UUID, patients: list[Patient]) -> None:
        # Same transient-attribute pattern as _attach_appointment_flags —
        # PatientResponse.assigned_doctor_name reads this, not a live join,
        # so every response stays a flat query plus one small IN lookup.
        doctor_ids = {p.assigned_doctor_id for p in patients if p.assigned_doctor_id}
        names: dict[UUID, str] = {}
        if doctor_ids:
            result = await db.execute(select(Doctor.id, Doctor.name).where(Doctor.id.in_(doctor_ids)))
            names = dict(result.all())
        for patient in patients:
            patient.assigned_doctor_name = names.get(patient.assigned_doctor_id) if patient.assigned_doctor_id else None
