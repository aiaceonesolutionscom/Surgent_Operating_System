from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class QualificationEntry(BaseModel):
    degree: str
    institution: str | None = None
    year: int | None = None


class CreateDoctorRequest(BaseModel):
    name: str
    email: str
    phone: str | None = None
    specialty: str | None = None
    license_number: str | None = None
    bio: str | None = None
    capabilities: list[str] = []
    qualifications: list[QualificationEntry] = []
    specializations: list[str] = []
    working_hours: dict = {}
    commission_percent: float | None = None


class UpdateDoctorRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    specialty: str | None = None
    license_number: str | None = None
    bio: str | None = None
    capabilities: list[str] | None = None
    qualifications: list[QualificationEntry] | None = None
    specializations: list[str] | None = None
    working_hours: dict | None = None
    commission_percent: float | None = None
    signature_url: str | None = None
    is_active: bool | None = None


class UpdateMyDoctorRequest(BaseModel):
    """A doctor updating their own profile. Name and photo are Owner-owned
    (they must stay put on their own PATCH /doctors/{id}); contact info,
    specialty, bio, education, and the weekly schedule are self-service."""

    phone: str | None = None
    email: str | None = None
    specialty: str | None = None
    bio: str | None = None
    license_number: str | None = None
    qualifications: list[QualificationEntry] | None = None
    specializations: list[str] | None = None
    working_hours: dict | None = None


class DoctorResponse(BaseModel):
    id: UUID
    practice_id: UUID
    user_id: UUID | None
    name: str
    email: str
    phone: str | None
    specialty: str | None
    license_number: str | None
    bio: str | None
    photo_url: str | None
    capabilities: list[str]
    qualifications: list[QualificationEntry]
    specializations: list[str]
    working_hours: dict
    commission_percent: float | None
    signature_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Doctor <-> Procedure (fee per doctor per procedure) --------------------

class CreateDoctorProcedureRequest(BaseModel):
    procedure_id: UUID
    consultation_fee: float | None = None
    surgery_fee: float | None = None


class UpdateDoctorProcedureRequest(BaseModel):
    consultation_fee: float | None = None
    surgery_fee: float | None = None
    is_active: bool | None = None


class DoctorProcedureResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    procedure_id: UUID
    consultation_fee: float | None
    surgery_fee: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Doctor availability overrides ------------------------------------------

class CreateDoctorAvailabilityRequest(BaseModel):
    date: datetime
    is_available: bool = False
    hours: list[dict] = []
    reason: str | None = None


class DoctorAvailabilityResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    date: datetime
    is_available: bool
    hours: list[dict]
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Personal time blocks (private, no effect on booking/availability) -----

class CreateDoctorTimeBlockRequest(BaseModel):
    title: str
    note: str | None = None
    start_time: datetime
    end_time: datetime


class DoctorTimeBlockResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    title: str
    note: str | None
    start_time: datetime
    end_time: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# --- "Today at a glance" dashboard ------------------------------------------

class WaitingRoomEntry(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    patient_name: str
    appointment_type: str
    status: str
    checked_in_at: datetime | None
    with_doctor_at: datetime | None


class PendingNoteEntry(BaseModel):
    note_id: UUID
    patient_id: UUID
    patient_name: str
    appointment_id: UUID | None
    created_at: datetime


class DoctorAlertEntry(BaseModel):
    type: str
    patient_id: UUID
    patient_name: str
    message: str
    since: datetime


class DoctorTodayResponse(BaseModel):
    waiting_room: list[WaitingRoomEntry]
    pending_notes: list[PendingNoteEntry]
    pending_consent_count: int
    alerts: list[DoctorAlertEntry]
