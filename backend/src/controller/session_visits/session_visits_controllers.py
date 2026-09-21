from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User, UserRole
from src.schemas.session_visit import (
    SessionVisitResponse, ScheduleSessionRequest, CompleteSessionRequest,
    UpdateSessionChecklistRequest, CancelSessionRequest,
)
from src.server.patient_access import verify_doctor_access
from src.services.clinical.session_visit_services import SessionVisitService


class SessionVisitsController:
    def __init__(self):
        self.service = SessionVisitService()

    async def list_for_item(self, db: AsyncSession, user: User, item_id: UUID) -> list[SessionVisitResponse]:
        sessions = await self.service.list_for_item(db, user.practice_id, item_id)
        if sessions:
            await verify_doctor_access(db, user, sessions[0].patient_id)
        return [SessionVisitResponse.model_validate(s) for s in sessions]

    async def list_for_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> list[SessionVisitResponse]:
        await verify_doctor_access(db, user, patient_id)
        sessions = await self.service.list_for_patient(db, user.practice_id, patient_id)
        return [SessionVisitResponse.model_validate(s) for s in sessions]

    async def list_mine(self, db: AsyncSession, user: User) -> list[SessionVisitResponse]:
        if user.role != UserRole.DOCTOR:
            return []
        sessions = await self.service.list_for_doctor(db, user.practice_id, user.id)
        return [SessionVisitResponse.model_validate(s) for s in sessions]

    async def get_session(self, db: AsyncSession, user: User, session_id: UUID) -> SessionVisitResponse:
        session = await self.service.get_session(db, user.practice_id, session_id)
        await verify_doctor_access(db, user, session.patient_id)
        return SessionVisitResponse.model_validate(session)

    async def schedule(self, db: AsyncSession, user: User, session_id: UUID, data: ScheduleSessionRequest) -> SessionVisitResponse:
        existing = await self.service.get_session(db, user.practice_id, session_id)
        await verify_doctor_access(db, user, existing.patient_id)
        session = await self.service.schedule_session(
            db, user.practice_id, session_id, data.doctor_id, data.start_time,
            appointment_type=data.appointment_type, notify_patient=data.notify_patient,
        )
        return SessionVisitResponse.model_validate(session)

    async def confirm(self, db: AsyncSession, user: User, session_id: UUID) -> SessionVisitResponse:
        existing = await self.service.get_session(db, user.practice_id, session_id)
        await verify_doctor_access(db, user, existing.patient_id)
        session = await self.service.confirm_session(db, user.practice_id, session_id)
        return SessionVisitResponse.model_validate(session)

    async def start(self, db: AsyncSession, user: User, session_id: UUID) -> SessionVisitResponse:
        existing = await self.service.get_session(db, user.practice_id, session_id)
        await verify_doctor_access(db, user, existing.patient_id)
        session = await self.service.start_session(db, user.practice_id, session_id)
        return SessionVisitResponse.model_validate(session)

    async def update_checklist(self, db: AsyncSession, user: User, session_id: UUID, data: UpdateSessionChecklistRequest) -> SessionVisitResponse:
        existing = await self.service.get_session(db, user.practice_id, session_id)
        await verify_doctor_access(db, user, existing.patient_id)
        session = await self.service.update_checklist(db, user.practice_id, session_id, data.checklist)
        return SessionVisitResponse.model_validate(session)

    async def complete(self, db: AsyncSession, user: User, session_id: UUID, data: CompleteSessionRequest) -> SessionVisitResponse:
        existing = await self.service.get_session(db, user.practice_id, session_id)
        await verify_doctor_access(db, user, existing.patient_id)
        session = await self.service.complete_session(
            db, user.practice_id, session_id, data.session_note, data.products_used, data.actual_price,
        )
        return SessionVisitResponse.model_validate(session)

    async def cancel(self, db: AsyncSession, user: User, session_id: UUID, data: CancelSessionRequest) -> SessionVisitResponse:
        existing = await self.service.get_session(db, user.practice_id, session_id)
        await verify_doctor_access(db, user, existing.patient_id)
        session = await self.service.cancel_session(db, user.practice_id, session_id, data.reason)
        return SessionVisitResponse.model_validate(session)
