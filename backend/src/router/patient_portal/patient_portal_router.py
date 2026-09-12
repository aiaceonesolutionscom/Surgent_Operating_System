from __future__ import annotations
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user, get_current_portal_patient
from src.models.user import User
from src.models.patient import Patient
from src.schemas.patient_portal import (
    PortalAccessResponse,
    PortalEnabledResponse,
    PortalPatientResponse,
    PortalBookingRequest,
    RequestOtpRequest,
    RequestOtpResponse,
    VerifyOtpRequest,
    PatientPortalLoginResponse,
    PinLoginRequest,
    SetPinRequest,
    PatientIntakeRequest,
    PortalMessage,
    PortalAppointment,
    PortalTreatmentPlan,
    SendPortalMessageRequest,
    UpdateMyProfileRequest,
    RescheduleAppointmentRequest,
    AppointmentActionResponse,
)
from src.schemas.availability import DoctorSlotsResponse
from src.schemas.recovery import SubmitCheckInRequest, RecoveryCheckInResponse, RecoveryJournalResponse
from src.controller.patient_portal.patient_portal_controllers import PatientPortalController
from src.controller.recovery.recovery_controllers import RecoveryController

router = APIRouter(prefix="/patient-portal", tags=["Patient Portal"])
controller = PatientPortalController()
recovery_controller = RecoveryController()


# Three distinct auth surfaces on one router:
#
#  - /patient-portal/patients/{id}/*     → practice-member only (staff turns
#    portal access on/off and can resend the "portal is ready" invite —
#    never handles a patient credential directly).
#  - /patient-portal/request-otp,verify  → PUBLIC. Phone number in, a
#    one-time code out over WhatsApp/email; the code back in for a
#    short-lived JWT scoped to that one patient (see
#    patient_portal_auth_service.py) — rate-limited against brute-forcing
#    and phone enumeration.
#  - /patient-portal/me*                 → requires that JWT
#    (get_current_portal_patient), not Clerk and not a raw token-in-URL.


