from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.session_visit import SessionVisit, SessionVisitStatus
from src.models.treatment_plan import TreatmentPlanItem, TreatmentPlanItemStatus
from src.models.procedure import Procedure
from src.models.doctor import Doctor
from src.models.patient import Patient
from src.server.exceptions import NotFoundException, AppException
from src.services.appointments.appointments_services import AppointmentsService
from src.services.inventory.inventory_services import InventoryService

logger = logging.getLogger(__name__)

_NON_TERMINAL_STATUSES = (
    SessionVisitStatus.PLANNED, SessionVisitStatus.SCHEDULED,
    SessionVisitStatus.CONFIRMED, SessionVisitStatus.IN_PROGRESS,
)


def _seed_checklist(default_checklist: list) -> list[dict]:
    return [
        {"item": str(entry), "checked": False, "checked_by": None, "checked_at": None}
        for entry in (default_checklist or [])
    ]


def session_progress(item: TreatmentPlanItem) -> dict:
    """Sessions completed/remaining for a treatment-plan item — read by the
    frontend's progress display AND by RefundService's pro-rata calculation,
    so both always agree on the same numbers."""
    visits = item.session_visits or []
    completed = sum(1 for v in visits if v.status == SessionVisitStatus.COMPLETED)
    cancelled = sum(1 for v in visits if v.status == SessionVisitStatus.CANCELLED)
    total = item.sessions_total or 1
    return {
        "sessions_total": total,
        "sessions_completed": completed,
        "sessions_cancelled": cancelled,
        "sessions_remaining": max(total - completed - cancelled, 0),
    }


