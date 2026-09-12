from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.surgery import Surgery, SurgeryStatus
from src.models.patient import Patient
from src.models.doctor import Doctor
from src.models.procedure import Procedure
from src.models.appointment import Appointment
from src.server.exceptions import NotFoundException, AppException
from src.services.inventory.inventory_services import InventoryService

import logging

logger = logging.getLogger(__name__)


class SurgeryService:
    """A real surgery record — see models/surgery.py's own docstring for
    exactly what's deliberately out of scope (a full OR-resourcing/room-
    conflict scheduler). Practice-scoped throughout; every lookup verifies
    the referenced patient/doctor/procedure belongs to the caller's own
    practice before allowing the link."""

    def __init__(self):
        self.inventory = InventoryService()

    async def _verify_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> None:
        result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id))
        if result.scalar_one_or_none() is None:
            raise NotFoundException("Patient not found")

    async def _verify_doctor(self, db: AsyncSession, practice_id: UUID, doctor_id: UUID) -> None:
        result = await db.execute(select(Doctor).where(Doctor.id == doctor_id, Doctor.practice_id == practice_id))
        if result.scalar_one_or_none() is None:
            raise NotFoundException("Doctor not found")

    async def create_surgery(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patient_id: UUID,
        procedure_id: UUID | None,
        doctor_id: UUID,
        assistant_doctor_id: UUID | None,
        scheduled_appointment_id: UUID | None,
        scheduled_date: datetime,
        duration_estimate_minutes: int | None,
        anesthesia_type: str | None,
        facility_note: str | None,
        pre_op_checklist: list[dict],
    ) -> Surgery:
        await self._verify_patient(db, practice_id, patient_id)
        await self._verify_doctor(db, practice_id, doctor_id)
        if assistant_doctor_id is not None:
            await self._verify_doctor(db, practice_id, assistant_doctor_id)
        if procedure_id is not None:
            result = await db.execute(select(Procedure).where(Procedure.id == procedure_id, Procedure.practice_id == practice_id))
            if result.scalar_one_or_none() is None:
                raise NotFoundException("Procedure not found")

        # An appointment link must be real, practice-local, and for the same
        # patient — you can't pin a surgery for Furqan onto Salma's check-up.
        if scheduled_appointment_id is not None:
            appointment_result = await db.execute(
                select(Appointment).where(
                    Appointment.id == scheduled_appointment_id,
                    Appointment.practice_id == practice_id,
                )
            )
            appointment = appointment_result.scalar_one_or_none()
            if appointment is None:
                raise NotFoundException("Appointment not found")
            if appointment.patient_id != patient_id:
                raise AppException("Appointment belongs to a different patient")

        surgery = Surgery(
            practice_id=practice_id,
            patient_id=patient_id,
            procedure_id=procedure_id,
            doctor_id=doctor_id,
            assistant_doctor_id=assistant_doctor_id,
            scheduled_appointment_id=scheduled_appointment_id,
            scheduled_date=scheduled_date,
            duration_estimate_minutes=duration_estimate_minutes,
            anesthesia_type=anesthesia_type,
            facility_note=facility_note,
            pre_op_checklist=pre_op_checklist,
        )
        db.add(surgery)
        await db.flush()
        # Re-fetch through the eager-loaded query rather than db.refresh() —
        # refresh() only reloads the row's own columns, not relationships,
        # and the controller reads surgery.patient/.procedure/.doctor/
        # .assistant_doctor to build the response. Accessing an unloaded
        # relationship outside the right async context raises
        # sqlalchemy.exc.MissingGreenlet instead of lazy-loading quietly.
        return await self.get_surgery(db, practice_id, surgery.id)

    def _base_query(self):
        return (
            select(Surgery)
            .options(
                selectinload(Surgery.patient),
                selectinload(Surgery.procedure),
                selectinload(Surgery.doctor),
                selectinload(Surgery.assistant_doctor),
            )
        )

    async def list_for_practice(self, db: AsyncSession, practice_id: UUID) -> list[Surgery]:
        result = await db.execute(
            self._base_query().where(Surgery.practice_id == practice_id).order_by(Surgery.scheduled_date.desc())
        )
        return list(result.scalars().all())

    async def list_for_doctor(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> list[Surgery]:
        """The surgeries where the calling user's roster row is the surgeon —
        a Doctor's own "Meri Surgeries" list. A doctor whose roster row is
        missing (never approved / unlinked) simply has no surgeries."""
        doctor_result = await db.execute(
            select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        if doctor is None:
            return []
        result = await db.execute(
            self._base_query()
            .where(Surgery.practice_id == practice_id, Surgery.doctor_id == doctor.id)
            .order_by(Surgery.scheduled_date.desc())
        )
        return list(result.scalars().all())

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[Surgery]:
        await self._verify_patient(db, practice_id, patient_id)
        result = await db.execute(
            self._base_query()
            .where(Surgery.practice_id == practice_id, Surgery.patient_id == patient_id)
            .order_by(Surgery.scheduled_date.desc())
        )
        return list(result.scalars().all())

    async def get_surgery(self, db: AsyncSession, practice_id: UUID, surgery_id: UUID) -> Surgery:
        result = await db.execute(self._base_query().where(Surgery.id == surgery_id, Surgery.practice_id == practice_id))
        surgery = result.scalar_one_or_none()
        if surgery is None:
            raise NotFoundException("Surgery not found")
        return surgery

    async def update_surgery(
        self,
        db: AsyncSession,
        practice_id: UUID,
        surgery_id: UUID,
        scheduled_date: datetime | None,
        duration_estimate_minutes: int | None,
        anesthesia_type: str | None,
        facility_note: str | None,
        assistant_doctor_id: UUID | None,
        pre_op_checklist: list[dict] | None,
        implants_used: list[dict] | None,
        operative_note: str | None,
    ) -> Surgery:
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status == SurgeryStatus.CANCELLED:
            raise AppException("Cannot edit a cancelled surgery")

        if scheduled_date is not None:
            surgery.scheduled_date = scheduled_date
        if duration_estimate_minutes is not None:
            surgery.duration_estimate_minutes = duration_estimate_minutes
        if anesthesia_type is not None:
            surgery.anesthesia_type = anesthesia_type
        if facility_note is not None:
            surgery.facility_note = facility_note
        if assistant_doctor_id is not None:
            await self._verify_doctor(db, practice_id, assistant_doctor_id)
            surgery.assistant_doctor_id = assistant_doctor_id
        if pre_op_checklist is not None:
            surgery.pre_op_checklist = pre_op_checklist
        if implants_used is not None:
            surgery.implants_used = implants_used
        if operative_note is not None:
            surgery.operative_note = operative_note
        await db.flush()
        # See create_surgery's comment — db.refresh() would leave the
        # relationships the controller reads (patient/procedure/doctor/
        # assistant_doctor) expired, not reloaded.
        return await self.get_surgery(db, practice_id, surgery.id)

    async def complete_surgery(
        self, db: AsyncSession, practice_id: UUID, surgery_id: UUID, operative_note: str, implants_used: list[dict]
    ) -> Surgery:
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status != SurgeryStatus.PLANNED:
            raise AppException(f"Cannot complete a {surgery.status.value} surgery")

        surgery.status = SurgeryStatus.COMPLETED
        surgery.operative_note = operative_note
        surgery.implants_used = implants_used
        await db.flush()

        # Consume-on-completion: an implant entry that names a real
        # InventoryItem (via inventory_item_id — optional, since
        # implants_used stays free-text for anything not tracked in the
        # catalog) decrements that item's stock FEFO, same real path
        # InventoryService.consume already uses elsewhere. A missing item,
        # or not enough stock on hand, is logged and skipped rather than
        # failing the whole surgery-completion call — the operative record
        # itself must never be blocked by an inventory bookkeeping gap.
        for entry in implants_used or []:
            item_id = entry.get("inventory_item_id")
            quantity = entry.get("quantity", 1)
            if not item_id:
                continue
            try:
                await self.inventory.consume(
                    db, practice_id, UUID(str(item_id)), int(quantity),
                    resource_type="surgery", resource_id=surgery.id, performed_by="system",
                )
            except Exception:
                logger.exception(
                    "Failed to consume inventory item %s (qty %s) for surgery %s — completing anyway",
                    item_id, quantity, surgery.id,
                )

        return await self.get_surgery(db, practice_id, surgery.id)

    async def cancel_surgery(self, db: AsyncSession, practice_id: UUID, surgery_id: UUID) -> Surgery:
        surgery = await self.get_surgery(db, practice_id, surgery_id)
        if surgery.status == SurgeryStatus.COMPLETED:
            raise AppException("Cannot cancel a completed surgery")

        surgery.status = SurgeryStatus.CANCELLED
        await db.flush()
        return await self.get_surgery(db, practice_id, surgery.id)
