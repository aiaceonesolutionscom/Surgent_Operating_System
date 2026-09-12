from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user, require_role, require_agent, PracticeContext
from src.models.user import User, UserRole
from src.schemas.ai_receptionist import (
    ChatMessageRequest,
    ChatMessageResponse,
    HandleCallResponse,
    TranslateRequest,
    TranslateResponse,
    SendReminderResponse,
    AIReceptionistOverviewResponse,
    SystemPromptResponse,
    UpdateSystemPromptRequest,
)
from src.controller.ai_receptionist.ai_receptionist_controllers import AIReceptionistController

router = APIRouter(prefix="/ai-receptionist", tags=["AI Receptionist"])
controller = AIReceptionistController()


@router.post("/handle-call", response_model=HandleCallResponse)
async def handle_call(
    user: User = Depends(get_current_practice_user),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.handle_call(db, user)


@router.post("/message", response_model=ChatMessageResponse)
async def process_message(
    data: ChatMessageRequest,
    user: User = Depends(get_current_practice_user),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.process_message(db, user, data.message)


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    data: TranslateRequest,
    user: User = Depends(get_current_practice_user),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.translate(db, user, data.text, data.target_language)


@router.post("/appointments/{appointment_id}/reminder", response_model=SendReminderResponse)
async def send_reminder(
    appointment_id: UUID,
    user: User = Depends(get_current_practice_user),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.send_reminder(db, user, appointment_id)


# Owner and Doctor always see this; Receptionist does too when granted the
# existing "view_ai_receptionist" permission (frontend-gated) — the dashboard
# sidebar exposes the monitor to Receptionists, so the backend must match.
@router.get("/overview", response_model=AIReceptionistOverviewResponse)
async def get_overview(
    user: User = Depends(require_role(UserRole.OWNER, UserRole.DOCTOR, UserRole.RECEPTIONIST)),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_overview(db, user)


# Anyone who can open the monitor can see what the AI is actually told to do;
# only the Owner can change it (the prompt is the practice's front line).
@router.get("/system-prompt", response_model=SystemPromptResponse)
async def get_system_prompt(
    user: User = Depends(require_role(UserRole.OWNER, UserRole.DOCTOR, UserRole.RECEPTIONIST)),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_system_prompt(db, user)


@router.put("/system-prompt", response_model=SystemPromptResponse)
async def update_system_prompt(
    body: UpdateSystemPromptRequest,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_system_prompt(db, user, body.custom_instructions)

