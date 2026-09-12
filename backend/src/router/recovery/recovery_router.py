from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user, require_agent, PracticeContext
from src.server.audit import audit_action
from src.models.user import User
from src.schemas.recovery import RecoveryJournalResponse, SubmitCheckInRequest, RecoveryCheckInResponse, FlaggedCheckInResponse
from src.controller.recovery.recovery_controllers import RecoveryController

router = APIRouter(tags=["Recovery"])
controller = RecoveryController()

# Staff-facing side of the post-op recovery timeline. The patient-facing
# submission endpoint lives on the Patient Portal router
# (POST /patient-portal/me/recovery/checkin) since it needs portal auth,
# not Clerk.


@router.get("/patients/{patient_id}/recovery", response_model=RecoveryJournalResponse | None)
async def get_patient_recovery(
    patient_id: UUID,
    user: User = Depends(audit_action("recovery.view", "patient", id_param="patient_id")),
    _agent: PracticeContext = Depends(require_agent("post_op_recovery")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_journal_for_patient(db, user, patient_id)


@router.post("/patients/{patient_id}/recovery/checkins", response_model=RecoveryCheckInResponse)
async def submit_patient_checkin(
    patient_id: UUID,
    data: SubmitCheckInRequest,
    user: User = Depends(audit_action("recovery.checkin.create", "patient", id_param="patient_id")),
    _agent: PracticeContext = Depends(require_agent("post_op_recovery")),
    db: AsyncSession = Depends(get_db),
):
    # Staff can log a checkpoint on a patient's behalf (e.g. a phone
    # follow-up call) — same submission path the portal itself uses.
    return await controller.submit_checkin_for_patient(db, user, patient_id, data)


@router.get("/recovery/flagged", response_model=list[FlaggedCheckInResponse])
async def list_flagged_checkins(
    user: User = Depends(get_current_practice_user),
    _agent: PracticeContext = Depends(require_agent("post_op_recovery")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_flagged(db, user)


@router.patch("/recovery/checkins/{checkin_id}/review", response_model=RecoveryCheckInResponse)
async def mark_checkin_reviewed(
    checkin_id: UUID,
    user: User = Depends(audit_action("recovery.checkin.review", "recovery_checkin", id_param="checkin_id")),
    _agent: PracticeContext = Depends(require_agent("post_op_recovery")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.mark_reviewed(db, user, checkin_id)


@router.post("/recovery/run-followups")
async def run_followups(
    user: User = Depends(get_current_practice_user),
    _agent: PracticeContext = Depends(require_agent("post_op_recovery")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger the same due-checkpoint check the background poller
    runs every 6 hours (see post_op_followup_poller.py) — mainly for
    testing/on-demand use, scoped to the caller's own practice only."""
    return await controller.run_followups(db, user)

