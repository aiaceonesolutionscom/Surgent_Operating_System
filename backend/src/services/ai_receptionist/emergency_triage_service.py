from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation, ConversationStatus
from src.models.message import Message, MessageRole
from src.models.practice import Practice
from src.models.patient import Patient
from src.services.llm.llm_service import LLMService
from src.services.agent_log.agent_log_service import AgentLogService
from src.services.ai_receptionist.human_availability_service import HumanAvailabilityService


# High-confidence emergency keywords that should trigger immediate escalation
# These are clinical red flags that require urgent human medical attention
EMERGENCY_KEYWORDS = [
    "bleeding heavily",
    "bleeding won't stop",
    "severe bleeding",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "shortness of breath",
    "chest pain",
    "heart attack",
    "stroke",
    "unconscious",
    "passed out",
    "fainted",
    "seizure",
    "allergic reaction",
    "anaphylaxis",
    "throat swelling",
    "tongue swelling",
    "can't swallow",
    "high fever",
    "fever over 103",
    "fever over 39",
    "severe pain",
    "worst pain",
    "unbearable pain",
    "signs of infection",
    "pus",
    "foul smell",
    "wound opened",
    "incision opened",
    "stitches came out",
    "sutures came out",
    "hematoma",
    "large bruise",
    "numbness",
    "loss of sensation",
    "can't move",
    "paralysis",
    "vision loss",
    "blindness",
    "slurred speech",
    "confusion",
    "disoriented",
]


class EmergencyTriageService:
    """
    Emergency triage for patient messages — detects clinical red flags
    and escalates to human staff immediately.

    This is a safety-critical layer that runs BEFORE the AI Receptionist
    generates a reply. If an emergency is detected, the conversation is
    flagged NEEDS_ATTENTION and staff are notified.
    """

    def __init__(self):
        self.llm = LLMService()
        self.agent_log = AgentLogService()
        self.human_availability = HumanAvailabilityService()

    async def check_for_emergency(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patient: Patient,
        conversation: Conversation,
        message_text: str,
    ) -> tuple[bool, str | None]:
        """
        Check if a patient message indicates a medical emergency.
        Returns (is_emergency, escalation_reason).
        """
        text = message_text.lower()

        # Quick keyword screening
        matched_keywords = [kw for kw in EMERGENCY_KEYWORDS if kw in text]

        if not matched_keywords:
            return False, None

        # LLM confirmation to reduce false positives
        is_emergency, reason = await self._llm_confirm_emergency(message_text, matched_keywords)

        if is_emergency:
            await self._escalate_emergency(db, practice_id, patient, conversation, reason, matched_keywords)

        return is_emergency, reason if is_emergency else None

    async def _llm_confirm_emergency(self, message: str, matched_keywords: list[str]) -> tuple[bool, str]:
        """
        Use LLM to confirm if the message truly indicates a medical emergency
        requiring immediate human attention.
        """
        system_prompt = (
            "You are a medical safety triage system for a plastic surgery clinic. "
            "A patient sent a message that contains these potential emergency keywords: "
            f"{', '.join(matched_keywords)}. "
            "The full message: \"{message}\"\n\n"
            "Determine if this represents a genuine medical emergency requiring "
            "IMMEDIATE human clinical staff attention (not just a routine question). "
            "Consider context: post-op patients may describe normal symptoms. "
            "Only flag TRUE emergencies: severe bleeding, breathing difficulty, "
            "chest pain, signs of stroke, anaphylaxis, wound dehiscence, "
            "high fever with signs of sepsis, neurological deficits.\n\n"
            "Respond with JSON only: "
            "{{\"is_emergency\": true/false, \"reason\": \"brief explanation\"}}"
        )

        try:
            result = await self.llm.chat_fast(
                messages=[{"role": "user", "content": message}],
                system_prompt=system_prompt,
                json_mode=True,
                max_tokens=200,
            )
            import json
            data = json.loads(result)
            return bool(data.get("is_emergency")), data.get("reason", "Emergency keywords detected")
        except Exception:
            # On LLM failure, err on the side of caution
            return True, f"Emergency keywords detected: {', '.join(matched_keywords)} (LLM confirmation failed)"

    async def _escalate_emergency(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patient: Patient,
        conversation: Conversation,
        reason: str,
        matched_keywords: list[str],
    ) -> None:
        """Escalate conversation to NEEDS_ATTENTION and log the emergency."""
        # Set conversation status
        conversation.status = ConversationStatus.NEEDS_ATTENTION
        conversation.extra_data = {
            **(conversation.extra_data or {}),
            "ai_paused": True,
            "emergency_flag": True,
            "emergency_reason": reason,
            "emergency_keywords": matched_keywords,
            "emergency_detected_at": datetime.now(timezone.utc).isoformat(),
        }

        # Add system message
        db.add(Message(
            conversation_id=conversation.id,
            role=MessageRole.SYSTEM,
            content=f"🚨 EMERGENCY DETECTED: {reason}. Keywords: {', '.join(matched_keywords)}. Patient needs immediate clinical attention.",
            content_type="text",
        ))

        # Log for audit trail
        await self.agent_log.log(
            db,
            practice_id,
            agent_type="emergency_triage",
            action="emergency_escalated",
            details={
                "patient_id": str(patient.id),
                "conversation_id": str(conversation.id),
                "reason": reason,
                "keywords": matched_keywords,
            },
            performed_by="ai_agent",
        )

        # Notify staff availability
        await self.human_availability.status_for_practice(db, practice_id)
        # The human_availability_service will handle notification logic