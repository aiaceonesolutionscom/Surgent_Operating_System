from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CreateConsentDocumentRequest(BaseModel):
    document_type: str
    content: str | None = None
    # When set, the service looks up that template's CURRENT active body and
    # snapshots it (+ its version) onto the new document — `content` above is
    # ignored in that case. Omit to raise an ad-hoc document with free-text
    # content instead (no template involved).
    template_id: UUID | None = None
    treatment_plan_notes: str | None = None


class SignConsentDocumentRequest(BaseModel):
    # Patient-typed full legal name, captured by staff while the patient is
    # physically present — see models/consent_document.py's own note on why
    # this signing model was chosen over a mailed e-sign link or a scanned
    # upload.
    signed_by_name: str


class VoidConsentDocumentRequest(BaseModel):
    reason: str | None = None


class ConsentDocumentResponse(BaseModel):
    id: UUID
    practice_id: UUID
    patient_id: UUID
    document_type: str
    content: str | None
    version: int
    template_id: UUID | None = None
    template_version: int | None = None
    sections: dict | None = None
    treatment_plan_notes: str | None = None
    file_url: str | None = None
    status: str
    signed_at: datetime | None
    signed_by_name: str | None
    witnessed_by: UUID | None
    discussed_at: datetime | None = None
    discussed_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
