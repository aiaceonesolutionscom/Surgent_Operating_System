import enum
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, Date, Enum, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class PatientLifecycleStage(str, enum.Enum):
    INQUIRY = "inquiry"
    CONTACTED = "contacted"
    CONSULT_SCHEDULED = "consult_scheduled"
    CONSULT_COMPLETED = "consult_completed"
    TREATMENT_PLANNED = "treatment_planned"
    PATIENT = "patient"
    LOST = "lost"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    # A patient can have more than one reachable number (home, work, a
    # relative's) beyond the one primary `phone` above (used for portal OTP
    # delivery, WhatsApp receipts, etc.) — list of {number, label}.
    additional_phones: Mapped[list] = mapped_column(JSONB, default=list)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=True)
    medical_history: Mapped[dict] = mapped_column(JSONB, default=dict)
    consent_status: Mapped[bool] = mapped_column(default=False)
    plan_type: Mapped[str] = mapped_column(String(50), default="solo")  # "solo" or "enterprise"
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=True)  # What the patient described — what the AI assignment below is based on
    needs_surgery: Mapped[bool] = mapped_column(default=False)
    ai_agent_assigned: Mapped[str] = mapped_column(String(100), nullable=True)  # Which agent is handling this patient
    agent_status: Mapped[str] = mapped_column(String(20), default="inactive")  # "active" or "inactive"
    agent_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0)  # Per-agent cost tracking
    # CRM funnel stage — separate from the frontend's derived `status`
    # ("active"/"lead"), which stays booking-based (has_upcoming/has_completed
    # appointment) for backward compat. This is the richer, explicit stage a
    # front-desk/marketing workflow actually tracks a lead through.
    lifecycle_stage: Mapped[PatientLifecycleStage] = mapped_column(
        Enum(PatientLifecycleStage), nullable=False, default=PatientLifecycleStage.INQUIRY
    )
    lost_reason: Mapped[str] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=True)  # e.g. "Instagram", "Referral", "Walk-in"
    # Patient Portal — portal_id is a human-readable reference identifier
    # (e.g. "PT-2026-00042") staff can quote back to a patient; it plays no
    # role in login. Real auth is phone number + a one-time code sent over
    # WhatsApp/email (see patient_portal_auth_service.py) — replaces an
    # earlier static-PIN scheme (before that, a plaintext-link-token
    # scheme) entirely, since a clinic-assigned shared secret was never as
    # strong as a code delivered live to a channel only the patient
    # controls. portal_enabled still gates access on/off.
    portal_id: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    portal_enabled: Mapped[bool] = mapped_column(default=False)
    # Patient-chosen login PIN — stored ONLY as a salted PBKDF2-HMAC-SHA256
    # hash ("pbkdf2_sha256$iterations$salt$hash"), never plaintext, staff can
    # never see or set it. Null until the patient sets their own PIN during
    # first-time OTP login; once set, phone + PIN is the cheap daily login
    # (README: OTP costs money on every send, so OTP stays only as the
    # first-time / forgot-PIN recovery path). See
    # patient_portal_auth_service.py for hashing + verification.
    portal_pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Clinic one-time (disposable) login PIN — deliberately staff-visible, so
    # front desk can hand a patient a PIN on the spot and the patient logs in
    # with phone + this PIN (no OTP). Short-lived and single-use: valid only
    # until portal_temp_pin_expires_at and cleared on first successful login,
    # so a handed-over PIN can't be reused. It is NOT the patient's permanent
    # PIN (portal_pin_hash); after a one-time-PIN login the portal prompts the
    # patient to set their own PIN, exactly like the OTP first-login flow.
    portal_temp_pin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    portal_temp_pin_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Patient profile depth (Week 2) ---------------------------------
    gender: Mapped[str] = mapped_column(String(30), nullable=True)
    emergency_contact_name: Mapped[str] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str] = mapped_column(String(50), nullable=True)
    # List of {name, severity, reaction} — kept separate from the general
    # medical_history blob above so it's the one thing every clinical screen
    # can surface prominently without parsing free text.
    allergies: Mapped[list] = mapped_column(JSONB, default=list)
    # `medical_history` above stays as-is (general conditions); this is the
    # patient's own surgical history specifically — list of {procedure,
    # year, facility, notes}.
    surgical_history: Mapped[list] = mapped_column(JSONB, default=list)
    # List of {name, dosage, frequency} — current, not historical.
    current_medications: Mapped[list] = mapped_column(JSONB, default=list)
    smoking_status: Mapped[str] = mapped_column(String(30), nullable=True)
    # List of {procedure, year, provider} — cosmetic work done elsewhere,
    # before this practice; distinct from this practice's own TreatmentPlan
    # records.
    previous_cosmetic_procedures: Mapped[list] = mapped_column(JSONB, default=list)
    # Who specifically referred this patient (a person's name — "Dr. Ahmed",
    # "existing patient Sara Khan") — distinct from `source` above, which is
    # the marketing CHANNEL ("Instagram", "Referral", "Walk-in"). A lead can
    # have a channel of "Referral" and a referral_source naming exactly who.
    referral_source: Mapped[str] = mapped_column(String(255), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(50), nullable=True)
    # {"sms": true, "email": true, "whatsapp": false, ...}
    communication_preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    insurance_provider: Mapped[str] = mapped_column(String(255), nullable=True)
    insurance_number: Mapped[str] = mapped_column(String(100), nullable=True)

    # --- AI workflows (Week 4) ------------------------------------------
    # {interested_procedure, budget_signal, urgency, score (0-100), summary}
    # — written once by LeadQualificationService after a few inbound
    # WhatsApp messages, read-only from the frontend's perspective.
    qualification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Doctor-facing risk-flag summary generated from the patient's own
    # structured portal intake submission (allergies/history/medications
    # above) — separate from chief_complaint, which is the patient's own
    # words, not an AI-derived clinical summary.
    intake_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Clinical ownership + lifecycle (Patient Management redesign) ---
    # The one place a doctor-patient link is stored durably, as opposed to
    # the per-encounter doctor_id on Appointment/ConsultationNote/
    # TreatmentPlan — this is "whose patient is this," checked by
    # server/patient_access.py to hard-restrict a Doctor's access to only
    # their own assigned patients. Owner and Receptionist can both set/
    # change it (see patients_services.py's assign_doctor).
    assigned_doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    # Administrative status — orthogonal to lifecycle_stage (which tracks
    # CRM/funnel progress, not whether the record is still "live"). Archiving
    # is Owner-only, disables portal login, and blocks new appointments (see
    # patients_services.py.archive_patient / AppointmentsService.create_appointment).
    is_archived: Mapped[bool] = mapped_column(default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice", back_populates="patients")
    assigned_doctor = relationship("Doctor", foreign_keys=[assigned_doctor_id])
    photos = relationship("PatientPhoto", back_populates="patient", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    recovery_journals = relationship("RecoveryJournal", back_populates="patient", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="patient", cascade="all, delete-orphan")
    review_requests = relationship("ReviewRequest", back_populates="patient", cascade="all, delete-orphan")
    consent_documents = relationship("ConsentDocument", back_populates="patient", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="patient", cascade="all, delete-orphan")
