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
    MarketsSettingsResponse,
    MarketSettingsUpdate,
    HumanAvailabilityResponse,
    HumanAvailabilityUpdate,
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


# Per-market configuration: the currency, clinic, approved price list and
# payment methods the receptionist is allowed to quote from (SOP s7, s10.1).
# Readable by anyone who can open the monitor so a receptionist can see what the
# AI will say and correct a patient in the moment; editable by the Owner only,
# because these are the numbers the clinic is held to.
@router.get("/markets", response_model=MarketsSettingsResponse)
async def get_market_settings(
    user: User = Depends(require_role(UserRole.OWNER, UserRole.DOCTOR, UserRole.RECEPTIONIST)),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_market_settings(db, user)


@router.put("/markets/{code}", response_model=MarketsSettingsResponse)
async def save_market_settings(
    code: str,
    body: MarketSettingsUpdate,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.save_market_settings(db, user, code, body)


@router.delete("/markets/{code}", response_model=MarketsSettingsResponse)
async def clear_market_settings(
    code: str,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.clear_market_settings(db, user, code)


# Front-desk support hours — when the AI's escalation tools (request_human_handoff,
# request_refund_or_cancellation) can honestly say "connecting you now" versus
# "the team will follow up when they reopen at X" (see inbound_service.py).
# Readable by anyone who can open the monitor; only the Owner changes it.
@router.get("/human-hours", response_model=HumanAvailabilityResponse)
async def get_human_availability(
    user: User = Depends(require_role(UserRole.OWNER, UserRole.DOCTOR, UserRole.RECEPTIONIST)),
    _agent: PracticeContext = Depends(require_agent("receptionist")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_human_availability(db, user)


@router.put("/human-hours", response_model=HumanAvailabilityResponse)
async def save_human_availability(
    body: HumanAvailabilityUpdate,
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.save_human_availability(db, user, body)

