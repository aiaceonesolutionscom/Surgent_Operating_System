from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.visit_document import VisitDocumentResponse
from src.server.patient_access import verify_doctor_access
from src.services.visit_documents.visit_document_service import VisitDocumentService


class VisitDocumentsController:
    def __init__(self):
        self.service = VisitDocumentService()

    async def list_for_patient(self, db: AsyncSession, user: User, patient_id: UUID) -> list[VisitDocumentResponse]:
        await verify_doctor_access(db, user, patient_id)
        documents = await self.service.list_for_patient(db, user.practice_id, patient_id)
        return [VisitDocumentResponse.model_validate(d) for d in documents]
