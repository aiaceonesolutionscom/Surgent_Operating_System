from __future__ import annotations
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.session_visit import (
    SessionVisitResponse, ScheduleSessionRequest, CompleteSessionRequest,
    UpdateSessionChecklistRequest, CancelSessionRequest,
)
from src.controller.session_visits.session_visits_controllers import SessionVisitsController

router = APIRouter(prefix="/session-visits", tags=["Session Visits"])
controller = SessionVisitsController()

# Same role split as surgery_router.py: front desk books/confirms, the
# Doctor owns the clinical side (checklist/start/complete), everyone
# involved can cancel, read is open to all three.
_SCHEDULING_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)
_CLINICAL_ROLES = (UserRole.OWNER, UserRole.DOCTOR)
_CANCEL_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST, UserRole.DOCTOR)
_READ_ROLES = (UserRole.OWNER, UserRole.DOCTOR, UserRole.RECEPTIONIST)


@router.get("", response_model=list[SessionVisitResponse])
async def list_sessions(
    treatment_plan_item_id: UUID | None = Query(default=None),
    patient_id: UUID | None = Query(default=None),
    scope: Literal["mine"] | None = Query(default=None),
    user: User = Depends(require_role(*_READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    if treatment_plan_item_id is not None:
        return await controller.list_for_item(db, user, treatment_plan_item_id)
    if patient_id is not None:
        return await controller.list_for_patient(db, user, patient_id)
    if scope == "mine":
        return await controller.list_mine(db, user)
    return []


@router.get("/{session_id}", response_model=SessionVisitResponse)
async def get_session(
    session_id: UUID,
    user: User = Depends(require_role(*_READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_session(db, user, session_id)


@router.post("/{session_id}/schedule", response_model=SessionVisitResponse)
async def schedule_session(
    session_id: UUID,
    data: ScheduleSessionRequest,
    user: User = Depends(require_role(*_SCHEDULING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.schedule(db, user, session_id, data)


@router.post("/{session_id}/confirm", response_model=SessionVisitResponse)
async def confirm_session(
    session_id: UUID,
    user: User = Depends(require_role(*_SCHEDULING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.confirm(db, user, session_id)


@router.post("/{session_id}/start", response_model=SessionVisitResponse)
async def start_session(
    session_id: UUID,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.start(db, user, session_id)


@router.patch("/{session_id}/checklist", response_model=SessionVisitResponse)
async def update_session_checklist(
    session_id: UUID,
    data: UpdateSessionChecklistRequest,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_checklist(db, user, session_id, data)


@router.post("/{session_id}/complete", response_model=SessionVisitResponse)
async def complete_session(
    session_id: UUID,
    data: CompleteSessionRequest,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.complete(db, user, session_id, data)


@router.post("/{session_id}/cancel", response_model=SessionVisitResponse)
async def cancel_session(
    session_id: UUID,
    data: CancelSessionRequest,
    user: User = Depends(require_role(*_CANCEL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.cancel(db, user, session_id, data)
