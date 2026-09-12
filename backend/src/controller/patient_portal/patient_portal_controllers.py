from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
    SendPortalMessageRequest,
    UpdateMyProfileRequest,
    RescheduleAppointmentRequest,
    AppointmentActionResponse,
)
from src.schemas.availability import DoctorSlotsResponse
from src.services.patient_portal.patient_portal_services import PatientPortalService
from src.services.patient_portal.patient_portal_auth_service import PatientPortalAuthService
from src.services.patient_portal.patient_intake_service import PatientIntakeService
from src.services.availability.availability_services import AvailabilitySlotService
from src.server.exceptions import AppException
from src.config import get_settings

settings = get_settings()


class PatientPortalController:
    def __init__(self):
        self.service = PatientPortalService()
        self.auth = PatientPortalAuthService()
        self.intake = PatientIntakeService()
        self.slots = AvailabilitySlotService()

    # --- Owner/staff-side management ---

    async def enable_portal(self, db: AsyncSession, user: User, patient_id: UUID) -> PortalEnabledResponse:
        portal_id, invite_sent, temp_pin, pin_expires_at = await self.auth.enable_portal(db, user.practice_id, patient_id)
        return PortalEnabledResponse(
            portal_id=portal_id,
            invite_sent=invite_sent,
            pin=temp_pin,
            pin_expires_at=pin_expires_at,
        )

    async def generate_pin(self, db: AsyncSession, user: User, patient_id: UUID) -> PortalAccessResponse:
        await self.auth.generate_portal_pin(db, user.practice_id, patient_id)
        return await self.get_access_state(db, user, patient_id)

    async def resend_invite(self, db: AsyncSession, user: User, patient_id: UUID) -> PortalAccessResponse:
        await self.auth.resend_invite(db, user.practice_id, patient_id)
        return await self.get_access_state(db, user, patient_id)

    async def disable_portal(self, db: AsyncSession, user: User, patient_id: UUID) -> PortalAccessResponse:
        await self.auth.disable_portal(db, user.practice_id, patient_id)
        return await self.get_access_state(db, user, patient_id)

    async def get_access_state(self, db: AsyncSession, user: User, patient_id: UUID) -> PortalAccessResponse:
        portal_id, enabled, temp_pin, pin_expires_at, pin_set = await self.auth.get_portal_state(db, user.practice_id, patient_id)
        return PortalAccessResponse(
            portal_id=portal_id,
            enabled=enabled,
            pin=temp_pin,
            pin_expires_at=pin_expires_at,
            pin_set=pin_set,
        )

    # --- Patient-side login ---

    async def request_otp(self, db: AsyncSession, data: RequestOtpRequest, client_key: str, ip_address: str | None = None) -> RequestOtpResponse:
        result = await self.auth.request_otp(db, data.phone, client_key, ip_address)
        return RequestOtpResponse(**result)

    async def verify_otp(self, db: AsyncSession, data: VerifyOtpRequest, client_key: str, ip_address: str | None = None) -> PatientPortalLoginResponse:
        token, _patient, requires_pin_setup = await self.auth.verify_otp(db, data.phone, data.code, client_key, ip_address)
        return PatientPortalLoginResponse(
            access_token=token,
            expires_in_minutes=settings.patient_portal_jwt_expires_minutes,
            requires_pin_setup=requires_pin_setup,
        )

    async def login_with_pin(self, db: AsyncSession, data: PinLoginRequest, client_key: str, ip_address: str | None = None) -> PatientPortalLoginResponse:
        token, _patient, requires_pin_setup = await self.auth.login_with_pin(db, data.phone, data.pin, client_key, ip_address)
        return PatientPortalLoginResponse(
            access_token=token,
            expires_in_minutes=settings.patient_portal_jwt_expires_minutes,
            requires_pin_setup=requires_pin_setup,
        )

    async def set_pin(self, db: AsyncSession, patient: Patient, data: SetPinRequest) -> PortalPatientResponse:
        await self.auth.set_pin(db, patient, data.pin, data.current_pin)
        return await self.service.get_my_portal_data(db, patient)

    # --- Patient-side data ---

    async def get_my_data(self, db: AsyncSession, patient: Patient) -> PortalPatientResponse:
        return await self.service.get_my_portal_data(db, patient)

    async def book_appointment(self, db: AsyncSession, patient: Patient, data: PortalBookingRequest) -> PortalPatientResponse:
        await self.service.book_appointment(db, patient, data)
        return await self.service.get_my_portal_data(db, patient)

    async def submit_intake(self, db: AsyncSession, patient: Patient, data: PatientIntakeRequest) -> PortalPatientResponse:
        await self.intake.submit_intake(db, patient, data)
        return await self.service.get_my_portal_data(db, patient)

    async def get_messages(self, db: AsyncSession, patient: Patient) -> list[PortalMessage]:
        return await self.service.get_messages(db, patient)

    async def send_message(self, db: AsyncSession, patient: Patient, data: SendPortalMessageRequest) -> PortalMessage:
        return await self.service.send_message(db, patient, data.content)

    async def update_my_profile(self, db: AsyncSession, patient: Patient, data: UpdateMyProfileRequest) -> PortalPatientResponse:
        updated = await self.service.update_my_profile(db, patient, data)
        return await self.service.get_my_portal_data(db, updated)

    # --- Patient self-service: appointment list/cancel/reschedule,
    # treatment-plan detail, and a view of their own doctor's open slots. ---

    async def get_my_appointments(
        self,
        db: AsyncSession,
        patient: Patient,
        scope: str,
        status: str | None,
    ):
        return await self.service.get_my_appointments(db, patient, scope, status)

    async def cancel_my_appointment(self, db: AsyncSession, patient: Patient, appointment_id: UUID) -> AppointmentActionResponse:
        appointment = await self.service.cancel_my_appointment(db, patient, appointment_id)
        return AppointmentActionResponse(
            id=appointment.id,
            appointment_type=appointment.appointment_type,
            status=appointment.status.value if hasattr(appointment.status, "value") else str(appointment.status),
            start_time=appointment.start_time,
            end_time=appointment.end_time,
        )

    async def reschedule_my_appointment(
        self,
        db: AsyncSession,
        patient: Patient,
        appointment_id: UUID,
        data: RescheduleAppointmentRequest,
    ) -> AppointmentActionResponse:
        appointment = await self.service.reschedule_my_appointment(db, patient, appointment_id, data)
        return AppointmentActionResponse(
            id=appointment.id,
            appointment_type=appointment.appointment_type,
            status=appointment.status.value if hasattr(appointment.status, "value") else str(appointment.status),
            start_time=appointment.start_time,
            end_time=appointment.end_time,
        )

    async def get_my_treatment_plan(self, db: AsyncSession, patient: Patient, treatment_plan_id: UUID):
        return await self.service.get_my_treatment_plan(db, patient, treatment_plan_id)

    async def get_my_doctor_slots(
        self,
        db: AsyncSession,
        patient: Patient,
        date,
        days: int,
        duration_minutes: int,
    ) -> list[DoctorSlotsResponse]:
        if not patient.assigned_doctor_id:
            raise AppException("You don't have a doctor assigned yet — please contact the clinic.")
        return await self.slots.get_slots(
            db, patient.practice_id, patient.assigned_doctor_id, date, days, duration_minutes
        )
