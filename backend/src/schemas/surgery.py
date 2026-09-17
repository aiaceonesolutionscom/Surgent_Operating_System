from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CreateSurgeryRequest(BaseModel):
    patient_id: UUID
    procedure_id: UUID | None = None
    doctor_id: UUID
    assistant_doctor_id: UUID | None = None
    scheduled_appointment_id: UUID | None = None
    scheduled_date: datetime
    duration_estimate_minutes: int | None = None
    anesthesia_type: str | None = None
    facility_note: str | None = None
    pre_op_checklist: list[dict] = []


class UpdateSurgeryRequest(BaseModel):
    """Scheduling-only update — the Receptionist's reschedule surface. Clinical
    fields (pre-op checklist / implants / operative note) move to
    UpdateSurgeryClinicalRequest, so a receptionist editing the date can never
    stamp over a doctor's note."""
    scheduled_date: datetime | None = None
    duration_estimate_minutes: int | None = None
    anesthesia_type: str | None = None
    facility_note: str | None = None
    assistant_doctor_id: UUID | None = None


class UpdateSurgeryClinicalRequest(BaseModel):
    """Clinical-only update — pre-op checklist ticks, locked to Doctor/Owner."""
    pre_op_checklist: list[dict] | None = None
    implants_used: list[dict] | None = None
    operative_note: str | None = None


class CompleteSurgeryRequest(BaseModel):
    operative_note: str
    implants_used: list[dict] = []


class CancelSurgeryRequest(BaseModel):
    reason: str = ""


class ConfirmSurgeryRequest(BaseModel):
    pass


class SurgeryAvailabilityCheckRequest(BaseModel):
    doctor_id: UUID
    scheduled_date: datetime
    duration_minutes: int | None = None


class SurgeryAvailabilityCheckResponse(BaseModel):
    available: bool
    reasons: list[str] = []


class SurgeryResponse(BaseModel):
    id: UUID
    practice_id: UUID
    patient_id: UUID
    patient_name: str | None = None
    procedure_id: UUID | None
    procedure_name: str | None = None
    doctor_id: UUID
    doctor_name: str | None = None
    assistant_doctor_id: UUID | None
    assistant_doctor_name: str | None = None
    scheduled_appointment_id: UUID | None
    recovery_journal_id: UUID | None
    scheduled_date: datetime
    duration_estimate_minutes: int | None
    anesthesia_type: str | None
    facility_note: str | None
    pre_op_checklist: list[dict]
    implants_used: list[dict]
    operative_note: str | None
    status: str
    confirmed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DoctorSurgerySummary(BaseModel):
    doctor_id: UUID
    doctor_name: str | None
    scheduled: int = 0
    confirmed: int = 0
    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0


class SurgeryOverviewResponse(BaseModel):
    by_status: dict[str, int]
    today: list[SurgeryResponse]
    upcoming: list[SurgeryResponse]
    in_progress: list[SurgeryResponse]
    completed_this_week: int
    per_doctor: list[DoctorSurgerySummary]