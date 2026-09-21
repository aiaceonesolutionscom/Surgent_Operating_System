from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User, UserRole
from src.schemas.patient import (
    CreatePatientRequest,
    UpdatePatientRequest,
    UpdatePatientStageRequest,
    AssignDoctorRequest,
    ArchivePatientRequest,
    PatientResponse,
    FunnelStageCount,
    PatientAuditLogEntry,
)
from src.server.exceptions import ForbiddenException
from src.server.patient_access import verify_doctor_access, resolve_doctor_id
from src.services.patients.patients_services import PatientsService
from src.services.audit.audit_log_service import AuditLogService
from src.services.audit.patient_audit_service import PatientAuditService

# Fields a Receptionist should never see or edit — clinical/medical detail
# that's Owner/Doctor territory (matches every other clinical surface in
# this app: consultation notes and photos are already Owner/Doctor-only via
# require_role; patients_router.py was the one domain that had never picked
# up that pattern). Front-desk-relevant fields (name/phone/DOB/emergency
# contact/insurance/chief_complaint/lead qualification) stay visible —
# Receptionist genuinely needs those to do check-in, billing, and follow-up.
_CLINICAL_FIELDS = (
    "allergies", "surgical_history", "current_medications",
    "smoking_status", "previous_cosmetic_procedures", "intake_summary",
)


class PatientsController:
    def __init__(self):
        self.service = PatientsService()
        self.audit = AuditLogService()
        self.patient_audit = PatientAuditService()

    def _redact_for_role(self, response: PatientResponse, user: User) -> PatientResponse:
        if user.role != UserRole.RECEPTIONIST:
            return response
        return response.model_copy(update={
            "allergies": [],
            "surgical_history": [],
            "current_medications": [],
            "smoking_status": None,
            "previous_cosmetic_procedures": [],
            "intake_summary": None,
        })

    async def create_patient(self, db: AsyncSession, user: User, data: CreatePatientRequest) -> PatientResponse:
        patient = await self.service.create_patient(db, user.practice_id, data)
        await self.audit.log(
            db, user.practice_id, "user", "patient.created", actor_user_id=user.id,
            resource_type="patient", resource_id=patient.id,
        )
        await db.commit()
        return PatientResponse.model_validate(patient)

    async def list_patients(self, db: AsyncSession, user: User, include_archived: bool = False) -> list[PatientResponse]:
        # A Doctor's list is scoped server-side to their own assigned
        # patients (the Doctor hard-restriction) — never trusts the client
        # to only ask for the right ones. Owner/Receptionist see the full
        # practice roster (Receptionist's per-field redaction still applies
        # below).
        doctor_id = await resolve_doctor_id(db, user)
        if user.role == UserRole.DOCTOR:
            include_archived = False  # a doctor has no "restore" action, no reason to see archived rows at all
        patients = await self.service.list_patients(db, user.practice_id, doctor_id=doctor_id, include_archived=include_archived)
        return [self._redact_for_role(PatientResponse.model_validate(p), user) for p in patients]

    async def get_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> PatientResponse:
        await verify_doctor_access(db, user, patient_id)
        patient = await self.service.get_patient(db, user.practice_id, patient_id)
        return self._redact_for_role(PatientResponse.model_validate(patient), user)

    async def update_patient(self, db: AsyncSession, user: User, patient_id: UUID, data: UpdatePatientRequest) -> PatientResponse:
        await verify_doctor_access(db, user, patient_id)
        if user.role == UserRole.RECEPTIONIST:
            attempted = data.model_dump(exclude_unset=True)
            blocked = [f for f in _CLINICAL_FIELDS if f in attempted]
            if blocked:
                raise ForbiddenException(f"Receptionist cannot edit clinical fields: {', '.join(blocked)}")
        patient = await self.service.update_patient(db, user.practice_id, patient_id, data)
        await self.audit.log(
            db, user.practice_id, "user", "patient.updated", actor_user_id=user.id,
            resource_type="patient", resource_id=patient.id,
        )
        await db.commit()
        return self._redact_for_role(PatientResponse.model_validate(patient), user)

    async def update_stage(self, db: AsyncSession, user: User, patient_id: UUID, data: UpdatePatientStageRequest) -> PatientResponse:
        await verify_doctor_access(db, user, patient_id)
        patient = await self.service.update_stage(db, user.practice_id, patient_id, data.stage, data.lost_reason)
        await self.audit.log(
            db, user.practice_id, "user", "patient.stage_changed", actor_user_id=user.id,
            resource_type="patient", resource_id=patient.id,
        )
        await db.commit()
        return PatientResponse.model_validate(patient)

    async def assign_doctor(self, db: AsyncSession, user: User, patient_id: UUID, data: AssignDoctorRequest) -> PatientResponse:
        # Doctor role never reaches this method (require_role gates the
        # route to Owner/Receptionist only — see patients_router.py) so no
        # verify_doctor_access call is needed here.
        patient = await self.service.assign_doctor(db, user.practice_id, patient_id, data.doctor_id)
        action = "patient.doctor_unassigned" if data.doctor_id is None else "patient.doctor_assigned"
        await self.audit.log(
            db, user.practice_id, "user", action, actor_user_id=user.id,
            resource_type="patient", resource_id=patient.id,
        )
        await db.commit()
        return PatientResponse.model_validate(patient)

    async def archive_patient(self, db: AsyncSession, user: User, patient_id: UUID, data: ArchivePatientRequest) -> PatientResponse:
        patient = await self.service.archive_patient(db, user.practice_id, patient_id, user.id)
        await self.audit.log(
            db, user.practice_id, "user", "patient.archived", actor_user_id=user.id,
            resource_type="patient", resource_id=patient.id,
        )
        await db.commit()
        return PatientResponse.model_validate(patient)

    async def delete_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> None:
        # Logged before the row is gone — resource_id on AuditLog isn't a
        # real FK to patients (same reasoning as every other
        # already-terminal audit entry here), but the Patient ORM object
        # itself gets expired by the DELETE flush below, so read patient_id
        # from the argument rather than the (about to be stale) object.
        await self.audit.log(
            db, user.practice_id, "user", "patient.deleted", actor_user_id=user.id,
            resource_type="patient", resource_id=patient_id,
        )
        await self.service.delete_patient(db, user.practice_id, patient_id)
        await db.commit()

    async def restore_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> PatientResponse:
        patient = await self.service.restore_patient(db, user.practice_id, patient_id)
        await self.audit.log(
            db, user.practice_id, "user", "patient.restored", actor_user_id=user.id,
            resource_type="patient", resource_id=patient.id,
        )
        await db.commit()
        return PatientResponse.model_validate(patient)

    async def funnel_summary(self, db: AsyncSession, user: User) -> list[FunnelStageCount]:
        return await self.service.funnel_summary(db, user.practice_id)

    async def get_audit_log(self, db: AsyncSession, user: User, patient_id: UUID) -> list[PatientAuditLogEntry]:
        entries = await self.patient_audit.list_for_patient(db, user.practice_id, patient_id)
        return [
            PatientAuditLogEntry(
                id=e.id, action=e.action, actor_type=e.actor_type,
                actor_name=e.actor_user.name if e.actor_user else None,
                resource_type=e.resource_type, created_at=e.created_at,
            )
            for e in entries
        ]
