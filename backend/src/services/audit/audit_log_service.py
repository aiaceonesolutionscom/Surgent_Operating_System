from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.audit_log import AuditLog


class AuditLogService:
    """Thin shared writer for AuditLog — mirrors AgentLogService's own
    pattern exactly (see services/agent_log/agent_log_service.py), kept as
    its own module with no dependency on server/dependencies.py so that
    both the FastAPI-dependency-based callers (server/audit.py) and
    plain service-layer callers (e.g. patient_portal_auth_service.py,
    which itself gets imported BY server/dependencies.py) can both import
    this without a circular import."""

    async def log(
        self,
        db: AsyncSession,
        practice_id: UUID | None,
        actor_type: str,
        action: str,
        actor_user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            practice_id=practice_id,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()
        return entry

    # --- Read-side (the audit trail is write-only today — these two methods
    # back the first staff-facing /audit-logs endpoints.) ---

    async def list_logs(
        self,
        db: AsyncSession,
        practice_id: UUID,
        *,
        actor_type: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        conditions = [AuditLog.practice_id == practice_id]
        if actor_type:
            conditions.append(AuditLog.actor_type == actor_type)
        if action:
            conditions.append(AuditLog.action.ilike(f"%{action}%"))
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(AuditLog.resource_id == resource_id)
        if from_date is not None:
            conditions.append(AuditLog.created_at >= from_date)
        if to_date is not None:
            conditions.append(AuditLog.created_at <= to_date)

        total = await db.scalar(
            select(func.count()).select_from(AuditLog).where(*conditions)
        )
        result = await db.execute(
            select(AuditLog)
            .options(selectinload(AuditLog.actor_user))
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total or 0

    async def get_log(self, db: AsyncSession, practice_id: UUID, log_id: UUID) -> AuditLog | None:
        result = await db.execute(
            select(AuditLog)
            .options(selectinload(AuditLog.actor_user))
            .where(AuditLog.id == log_id, AuditLog.practice_id == practice_id)
        )
        return result.scalar_one_or_none()
