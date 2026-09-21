from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.refund_request import RefundRequest, RefundRequestStatus, RefundRequestedByType
from src.models.invoice import Invoice, InvoiceStatus
from src.models.treatment_plan import TreatmentPlanItem
from src.models.patient import Patient
from src.server.exceptions import NotFoundException, AppException
from src.services.billing.invoice_services import InvoiceService
from src.services.clinical.session_visit_services import SessionVisitService, session_progress
from src.services.messaging.messaging_service import MessagingService
from src.services.messaging.quiet_hours import MessageTiming
from src.services.notifications.notification_service import NotificationService
from src.services.audit.audit_log_service import AuditLogService

logger = logging.getLogger("aesthetixai.refunds")


class RefundService:
    """A refund/cancellation request always lands here as a real, reviewable
    record — REQUESTED -> APPROVED (decision made) -> COMPLETED (money
    actually reversed on the invoice), or REJECTED at the approval step.
    Nothing in this service lets the AI receptionist (or the patient
    directly) skip straight to APPROVED/COMPLETED — see create_request's
    `requested_by_type` handling and inbound_service.py's tool, which only
    ever calls create_request.

    Pro-rata suggestion (create_request, when a multi-session
    treatment_plan_item_id is given): remaining_sessions / sessions_total *
    the item's own price — a suggestion the reviewer can freely override,
    never a binding number."""

    def __init__(self):
        self.invoices = InvoiceService()
        self.session_visits = SessionVisitService()
        self.messaging = MessagingService()
        self.notifications = NotificationService()
        self.audit = AuditLogService()

    async def _get_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> Patient:
        result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id))
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")
        return patient

    async def _resolve_item_with_sessions(self, db: AsyncSession, practice_id: UUID, item_id: UUID) -> TreatmentPlanItem:
        result = await db.execute(
            select(TreatmentPlanItem)
            .options(selectinload(TreatmentPlanItem.session_visits))
            .join(TreatmentPlanItem.treatment_plan)
            .where(TreatmentPlanItem.id == item_id)
            .where(TreatmentPlanItem.treatment_plan.has(practice_id=practice_id))
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException("Treatment plan item not found")
        return item

    async def _auto_resolve_invoice(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> UUID | None:
        """Best-effort only — used when the AI receptionist raises a
        request with no invoice in hand. Picks the patient's single most
        recent invoice that still has money paid on it and isn't already
        cancelled/refunded; leaves it unset (staff resolves during review)
        if there's more than one plausible candidate, since guessing wrong
        here is worse than leaving it blank."""
        result = await db.execute(
            select(Invoice)
            .where(
                Invoice.practice_id == practice_id, Invoice.patient_id == patient_id,
                Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]),
            )
            .order_by(Invoice.created_at.desc())
            .limit(2)
        )
        candidates = list(result.scalars().all())
        return candidates[0].id if len(candidates) == 1 else None

    async def create_request(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID,
        requested_by_type: RefundRequestedByType, reason: str | None,
        invoice_id: UUID | None = None, treatment_plan_item_id: UUID | None = None,
        requested_by_user_id: UUID | None = None,
    ) -> RefundRequest:
        patient = await self._get_patient(db, practice_id, patient_id)

        if invoice_id is None and requested_by_type == RefundRequestedByType.AI_RECEPTIONIST:
            invoice_id = await self._auto_resolve_invoice(db, practice_id, patient_id)

        requested_amount: float | None = None
        calculation_basis: dict | None = None

        if treatment_plan_item_id is not None:
            item = await self._resolve_item_with_sessions(db, practice_id, treatment_plan_item_id)
            progress = session_progress(item)
            item_total = item.actual_price if item.actual_price is not None else item.estimated_price
            if item_total is not None and progress["sessions_total"] > 0:
                pro_rata = round(float(item_total) * progress["sessions_remaining"] / progress["sessions_total"], 2)
                calculation_basis = {
                    "formula": "pro_rata",
                    "item_total": float(item_total),
                    **progress,
                }
                if invoice_id is not None:
                    invoice = await self.invoices.get_invoice(db, practice_id, invoice_id)
                    # Never suggest refunding more than was actually paid.
                    pro_rata = min(pro_rata, invoice.amount_paid)
                    calculation_basis["amount_paid"] = invoice.amount_paid
                requested_amount = pro_rata
            else:
                calculation_basis = {"formula": "manual", "note": "No price or session count on file to calculate from.", **progress}
        elif invoice_id is not None:
            invoice = await self.invoices.get_invoice(db, practice_id, invoice_id)
            calculation_basis = {"formula": "manual", "amount_paid": invoice.amount_paid}

        request = RefundRequest(
            practice_id=practice_id,
            patient_id=patient_id,
            invoice_id=invoice_id,
            treatment_plan_item_id=treatment_plan_item_id,
            requested_by_type=requested_by_type,
            requested_by_user_id=requested_by_user_id,
            reason=reason,
            requested_amount=requested_amount,
            calculation_basis=calculation_basis,
        )
        db.add(request)
        await db.flush()
        await db.refresh(request)

        await self.notifications.notify(
            db, practice_id, "refund_requested",
            title=f"Refund request — {patient.first_name} {patient.last_name}",
            body=(reason or "A refund/cancellation request needs review.")[:300],
            resource_type="refund_request", resource_id=request.id,
        )
        try:
            await self.audit.log(
                db, practice_id, actor_type=requested_by_type.value, action="refund_request.created",
                actor_user_id=requested_by_user_id, resource_type="refund_request", resource_id=request.id,
            )
        except Exception:
            logger.exception("Audit log write failed for refund_request.created (%s)", request.id)

        return request

    async def list_for_practice(self, db: AsyncSession, practice_id: UUID, status: RefundRequestStatus | None = None) -> list[RefundRequest]:
        query = select(RefundRequest).where(RefundRequest.practice_id == practice_id)
        if status is not None:
            query = query.where(RefundRequest.status == status)
        query = query.order_by(RefundRequest.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[RefundRequest]:
        result = await db.execute(
            select(RefundRequest)
            .where(RefundRequest.practice_id == practice_id, RefundRequest.patient_id == patient_id)
            .order_by(RefundRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_request(self, db: AsyncSession, practice_id: UUID, request_id: UUID) -> RefundRequest:
        result = await db.execute(select(RefundRequest).where(RefundRequest.id == request_id, RefundRequest.practice_id == practice_id))
        request = result.scalar_one_or_none()
        if request is None:
            raise NotFoundException("Refund request not found")
        return request

    async def _notify_patient_best_effort(self, db: AsyncSession, practice_id: UUID, patient_id: UUID, text: str) -> None:
        try:
            patient = await self._get_patient(db, practice_id, patient_id)
            if not patient.phone:
                return
            await self.messaging.send_and_log(db, practice_id, patient, "refund_workflow", text, timing=MessageTiming.ON_DEMAND)
        except Exception:
            logger.exception("Refund-status message not sent for patient %s", patient_id)

    async def approve_request(
        self, db: AsyncSession, practice_id: UUID, request_id: UUID, reviewer_user_id: UUID,
        approved_amount: float | None, review_notes: str | None,
    ) -> RefundRequest:
        request = await self.get_request(db, practice_id, request_id)
        if request.status != RefundRequestStatus.REQUESTED:
            raise AppException(f"Cannot approve a {request.status.value} refund request")

        final_amount = approved_amount if approved_amount is not None else request.requested_amount
        if final_amount is None or final_amount <= 0:
            raise AppException("An approved refund needs a positive amount — this request had no auto-calculated figure, set one explicitly.")

        request.status = RefundRequestStatus.APPROVED
        request.approved_amount = final_amount
        request.reviewed_by = reviewer_user_id
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_notes = review_notes
        await db.flush()
        await db.refresh(request)

        await self._notify_patient_best_effort(
            db, practice_id, request.patient_id,
            f"Your refund request has been approved for {final_amount:,.2f} — our team will process it shortly.",
        )
        return request

    async def reject_request(
        self, db: AsyncSession, practice_id: UUID, request_id: UUID, reviewer_user_id: UUID, review_notes: str | None,
    ) -> RefundRequest:
        request = await self.get_request(db, practice_id, request_id)
        if request.status != RefundRequestStatus.REQUESTED:
            raise AppException(f"Cannot reject a {request.status.value} refund request")

        request.status = RefundRequestStatus.REJECTED
        request.reviewed_by = reviewer_user_id
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_notes = review_notes
        await db.flush()
        await db.refresh(request)

        await self._notify_patient_best_effort(
            db, practice_id, request.patient_id,
            "We've reviewed your refund/cancellation request — a team member will reach out with the details shortly.",
        )
        return request

    async def complete_request(self, db: AsyncSession, practice_id: UUID, request_id: UUID, actor_user_id: UUID) -> RefundRequest:
        request = await self.get_request(db, practice_id, request_id)
        if request.status != RefundRequestStatus.APPROVED:
            raise AppException(f"Cannot complete a {request.status.value} refund request — it must be approved first")

        if request.invoice_id is not None:
            await self.invoices.record_refund(
                db, practice_id, request.invoice_id, float(request.approved_amount),
                recorded_by=actor_user_id, notes=f"Refund request {str(request.id)[:8]}: {request.reason or ''}".strip(),
            )
        if request.treatment_plan_item_id is not None:
            await self.session_visits.cancel_remaining_for_item(
                db, practice_id, request.treatment_plan_item_id,
                reason=f"Refunded (request {str(request.id)[:8]})",
            )

        request.status = RefundRequestStatus.COMPLETED
        request.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(request)

        try:
            await self.audit.log(
                db, practice_id, actor_type="user", action="refund_request.completed",
                actor_user_id=actor_user_id, resource_type="refund_request", resource_id=request.id,
            )
        except Exception:
            logger.exception("Audit log write failed for refund_request.completed (%s)", request.id)

        await self._notify_patient_best_effort(
            db, practice_id, request.patient_id,
            f"Your refund of {float(request.approved_amount):,.2f} has been processed. Thank you for your patience.",
        )
        return request