class SessionVisitService:
    """Per-visit records within a (possibly multi-visit) TreatmentPlanItem —
    generalizes SurgeryService's status-machine + checklist pattern
    (services/surgery/surgery_services.py) to every procedure. Scheduling a
    session reuses AppointmentsService.create_appointment directly, so a
    session gets the same doctor-conflict check, patient notification and
    auto-generated visit document every other appointment gets for free,
    rather than re-implementing that machinery here."""

    def __init__(self):
        self.appointments = AppointmentsService()
        self.inventory = InventoryService()

    async def _get_item(self, db: AsyncSession, practice_id: UUID, item_id: UUID) -> TreatmentPlanItem:
        result = await db.execute(
            select(TreatmentPlanItem)
            .join(TreatmentPlanItem.treatment_plan)
            .where(TreatmentPlanItem.id == item_id)
            .where(TreatmentPlanItem.treatment_plan.has(practice_id=practice_id))
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException("Treatment plan item not found")
        return item

    async def create_sessions_for_item(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID, item: TreatmentPlanItem, procedure: Procedure
    ) -> list[SessionVisit]:
        """Called once, right after a TreatmentPlanItem is created (see
        TreatmentPlanService.create_plan) — pre-creates every session the
        item will need (session_index 1..sessions_total) in PLANNED status,
        so "session 2 of 6" is visible immediately, before front desk has
        scheduled a single date."""
        sessions_total = max(item.sessions_total or 1, 1)
        per_session_price = None
        if item.estimated_price is not None:
            per_session_price = round(float(item.estimated_price) / sessions_total, 2)

        visits = []
        for index in range(1, sessions_total + 1):
            visit = SessionVisit(
                practice_id=practice_id,
                patient_id=patient_id,
                treatment_plan_item_id=item.id,
                session_index=index,
                duration_minutes=procedure.duration_minutes,
                checklist=_seed_checklist(procedure.default_checklist),
                price=per_session_price,
                status=SessionVisitStatus.PLANNED,
            )
            db.add(visit)
            visits.append(visit)
        await db.flush()
        return visits

    def _base_query(self):
        return select(SessionVisit).options(
            selectinload(SessionVisit.doctor), selectinload(SessionVisit.patient), selectinload(SessionVisit.appointment),
        )

    async def list_for_item(self, db: AsyncSession, practice_id: UUID, item_id: UUID) -> list[SessionVisit]:
        await self._get_item(db, practice_id, item_id)
        result = await db.execute(
            self._base_query()
            .where(SessionVisit.practice_id == practice_id, SessionVisit.treatment_plan_item_id == item_id)
            .order_by(SessionVisit.session_index)
        )
        return list(result.scalars().all())

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[SessionVisit]:
        result = await db.execute(
            self._base_query()
            .where(SessionVisit.practice_id == practice_id, SessionVisit.patient_id == patient_id)
            .order_by(SessionVisit.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_doctor(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> list[SessionVisit]:
        doctor_result = await db.execute(select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id))
        doctor = doctor_result.scalar_one_or_none()
        if doctor is None:
            return []
        result = await db.execute(
            self._base_query()
            .where(SessionVisit.practice_id == practice_id, SessionVisit.doctor_id == doctor.id)
            .order_by(SessionVisit.scheduled_date)
        )
        return list(result.scalars().all())

    async def get_session(self, db: AsyncSession, practice_id: UUID, session_id: UUID) -> SessionVisit:
        result = await db.execute(self._base_query().where(SessionVisit.id == session_id, SessionVisit.practice_id == practice_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundException("Session visit not found")
        return session

    async def schedule_session(
        self, db: AsyncSession, practice_id: UUID, session_id: UUID, doctor_id: UUID, start_time: datetime,
        appointment_type: str | None = None, notify_patient: bool = True,
    ) -> SessionVisit:
        session = await self.get_session(db, practice_id, session_id)
        if session.status not in (SessionVisitStatus.PLANNED, SessionVisitStatus.SCHEDULED):
            raise AppException(f"Cannot schedule a {session.status.value} session")

        item = await self._get_item(db, practice_id, session.treatment_plan_item_id)
        duration = session.duration_minutes or 30
        end_time = start_time + timedelta(minutes=duration)
        label = appointment_type or f"Session {session.session_index}/{item.sessions_total}"

        appointment = await self.appointments.create_appointment(
            db, practice_id, session.patient_id, doctor_id, label, start_time, end_time,
            notes=f"Treatment plan session {session.session_index} of {item.sessions_total}",
            notify_patient=notify_patient,
        )

        session.appointment_id = appointment.id
        session.doctor_id = doctor_id
        session.scheduled_date = start_time
        session.status = SessionVisitStatus.SCHEDULED
        await db.flush()

        # Convenience pointer on the parent item — "most recently booked
        # session" for anything still reading the item's own single
        # scheduled_appointment_id field (pre-dating multi-session support).
        item.scheduled_appointment_id = appointment.id
        if item.status == TreatmentPlanItemStatus.PLANNED:
            item.status = TreatmentPlanItemStatus.SCHEDULED
        await db.flush()
        return await self.get_session(db, practice_id, session_id)

    async def confirm_session(self, db: AsyncSession, practice_id: UUID, session_id: UUID) -> SessionVisit:
        session = await self.get_session(db, practice_id, session_id)
        if session.status != SessionVisitStatus.SCHEDULED:
            raise AppException(f"Cannot confirm a {session.status.value} session")
        session.status = SessionVisitStatus.CONFIRMED
        session.confirmed_at = datetime.now(timezone.utc)
        await db.flush()
        return await self.get_session(db, practice_id, session_id)

    async def start_session(self, db: AsyncSession, practice_id: UUID, session_id: UUID) -> SessionVisit:
        session = await self.get_session(db, practice_id, session_id)
        if session.status not in (SessionVisitStatus.CONFIRMED, SessionVisitStatus.SCHEDULED):
            raise AppException(f"Cannot start a {session.status.value} session")
        session.status = SessionVisitStatus.IN_PROGRESS
        session.started_at = datetime.now(timezone.utc)
        await db.flush()
        return await self.get_session(db, practice_id, session_id)

    async def update_checklist(self, db: AsyncSession, practice_id: UUID, session_id: UUID, checklist: list[dict]) -> SessionVisit:
        session = await self.get_session(db, practice_id, session_id)
        if session.status in (SessionVisitStatus.COMPLETED, SessionVisitStatus.CANCELLED):
            raise AppException("Cannot edit the checklist of a completed or cancelled session")
        session.checklist = checklist
        await db.flush()
        return await self.get_session(db, practice_id, session_id)

    async def complete_session(
        self, db: AsyncSession, practice_id: UUID, session_id: UUID,
        session_note: str | None, products_used: list[dict], actual_price: float | None,
    ) -> SessionVisit:
        session = await self.get_session(db, practice_id, session_id)
        if session.status not in (SessionVisitStatus.IN_PROGRESS, SessionVisitStatus.CONFIRMED, SessionVisitStatus.SCHEDULED):
            raise AppException(f"Cannot complete a {session.status.value} session")

        session.status = SessionVisitStatus.COMPLETED
        session.session_note = session_note
        session.products_used = products_used
        if actual_price is not None:
            session.price = actual_price
        session.completed_at = datetime.now(timezone.utc)
        await db.flush()

        for entry in products_used or []:
            item_id = entry.get("inventory_item_id")
            quantity = entry.get("quantity", 1)
            if not item_id:
                continue
            try:
                await self.inventory.consume(
                    db, practice_id, UUID(str(item_id)), int(quantity),
                    resource_type="session_visit", resource_id=session.id, performed_by="system",
                )
            except Exception:
                logger.exception(
                    "Failed to consume inventory item %s (qty %s) for session %s — completing anyway",
                    item_id, quantity, session.id,
                )

        # Cascade to the parent item: once every session is either completed
        # or cancelled (and at least one is completed), the item itself is
        # done — same "stamp once" pattern TreatmentPlanService.update_item
        # already uses for performed_at.
        item = await self._get_item(db, practice_id, session.treatment_plan_item_id)
        siblings = await self.list_for_item(db, practice_id, item.id)
        if all(s.status in (SessionVisitStatus.COMPLETED, SessionVisitStatus.CANCELLED) for s in siblings):
            item.status = TreatmentPlanItemStatus.COMPLETED
            if item.performed_at is None:
                item.performed_at = datetime.now(timezone.utc)
            if item.actual_price is None:
                item.actual_price = sum(float(s.price) for s in siblings if s.price is not None) or None
            await db.flush()

        return await self.get_session(db, practice_id, session_id)

    async def cancel_session(self, db: AsyncSession, practice_id: UUID, session_id: UUID, reason: str | None) -> SessionVisit:
        session = await self.get_session(db, practice_id, session_id)
        if session.status in (SessionVisitStatus.COMPLETED, SessionVisitStatus.CANCELLED):
            raise AppException(f"Cannot cancel a {session.status.value} session")
        session.status = SessionVisitStatus.CANCELLED
        session.cancelled_at = datetime.now(timezone.utc)
        session.cancelled_reason = reason or None
        await db.flush()
        return await self.get_session(db, practice_id, session_id)

    async def cancel_remaining_for_item(
        self, db: AsyncSession, practice_id: UUID, item_id: UUID, reason: str
    ) -> list[SessionVisit]:
        """Called by RefundService when a refund completes on a multi-session
        item — every session not already completed or cancelled is
        cancelled, so front desk stops trying to book sessions the patient
        has been refunded for."""
        visits = await self.list_for_item(db, practice_id, item_id)
        cancelled = []
        for visit in visits:
            if visit.status in _NON_TERMINAL_STATUSES:
                visit.status = SessionVisitStatus.CANCELLED
                visit.cancelled_at = datetime.now(timezone.utc)
                visit.cancelled_reason = reason
                cancelled.append(visit)
        if cancelled:
            await db.flush()
        return cancelled
