from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from src.services.audit.audit_log_service import AuditLogService
from src.server.exceptions import NotFoundException


class AuditController:
    def __init__(self):
        self.service = AuditLogService()

    @staticmethod
    def _to_response(entry) -> AuditLogResponse:
        return AuditLogResponse(
            id=entry.id,
            actor_user_id=entry.actor_user_id,
            actor_name=entry.actor_user.name if entry.actor_user else None,
            actor_type=entry.actor_type,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            ip_address=entry.ip_address,
            created_at=entry.created_at,
        )

    async def list_logs(
        self,
        db: AsyncSession,
        user: User,
        *,
        actor_type: str | None,
        action: str | None,
        resource_type: str | None,
        resource_id: UUID | None,
        from_date: datetime | None,
        to_date: datetime | None,
        limit: int,
        offset: int,
    ) -> AuditLogListResponse:
        items, total = await self.service.list_logs(
            db,
            user.practice_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return AuditLogListResponse(total=total, items=[self._to_response(e) for e in items])

    async def get_log(self, db: AsyncSession, user: User, log_id: UUID) -> AuditLogResponse:
        entry = await self.service.get_log(db, user.practice_id, log_id)
        if entry is None:
            raise NotFoundException("Audit log entry not found")
        return self._to_response(entry)