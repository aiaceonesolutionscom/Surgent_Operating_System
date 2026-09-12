from __future__ import annotations
import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.consultation_note import ConsultationNote, ConsultationNoteStatus
from src.models.doctor import Doctor
from src.models.patient import Patient
from src.schemas.clinical import CreateConsultationNoteRequest, UpdateConsultationNoteRequest, AIConsultationDraftResponse
from src.services.llm.llm_service import LLMService
from src.services.speech.speech_service import SpeechService
from src.server.exceptions import NotFoundException, AppException

logger = logging.getLogger(__name__)

_AI_DRAFT_SYSTEM_PROMPT = (
    "You turn a plastic surgery doctor's raw, freeform consultation notes (often dictated, unstructured) into a "
    "clean SOAP note plus a short follow-up task list. Respond with ONLY a JSON object, no other text, in exactly "
    "this shape:\n"
    '{"subjective": string, "objective": string, "assessment": string, "plan": string, '
    '"follow_up_tasks": [string, ...]}\n\n'
    "Subjective = what the patient reports in their own words/history. Objective = exam findings/measurements "
    "mentioned. Assessment = clinical impression. Plan = next steps/treatment direction. follow_up_tasks = short "
    "actionable items staff should do (e.g. \"Schedule pre-op bloodwork\", \"Send consent form for rhinoplasty\") "
    "— empty list if none apply. Only use what's actually in the doctor's notes below — never invent findings, "
    "diagnoses, or measurements that aren't there. If a section has nothing to go on, leave it as an empty string."
)


class ConsultationService:
    """Backs the Doctor's clinical documentation workflow — SOAP-structured
    notes (Subjective/Objective/Assessment/Plan) tied to a patient and
    optionally the appointment they were written during. Every method is
    practice-scoped; callers always pass the requesting user's own
    practice_id."""

    def __init__(self):
        self.llm = LLMService()
        self.speech = SpeechService()

    async def transcribe_dictation(self, audio_bytes: bytes, filename: str) -> str:
        """Voice dictation for the Consultation Assistant's raw-notes box —
        same Groq Whisper backend already proven live for WhatsApp voice
        notes (see channels/green_api_poller.py), just a different caller.
        Doesn't touch the DB at all; purely audio-in, text-out."""
        if not self.speech.is_configured:
            raise AppException("Voice dictation isn't configured for this environment (missing Groq API key)")
        try:
            return await self.speech.transcribe(audio_bytes, filename=filename)
        except Exception as exc:
            raise AppException(f"Transcription failed: {exc}")

    async def ai_draft(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID, raw_notes: str
    ) -> AIConsultationDraftResponse:
        """Consultation Assistant (Week 4) — drafts a SOAP note + follow-up
        tasks from a doctor's own freeform/dictated notes. Purely a drafting
        aid: the doctor still reviews and edits before saving via the normal
        create_note flow — this never writes a ConsultationNote itself."""
        patient_result = await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id)
        )
        patient = patient_result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")

        context = f"Chief complaint on file: {patient.chief_complaint or 'none recorded'}\n\nDoctor's raw notes:\n{raw_notes}"

        # tier="low" (free Mistral, Groq/OpenAI fallback on rate-limit) is a
        # deliberate choice, not an oversight — a real tier="high" call goes
        # straight to OpenAI with no fallback (see LLMService._client_and_model's
        # own comment), and OPENAI_API_KEY is still a placeholder in this
        # environment; forcing "high" would break this feature outright
        # rather than improve it. Revisit once a real OpenAI key is set.
        async def _call_and_parse() -> dict:
            raw = await self.llm.chat(
                messages=[{"role": "user", "content": context}],
                system_prompt=_AI_DRAFT_SYSTEM_PROMPT,
                tier="low",
                json_mode=True,
            )
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(cleaned)

        try:
            try:
                data = await _call_and_parse()
            except (json.JSONDecodeError, ValueError):
                # One retry — a malformed response from a free-tier model is
                # an occasional real hiccup, not necessarily worth failing
                # the doctor's whole draft attempt over.
                logger.warning("Consultation AI draft returned malformed JSON for patient %s, retrying once", patient_id)
                data = await _call_and_parse()

            return AIConsultationDraftResponse(
                subjective=str(data.get("subjective") or ""),
                objective=str(data.get("objective") or ""),
                assessment=str(data.get("assessment") or ""),
                plan=str(data.get("plan") or ""),
                follow_up_tasks=[str(t) for t in (data.get("follow_up_tasks") or [])],
            )
        except Exception as exc:
            logger.exception("Consultation AI draft failed for patient %s", patient_id)
            raise AppException(f"AI draft generation failed: {exc}")

    async def _resolve_doctor(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> Doctor:
        result = await db.execute(select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id))
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise NotFoundException("No doctor profile linked to this account")
        return doctor

    async def create_note(
        self, db: AsyncSession, practice_id: UUID, user_id: UUID, data: CreateConsultationNoteRequest
    ) -> ConsultationNote:
        doctor = await self._resolve_doctor(db, practice_id, user_id)

        patient_result = await db.execute(
            select(Patient).where(Patient.id == data.patient_id, Patient.practice_id == practice_id)
        )
        if patient_result.scalar_one_or_none() is None:
            raise NotFoundException("Patient not found")

        note = ConsultationNote(
            practice_id=practice_id,
            patient_id=data.patient_id,
            doctor_id=doctor.id,
            appointment_id=data.appointment_id,
            chief_complaint=data.chief_complaint,
            subjective=data.subjective,
            objective=data.objective,
            assessment=data.assessment,
            plan=data.plan,
            status=ConsultationNoteStatus(data.status),
        )
        db.add(note)
        await db.flush()
        await db.refresh(note)
        return note

    async def list_for_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> list[ConsultationNote]:
        query = (
            select(ConsultationNote)
            .where(ConsultationNote.practice_id == practice_id, ConsultationNote.patient_id == patient_id)
            .order_by(ConsultationNote.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_note(self, db: AsyncSession, practice_id: UUID, note_id: UUID) -> ConsultationNote:
        query = select(ConsultationNote).where(ConsultationNote.id == note_id, ConsultationNote.practice_id == practice_id)
        result = await db.execute(query)
        note = result.scalar_one_or_none()
        if note is None:
            raise NotFoundException("Consultation note not found")
        return note

    async def update_note(
        self, db: AsyncSession, practice_id: UUID, note_id: UUID, data: UpdateConsultationNoteRequest
    ) -> ConsultationNote:
        note = await self.get_note(db, practice_id, note_id)
        if note.status == ConsultationNoteStatus.FINAL:
            raise AppException("This note has been finalized — create a new note instead of editing it.")

        fields = data.model_dump(exclude_unset=True)
        if "status" in fields:
            fields["status"] = ConsultationNoteStatus(fields["status"])
        for field, value in fields.items():
            setattr(note, field, value)
        await db.flush()
        await db.refresh(note)
        return note
