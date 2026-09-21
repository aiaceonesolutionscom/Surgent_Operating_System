from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CreateConsentTemplateRequest(BaseModel):
    document_type: str
    body: str
    # Structured, admin-configurable per-treatment-type clause groups — see
    # models/consent_document.py's ConsentTemplate.sections docstring for the
    # shape. Optional: a practice can still raise a plain free-text template
    # with no structured sections at all.
    sections: dict | None = None


class UpdateConsentTemplateRequest(BaseModel):
    # Editing the body OR sections bumps `version` server-side — see
    # services/consent/consent_template_services.py. is_active lets the
    # Owner retire a template without deleting its history (past
    # ConsentDocuments still reference it by id).
    body: str | None = None
    sections: dict | None = None
    is_active: bool | None = None


class ConsentTemplateResponse(BaseModel):
    id: UUID
    practice_id: UUID
    document_type: str
    version: int
    body: str
    sections: dict | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
