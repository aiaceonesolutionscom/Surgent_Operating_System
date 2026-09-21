from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.ai_receptionist import (
    HandleCallResponse,
    ChatMessageResponse,
    TranslateResponse,
    SendReminderResponse,
    AIReceptionistOverviewResponse,
    SystemPromptResponse,
    MarketSettingsUpdate,
    MarketsSettingsResponse,
    HumanAvailabilityUpdate,
    HumanAvailabilityResponse,
)
from src.services.ai_receptionist.voice_chat_service import VoiceChatService
from src.services.ai_receptionist.reminder_service import ReminderService
from src.services.ai_receptionist.translation_service import TranslationService
from src.services.ai_receptionist.overview_service import AIReceptionistOverviewService
from src.services.ai_receptionist.system_prompt_service import SystemPromptService
from src.services.ai_receptionist.market_settings_service import MarketSettingsService
from src.services.ai_receptionist.human_availability_service import HumanAvailabilityService


class AIReceptionistController:
    def __init__(self):
        self.voice_chat = VoiceChatService()
        self.reminders = ReminderService()
        self.translation = TranslationService()
        self.overview = AIReceptionistOverviewService()
        self.system_prompt = SystemPromptService()
        self.markets = MarketSettingsService()
        self.human_availability = HumanAvailabilityService()

    async def handle_call(self, db: AsyncSession, user: User) -> HandleCallResponse:
        result = await self.voice_chat.handle_call(db, user.practice_id, performed_by="ai_agent")
        return HandleCallResponse(**result)

    async def process_message(self, db: AsyncSession, user: User, message: str) -> ChatMessageResponse:
        response = await self.voice_chat.process_message(db, user.practice_id, message, performed_by="ai_agent")
        return ChatMessageResponse(response=response)

    async def translate(self, db: AsyncSession, user: User, text: str, target_language: str) -> TranslateResponse:
        translated = await self.translation.translate(db, user.practice_id, text, target_language, performed_by=str(user.id))
        return TranslateResponse(translated_text=translated)

    async def send_reminder(self, db: AsyncSession, user: User, appointment_id: UUID) -> SendReminderResponse:
        result = await self.reminders.send_reminder(db, user.practice_id, appointment_id, performed_by="ai_agent")
        return SendReminderResponse(**result)

    async def get_overview(self, db: AsyncSession, user: User) -> AIReceptionistOverviewResponse:
        return await self.overview.get_overview(db, user.practice_id)

    async def get_system_prompt(self, db: AsyncSession, user: User) -> SystemPromptResponse:
        return await self.system_prompt.get_system_prompt(db, user.practice_id)

    async def update_system_prompt(self, db: AsyncSession, user: User, custom_instructions: str) -> SystemPromptResponse:
        return await self.system_prompt.save_custom_instructions(db, user.practice_id, custom_instructions, user.id)

    async def get_market_settings(self, db: AsyncSession, user: User) -> MarketsSettingsResponse:
        return await self.markets.get_settings(db, user.practice_id)

    async def save_market_settings(
        self, db: AsyncSession, user: User, code: str, payload: MarketSettingsUpdate
    ) -> MarketsSettingsResponse:
        return await self.markets.save_market(db, user.practice_id, code, payload, user.id)

    async def clear_market_settings(self, db: AsyncSession, user: User, code: str) -> MarketsSettingsResponse:
        return await self.markets.clear_market(db, user.practice_id, code, user.id)

    async def get_human_availability(self, db: AsyncSession, user: User) -> HumanAvailabilityResponse:
        return await self.human_availability.get_settings(db, user.practice_id)

    async def save_human_availability(
        self, db: AsyncSession, user: User, payload: HumanAvailabilityUpdate
    ) -> HumanAvailabilityResponse:
        return await self.human_availability.save_settings(db, user.practice_id, payload)
