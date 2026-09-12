from __future__ import annotations
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user, require_role
from src.models.user import User, UserRole
from src.schemas.doctor import (
    CreateDoctorRequest,
    UpdateDoctorRequest,
    UpdateMyDoctorRequest,
    DoctorResponse,
    CreateDoctorProcedureRequest,
    UpdateDoctorProcedureRequest,
    DoctorProcedureResponse,
    CreateDoctorAvailabilityRequest,
    DoctorAvailabilityResponse,
    DoctorTodayResponse,
    CreateDoctorTimeBlockRequest,
    DoctorTimeBlockResponse,
)
from src.schemas.availability import DoctorSlotsResponse
from src.controller.doctors.doctors_controllers import DoctorsController

router = APIRouter(prefix="/doctors", tags=["Doctors"])
controller = DoctorsController()


@router.post("", response_model=DoctorResponse)
async def create_doctor(
    data: CreateDoctorRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_doctor(db, user, data)


@router.get("", response_model=list[DoctorResponse])
async def list_doctors(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_doctors(db, user)


@router.get("/me", response_model=DoctorResponse)
async def get_my_doctor(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # Must be registered before /{doctor_id} — otherwise "me" is parsed as a
    # (rejected) UUID path param instead of matching this route.
    return await controller.get_my_doctor(db, user)


@router.get("/me/today", response_model=DoctorTodayResponse)
async def get_my_today(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # Also before /{doctor_id} — same ordering reason as /me above.
    return await controller.get_my_today(db, user)


@router.patch("/me", response_model=DoctorResponse)
async def update_my_doctor(
    data: UpdateMyDoctorRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    """A doctor updating their own recurring weekly schedule (working_hours
    only). Must stay before /{doctor_id} — otherwise "me" is parsed as a
    UUID path param."""
    return await controller.update_my_doctor(db, user, data)


@router.post("/me/time-blocks", response_model=DoctorTimeBlockResponse)
async def create_my_time_block(
    data: CreateDoctorTimeBlockRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    """A doctor's own private calendar note/block — no require_role beyond
    being an authenticated practice member, since the service resolves and
    writes only to the caller's own linked Doctor row (see
    DoctorTimeBlockService._resolve_doctor). Also before /{doctor_id}."""
    return await controller.create_my_time_block(db, user, data)


@router.get("/me/time-blocks", response_model=list[DoctorTimeBlockResponse])
async def list_my_time_blocks(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_my_time_blocks(db, user)


@router.delete("/me/time-blocks/{block_id}", status_code=204)
async def delete_my_time_block(
    block_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    await controller.delete_my_time_block(db, user, block_id)


@router.get("/me/slots", response_model=list[DoctorSlotsResponse])
async def get_my_slots(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    date: date = Query(description="Practice-local day to start from"),
    days: int = Query(default=7, ge=1, le=31),
    duration_minutes: int = Query(default=30, ge=15, le=240),
):
    """The caller's own bookable slots — weekly working_hours minus one-off
    availability overrides, each slot flagged when an existing appointment
    occupies it. Must stay before /{doctor_id} (same ordering rule as /me)."""
    return await controller.get_my_slots(db, user, date, days, duration_minutes)


@router.get("/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(
    doctor_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_doctor(db, user, doctor_id)


@router.patch("/{doctor_id}", response_model=DoctorResponse)
async def update_doctor(
    doctor_id: UUID,
    data: UpdateDoctorRequest,
    # Owner-only — a Doctor editing another Doctor's record (or toggling
    # is_active, which now also flips the linked User's login access, see
    # doctors_services.py) is exactly the kind of Owner-level control a
    # Doctor must never have.
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_doctor(db, user, doctor_id, data)


@router.post("/{doctor_id}/invite", response_model=DoctorResponse)
async def invite_doctor(
    doctor_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.invite_doctor(db, user, doctor_id)


# --- Doctor <-> Procedure (fees) — viewing is open to any active practice
# member, matching Doctor's own visibility; managing fees is Owner-only,
# same reasoning as update_doctor above. ---

@router.post("/{doctor_id}/procedures", response_model=DoctorProcedureResponse)
async def add_doctor_procedure(
    doctor_id: UUID,
    data: CreateDoctorProcedureRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.add_procedure(db, user, doctor_id, data)


@router.get("/{doctor_id}/procedures", response_model=list[DoctorProcedureResponse])
async def list_doctor_procedures(
    doctor_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_procedures(db, user, doctor_id)


@router.patch("/{doctor_id}/procedures/{link_id}", response_model=DoctorProcedureResponse)
async def update_doctor_procedure(
    doctor_id: UUID,
    link_id: UUID,
    data: UpdateDoctorProcedureRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_procedure(db, user, doctor_id, link_id, data)


@router.delete("/{doctor_id}/procedures/{link_id}", status_code=204)
async def remove_doctor_procedure(
    doctor_id: UUID,
    link_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    await controller.remove_procedure(db, user, doctor_id, link_id)


# --- Doctor availability overrides ---

@router.post("/{doctor_id}/availability", response_model=DoctorAvailabilityResponse)
async def add_doctor_availability(
    doctor_id: UUID,
    data: CreateDoctorAvailabilityRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.add_availability(db, user, doctor_id, data)


@router.get("/{doctor_id}/availability", response_model=list[DoctorAvailabilityResponse])
async def list_doctor_availability(
    doctor_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_availability(db, user, doctor_id)


@router.delete("/{doctor_id}/availability/{override_id}", status_code=204)
async def remove_doctor_availability(
    doctor_id: UUID,
    override_id: UUID,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    await controller.remove_availability(db, user, doctor_id, override_id)


@router.get("/{doctor_id}/slots", response_model=list[DoctorSlotsResponse])
async def get_doctor_slots(
    doctor_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    date: date = Query(description="Practice-local day to start from"),
    days: int = Query(default=7, ge=1, le=31),
    duration_minutes: int = Query(default=30, ge=15, le=240),
):
    """Any doctor's bookable slots — the staff/front-desk view of what time
    windows are actually open (working_hours, overrides, booked busy)."""
    return await controller.get_doctor_slots(db, user, doctor_id, date, days, duration_minutes)
