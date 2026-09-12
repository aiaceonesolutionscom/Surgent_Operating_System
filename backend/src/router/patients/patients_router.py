from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user, require_role
from src.server.audit import audit_action
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
from src.controller.patients.patients_controllers import PatientsController

router = APIRouter(prefix="/patients", tags=["Patients"])
controller = PatientsController()


@router.post("", response_model=PatientResponse)
async def create_patient(
    data: CreatePatientRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_patient(db, user, data)


@router.get("", response_model=list[PatientResponse])
async def list_patients(
    include_archived: bool = Query(False),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # Role-based filtering (Doctor → only their assigned patients) happens
    # server-side inside the controller — never trusts a client-supplied
    # role or doctor_id.
    return await controller.list_patients(db, user, include_archived=include_archived)


# Must be declared before GET /{patient_id} — otherwise FastAPI tries to
# parse "funnel-summary" as a patient_id UUID and 422s before ever reaching
# this handler.
@router.get("/funnel-summary", response_model=list[FunnelStageCount])
async def funnel_summary(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.funnel_summary(db, user)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    user: User = Depends(audit_action("patient.view", "patient", id_param="patient_id")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_patient(db, user, patient_id)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    data: UpdatePatientRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_patient(db, user, patient_id, data)


@router.patch("/{patient_id}/stage", response_model=PatientResponse)
async def update_stage(
    patient_id: UUID,
    data: UpdatePatientStageRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_stage(db, user, patient_id, data)


@router.patch("/{patient_id}/assign-doctor", response_model=PatientResponse)
async def assign_doctor(
    patient_id: UUID,
    data: AssignDoctorRequest,
    user: User = Depends(require_role(UserRole.OWNER, UserRole.RECEPTIONIST)),
    db: AsyncSession = Depends(get_db),
):
    """Sets or changes a patient's assigned/primary doctor — the one durable
    doctor-patient link (distinct from the per-encounter doctor_id on
    Appointment/ConsultationNote/TreatmentPlan), and what a Doctor's own
    hard-restricted patient access is scoped against (see
    server/patient_access.py). Owner and Receptionist can both assign and
    reassign; Doctors never self-assign."""
    return await controller.assign_doctor(db, user, patient_id, data)


@router.post("/{patient_id}/archive", response_model=PatientResponse)
async def archive_patient(
    patient_id: UUID,
    data: ArchivePatientRequest,
    user: User = Depends(require_role(UserRole.OWNER, UserRole.RECEPTIONIST)),
    db: AsyncSession = Depends(get_db),
):
    """Owner + Receptionist (front-desk needs to be able to remove a
    duplicate/mistaken record without waiting on the Owner). Archiving
    hides the patient from the default list, disables portal login, and
    blocks new appointments (see AppointmentsService.create_appointment) —
    a real administrative status, not a soft/cosmetic flag. There is
    deliberately no hard-delete endpoint for patients — medical and
    financial records don't get casually destroyed."""
    return await controller.archive_patient(db, user, patient_id, data)


@router.post("/{patient_id}/restore", response_model=PatientResponse)
async def restore_patient(
    patient_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER, UserRole.RECEPTIONIST)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.restore_patient(db, user, patient_id)


@router.get("/{patient_id}/audit-log", response_model=list[PatientAuditLogEntry])
async def get_patient_audit_log(
    patient_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    """Owner-only Activity/Audit tab — who did what to this patient record
    and when, assembled across every resource type that touches this
    patient (see services/audit/patient_audit_service.py)."""
    return await controller.get_audit_log(db, user, patient_id)
