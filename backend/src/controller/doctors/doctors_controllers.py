from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.doctor import (
    CreateDoctorRequest,
    UpdateDoctorRequest,
    UpdateMyDoctorRequest,
    DoctorResponse,
    CreateDoctorProcedureRequest,
    UpdateDoctorProcedureRequest,
    DoctorProcedureResponse,
    CreateDoctorAvailabilityRequest,
    DoctorAvailabilityResponse,
    DoctorTodayResponse,
    CreateDoctorTimeBlockRequest,
    DoctorTimeBlockResponse,
)
from src.schemas.availability import DoctorSlotsResponse
from src.services.doctors.doctors_services import DoctorsService
from src.services.doctors.doctor_procedures_services import DoctorProceduresService
from src.services.doctors.doctor_availability_services import DoctorAvailabilityService
from src.services.doctors.doctor_dashboard_services import DoctorDashboardService
from src.services.doctors.doctor_time_block_services import DoctorTimeBlockService
from src.services.availability.availability_services import AvailabilitySlotService


class DoctorsController:
    def __init__(self):
        self.service = DoctorsService()
        self.procedures = DoctorProceduresService()
        self.availability = DoctorAvailabilityService()
        self.dashboard = DoctorDashboardService()
        self.time_blocks = DoctorTimeBlockService()
        self.slots = AvailabilitySlotService()

    async def create_doctor(self, db: AsyncSession, user: User, data: CreateDoctorRequest) -> DoctorResponse:
        doctor = await self.service.create_doctor(db, user.practice_id, data)
        return DoctorResponse.model_validate(doctor)

    async def list_doctors(self, db: AsyncSession, user: User) -> list[DoctorResponse]:
        doctors = await self.service.list_doctors(db, user.practice_id)
        return [DoctorResponse.model_validate(d) for d in doctors]

    async def get_doctor(self, db: AsyncSession, user: User, doctor_id: UUID) -> DoctorResponse:
        doctor = await self.service.get_doctor(db, user.practice_id, doctor_id)
        return DoctorResponse.model_validate(doctor)

    async def get_my_doctor(self, db: AsyncSession, user: User) -> DoctorResponse:
        doctor = await self.service.get_my_doctor(db, user.practice_id, user.id)
        return DoctorResponse.model_validate(doctor)

    async def get_my_today(self, db: AsyncSession, user: User) -> DoctorTodayResponse:
        snapshot = await self.dashboard.get_today_snapshot(db, user.practice_id, user.id)
        return DoctorTodayResponse(**snapshot)

    async def update_my_doctor(self, db: AsyncSession, user: User, data: UpdateMyDoctorRequest) -> DoctorResponse:
        doctor = await self.service.update_my_doctor(db, user.practice_id, user.id, data)
        return DoctorResponse.model_validate(doctor)

    async def update_doctor(
        self, db: AsyncSession, user: User, doctor_id: UUID, data: UpdateDoctorRequest
    ) -> DoctorResponse:
        doctor = await self.service.update_doctor(db, user.practice_id, doctor_id, data)
        return DoctorResponse.model_validate(doctor)

    async def invite_doctor(self, db: AsyncSession, user: User, doctor_id: UUID) -> DoctorResponse:
        doctor = await self.service.invite_doctor(db, user.practice_id, doctor_id)
        return DoctorResponse.model_validate(doctor)

    # --- Doctor <-> Procedure ---

    async def add_procedure(self, db: AsyncSession, user: User, doctor_id: UUID, data: CreateDoctorProcedureRequest) -> DoctorProcedureResponse:
        link = await self.procedures.add_procedure(db, user.practice_id, doctor_id, data)
        return DoctorProcedureResponse.model_validate(link)

    async def list_procedures(self, db: AsyncSession, user: User, doctor_id: UUID) -> list[DoctorProcedureResponse]:
        links = await self.procedures.list_procedures(db, user.practice_id, doctor_id)
        return [DoctorProcedureResponse.model_validate(l) for l in links]

    async def update_procedure(self, db: AsyncSession, user: User, doctor_id: UUID, link_id: UUID, data: UpdateDoctorProcedureRequest) -> DoctorProcedureResponse:
        link = await self.procedures.update_procedure(db, user.practice_id, doctor_id, link_id, data)
        return DoctorProcedureResponse.model_validate(link)

    async def remove_procedure(self, db: AsyncSession, user: User, doctor_id: UUID, link_id: UUID) -> None:
        await self.procedures.remove_procedure(db, user.practice_id, doctor_id, link_id)

    # --- Doctor availability ---

    async def add_availability(self, db: AsyncSession, user: User, doctor_id: UUID, data: CreateDoctorAvailabilityRequest) -> DoctorAvailabilityResponse:
        override = await self.availability.add_override(db, user.practice_id, doctor_id, data)
        return DoctorAvailabilityResponse.model_validate(override)

    async def list_availability(self, db: AsyncSession, user: User, doctor_id: UUID) -> list[DoctorAvailabilityResponse]:
        overrides = await self.availability.list_overrides(db, user.practice_id, doctor_id)
        return [DoctorAvailabilityResponse.model_validate(o) for o in overrides]

    async def remove_availability(self, db: AsyncSession, user: User, doctor_id: UUID, override_id: UUID) -> None:
        await self.availability.remove_override(db, user.practice_id, doctor_id, override_id)

    # --- Personal time blocks ("me" only — no cross-doctor access) ---

    async def create_my_time_block(self, db: AsyncSession, user: User, data: CreateDoctorTimeBlockRequest) -> DoctorTimeBlockResponse:
        block = await self.time_blocks.create_block(db, user.practice_id, user.id, data)
        return DoctorTimeBlockResponse.model_validate(block)

    async def list_my_time_blocks(self, db: AsyncSession, user: User) -> list[DoctorTimeBlockResponse]:
        blocks = await self.time_blocks.list_blocks(db, user.practice_id, user.id)
        return [DoctorTimeBlockResponse.model_validate(b) for b in blocks]

    async def delete_my_time_block(self, db: AsyncSession, user: User, block_id: UUID) -> None:
        await self.time_blocks.delete_block(db, user.practice_id, user.id, block_id)

    # --- Bookable time slots ---

    async def get_my_slots(
        self,
        db: AsyncSession,
        user: User,
        date,
        days: int,
        duration_minutes: int,
    ) -> list[DoctorSlotsResponse]:
        doctor = await self.service.get_my_doctor(db, user.practice_id, user.id)
        return await self.slots.get_slots(db, user.practice_id, doctor.id, date, days, duration_minutes)

    async def get_doctor_slots(
        self,
        db: AsyncSession,
        user: User,
        doctor_id: UUID,
        date,
        days: int,
        duration_minutes: int,
    ) -> list[DoctorSlotsResponse]:
        return await self.slots.get_slots(db, user.practice_id, doctor_id, date, days, duration_minutes)
