from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class AskSuperAgentRequest(BaseModel):
    question: str
    session_id: UUID | None = None


class AskSuperAgentResponse(BaseModel):
    session_id: UUID
    answer: str


class SuperAgentMessage(BaseModel):
    role: Literal["staff", "agent"]
    content: str
    created_at: datetime


class SuperAgentSessionSummary(BaseModel):
    id: UUID
    title: str
    updated_at: datetime


class SuperAgentSessionDetail(BaseModel):
    id: UUID
    title: str
    messages: list[SuperAgentMessage]