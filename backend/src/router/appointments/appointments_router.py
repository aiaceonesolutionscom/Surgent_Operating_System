from __future__ import annotations
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user
from src.server.audit import audit_action
from src.models.user import User
from src.schemas.appointment import (
    AppointmentResponse,
    CreateAppointmentRequest,
    RescheduleAppointmentRequest,
    CancelAppointmentRequest,
)
from src.controller.appointments.appointments_controllers import AppointmentsController

router = APIRouter(prefix="/appointments", tags=["Appointments"])
controller = AppointmentsController()


@router.get("", response_model=list[AppointmentResponse])
async def list_appointments(
    doctor_id: str = Query(default="me"),
    scope: str = Query(default="me"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    patient_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # scope=practice — every doctor's appointments (Owner/Receptionist front
    # desk view). Default stays "me" (the caller's own linked Doctor row) to
    # not change the Doctor Dashboard's existing behavior.
    if scope == "practice":
        return await controller.list_practice_appointments(db, user, start, end, patient_id)
    return await controller.list_my_appointments(db, user, patient_id)


@router.post("", response_model=AppointmentResponse)
async def create_appointment(
    data: CreateAppointmentRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_appointment(db, user, data)


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appointment_id: UUID,
    data: RescheduleAppointmentRequest,
    user: User = Depends(audit_action("appointment.reschedule", "appointment", id_param="appointment_id")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.reschedule_appointment(db, user, appointment_id, data)


@router.patch("/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: UUID,
    data: CancelAppointmentRequest,
    user: User = Depends(audit_action("appointment.cancel", "appointment", id_param="appointment_id")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.cancel_appointment(db, user, appointment_id, data)


@router.patch("/{appointment_id}/check-in", response_model=AppointmentResponse)
async def check_in_appointment(
    appointment_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.check_in_appointment(db, user, appointment_id)


@router.patch("/{appointment_id}/complete", response_model=AppointmentResponse)
async def complete_appointment(
    appointment_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.complete_appointment(db, user, appointment_id)


@router.patch("/{appointment_id}/start-with-doctor", response_model=AppointmentResponse)
async def start_with_doctor(
    appointment_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.start_with_doctor(db, user, appointment_id)


@router.patch("/{appointment_id}/ready-for-checkout", response_model=AppointmentResponse)
async def ready_for_checkout(
    appointment_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.mark_ready_for_checkout(db, user, appointment_id)


@router.patch("/{appointment_id}/no-show", response_model=AppointmentResponse)
async def mark_no_show(
    appointment_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.mark_no_show(db, user, appointment_id)
