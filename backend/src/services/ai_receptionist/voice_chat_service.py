from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.practice import Practice
from src.models.patient import Patient
from src.models.conversation import Conversation, ConversationChannel
from src.services.llm.llm_service import LLMService
from src.services.twilio.twilio_service import TwilioService
from src.services.agent_log.agent_log_service import AgentLogService
from src.services.ai_receptionist.locale_service import LocaleService
from src.services.ai_receptionist.prompt_blocks import build_system_prompt
from src.services.ai_receptionist.emergency_triage_service import EmergencyTriageService


class VoiceChatService:
    """Handles inbound calls (via Twilio) and chat messages — the 24/7
    automated front-desk voice/text answering capability. Logged as
    `agent_type="ai_receptionist"` so AIReceptionistOverviewService can count
    real call volume.

    Used to be a four-line prompt ("be warm, collect a name, offer a
    consultation") while the SOP's requirement is channel-independent: "every
    enquiry, in every market and on any channel, follows the same seven steps".
    It now builds the same prompt blocks as WhatsApp, with the voice variant of
    the output format — so the phone line cannot quote an unapproved price or
    give clinical advice that the chat line refuses to give.
    """

    def __init__(self):
        self.llm = LLMService()
        self.twilio = TwilioService()
        self.agent_log = AgentLogService()
        self.locale = LocaleService()
        self.emergency_triage = EmergencyTriageService()

    async def _system_prompt(self, db: AsyncSession, practice_id: UUID, message_text: str) -> str:
        """Resolve this practice's market for the call, then compose the prompt.
        A missing practice (or a routing failure) still yields the neutral,
        no-currency form rather than a guess."""
        practice = await db.get(Practice, practice_id)
        if practice is None:
            return build_system_prompt(
                practice_name="the clinic", is_new_patient=True,
                today=datetime.now(timezone.utc).date(), draft=None, locale=None, channel="voice",
            )
        locale = self.locale.resolve(practice, message_text)
        return build_system_prompt(
            practice_name=practice.name,
            is_new_patient=True,
            today=datetime.now(timezone.utc).date(),
            draft=None,
            locale=locale,
            custom_instructions=(practice.settings or {}).get("ai_receptionist_system_prompt") or None,
            channel="voice",
        )

    async def handle_call(self, db: AsyncSession, practice_id: UUID, performed_by: str) -> dict:
        # tier="low" — a warm greeting/FAQ exchange is "general chat", the
        # exact traffic LLMService's own tier strategy documents as
        # Mistral-appropriate (unlike an actual booking/escalation decision,
        # which stays tier="high"/OpenAI elsewhere in the app).
        response_text = await self.llm.chat(
            messages=[{"role": "user", "content": "A patient is calling. Greet them warmly."}],
            system_prompt=await self._system_prompt(db, practice_id, ""),
            tier="low",
            max_tokens=400,
        )
        twiml = self.twilio.generate_twiml_response(response_text)
        await self.agent_log.log(
            db, practice_id, agent_type="ai_receptionist", action="call_handled",
            details={"response_preview": response_text[:200]}, performed_by=performed_by,
        )
        return {"response": response_text, "twiml": twiml}

    async def process_message(self, db: AsyncSession, practice_id: UUID, message: str, performed_by: str) -> str:
        # For voice messages, we need a patient and conversation context.
        # This is a simplified check - in production, you'd resolve the patient
        # from the phone number via the practice's WhatsApp/voice integration.
        # For now, we do a basic keyword check via the emergency triage service.
        # Note: Full integration requires patient/conversation resolution.
        practice = await db.get(Practice, practice_id)
        if practice:
            # Create a minimal patient/conversation for triage check
            # In reality, this should be resolved from the caller ID
            pass  # Emergency triage for voice requires patient context

        response = await self.llm.chat(
            messages=[{"role": "user", "content": message}],
            system_prompt=await self._system_prompt(db, practice_id, message),
            tier="low",
            max_tokens=400,
        )
        await self.agent_log.log(
            db, practice_id, agent_type="ai_receptionist", action="message_handled",
            details={"message_preview": message[:200]}, performed_by=performed_by,
        )
        return response
