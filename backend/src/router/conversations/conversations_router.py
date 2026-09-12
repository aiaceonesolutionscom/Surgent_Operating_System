from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user
from src.models.user import User
from src.models.conversation import ConversationStatus
from src.schemas.conversation import ConversationListItem, ConversationDetail, CreateMessageRequest, ToggleAiRequest
from src.controller.conversations.conversations_controllers import ConversationsController

router = APIRouter(prefix="/conversations", tags=["Conversations"])
controller = ConversationsController()


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    status: ConversationStatus | None = None,
    channel: str | None = None,
    agent_type: list[str] | None = Query(default=None),
    search: str | None = None,
    patient_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # patient_id scopes to one patient's conversations only — used by a
    # Doctor's own per-patient Communication tab (see
    # DoctorPatientDetail.tsx), which must never become a way to browse the
    # practice-wide lead/CRM inbox by omitting it. When set, the Doctor
    # hard-restriction is enforced in the controller (verify_doctor_access)
    # before any conversation data is returned.
    return await controller.list_conversations(db, user, status, channel, agent_type, search, patient_id, limit, offset)


@router.get("/patient-messages", response_model=list[ConversationListItem])
async def list_patient_messages(
    limit: int = Query(default=100, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # Dedicated Patient Messages inbox (MessagesPage's "Patient messages"
    # tab) — portal messages a patient sent their own doctor. A Doctor sees
    # only their own assigned patients (service-level filter on their Doctor
    # row); Owner sees everything read-only; Receptionist sees and answers
    # everything. Never part of the generic Agent Sessions inbox.
    return await controller.list_patient_messages(db, user, limit, offset)


@router.get("/patient-messages/{conversation_id}", response_model=ConversationDetail)
async def get_patient_message(
    conversation_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_patient_message(db, user, conversation_id)


@router.post("/patient-messages/{conversation_id}/messages", response_model=ConversationDetail)
async def reply_patient_message(
    conversation_id: UUID,
    data: CreateMessageRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # Assigned doctor or receptionist only — the Owner is read-only here
    # (enforced in the controller via _require_can_reply).
    return await controller.reply_to_patient_message(db, user, conversation_id, data.body)


@router.post("/patient-messages/{conversation_id}/resolve", response_model=ConversationDetail)
async def resolve_patient_message(
    conversation_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.resolve_patient_message(db, user, conversation_id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_conversation(db, user, conversation_id)


@router.post("/{conversation_id}/resolve", response_model=ConversationDetail)
async def resolve_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.resolve_conversation(db, user, conversation_id)


@router.post("/{conversation_id}/messages", response_model=ConversationDetail)
async def send_message(
    conversation_id: UUID,
    data: CreateMessageRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    # A staff member replying directly — sends over the real channel
    # (WhatsApp today) and pauses AI auto-replies for this conversation.
    return await controller.send_message(db, user, conversation_id, data.body)


@router.post("/{conversation_id}/toggle-ai", response_model=ConversationDetail)
async def toggle_ai(
    conversation_id: UUID,
    data: ToggleAiRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.toggle_ai(db, user, conversation_id, data.paused)
