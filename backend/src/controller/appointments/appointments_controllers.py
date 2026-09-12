from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.appointment import (
    AppointmentResponse,
    CreateAppointmentRequest,
    RescheduleAppointmentRequest,
    CancelAppointmentRequest,
)
from src.services.appointments.appointments_services import AppointmentsService
from src.services.agent_log.agent_log_service import AgentLogService


class AppointmentsController:
    def __init__(self):
        self.service = AppointmentsService()
        self.agent_log = AgentLogService()

    async def list_my_appointments(
        self, db: AsyncSession, user: User, patient_id: UUID | None = None
    ) -> list[AppointmentResponse]:
        appointments = await self.service.list_for_doctor_user(db, user.practice_id, user.id, patient_id)
        return [AppointmentResponse.model_validate(a) for a in appointments]

    async def list_practice_appointments(
        self,
        db: AsyncSession,
        user: User,
        start: datetime | None,
        end: datetime | None,
        patient_id: UUID | None = None,
    ) -> list[AppointmentResponse]:
        appointments = await self.service.list_for_practice(db, user.practice_id, start, end, patient_id)
        return [AppointmentResponse.model_validate(a) for a in appointments]

    async def create_appointment(self, db: AsyncSession, user: User, data: CreateAppointmentRequest) -> AppointmentResponse:
        appointment = await self.service.create_appointment(
            db,
            user.practice_id,
            data.patient_id,
            data.doctor_id,
            data.appointment_type,
            data.start_time,
            data.end_time,
            data.notes,
        )
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="appointment_booking",
            action="appointment_booked",
            details={"appointment_id": str(appointment.id), "patient_id": str(appointment.patient_id)},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)

    async def reschedule_appointment(
        self, db: AsyncSession, user: User, appointment_id: UUID, data: RescheduleAppointmentRequest
    ) -> AppointmentResponse:
        appointment = await self.service.reschedule_appointment(
            db, user.practice_id, appointment_id, data.start_time, data.end_time
        )
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="reschedule_cancellation",
            action="appointment_rescheduled",
            details={"appointment_id": str(appointment.id)},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)

    async def cancel_appointment(
        self, db: AsyncSession, user: User, appointment_id: UUID, data: CancelAppointmentRequest
    ) -> AppointmentResponse:
        appointment = await self.service.cancel_appointment(db, user.practice_id, appointment_id, data.reason)
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="reschedule_cancellation",
            action="appointment_cancelled",
            details={"appointment_id": str(appointment.id), "reason": data.reason},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)

    async def check_in_appointment(self, db: AsyncSession, user: User, appointment_id: UUID) -> AppointmentResponse:
        appointment = await self.service.check_in_appointment(db, user.practice_id, appointment_id)
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="front_desk",
            action="appointment_checked_in",
            details={"appointment_id": str(appointment.id)},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)

    async def complete_appointment(self, db: AsyncSession, user: User, appointment_id: UUID) -> AppointmentResponse:
        appointment = await self.service.complete_appointment(db, user.practice_id, appointment_id)
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="appointment_booking",
            action="appointment_completed",
            details={"appointment_id": str(appointment.id)},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)

    async def start_with_doctor(self, db: AsyncSession, user: User, appointment_id: UUID) -> AppointmentResponse:
        appointment = await self.service.start_with_doctor(db, user.practice_id, appointment_id)
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="front_desk",
            action="appointment_with_doctor",
            details={"appointment_id": str(appointment.id)},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)

    async def mark_ready_for_checkout(self, db: AsyncSession, user: User, appointment_id: UUID) -> AppointmentResponse:
        appointment = await self.service.mark_ready_for_checkout(db, user.practice_id, appointment_id)
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="front_desk",
            action="appointment_ready_for_checkout",
            details={"appointment_id": str(appointment.id)},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)

    async def mark_no_show(self, db: AsyncSession, user: User, appointment_id: UUID) -> AppointmentResponse:
        appointment = await self.service.mark_no_show(db, user.practice_id, appointment_id)
        await self.agent_log.log(
            db,
            user.practice_id,
            agent_type="front_desk",
            action="appointment_no_show",
            details={"appointment_id": str(appointment.id)},
            performed_by=str(user.id),
        )
        return AppointmentResponse.model_validate(appointment)
