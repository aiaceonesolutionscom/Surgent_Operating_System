from __future__ import annotations
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.patient import Patient
from src.schemas.patient_portal import PatientIntakeRequest
from src.services.llm.llm_service import LLMService

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are drafting a short, doctor-facing pre-consultation summary from a patient's own intake submission at "
    "a plastic surgery clinic. In 2-4 plain-language sentences, flag anything clinically relevant the doctor "
    "should notice before the first consultation — allergy conflicts, smoking combined with a planned surgical "
    "procedure, medications with common surgical interactions, or prior surgical complications. Never diagnose "
    "or recommend a treatment — that decision belongs to the doctor. If nothing about the intake stands out, say "
    "so briefly rather than padding the summary."
)


class PatientIntakeService:
    """Turns a patient's own pre-consultation intake submission (structured
    history fields the Portal already has real UI slots for — see Patient's
    Week 2 profile-depth columns) into a short summary a doctor can read in
    seconds instead of reading the raw form. AI's role here is strictly
    summarize → flag, never diagnose, matching this project's established
    AI-boundary convention (see PostOpFollowUpService's own docstring)."""

    def __init__(self):
        self.llm = LLMService()

    async def submit_intake(self, db: AsyncSession, patient: Patient, data: PatientIntakeRequest) -> Patient:
        patient.allergies = data.allergies
        patient.surgical_history = data.surgical_history
        patient.current_medications = data.current_medications
        if data.smoking_status:
            patient.smoking_status = data.smoking_status
        patient.previous_cosmetic_procedures = data.previous_cosmetic_procedures

        await self.refresh_intake_summary(db, patient, additional_notes=data.additional_notes)
        return patient

    async def refresh_intake_summary(
        self, db: AsyncSession, patient: Patient, additional_notes: str | None = None
    ) -> Patient:
        """Regenerate `intake_summary` from whatever structured intake fields
        are CURRENTLY on `patient` — reads the live row rather than a
        specific request payload, so it's reusable from any channel that
        writes intake fields (the patient-portal form via submit_intake
        above, and the AI-receptionist WhatsApp tool in inbound_service.py),
        keeping one summary-generation implementation instead of two."""
        try:
            summary = await self.llm.chat(
                messages=[{"role": "user", "content": self._format_intake(patient, additional_notes)}],
                system_prompt=_SYSTEM_PROMPT,
                tier="low",
            )
            patient.intake_summary = summary.strip()[:2000]
        except Exception:
            logger.exception("AI intake summary generation failed for patient %s — structured fields still saved", patient.id)
            patient.intake_summary = "AI summary unavailable right now — see the structured intake fields on this patient's profile."

        await db.flush()
        await db.refresh(patient)
        return patient

    def _format_intake(self, patient: Patient, additional_notes: str | None) -> str:
        parts = [
            f"Gender: {patient.gender or 'not specified'}",
            f"Pregnancy/nursing status: {patient.pregnancy_status.value if patient.pregnancy_status else 'not specified'}",
            f"Allergies: {patient.allergies or 'none reported'}",
            f"Surgical history: {patient.surgical_history or 'none reported'}",
            f"Current medications: {patient.current_medications or 'none reported'}",
            f"Smoking status: {patient.smoking_status or 'not specified'}",
            f"Previous cosmetic procedures: {patient.previous_cosmetic_procedures or 'none reported'}",
        ]
        if patient.medical_history:
            parts.append(f"Other medical history notes: {patient.medical_history}")
        if additional_notes:
            parts.append(f"Additional notes from patient: {additional_notes}")
        return "\n".join(parts)
