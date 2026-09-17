from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    content_type: str
    extra_data: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: UUID
    practice_id: UUID
    patient_id: UUID | None
    agent_type: str
    channel: str
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    """Shape for GET /conversations — matches the frontend dashboard's
    `Session` type (frontend/src/app/dashboard/sessions/types.ts) so that
    page's mock data can be swapped for a real fetch without a UI rewrite."""
    id: UUID
    patient_id: UUID | None
    patient_name: str
    agent_type: str
    channel: str
    status: str
    last_message_preview: str
    updated_at: datetime
    # WhatsApp (or other channel) contact photo — cached on Conversation.extra_data
    # the first time it's fetched, not re-fetched on every message. None when
    # the channel doesn't support avatars, the contact has none set, or it
    # hasn't been fetched yet.
    avatar_url: str | None = None
    # True once a staff member has sent a manual reply in this conversation —
    # the AI Receptionist stops auto-replaying until a staff member (or the
    # patient re-engaging) explicitly resumes it, so a human and the AI never
    # talk over each other. See services/conversations/conversations_services.py.
    ai_paused: bool = False
    # Set when the AI Receptionist books an appointment mid-conversation —
    # lets the dashboard badge a conversation as "just booked" without
    # reading the transcript.
    ai_booked_appointment_id: UUID | None = None
    # Whether the requesting user may reply to this conversation. False for
    # the Owner on portal Patient Messages (read-only); a Doctor/Receptionist
    # can always reply. The general Agent Sessions inbox leaves this True.
    can_reply: bool = True


class ConversationDetail(ConversationListItem):
    messages: list[MessageResponse]
    # Set only on the response to a just-sent staff message that didn't
    # actually reach the patient over WhatsApp (no phone on file, WhatsApp
    # not connected, or the send itself failed) — the message is still saved
    # either way (see ConversationsService.send_staff_message), this is what
    # lets the dashboard show a real warning instead of a false "sent" state.
    # None on every other response (GET, resolve, toggle-ai) — there's
    # nothing to warn about outside the send path.
    send_warning: str | None = None


class CreateMessageRequest(BaseModel):
    body: str


class ToggleAiRequest(BaseModel):
    paused: bool
