from __future__ import annotations
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_user
from src.models.user import User
from src.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from src.controller.audit.audit_controllers import AuditController

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])
controller = AuditController()


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    actor_type: str | None = Query(default=None, description="user | patient_portal | ai_agent | system"),
    action: str | None = Query(default=None, description="Substring match, e.g. 'appointment.cancel'"),
    resource_type: str | None = Query(default=None),
    resource_id: UUID | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Practice-scoped browse over the write-only audit trail — the first
    staff-facing read surface for who did what (and from where) on sensitive
    records."""
    return await controller.list_logs(
        db,
        user,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: UUID,
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_log(db, user, log_id)