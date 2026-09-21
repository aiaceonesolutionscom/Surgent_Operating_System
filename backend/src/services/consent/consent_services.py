from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.consent_document import ConsentDocument, ConsentDocumentStatus, ConsentTemplate
from src.models.patient import Patient
from src.models.practice import Practice
from src.models.user import User
from src.schemas.consent_document import CreateConsentDocumentRequest
from src.server.exceptions import NotFoundException, AppException
from src.services.notifications.notification_service import NotificationService
from src.services.storage.storage_service import StorageService
from src.services.consent.consent_pdf_service import generate_consent_pdf

import logging

logger = logging.getLogger("aesthetixai.consent")


class ConsentService:
    """Real per-document consent, replacing Patient.consent_status as the
    only signal (kept as a denormalized flag, recomputed here whenever a
    document is signed or voided, so existing reads of it keep working).
    Administrative/legal, not clinical judgment — deliberately open to
    Owner/Doctor/Receptionist alike (front desk routinely collects consent
    at intake), unlike clinical notes."""

    def __init__(self):
        self.notifications = NotificationService()
        self.storage = StorageService()

    async def _get_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> Patient:
        result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id))
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")
        return patient

    async def _recompute_consent_status(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> None:
        has_signed = await db.scalar(
            select(ConsentDocument.id)
            .where(
                ConsentDocument.practice_id == practice_id,
                ConsentDocument.patient_id == patient_id,
                ConsentDocument.status == ConsentDocumentStatus.SIGNED,
            )
            .limit(1)
        )
        patient = await self._get_patient(db, practice_id, patient_id)
        patient.consent_status = has_signed is not None
        await db.flush()

    async def create_document(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID, data: CreateConsentDocumentRequest
    ) -> ConsentDocument:
        await self._get_patient(db, practice_id, patient_id)

        content = data.content
        sections = None
        template_id = None
        template_version = None
        if data.template_id is not None:
            result = await db.execute(
                select(ConsentTemplate).where(ConsentTemplate.id == data.template_id, ConsentTemplate.practice_id == practice_id)
            )
            template = result.scalar_one_or_none()
            if template is None:
                raise NotFoundException("Consent template not found")
            # Snapshot NOW — the whole point of versioning is that a later
            # edit to this template never rewrites what gets signed here.
            content = template.body
            sections = template.sections
            template_id = template.id
            template_version = template.version

        document = ConsentDocument(
            practice_id=practice_id,
            patient_id=patient_id,
            document_type=data.document_type,
            content=content,
            sections=sections,
            treatment_plan_notes=data.treatment_plan_notes,
            template_id=template_id,
            template_version=template_version,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

        patient = await self._get_patient(db, practice_id, patient_id)
        await self.notifications.notify(
            db, practice_id, "consent_pending",
            title=f"Consent pending — {patient.first_name} {patient.last_name}",
            body=f"A {data.document_type} consent document is awaiting signature.",
            resource_type="consent_document", resource_id=document.id,
        )
        return document

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[ConsentDocument]:
        query = (
            select(ConsentDocument)
            .where(ConsentDocument.practice_id == practice_id, ConsentDocument.patient_id == patient_id)
            .order_by(ConsentDocument.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_document(self, db: AsyncSession, practice_id: UUID, document_id: UUID) -> ConsentDocument:
        query = select(ConsentDocument).where(ConsentDocument.id == document_id, ConsentDocument.practice_id == practice_id)
        result = await db.execute(query)
        document = result.scalar_one_or_none()
        if document is None:
            raise NotFoundException("Consent document not found")
        return document

    async def sign_document(
        self, db: AsyncSession, practice_id: UUID, document_id: UUID, signed_by_name: str, witnessed_by: UUID
    ) -> ConsentDocument:
        document = await self.get_document(db, practice_id, document_id)
        if document.status == ConsentDocumentStatus.SIGNED:
            raise AppException("This document is already signed.")
        if document.status == ConsentDocumentStatus.VOID:
            raise AppException("This document was voided — create a new one instead.")

        document.status = ConsentDocumentStatus.SIGNED
        document.signed_at = datetime.now(timezone.utc)
        document.signed_by_name = signed_by_name
        document.witnessed_by = witnessed_by
        await db.flush()
        await db.refresh(document)

        await self._recompute_consent_status(db, practice_id, document.patient_id)
        await self._generate_and_attach_pdf(db, practice_id, document)
        return document

    async def _generate_and_attach_pdf(self, db: AsyncSession, practice_id: UUID, document: ConsentDocument) -> None:
        """Renders the signed PDF from document's now-frozen snapshot and
        uploads it — best-effort: signing itself must already have
        succeeded and committed its DB state by the time this runs, so a PDF
        or storage failure here must never undo or fail the signature."""
        try:
            patient = await self._get_patient(db, practice_id, document.patient_id)
            practice_result = await db.execute(select(Practice).where(Practice.id == practice_id))
            practice = practice_result.scalar_one_or_none()
            witness = None
            if document.witnessed_by is not None:
                witness_result = await db.execute(select(User).where(User.id == document.witnessed_by))
                witness = witness_result.scalar_one_or_none()
            if practice is None:
                return
            pdf_bytes = generate_consent_pdf(document, patient, practice, witness)
            upload = await self.storage.upload(
                pdf_bytes, f"consent-{document.id}", folder="consent_documents", resource_type="raw"
            )
            document.file_url = upload["url"]
            await db.flush()
        except Exception:
            logger.exception("Consent PDF generation/upload failed for document %s", document.id)
            return

        try:
            await self.notifications.notify(
                db, practice_id, "consent_signed",
                title=f"Consent signed — {patient.first_name} {patient.last_name}",
                body=f"A signed {document.document_type} consent PDF is ready for review.",
                resource_type="consent_document", resource_id=document.id,
            )
        except Exception:
            logger.exception("consent_signed notification failed for document %s", document.id)

    async def void_document(self, db: AsyncSession, practice_id: UUID, document_id: UUID) -> ConsentDocument:
        document = await self.get_document(db, practice_id, document_id)
        document.status = ConsentDocumentStatus.VOID
        await db.flush()
        await db.refresh(document)

        await self._recompute_consent_status(db, practice_id, document.patient_id)
        return document

    async def mark_discussed(self, db: AsyncSession, practice_id: UUID, document_id: UUID, doctor_user_id: UUID) -> ConsentDocument:
        """The one consent action a Doctor gets (see consent_router.py's
        role split) — a lightweight "I went over this with the patient"
        note, independent of the actual send/sign/void workflow which stays
        Owner/Receptionist territory."""
        document = await self.get_document(db, practice_id, document_id)
        document.discussed_at = datetime.now(timezone.utc)
        document.discussed_by = doctor_user_id
        await db.flush()
        await db.refresh(document)
        return document
