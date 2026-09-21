from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class VisitDocumentResponse(BaseModel):
    id: UUID
    practice_id: UUID
    patient_id: UUID
    appointment_id: UUID | None
    doctor_id: UUID | None
    document_type: str
    file_url: str
    generated_by: str
    generated_at: datetime
    sent_to_patient_at: datetime | None
    sent_to_doctor_at: datetime | None
    sent_to_receptionist_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
