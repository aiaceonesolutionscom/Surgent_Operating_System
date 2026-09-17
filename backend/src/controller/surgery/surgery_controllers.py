from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.surgery import Surgery
from src.schemas.surgery import (
    CreateSurgeryRequest,
    UpdateSurgeryRequest,
    UpdateSurgeryClinicalRequest,
    CompleteSurgeryRequest,
    CancelSurgeryRequest,
    ConfirmSurgeryRequest,
    SurgeryAvailabilityCheckRequest,
    SurgeryAvailabilityCheckResponse,
    SurgeryOverviewResponse,
    DoctorSurgerySummary,
    SurgeryResponse,
)
from src.services.surgery.surgery_services import SurgeryService


class SurgeryController:
    def __init__(self):
        self.service = SurgeryService()

    def _to_response(self, surgery: Surgery) -> SurgeryResponse:
        data = SurgeryResponse.model_validate(surgery).model_dump()
        data["patient_name"] = f"{surgery.patient.first_name} {surgery.patient.last_name}".strip() if surgery.patient else None
        data["procedure_name"] = surgery.procedure.name if surgery.procedure else None
        data["doctor_name"] = surgery.doctor.name if surgery.doctor else None
        data["assistant_doctor_name"] = surgery.assistant_doctor.name if surgery.assistant_doctor else None
        return SurgeryResponse(**data)

    async def create_surgery(self, db: AsyncSession, user: User, data: CreateSurgeryRequest) -> SurgeryResponse:
        surgery = await self.service.create_surgery(
            db, user.practice_id, data.patient_id, data.procedure_id, data.doctor_id, data.assistant_doctor_id,
            data.scheduled_appointment_id, data.scheduled_date, data.duration_estimate_minutes,
            data.anesthesia_type, data.facility_note, data.pre_op_checklist,
        )
        return self._to_response(surgery)

    async def list_for_practice(self, db: AsyncSession, user: User) -> list[SurgeryResponse]:
        surgeries = await self.service.list_for_practice(db, user.practice_id)
        return [self._to_response(s) for s in surgeries]

    async def list_for_doctor(self, db: AsyncSession, user: User) -> list[SurgeryResponse]:
        surgeries = await self.service.list_for_doctor(db, user.practice_id, user.id)
        return [self._to_response(s) for s in surgeries]

    async def list_for_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> list[SurgeryResponse]:
        surgeries = await self.service.list_for_patient(db, user.practice_id, patient_id)
        return [self._to_response(s) for s in surgeries]

    async def get_surgery(self, db: AsyncSession, user: User, surgery_id: UUID) -> SurgeryResponse:
        surgery = await self.service.get_surgery(db, user.practice_id, surgery_id)
        return self._to_response(surgery)

    async def update_surgery(self, db: AsyncSession, user: User, surgery_id: UUID, data: UpdateSurgeryRequest) -> SurgeryResponse:
        surgery = await self.service.update_surgery(
            db, user.practice_id, surgery_id, data.scheduled_date, data.duration_estimate_minutes,
            data.anesthesia_type, data.facility_note, data.assistant_doctor_id,
        )
        return self._to_response(surgery)

    async def update_surgery_clinical(self, db: AsyncSession, user: User, surgery_id: UUID, data: UpdateSurgeryClinicalRequest) -> SurgeryResponse:
        surgery = await self.service.update_surgery_clinical(
            db, user.practice_id, surgery_id, data.pre_op_checklist, data.implants_used, data.operative_note
        )
        return self._to_response(surgery)

    async def confirm_surgery(self, db: AsyncSession, user: User, surgery_id: UUID, data: ConfirmSurgeryRequest) -> SurgeryResponse:
        surgery = await self.service.confirm_surgery(db, user.practice_id, surgery_id)
        return self._to_response(surgery)

    async def start_surgery(self, db: AsyncSession, user: User, surgery_id: UUID) -> SurgeryResponse:
        surgery = await self.service.start_surgery(db, user.practice_id, surgery_id)
        return self._to_response(surgery)

    async def complete_surgery(self, db: AsyncSession, user: User, surgery_id: UUID, data: CompleteSurgeryRequest) -> SurgeryResponse:
        surgery = await self.service.complete_surgery(db, user.practice_id, surgery_id, data.operative_note, data.implants_used)
        return self._to_response(surgery)

    async def cancel_surgery(self, db: AsyncSession, user: User, surgery_id: UUID, data: CancelSurgeryRequest) -> SurgeryResponse:
        surgery = await self.service.cancel_surgery(db, user.practice_id, surgery_id, data.reason)
        return self._to_response(surgery)

    async def check_surgery_availability(
        self, db: AsyncSession, user: User, data: SurgeryAvailabilityCheckRequest
    ) -> SurgeryAvailabilityCheckResponse:
        available, reasons = await self.service.check_surgery_availability(
            db, user.practice_id, data.doctor_id, data.scheduled_date, data.duration_minutes
        )
        return SurgeryAvailabilityCheckResponse(available=available, reasons=reasons)

    async def overview(self, db: AsyncSession, user: User) -> SurgeryOverviewResponse:
        data = await self.service.overview(db, user.practice_id)
        return SurgeryOverviewResponse(
            by_status=data["by_status"],
            today=[self._to_response(s) for s in data["today"]],
            upcoming=[self._to_response(s) for s in data["upcoming"]],
            in_progress=[self._to_response(s) for s in data["in_progress"]],
            completed_this_week=data["completed_this_week"],
            per_doctor=[DoctorSurgerySummary(**d) for d in data["per_doctor"]],
        )