from __future__ import annotations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.procedure import Procedure
from src.schemas.procedure import CreateProcedureRequest, UpdateProcedureRequest
from src.server.exceptions import NotFoundException


class ProceduresService:
    """Backs the practice's own procedure/pricing catalog — no seeded data
    (a fake starter catalog would itself violate the no-fabrication rule);
    the Owner enters their own procedures and prices. First real writer of
    the previously-dormant Procedure model. Mirrors services/patients/
    patients_services.py's shape."""

    async def create_procedure(self, db: AsyncSession, practice_id: UUID, data: CreateProcedureRequest) -> Procedure:
        procedure = Procedure(
            practice_id=practice_id,
            name=data.name,
            category=data.category,
            description=data.description,
            base_price=data.base_price,
            duration_minutes=data.duration_minutes,
            default_session_count=data.default_session_count,
            default_checklist=data.default_checklist,
        )
        db.add(procedure)
        await db.flush()
        await db.refresh(procedure)
        return procedure

    async def list_procedures(self, db: AsyncSession, practice_id: UUID, active_only: bool = False) -> list[Procedure]:
        query = select(Procedure).where(Procedure.practice_id == practice_id)
        if active_only:
            query = query.where(Procedure.is_active.is_(True))
        query = query.order_by(Procedure.name)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_procedure(self, db: AsyncSession, practice_id: UUID, procedure_id: UUID) -> Procedure:
        query = select(Procedure).where(Procedure.id == procedure_id, Procedure.practice_id == practice_id)
        result = await db.execute(query)
        procedure = result.scalar_one_or_none()
        if procedure is None:
            raise NotFoundException("Procedure not found")
        return procedure

    async def update_procedure(
        self, db: AsyncSession, practice_id: UUID, procedure_id: UUID, data: UpdateProcedureRequest
    ) -> Procedure:
        procedure = await self.get_procedure(db, practice_id, procedure_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(procedure, field, value)
        await db.flush()
        await db.refresh(procedure)
        return procedure
