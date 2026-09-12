from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.patient import Patient
from src.models.appointment import Appointment, AppointmentStatus
from src.models.consent_document import ConsentDocument
from src.models.invoice import Invoice, InvoiceStatus
from src.models.patient_photo import PatientPhoto
from src.models.doctor import Doctor
from src.models.treatment_plan import TreatmentPlan, TreatmentPlanItem
from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.message import Message, MessageRole
from src.schemas.patient_portal import (
    PortalAppointment,
    PortalBookingRequest,
    PortalConsentDocument,
    PortalInvoice,
    PortalPatientResponse,
    PortalPhoto,
    PortalDoctorInfo,
    PortalTreatmentPlan,
    PortalTreatmentPlanItem,
    PortalMessage,
    UpdateMyProfileRequest,
    RescheduleAppointmentRequest,
)
from src.server.exceptions import AppException, NotFoundException
from src.services.audit.audit_log_service import AuditLogService


class PatientPortalService:
    """Read/write data access for a *logged-in* patient (see
    patient_portal_auth_service.py for the login itself — everything here
    takes an already-verified Patient, resolved by the
    get_current_portal_patient dependency, never a raw token)."""

    async def get_my_portal_data(self, db: AsyncSession, patient: Patient) -> PortalPatientResponse:
        appointments, consents, invoices, photos, pending = await self._load_related(db, patient.id)
        doctor = await self._resolve_assigned_doctor(db, patient)
        treatment_plans = await self._load_treatment_plans(db, patient.id)
        return PortalPatientResponse(
            id=patient.id,
            portal_id=patient.portal_id,
            first_name=patient.first_name,
            last_name=patient.last_name,
            email=patient.email,
            phone=patient.phone,
            additional_phones=patient.additional_phones,
            chief_complaint=patient.chief_complaint,
            consent_status=patient.consent_status,
            doctor=doctor,
            appointments=appointments,
            consent_documents=consents,
            invoices=invoices,
            photos=photos,
            treatment_plans=treatment_plans,
            invoice_total_pending=pending,
            intake_completed=patient.intake_summary is not None,
            intake_summary=patient.intake_summary,
            pin_set=patient.portal_pin_hash is not None,
        )

    async def book_appointment(self, db: AsyncSession, patient: Patient, data: PortalBookingRequest) -> Appointment:
        if data.end_time <= data.start_time:
            raise AppException("Appointment end time must be after start time")
        if data.start_time < datetime.now(timezone.utc):
            raise AppException("Appointment time must be in the future")

        appointment = Appointment(
            practice_id=patient.practice_id,
            patient_id=patient.id,
            doctor_id=None,
            appointment_type=data.appointment_type,
            status=AppointmentStatus.SCHEDULED,
            start_time=data.start_time,
            end_time=data.end_time,
            notes=data.notes,
        )
        db.add(appointment)
        await db.flush()
        await db.refresh(appointment)
        return appointment

    # Portal messaging is patient-to-their-own-doctor only — a dedicated
    # agent_type, distinct from "ai_receptionist" (the AI-driven call/
    # WhatsApp intake flow). Mixing the two made a portal message land in
    # the same generic inbox as automated receptionist chatter instead of
    # reading as "a message to your doctor."
    _AGENT_TYPE = "patient_doctor_message"

    async def _find_or_create_conversation(self, db: AsyncSession, patient: Patient) -> Conversation:
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.practice_id == patient.practice_id,
                Conversation.patient_id == patient.id,
                Conversation.agent_type == self._AGENT_TYPE,
            )
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None and existing.status != ConversationStatus.RESOLVED:
            return existing

        conversation = Conversation(
            practice_id=patient.practice_id,
            patient_id=patient.id,
            agent_type=self._AGENT_TYPE,
            channel=ConversationChannel.WEB_CHAT,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def get_messages(self, db: AsyncSession, patient: Patient) -> list[PortalMessage]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.practice_id == patient.practice_id, Conversation.patient_id == patient.id, Conversation.agent_type == self._AGENT_TYPE)
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            return []
        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)
        )
        return [
            PortalMessage(id=m.id, role=m.role.value, content=m.content, created_at=m.created_at)
            for m in msg_result.scalars().all()
            if m.role != MessageRole.SYSTEM
        ]

    async def send_message(self, db: AsyncSession, patient: Patient, content: str) -> PortalMessage:
        content = content.strip()
        if not content:
            raise AppException("Message can't be empty")
        # assigned_doctor_id (not the appointment/plan-inferred lookup used
        # for the "My Doctor" display elsewhere) is the same field
        # server/patient_access.py's Doctor hard-restriction checks — this
        # is what actually determines who the message will reach.
        if not patient.assigned_doctor_id:
            raise AppException("You don't have a doctor assigned yet — please contact the clinic before sending a message.")

        conversation = await self._find_or_create_conversation(db, patient)
        message = Message(conversation_id=conversation.id, role=MessageRole.PATIENT, content=content, content_type="text")
        db.add(message)
        # A message sent from the portal always needs a human look — unlike
        # WhatsApp, there's no AI-reply pipeline wired to this entry point,
        # so silently leaving it ACTIVE would mean nobody ever gets nudged
        # to answer it.
        conversation.status = ConversationStatus.NEEDS_ATTENTION
        await db.flush()
        await db.refresh(message)

        return PortalMessage(id=message.id, role=message.role.value, content=message.content, created_at=message.created_at)

    async def update_my_profile(self, db: AsyncSession, patient: Patient, data: UpdateMyProfileRequest) -> Patient:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(patient, field, value)
        await db.flush()
        await db.refresh(patient)
        return patient

    # --- Appointment self-service (split upcoming/past views + cancel/
    # reschedule — the portal previously only had the flat list in /me and
    # the one-way POST booking, so a patient could never change (or even
    # cleanly re-read) their own schedule.) ---

    async def get_my_appointments(
        self,
        db: AsyncSession,
        patient: Patient,
        scope: str = "upcoming",
        status: str | None = None,
    ) -> list[PortalAppointment]:
        now = datetime.now(timezone.utc)
        conditions = [Appointment.patient_id == patient.id]
        if scope not in ("upcoming", "past"):
            raise AppException("scope must be 'upcoming' or 'past'")
        if scope == "upcoming":
            conditions.append(Appointment.start_time >= now)
        else:
            conditions.append(Appointment.start_time < now)
        if status is not None:
            try:
                status_enum = AppointmentStatus(status)
            except ValueError:
                raise AppException(f"Invalid appointment status: {status}")
            conditions.append(Appointment.status == status_enum)
        result = await db.execute(
            select(Appointment).where(*conditions).order_by(Appointment.start_time.asc())
        )
        return [
            PortalAppointment(
                id=a.id,
                appointment_type=a.appointment_type,
                status=a.status.value if hasattr(a.status, "value") else str(a.status),
                start_time=a.start_time,
                end_time=a.end_time,
                notes=a.notes,
            )
            for a in result.scalars().all()
        ]

    async def cancel_my_appointment(self, db: AsyncSession, patient: Patient, appointment_id: UUID) -> Appointment:
        appointment = await self._get_patient_appointment(db, patient, appointment_id)
        if appointment.status not in (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED):
            raise AppException("Only scheduled or confirmed appointments can be cancelled")
        appointment.status = AppointmentStatus.CANCELLED
        await db.flush()
        await AuditLogService().log(
            db,
            patient.practice_id,
            "patient_portal",
            "appointment.cancel",
            actor_user_id=None,
            resource_type="appointment",
            resource_id=appointment.id,
        )
        return appointment

    async def reschedule_my_appointment(
        self,
        db: AsyncSession,
        patient: Patient,
        appointment_id: UUID,
        data: RescheduleAppointmentRequest,
    ) -> Appointment:
        appointment = await self._get_patient_appointment(db, patient, appointment_id)
        if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
            raise AppException("This appointment can no longer be rescheduled")
        if data.end_time <= data.start_time:
            raise AppException("Appointment end time must be after start time")
        if data.start_time < datetime.now(timezone.utc):
            raise AppException("Appointment time must be in the future")
        appointment.start_time = data.start_time
        appointment.end_time = data.end_time
        await db.flush()
        await AuditLogService().log(
            db,
            patient.practice_id,
            "patient_portal",
            "appointment.reschedule",
            actor_user_id=None,
            resource_type="appointment",
            resource_id=appointment.id,
        )
        return appointment

    async def get_my_treatment_plan(
        self, db: AsyncSession, patient: Patient, treatment_plan_id: UUID
    ) -> PortalTreatmentPlan:
        result = await db.execute(
            select(TreatmentPlan)
            .options(selectinload(TreatmentPlan.items).selectinload(TreatmentPlanItem.procedure))
            .where(TreatmentPlan.id == treatment_plan_id, TreatmentPlan.patient_id == patient.id)
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise NotFoundException("Treatment plan not found")
        return PortalTreatmentPlan(
            id=plan.id,
            title=plan.title,
            status=plan.status.value if hasattr(plan.status, "value") else str(plan.status),
            items=[
                PortalTreatmentPlanItem(
                    id=item.id,
                    procedure_name=item.procedure.name if item.procedure else "Procedure",
                    status=item.status.value if hasattr(item.status, "value") else str(item.status),
                    estimated_price=float(item.estimated_price) if item.estimated_price is not None else None,
                    actual_price=float(item.actual_price) if item.actual_price is not None else None,
                )
                for item in plan.items
            ],
            created_at=plan.created_at,
        )

    # --- Helpers ----------------------------------------------------------

    async def _get_patient_appointment(self, db: AsyncSession, patient: Patient, appointment_id: UUID) -> Appointment:
        result = await db.execute(
            select(Appointment).where(Appointment.id == appointment_id, Appointment.patient_id == patient.id)
        )
        appointment = result.scalar_one_or_none()
        if appointment is None:
            raise NotFoundException("Appointment not found")
        return appointment

    async def _resolve_assigned_doctor(self, db: AsyncSession, patient: Patient) -> PortalDoctorInfo | None:
        # patient.assigned_doctor_id is the durable, staff-set link — the
        # SAME field server/patient_access.py's Doctor hard-restriction
        # checks, so this must be the primary source of truth: showing a
        # different "your doctor" here than the one actually authorized to
        # see this patient's messages would be genuinely confusing. Only
        # falls back to inferring from appointments/treatment-plan history
        # when no explicit assignment exists yet.
        if patient.assigned_doctor_id:
            assigned_result = await db.execute(select(Doctor).where(Doctor.id == patient.assigned_doctor_id))
            assigned = assigned_result.scalar_one_or_none()
            if assigned is not None:
                return PortalDoctorInfo(id=assigned.id, name=assigned.name, specialty=assigned.specialty, bio=assigned.bio, photo_url=assigned.photo_url)

        apt_result = await db.execute(
            select(Doctor)
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .where(Appointment.patient_id == patient.id, Appointment.doctor_id.isnot(None))
            .order_by(Appointment.start_time.desc())
            .limit(1)
        )
        doctor = apt_result.scalar_one_or_none()
        if doctor is None:
            plan_result = await db.execute(
                select(Doctor)
                .join(TreatmentPlan, TreatmentPlan.doctor_id == Doctor.id)
                .where(TreatmentPlan.patient_id == patient.id)
                .order_by(TreatmentPlan.created_at.desc())
                .limit(1)
            )
            doctor = plan_result.scalar_one_or_none()
        if doctor is None:
            return None
        return PortalDoctorInfo(id=doctor.id, name=doctor.name, specialty=doctor.specialty, bio=doctor.bio, photo_url=doctor.photo_url)

    async def _load_treatment_plans(self, db: AsyncSession, patient_id: UUID) -> list[PortalTreatmentPlan]:
        result = await db.execute(
            select(TreatmentPlan)
            .options(selectinload(TreatmentPlan.items).selectinload(TreatmentPlanItem.procedure))
            .where(TreatmentPlan.patient_id == patient_id)
            .order_by(TreatmentPlan.created_at.desc())
        )
        plans = []
        for plan in result.scalars().all():
            plans.append(
                PortalTreatmentPlan(
                    id=plan.id,
                    title=plan.title,
                    status=plan.status.value if hasattr(plan.status, "value") else str(plan.status),
                    items=[
                        PortalTreatmentPlanItem(
                            id=item.id,
                            procedure_name=item.procedure.name if item.procedure else "Procedure",
                            status=item.status.value if hasattr(item.status, "value") else str(item.status),
                            estimated_price=float(item.estimated_price) if item.estimated_price is not None else None,
                            actual_price=float(item.actual_price) if item.actual_price is not None else None,
                        )
                        for item in plan.items
                    ],
                    created_at=plan.created_at,
                )
            )
        return plans

    async def _load_related(
        self, db: AsyncSession, patient_id: UUID
    ) -> tuple[
        list[PortalAppointment],
        list[PortalConsentDocument],
        list[PortalInvoice],
        list[PortalPhoto],
        float,
    ]:
        apt_result = await db.execute(
            select(Appointment)
            .where(Appointment.patient_id == patient_id)
            .order_by(Appointment.start_time.asc())
        )
        consent_result = await db.execute(
            select(ConsentDocument)
            .where(ConsentDocument.patient_id == patient_id)
            .order_by(ConsentDocument.created_at.desc())
        )
        inv_result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.line_items))
            .where(Invoice.patient_id == patient_id)
            .order_by(Invoice.created_at.desc())
        )
        photo_result = await db.execute(
            select(PatientPhoto)
            .where(PatientPhoto.patient_id == patient_id)
            .order_by(PatientPhoto.created_at.desc())
        )

        appointments = [
            PortalAppointment(
                id=a.id,
                appointment_type=a.appointment_type,
                status=a.status.value if hasattr(a.status, "value") else str(a.status),
                start_time=a.start_time,
                end_time=a.end_time,
                notes=a.notes,
            )
            for a in apt_result.scalars().all()
        ]
        consents = [
            PortalConsentDocument(
                id=c.id,
                document_type=c.document_type,
                status=c.status.value if hasattr(c.status, "value") else str(c.status),
                signed_at=c.signed_at,
                signed_by_name=c.signed_by_name,
            )
            for c in consent_result.scalars().all()
        ]
        photos = [
            PortalPhoto(
                id=p.id,
                photo_type=p.photo_type,
                notes=p.notes,
                url=p.cloudinary_url,
                taken_at=p.created_at,
            )
            for p in photo_result.scalars().all()
        ]

        pending = 0.0
        invoices = []
        for i in inv_result.scalars().all():
            if i.status in (InvoiceStatus.PENDING, InvoiceStatus.OVERDUE):
                pending += float(i.total_amount)
            first_line = i.line_items[0].description if i.line_items else "Invoice"
            invoices.append(
                PortalInvoice(
                    id=i.id,
                    description=first_line,
                    total_amount=float(i.total_amount),
                    status=i.status.value if hasattr(i.status, "value") else str(i.status),
                    due_date=i.due_date,
                    created_at=i.created_at,
                )
            )
        return appointments, consents, invoices, photos, round(pending, 2)
