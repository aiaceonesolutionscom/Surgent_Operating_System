from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.visit_document import VisitDocumentResponse
from src.controller.visit_documents.visit_documents_controllers import VisitDocumentsController

router = APIRouter(tags=["Visit Documents"])
controller = VisitDocumentsController()

# View-only — same roles as consent_router.py's _VIEW_ROLES: Owner sees
# everything, Receptionist sees everything, Doctor is restricted to their
# own assigned patients (enforced in the controller via verify_doctor_access).
_VIEW_ROLES = (UserRole.OWNER, UserRole.DOCTOR, UserRole.RECEPTIONIST)


@router.get("/patients/{patient_id}/visit-documents", response_model=list[VisitDocumentResponse])
async def list_visit_documents(
    patient_id: UUID,
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_for_patient(db, user, patient_id)
