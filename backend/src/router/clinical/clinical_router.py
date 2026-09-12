from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.clinical import (
    CreateConsultationNoteRequest,
    UpdateConsultationNoteRequest,
    ConsultationNoteResponse,
    AIConsultationDraftRequest,
    AIConsultationDraftResponse,
    TranscriptionResponse,
    CreateTreatmentPlanRequest,
    UpdateTreatmentPlanRequest,
    UpdateTreatmentPlanItemRequest,
    TreatmentPlanResponse,
    TreatmentPlanItemResponse,
)
from src.controller.clinical.clinical_controllers import ClinicalController

router = APIRouter(prefix="/clinical", tags=["Clinical"])
controller = ClinicalController()

# Clinical documentation — Owner and Doctor can read and write notes and use
# the Consultation Assistant (transcribe / AI draft), so the Owner can test the
# same workflow the Doctor sees. Deliberately excludes Receptionist (roadmap
# decision #3) and keeps treatment-plan *writes* Doctor-only below.
_VIEW_ROLES = (UserRole.OWNER, UserRole.DOCTOR)
_WRITE_ROLES = (UserRole.OWNER, UserRole.DOCTOR)


@router.post("/notes", response_model=ConsultationNoteResponse)
async def create_note(
    data: CreateConsultationNoteRequest,
    user: User = Depends(require_role(*_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_note(db, user, data)


@router.get("/notes", response_model=list[ConsultationNoteResponse])
async def list_notes(
    patient_id: UUID = Query(...),
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_notes_for_patient(db, user, patient_id)


@router.get("/notes/{note_id}", response_model=ConsultationNoteResponse)
async def get_note(
    note_id: UUID,
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_note(db, user, note_id)


@router.patch("/notes/{note_id}", response_model=ConsultationNoteResponse)
async def update_note(
    note_id: UUID,
    data: UpdateConsultationNoteRequest,
    user: User = Depends(require_role(*_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_note(db, user, note_id, data)


@router.post("/notes/transcribe", response_model=TranscriptionResponse)
async def transcribe_dictation(
    file: UploadFile = File(...),
    user: User = Depends(require_role(*_WRITE_ROLES)),
):
    """Voice dictation for the Consultation Assistant — transcribes an
    uploaded audio clip (webm/wav/m4a/etc.) via Groq Whisper. No DB access,
    doesn't need `db` injected."""
    audio_bytes = await file.read()
    return await controller.transcribe_dictation(audio_bytes, file.filename or "dictation.webm")


@router.post("/notes/ai-draft", response_model=AIConsultationDraftResponse)
async def ai_draft_note(
    data: AIConsultationDraftRequest,
    user: User = Depends(require_role(*_WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Consultation Assistant — drafts a SOAP note + follow-up tasks from
    the doctor's own raw/dictated notes. A drafting aid only: nothing is
    saved until the doctor reviews it and calls create_note separately."""
    return await controller.ai_draft_note(db, user, data)


@router.post("/treatment-plans", response_model=TreatmentPlanResponse)
async def create_plan(
    data: CreateTreatmentPlanRequest,
    user: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_plan(db, user, data)


@router.get("/treatment-plans", response_model=list[TreatmentPlanResponse])
async def list_plans(
    patient_id: UUID = Query(...),
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_plans_for_patient(db, user, patient_id)


@router.get("/treatment-plans/{plan_id}", response_model=TreatmentPlanResponse)
async def get_plan(
    plan_id: UUID,
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_plan(db, user, plan_id)


@router.patch("/treatment-plans/{plan_id}", response_model=TreatmentPlanResponse)
async def update_plan(
    plan_id: UUID,
    data: UpdateTreatmentPlanRequest,
    user: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_plan(db, user, plan_id, data)


@router.patch("/treatment-plan-items/{item_id}", response_model=TreatmentPlanItemResponse)
async def update_item(
    item_id: UUID,
    data: UpdateTreatmentPlanItemRequest,
    user: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_item(db, user, item_id, data)