@router.post("/patients/{patient_id}/enable", response_model=PortalEnabledResponse)
async def enable_portal(
    patient_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    """Turns portal access on and sends a "your portal is ready" invite
    over WhatsApp/email carrying the freshly issued one-time PIN — that PIN
    is also returned so staff can hand it over in person if the message
    never lands."""
    return await controller.enable_portal(db, user, patient_id)


@router.post("/patients/{patient_id}/pin", response_model=PortalAccessResponse)
async def generate_pin(
    patient_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    """(Re)issues the staff-visible one-time login PIN for an already
    enabled patient — the "Generate new PIN" action in the staff panel."""
    return await controller.generate_pin(db, user, patient_id)


@router.post("/patients/{patient_id}/resend-invite", response_model=PortalAccessResponse)
async def resend_invite(
    patient_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.resend_invite(db, user, patient_id)


@router.post("/patients/{patient_id}/disable", response_model=PortalAccessResponse)
async def disable_portal(
    patient_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.disable_portal(db, user, patient_id)


@router.get("/patients/{patient_id}/access", response_model=PortalAccessResponse)
async def get_access_state(
    patient_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_access_state(db, user, patient_id)


@router.post("/request-otp", response_model=RequestOtpResponse)
async def request_otp(
    data: RequestOtpRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate-limit key mixes the client IP and the phone being attempted —
    # slows both OTP-spam against one number and phone enumeration across
    # numbers.
    ip = request.client.host if request.client else None
    client_key = f"{ip or 'unknown'}:{data.phone}"
    return await controller.request_otp(db, data, client_key, ip)


@router.post("/verify-otp", response_model=PatientPortalLoginResponse)
async def verify_otp(
    data: VerifyOtpRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    client_key = f"{ip or 'unknown'}:{data.phone}"
    return await controller.verify_otp(db, data, client_key, ip)


@router.post("/patient-login", response_model=PatientPortalLoginResponse)
async def patient_login(
    data: PinLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # The cheap, OTP-free daily login — phone + the patient's own PIN (set
    # during first-time setup after a one-time code). Same rate-limit shape
    # as verify-otp (IP + phone) so a stolen/guessed PIN still can't be
    # brute-forced across the network.
    ip = request.client.host if request.client else None
    client_key = f"{ip or 'unknown'}:{data.phone}"
    return await controller.login_with_pin(db, data, client_key, ip)


@router.post("/me/pin", response_model=PortalPatientResponse)
async def set_my_pin(
    data: SetPinRequest,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    """First-time PIN setup (after a one-time-code login flagged
    requires_pin_setup) or a PIN change (requires `current_pin`)."""
    return await controller.set_pin(db, patient, data)


@router.get("/me", response_model=PortalPatientResponse)
async def get_my_data(
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_my_data(db, patient)


@router.post("/me/appointments", response_model=PortalPatientResponse)
async def book_appointment(
    data: PortalBookingRequest,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.book_appointment(db, patient, data)


@router.post("/me/intake", response_model=PortalPatientResponse)
async def submit_intake(
    data: PatientIntakeRequest,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    """One-time structured pre-consultation intake (allergies/surgical
    history/medications/smoking) — writes onto the patient's real profile
    fields and generates a doctor-facing AI summary flagging anything
    clinically relevant. Re-submitting overwrites the previous summary."""
    return await controller.submit_intake(db, patient, data)


@router.get("/me/messages", response_model=list[PortalMessage])
async def get_my_messages(
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_messages(db, patient)


@router.post("/me/messages", response_model=PortalMessage)
async def send_my_message(
    data: SendPortalMessageRequest,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.send_message(db, patient, data)


@router.patch("/me/profile", response_model=PortalPatientResponse)
async def update_my_profile(
    data: UpdateMyProfileRequest,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    """Patient self-service edit — name, email, and additional phone
    numbers only. The primary phone (portal login identity, staff's
    on-file number) is deliberately not editable here."""
    return await controller.update_my_profile(db, patient, data)


@router.get("/me/recovery", response_model=RecoveryJournalResponse | None)
async def get_my_recovery(
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await recovery_controller.get_journal_for_portal_patient(db, patient)


@router.post("/me/recovery/checkin", response_model=RecoveryCheckInResponse)
async def submit_my_recovery_checkin(
    data: SubmitCheckInRequest,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await recovery_controller.submit_checkin_from_portal(db, patient, data)


# --- Patient self-service beyond the flat /me bundle: a filtered appointment
# list, cancel/reschedule on their own appointments, a focused treatment-plan
# view, and their own doctor's open slots for picking a new time. ---

@router.get("/me/appointments", response_model=list[PortalAppointment])
async def get_my_appointments(
    scope: str = Query(default="upcoming", pattern="^(upcoming|past)$"),
    status: str | None = Query(default=None),
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_my_appointments(db, patient, scope, status)


@router.patch("/me/appointments/{appointment_id}/cancel", response_model=AppointmentActionResponse)
async def cancel_my_appointment(
    appointment_id: UUID,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.cancel_my_appointment(db, patient, appointment_id)


@router.patch("/me/appointments/{appointment_id}/reschedule", response_model=AppointmentActionResponse)
async def reschedule_my_appointment(
    appointment_id: UUID,
    data: RescheduleAppointmentRequest,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.reschedule_my_appointment(db, patient, appointment_id, data)


@router.get("/me/treatment-plans/{treatment_plan_id}", response_model=PortalTreatmentPlan)
async def get_my_treatment_plan(
    treatment_plan_id: UUID,
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_my_treatment_plan(db, patient, treatment_plan_id)


@router.get("/me/doctor-slots", response_model=list[DoctorSlotsResponse])
async def get_my_doctor_slots(
    patient: Patient = Depends(get_current_portal_patient),
    db: AsyncSession = Depends(get_db),
    date: date = Query(description="Practice-local day to start from"),
    days: int = Query(default=7, ge=1, le=31),
    duration_minutes: int = Query(default=30, ge=15, le=240),
):
    """The assigned doctor's open slots — powers a patient-side slot picker
    instead of the current blind POST /me/appointments with a raw time."""
    return await controller.get_my_doctor_slots(db, patient, date, days, duration_minutes)
