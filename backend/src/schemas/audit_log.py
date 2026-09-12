from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    actor_name: str | None
    actor_type: str
    action: str
    resource_type: str | None
    resource_id: UUID | None
    ip_address: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    items: list[AuditLogResponse]