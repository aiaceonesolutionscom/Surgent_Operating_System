from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user
from src.models.user import User
from src.schemas.staff_message import (
    CreateStaffMessageRequest,
    StartConversationRequest,
    StaffContactResponse,
    StaffConversationResponse,
    StaffMessageResponse,
)
from src.controller.staff_messages.staff_message_controllers import StaffMessageController

router = APIRouter(prefix="/staff-messages", tags=["Staff Messages"])
controller = StaffMessageController()


# Any practice user (owner, doctor, receptionist, staff) can use the team
# chat — every handler below is scoped by the caller's own practice and only
# ever reaches their own conversations.
@router.get("/contacts", response_model=list[StaffContactResponse])
async def list_contacts(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_contacts(db, user)


@router.get("/conversations", response_model=list[StaffConversationResponse])
async def list_conversations(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_conversations(db, user)


@router.post("/conversations", response_model=StaffConversationResponse)
async def start_conversation(
    data: StartConversationRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.start_conversation(db, user, data)


@router.get("/conversations/{conversation_id}", response_model=list[StaffMessageResponse])
async def list_messages(
    conversation_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_messages(db, user, conversation_id)


@router.post("/conversations/{conversation_id}", response_model=StaffMessageResponse)
async def send_message(
    conversation_id: UUID,
    data: CreateStaffMessageRequest,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.send_message(db, user, conversation_id, data)


@router.post("/conversations/{conversation_id}/upload", response_model=StaffMessageResponse)
async def upload_file(
    conversation_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    return await controller.send_file(
        db, user, conversation_id, file_bytes, file.filename or "file", file.content_type or "application/octet-stream"
    )