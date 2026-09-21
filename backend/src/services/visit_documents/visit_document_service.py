from __future__ import annotations
import base64
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.patient import Patient
from src.models.practice import Practice
from src.models.doctor import Doctor
from src.models.appointment import Appointment
from src.models.visit_document import VisitDocument, VisitDocumentType, VisitDocumentGeneratedBy
from src.services.visit_documents.visit_document_pdf_service import generate_visit_document_pdf
from src.services.messaging.messaging_service import MessagingService
from src.services.messaging.quiet_hours import MessageTiming
from src.services.email.resend_service import ResendService
from src.services.storage.storage_service import StorageService
from src.services.notifications.notification_service import NotificationService
from src.services.audit.audit_log_service import AuditLogService
from datetime import datetime, timezone

logger = logging.getLogger("aesthetixai.visit_documents")


class VisitDocumentService:
    """Generates and delivers the auto-generated "bring this to your visit"
    intake-summary PDF — whatever structured intake data currently exists on
    a Patient (AI-receptionist-collected or patient-portal-collected),
    rendered once and sent to the patient immediately (WhatsApp + email),
    with an in-app notification for the practice's staff (doctor +
    receptionist see it via the existing Notification feed, no forced
    WhatsApp/email push to internal staff).

    Deliberately fire-and-forget end to end, mirroring InvoiceReceiptService:
    a missing phone/email, unconnected WhatsApp instance, or storage hiccup
    must never block the appointment-booking or AI-receptionist chat flow
    that triggered generation."""

    def __init__(self):
        self.messaging = MessagingService()
        self.email = ResendService()
        self.storage = StorageService()
        self.notifications = NotificationService()
        self.audit = AuditLogService()

    async def generate_and_send(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patient: Patient,
        appointment: Appointment | None = None,
        doctor: Doctor | None = None,
        generated_by: VisitDocumentGeneratedBy = VisitDocumentGeneratedBy.SYSTEM,
    ) -> VisitDocument | None:
        try:
            practice_result = await db.execute(select(Practice).where(Practice.id == practice_id))
            practice = practice_result.scalar_one_or_none()
            if practice is None:
                return None
            pdf_bytes = generate_visit_document_pdf(patient, practice, doctor, appointment)
            upload = await self.storage.upload(
                pdf_bytes, f"visit-doc-{patient.id}", folder="visit_documents", resource_type="raw"
            )
        except Exception as exc:
            logger.info("Could not build/upload visit document for patient %s: %s", patient.id, exc)
            return None

        document = VisitDocument(
            practice_id=practice_id,
            patient_id=patient.id,
            appointment_id=appointment.id if appointment else None,
            doctor_id=doctor.id if doctor else (patient.assigned_doctor_id or None),
            document_type=VisitDocumentType.INTAKE_SUMMARY,
            file_url=upload["url"],
            generated_by=generated_by,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

        try:
            await self.audit.log(
                db, practice_id, actor_type=generated_by.value, action="visit_document.generated",
                resource_type="visit_document", resource_id=document.id,
            )
        except Exception:
            logger.exception("Audit log write failed for visit_document.generated (patient %s)", patient.id)

        await self._send_to_patient(db, practice_id, patient, document, pdf_bytes)
        await self._notify_staff(db, practice_id, patient, document)
        return document

    async def _send_to_patient(
        self, db: AsyncSession, practice_id: UUID, patient: Patient, document: VisitDocument, pdf_bytes: bytes
    ) -> None:
        filename = f"visit-summary-{str(document.id)[:8]}.pdf"
        caption = (
            f"Hi {patient.first_name}, here's your visit summary — please bring it (or show it on your phone) "
            f"to your appointment."
        )
        try:
            await self.messaging.send_document_and_log(
                db, practice_id, patient, "visit_document", document.file_url, filename, caption,
                timing=MessageTiming.ON_DEMAND,
            )
        except Exception as exc:
            logger.info("Visit document not sent via WhatsApp for patient %s: %s", patient.id, exc)

        if patient.email:
            try:
                await self.email.send(
                    patient.email, "Your visit summary", f"<p>{caption}</p>",
                    attachments=[{"filename": filename, "content_base64": base64.b64encode(pdf_bytes).decode("ascii")}],
                )
            except Exception as exc:
                logger.info("Visit document email not sent for patient %s: %s", patient.id, exc)

        try:
            document.sent_to_patient_at = datetime.now(timezone.utc)
            await db.flush()
        except Exception:
            logger.exception("Could not update sent_to_patient_at for visit document %s", document.id)

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[VisitDocument]:
        result = await db.execute(
            select(VisitDocument)
            .where(VisitDocument.practice_id == practice_id, VisitDocument.patient_id == patient_id)
            .order_by(VisitDocument.generated_at.desc())
        )
        return list(result.scalars().all())

    async def _notify_staff(
        self, db: AsyncSession, practice_id: UUID, patient: Patient, document: VisitDocument
    ) -> None:
        try:
            await self.notifications.notify(
                db, practice_id, "visit_document_ready",
                title=f"Visit summary ready — {patient.first_name} {patient.last_name}",
                body="A patient intake summary has been generated and is ready for review.",
                resource_type="visit_document", resource_id=document.id,
            )
            now = datetime.now(timezone.utc)
            document.sent_to_doctor_at = now
            document.sent_to_receptionist_at = now
            await db.flush()
        except Exception:
            logger.exception("Could not raise in-app notification for visit document %s", document.id)
