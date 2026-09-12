from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.llm.llm_service import LLMService
from src.services.twilio.twilio_service import TwilioService
from src.services.agent_log.agent_log_service import AgentLogService

_SYSTEM_PROMPT = (
    "You are a warm, professional AI receptionist for an aesthetic medicine practice. "
    "Answer calls and messages politely, collect the patient's name and reason for contact, "
    "and offer to book a consultation. Reply in 1-2 short sentences — be concise."
)


class VoiceChatService:
    """Handles inbound calls (via Twilio) and chat messages — the 24/7
    automated front-desk voice/text answering capability. Logged as
    `agent_type="ai_receptionist"` so AIReceptionistOverviewService can count
    real call volume."""

    def __init__(self):
        self.llm = LLMService()
        self.twilio = TwilioService()
        self.agent_log = AgentLogService()

    async def handle_call(self, db: AsyncSession, practice_id: UUID, performed_by: str) -> dict:
        # tier="low" — a warm greeting/FAQ exchange is "general chat", the
        # exact traffic LLMService's own tier strategy documents as
        # Mistral-appropriate (unlike an actual booking/escalation decision,
        # which stays tier="high"/OpenAI elsewhere in the app).
        response_text = await self.llm.chat(
            messages=[{"role": "user", "content": "A patient is calling. Greet them warmly."}],
            system_prompt=_SYSTEM_PROMPT,
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
        response = await self.llm.chat(
            messages=[{"role": "user", "content": message}],
            system_prompt=_SYSTEM_PROMPT,
            tier="low",
            max_tokens=400,
        )
        await self.agent_log.log(
            db, practice_id, agent_type="ai_receptionist", action="message_handled",
            details={"message_preview": message[:200]}, performed_by=performed_by,
        )
        return response
