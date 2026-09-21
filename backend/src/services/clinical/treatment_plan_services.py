from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.treatment_plan import TreatmentPlan, TreatmentPlanItem, TreatmentPlanStatus, TreatmentPlanItemStatus
from src.models.doctor import Doctor
from src.models.patient import Patient
from src.models.procedure import Procedure
from src.schemas.clinical import CreateTreatmentPlanRequest, UpdateTreatmentPlanRequest, UpdateTreatmentPlanItemRequest
from src.server.exceptions import NotFoundException
from src.services.clinical.session_visit_services import SessionVisitService


class TreatmentPlanService:
    """Backs the Doctor's treatment-plan workflow — a titled plan made up of
    ordered Procedure line items, each trackable from planned through
    performed. Every method is practice-scoped."""

    def __init__(self):
        self.session_visits = SessionVisitService()

    async def _resolve_doctor(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> Doctor:
        result = await db.execute(select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id))
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise NotFoundException("No doctor profile linked to this account")
        return doctor

    async def create_plan(
        self, db: AsyncSession, practice_id: UUID, user_id: UUID, data: CreateTreatmentPlanRequest
    ) -> TreatmentPlan:
        doctor = await self._resolve_doctor(db, practice_id, user_id)

        patient_result = await db.execute(
            select(Patient).where(Patient.id == data.patient_id, Patient.practice_id == practice_id)
        )
        if patient_result.scalar_one_or_none() is None:
            raise NotFoundException("Patient not found")

        plan = TreatmentPlan(
            practice_id=practice_id,
            patient_id=data.patient_id,
            doctor_id=doctor.id,
            consultation_note_id=data.consultation_note_id,
            title=data.title,
        )
        db.add(plan)
        await db.flush()

        for item_data in data.items:
            procedure_result = await db.execute(
                select(Procedure).where(Procedure.id == item_data.procedure_id, Procedure.practice_id == practice_id)
            )
            procedure = procedure_result.scalar_one_or_none()
            if procedure is None:
                raise NotFoundException(f"Procedure {item_data.procedure_id} not found")
            item = TreatmentPlanItem(
                treatment_plan_id=plan.id,
                procedure_id=item_data.procedure_id,
                phase_order=item_data.phase_order,
                estimated_price=item_data.estimated_price,
                # A doctor can still override how many sessions THIS patient
                # needs; the procedure's own default is just the starting
                # point (see Procedure.default_session_count).
                sessions_total=item_data.sessions_total or procedure.default_session_count or 1,
                notes=item_data.notes,
            )
            db.add(item)
            await db.flush()
            # Pre-creates every session (1..sessions_total) up front — see
            # SessionVisitService.create_sessions_for_item's own docstring
            # for why this happens immediately rather than on first booking.
            await self.session_visits.create_sessions_for_item(db, practice_id, data.patient_id, item, procedure)

        await db.flush()
        return await self.get_plan(db, practice_id, plan.id)

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[TreatmentPlan]:
        query = (
            select(TreatmentPlan)
            .options(selectinload(TreatmentPlan.items).selectinload(TreatmentPlanItem.session_visits))
            .where(TreatmentPlan.practice_id == practice_id, TreatmentPlan.patient_id == patient_id)
            .order_by(TreatmentPlan.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_plan(self, db: AsyncSession, practice_id: UUID, plan_id: UUID) -> TreatmentPlan:
        query = (
            select(TreatmentPlan)
            .options(selectinload(TreatmentPlan.items).selectinload(TreatmentPlanItem.session_visits))
            .where(TreatmentPlan.id == plan_id, TreatmentPlan.practice_id == practice_id)
        )
        result = await db.execute(query)
        plan = result.scalar_one_or_none()
        if plan is None:
            raise NotFoundException("Treatment plan not found")
        return plan

    async def update_plan(
        self, db: AsyncSession, practice_id: UUID, plan_id: UUID, data: UpdateTreatmentPlanRequest
    ) -> TreatmentPlan:
        plan = await self.get_plan(db, practice_id, plan_id)
        fields = data.model_dump(exclude_unset=True)
        if "status" in fields:
            fields["status"] = TreatmentPlanStatus(fields["status"])
        for field, value in fields.items():
            setattr(plan, field, value)
        await db.flush()
        return await self.get_plan(db, practice_id, plan_id)

    async def get_plan_for_item(self, db: AsyncSession, practice_id: UUID, item_id: UUID) -> TreatmentPlan:
        """Resolves the parent plan (and its patient_id) for an item —
        used by ClinicalController.update_item to run the Doctor
        hard-restriction check before the item itself is fetched."""
        query = (
            select(TreatmentPlan)
            .join(TreatmentPlanItem, TreatmentPlanItem.treatment_plan_id == TreatmentPlan.id)
            .where(TreatmentPlanItem.id == item_id, TreatmentPlan.practice_id == practice_id)
        )
        result = await db.execute(query)
        plan = result.scalar_one_or_none()
        if plan is None:
            raise NotFoundException("Treatment plan item not found")
        return plan

    async def update_item(
        self, db: AsyncSession, practice_id: UUID, item_id: UUID, data: UpdateTreatmentPlanItemRequest
    ) -> TreatmentPlanItem:
        query = (
            select(TreatmentPlanItem)
            .join(TreatmentPlan, TreatmentPlanItem.treatment_plan_id == TreatmentPlan.id)
            .where(TreatmentPlanItem.id == item_id, TreatmentPlan.practice_id == practice_id)
        )
        result = await db.execute(query)
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException("Treatment plan item not found")

        fields = data.model_dump(exclude_unset=True)
        if "status" in fields:
            new_status = TreatmentPlanItemStatus(fields["status"])
            fields["status"] = new_status
            # First transition into COMPLETED stamps performed_at — a status
            # bounced back and forth doesn't keep re-stamping it.
            if new_status == TreatmentPlanItemStatus.COMPLETED and item.performed_at is None:
                fields["performed_at"] = datetime.now(timezone.utc)
        for field, value in fields.items():
            setattr(item, field, value)
        await db.flush()
        await db.refresh(item)
        return item
