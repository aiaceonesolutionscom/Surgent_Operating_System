from __future__ import annotations
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.surgery import (
    CreateSurgeryRequest,
    UpdateSurgeryRequest,
    UpdateSurgeryClinicalRequest,
    CompleteSurgeryRequest,
    CancelSurgeryRequest,
    ConfirmSurgeryRequest,
    SurgeryAvailabilityCheckRequest,
    SurgeryAvailabilityCheckResponse,
    SurgeryOverviewResponse,
    SurgeryResponse,
)
from src.controller.surgery.surgery_controllers import SurgeryController

router = APIRouter(prefix="/surgeries", tags=["Surgery"])
controller = SurgeryController()

# Front-desk scheduling owns the booking surface: the Receptionist books,
# confirms, reschedules, and cancels; the Owner has the same power as backup.
_SCHEDULING_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)
# The Doctor owns the clinical side — pre-op ticks, starting the case, and the
# operative note at completion. Owner can do these too (practice-wide visibility).
_CLINICAL_ROLES = (UserRole.OWNER, UserRole.DOCTOR)
_CANCEL_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST, UserRole.DOCTOR)
# Listing/viewing is wide open to the three practice roles.
_READ_ROLES = (UserRole.OWNER, UserRole.DOCTOR, UserRole.RECEPTIONIST)


@router.post("", response_model=SurgeryResponse)
async def create_surgery(
    data: CreateSurgeryRequest,
    user: User = Depends(require_role(*_SCHEDULING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_surgery(db, user, data)


@router.get("", response_model=list[SurgeryResponse])
async def list_surgeries(
    patient_id: UUID | None = Query(default=None),
    scope: Literal["all", "mine"] | None = Query(default=None),
    user: User = Depends(require_role(*_READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    if patient_id is not None:
        return await controller.list_for_patient(db, user, patient_id)
    # A Doctor's "Meri Surgeries" dashboard — their own surgeries as surgeon.
    # Meaningless for Owner/Receptionist (no roster doctor row), so it is
    # only honored for the DOCTOR role.
    if scope == "mine" and user.role == UserRole.DOCTOR:
        return await controller.list_for_doctor(db, user)
    return await controller.list_for_practice(db, user)


# Static route BEFORE /{surgery_id} so FastAPI never tries to parse
# "overview" as a surgery UUID.
@router.get("/overview", response_model=SurgeryOverviewResponse)
async def surgery_overview(
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.overview(db, user)


@router.post("/availability-check", response_model=SurgeryAvailabilityCheckResponse)
async def check_surgery_availability(
    data: SurgeryAvailabilityCheckRequest,
    user: User = Depends(require_role(*_SCHEDULING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.check_surgery_availability(db, user, data)


@router.get("/{surgery_id}", response_model=SurgeryResponse)
async def get_surgery(
    surgery_id: UUID,
    user: User = Depends(require_role(*_READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_surgery(db, user, surgery_id)


@router.patch("/{surgery_id}", response_model=SurgeryResponse)
async def update_surgery(
    surgery_id: UUID,
    data: UpdateSurgeryRequest,
    user: User = Depends(require_role(*_SCHEDULING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_surgery(db, user, surgery_id, data)


# Clinical actions — the Doctor's side of the record, do NOT touch the
# scheduling surface (and vice versa: requirement #1's separation of who does
# what).
@router.patch("/{surgery_id}/clinical", response_model=SurgeryResponse)
async def update_surgery_clinical(
    surgery_id: UUID,
    data: UpdateSurgeryClinicalRequest,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_surgery_clinical(db, user, surgery_id, data)


@router.post("/{surgery_id}/confirm", response_model=SurgeryResponse)
async def confirm_surgery(
    surgery_id: UUID,
    data: ConfirmSurgeryRequest,
    user: User = Depends(require_role(*_SCHEDULING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.confirm_surgery(db, user, surgery_id, data)


@router.post("/{surgery_id}/start", response_model=SurgeryResponse)
async def start_surgery(
    surgery_id: UUID,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.start_surgery(db, user, surgery_id)


@router.post("/{surgery_id}/complete", response_model=SurgeryResponse)
async def complete_surgery(
    surgery_id: UUID,
    data: CompleteSurgeryRequest,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.complete_surgery(db, user, surgery_id, data)


@router.post("/{surgery_id}/cancel", response_model=SurgeryResponse)
async def cancel_surgery(
    surgery_id: UUID,
    data: CancelSurgeryRequest,
    user: User = Depends(require_role(*_CANCEL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.cancel_surgery(db, user, surgery_id, data)