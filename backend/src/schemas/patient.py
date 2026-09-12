from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date


class CreatePatientRequest(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    additional_phones: list[dict] | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    chief_complaint: str | None = None
    needs_surgery: bool = False
    # Set by the frontend's classifyPatient() before the request is sent —
    # the backend stores whatever it's told rather than re-deriving it, since
    # the classification logic lives client-side (dashboard/patients/classifyPatient.ts).
    ai_agent_assigned: str | None = None
    source: str | None = None


# Shared by Update and the profile-depth section of Response — every field
# here is optional to fill in over time, not required at intake.
class PatientProfileFields(BaseModel):
    gender: str | None = None
    # A patient can have more than one reachable number — list of
    # {number, label} (e.g. {"number": "+1...", "label": "Home"}). The
    # primary `phone` field above/below stays the main one (used for portal
    # OTP delivery, WhatsApp receipts); this is the extras.
    additional_phones: list[dict] | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    allergies: list[dict] | None = None
    surgical_history: list[dict] | None = None
    current_medications: list[dict] | None = None
    smoking_status: str | None = None
    previous_cosmetic_procedures: list[dict] | None = None
    referral_source: str | None = None
    preferred_language: str | None = None
    communication_preferences: dict | None = None
    insurance_provider: str | None = None
    insurance_number: str | None = None


class UpdatePatientRequest(PatientProfileFields):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    chief_complaint: str | None = None
    needs_surgery: bool | None = None
    source: str | None = None


class UpdatePatientStageRequest(BaseModel):
    stage: str
    lost_reason: str | None = None


class AssignDoctorRequest(BaseModel):
    # None unassigns — Owner or Receptionist may call this (see
    # patients_router.py); a dedicated endpoint rather than folding into
    # UpdatePatientRequest so it gets its own audited action
    # ("assigned"/"reassigned"/"unassigned"), matching every other
    # clinically-meaningful change on this record.
    doctor_id: UUID | None = None


class ArchivePatientRequest(BaseModel):
    reason: str | None = None


class FunnelStageCount(BaseModel):
    stage: str
    count: int


class PatientAuditLogEntry(BaseModel):
    id: UUID
    action: str
    actor_name: str | None
    actor_type: str
    resource_type: str | None
    created_at: datetime


class PatientResponse(BaseModel):
    id: UUID
    practice_id: UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    additional_phones: list[dict] = []
    date_of_birth: date | None
    chief_complaint: str | None
    needs_surgery: bool
    consent_status: bool
    ai_agent_assigned: str | None
    agent_status: str
    lifecycle_stage: str
    lost_reason: str | None
    source: str | None
    # Derived from real Appointment rows (see patients_services.py's
    # _attach_appointment_flags) rather than a stored lifecycle status — lets
    # the frontend stop hardcoding every patient as a "lead". Default False
    # covers a freshly created patient with no appointments yet.
    has_upcoming_appointment: bool = False
    has_completed_appointment: bool = False
    # --- profile depth (Week 2) ---
    gender: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    allergies: list[dict] = []
    surgical_history: list[dict] = []
    current_medications: list[dict] = []
    smoking_status: str | None = None
    previous_cosmetic_procedures: list[dict] = []
    referral_source: str | None = None
    preferred_language: str | None = None
    communication_preferences: dict = {}
    insurance_provider: str | None = None
    insurance_number: str | None = None
    # --- AI workflows (Week 4) ---
    qualification: dict | None = None
    intake_summary: str | None = None
    portal_id: str | None = None
    portal_enabled: bool = False
    # --- Clinical ownership + lifecycle ---
    assigned_doctor_id: UUID | None = None
    # Attached as a transient attribute (see patients_services.py's
    # _attach_doctor_names), same pattern as has_upcoming_appointment — the
    # column only stores the id, not a live join, on every response.
    assigned_doctor_name: str | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
