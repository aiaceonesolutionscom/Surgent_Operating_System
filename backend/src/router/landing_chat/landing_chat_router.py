from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.sse import sse_response
from src.services.landing_chat.landing_chat_service import LandingChatService

router = APIRouter(prefix="/landing-chat", tags=["Landing Chat"])

service = LandingChatService()


class LandingChatMessageRequest(BaseModel):
    # Client passes back the conversation_id from a previous turn to continue
    # the same thread (the frontend persists it in sessionStorage). Like the
    # public consultation form, this endpoint is unauthenticated by design —
    # the website chat IS the funnel entry.
    conversation_id: Optional[uuid.UUID] = None
    message: str = Field(min_length=1, max_length=2000)
    # Optional context blob from the marketing site (e.g. the hero headline
    # the visitor clicked on), saved onto the conversation.
    context: Optional[str] = None


@router.post("/message")
async def landing_chat_message(
    data: LandingChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    return await service.handle_message(
        db,
        str(data.conversation_id) if data.conversation_id else None,
        data.message,
        context=data.context,
    )


@router.post("/message/stream")
async def landing_chat_message_stream(
    data: LandingChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    return sse_response(
        service.handle_message_stream(
            db,
            str(data.conversation_id) if data.conversation_id else None,
            data.message,
            context=data.context,
        )
    )