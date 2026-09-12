from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date


class PortalAppointment(BaseModel):
    id: UUID
    appointment_type: str
    status: str
    start_time: datetime
    end_time: datetime
    notes: str | None


class PortalConsentDocument(BaseModel):
    id: UUID
    document_type: str
    status: str
    signed_at: datetime | None
    signed_by_name: str | None


class PortalInvoice(BaseModel):
    id: UUID
    description: str
    total_amount: float
    status: str
    due_date: date | None
    created_at: datetime


class PortalPhoto(BaseModel):
    id: UUID
    photo_type: str | None
    notes: str | None
    url: str
    taken_at: datetime


class PortalDoctorInfo(BaseModel):
    id: UUID
    name: str
    specialty: str | None
    bio: str | None
    photo_url: str | None


class PortalTreatmentPlanItem(BaseModel):
    id: UUID
    procedure_name: str
    status: str
    estimated_price: float | None
    actual_price: float | None


class PortalTreatmentPlan(BaseModel):
    id: UUID
    title: str
    status: str
    items: list[PortalTreatmentPlanItem]
    created_at: datetime


class PortalMessage(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class SendPortalMessageRequest(BaseModel):
    content: str


class UpdateMyProfileRequest(BaseModel):
    # Deliberately no `phone` here — the primary number is what portal OTP
    # login is keyed on (see patient_portal_auth_service.py's
    # _find_patients_by_phone) and what staff already has on file; a
    # patient can add more numbers but not silently change the one their
    # own login depends on. See PatientsController for the staff-side
    # equivalent that CAN change it.
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    additional_phones: list[dict] | None = None


class PortalBookingRequest(BaseModel):
    appointment_type: str
    start_time: datetime
    end_time: datetime
    notes: str | None = None


class PatientIntakeRequest(BaseModel):
    allergies: list[dict] = []
    surgical_history: list[dict] = []
    current_medications: list[dict] = []
    smoking_status: str | None = None
    previous_cosmetic_procedures: list[dict] = []
    # Freeform context for the AI summary only — not stored as a structured
    # field on Patient, just fed into the doctor-facing summary generation.
    additional_notes: str | None = None


class PortalPatientResponse(BaseModel):
    id: UUID
    portal_id: str | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    additional_phones: list[dict] = []
    chief_complaint: str | None
    consent_status: bool
    doctor: PortalDoctorInfo | None
    appointments: list[PortalAppointment]
    consent_documents: list[PortalConsentDocument]
    invoices: list[PortalInvoice]
    photos: list[PortalPhoto] = []
    treatment_plans: list[PortalTreatmentPlan] = []
    invoice_total_pending: float = 0.0
    # AI Patient Intake (Week 4) — intake_completed gates whether the portal
    # shows the intake form or the doctor-facing summary it produced.
    intake_completed: bool = False
    intake_summary: str | None = None
    # True once the patient has set their own login PIN (see
    # patient_portal_auth_service.py.set_pin).
    pin_set: bool = False


# --- Owner/staff-side portal management ---

class PortalAccessResponse(BaseModel):
    portal_id: str | None
    enabled: bool
    # Staff-visible clinic one-time login PIN (phone + this PIN logs the
    # patient in — no OTP), with its expiry. Staff hand it to the patient if
    # the WhatsApp/email invite never arrived. Single-use.
    pin: str | None = None
    pin_expires_at: datetime | None = None
    # True once the patient has set their own permanent PIN.
    pin_set: bool = False


class PortalEnabledResponse(BaseModel):
    """Returned after enabling portal access — portal_id is a reference
    identifier only (see PatientPortalAuthService's own docstring on why
    it no longer participates in login); invite_sent tells staff whether
    the "portal is ready" message actually went out or needs a manual
    resend (patient has no phone/email on file, or delivery failed)."""
    portal_id: str
    invite_sent: bool
    pin: str | None = None
    pin_expires_at: datetime | None = None


# --- Patient-side login (phone + one-time code) ---

class RequestOtpRequest(BaseModel):
    phone: str


class RequestOtpResponse(BaseModel):
    found: bool
    delivered_via: str | None = None


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str


class PinLoginRequest(BaseModel):
    """Primary patient login path — phone + the patient's own PIN. No OTP is
    sent for PIN logins, so it costs nothing (quite the point of switching
    from a code-on-every-login scheme)."""
    phone: str
    pin: str


class SetPinRequest(BaseModel):
    """First-time setup (patient already authenticated via a login code) or a
    PIN change — `current_pin` is required when a PIN already exists."""
    pin: str
    current_pin: str | None = None


class PatientPortalLoginResponse(BaseModel):
    access_token: str
    expires_in_minutes: int
    # True when this patient still has no PIN set and the portal must show the
    # "set your PIN" screen (called at the end of the one-time OTP setup
    # flow) before treating the session as fully ready.
    requires_pin_setup: bool = False


class RescheduleAppointmentRequest(BaseModel):
    """Patient self-service reschedule — a new window for an existing
    appointment. Kept deliberately free-form (no slot-lock) so a patient who
    can't see open slots can still request one, matching the existing
    PortalBookingRequest shape."""

    start_time: datetime
    end_time: datetime


class AppointmentActionResponse(BaseModel):
    """Returned after a patient cancels or reschedules an appointment — the
    updated appointment plus a friendly status to show in the UI."""

    id: UUID
    appointment_type: str
    status: str
    start_time: datetime
    end_time: datetime
