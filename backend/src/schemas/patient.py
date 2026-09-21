from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date


# Shared by Create, Update and the profile-depth section of Response — every
# field here is optional to fill in over time, not required at intake, but a
# front-desk walk-in intake CAN set all of them in one go at creation time
# too (see CreatePatientRequest below).
class PatientProfileFields(BaseModel):
    gender: str | None = None
    # A patient can have more than one reachable number — list of
    # {number, label} (e.g. {"number": "+1...", "label": "WhatsApp"}). The
    # primary `phone` field above/below stays the main one (used for portal
    # OTP delivery, WhatsApp receipts); this is the extras.
    additional_phones: list[dict] | None = None
    father_name: str | None = None
    # "not_applicable" | "pregnant" | "nursing" | "not_pregnant_or_nursing" |
    # "declined_to_answer" — see models/patient.py's PregnancyStatus. Only
    # meaningful when gender is female; the frontend hides the question
    # otherwise, matching the AI receptionist's own conversational rule.
    pregnancy_status: str | None = None
    occupation: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None
    regular_physician_name: str | None = None
    regular_physician_phone: str | None = None
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


class CreatePatientRequest(PatientProfileFields):
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    chief_complaint: str | None = None
    needs_surgery: bool = False
    # Set by the frontend's classifyPatient() before the request is sent —
    # the backend stores whatever it's told rather than re-deriving it, since
    # the classification logic lives client-side (dashboard/patients/classifyPatient.ts).
    ai_agent_assigned: str | None = None
    source: str | None = None
    # Front desk can assign the doctor right at walk-in intake instead of a
    # separate follow-up call to /assign-doctor — same validation either way
    # (see PatientsService.create_patient).
    assigned_doctor_id: UUID | None = None
    # "whatsapp" — front desk confirming the walk-in patient's number IS a
    # WhatsApp number. MessagingService.resolve_channel has no stored
    # preference on Patient itself; it infers the channel from the most
    # recent Conversation row instead, so this seeds one (see
    # PatientsService.create_patient) purely so the very first automated
    # send (a visit document, a confirmation) goes out over WhatsApp instead
    # of falling back to SMS for a patient with no message history yet.
    preferred_channel: str | None = None


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
    # Actual timestamps behind the two booleans above — soonest non-cancelled
    # future appointment, and most recent COMPLETED one. None when the
    # matching flag is False.
    next_appointment_at: datetime | None = None
    last_appointment_at: datetime | None = None
    # --- profile depth (Week 2) ---
    gender: str | None = None
    father_name: str | None = None
    pregnancy_status: str | None = None
    occupation: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None
    regular_physician_name: str | None = None
    regular_physician_phone: str | None = None
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
