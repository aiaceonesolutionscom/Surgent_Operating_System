from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.practice import Practice
from src.schemas.ai_receptionist import SystemPromptResponse
from src.services.ai_receptionist.locale_service import LocaleService
from src.services.channels.inbound_service import _system_prompt

_SETTINGS_KEY = "ai_receptionist_system_prompt"
_SETTINGS_UPDATED_AT_KEY = "ai_receptionist_system_prompt_updated_at"
_SETTINGS_UPDATED_BY_KEY = "ai_receptionist_system_prompt_updated_by"


class SystemPromptService:
    """View/edit the WhatsApp AI Receptionist system prompt.

    The base prompt template lives in inbound_service._system_prompt; whatever
    a practice owner writes as `custom_instructions` is appended to it on every
    inbound message. GET is available to anyone who can open the monitor
    (Owner/Doctor/Receptionist); PUT is Owner-only — enforced in the router."""

    def __init__(self):
        self.locale = LocaleService()

    async def get_system_prompt(self, db: AsyncSession, practice_id: UUID) -> SystemPromptResponse:
        practice = await db.get(Practice, practice_id)
        settings = (practice.settings or {}) if practice else {}
        return self._to_response(practice, settings)

    async def save_custom_instructions(
        self, db: AsyncSession, practice_id: UUID, custom_instructions: str, updated_by: UUID
    ) -> SystemPromptResponse:
        practice = await db.get(Practice, practice_id)
        settings = dict((practice.settings or {}) if practice else {})
        if custom_instructions.strip():
            settings[_SETTINGS_KEY] = custom_instructions.strip()
        else:
            settings.pop(_SETTINGS_KEY, None)
        settings[_SETTINGS_UPDATED_AT_KEY] = datetime.now(timezone.utc).isoformat()
        settings[_SETTINGS_UPDATED_BY_KEY] = str(updated_by)
        practice.settings = settings
        await db.commit()
        return self._to_response(practice, settings)

    def _to_response(self, practice: Practice | None, settings: dict) -> SystemPromptResponse:
        custom = settings.get(_SETTINGS_KEY) or ""
        # is_new_patient/today vary per conversation; the monitor shows the
        # standard new-patient form plus this practice's custom block — that
        # is exactly the prompt a first-time caller gets. The market block is
        # this practice's own home market, the same one a first message from an
        # unknown number routes to, so an owner can see the currency and price
        # list their receptionist will actually quote from.
        effective = _system_prompt(
            is_new_patient=True,
            today=datetime.now(timezone.utc).date(),
            draft=None,
            extra_instructions=custom or None,
            locale=self.locale.preview(practice) if practice else None,
            practice_name=practice.name if practice else "the clinic",
        )
        return SystemPromptResponse(
            system_prompt=effective,
            custom_instructions=custom,
            updated_at=settings.get(_SETTINGS_UPDATED_AT_KEY),
            updated_by=settings.get(_SETTINGS_UPDATED_BY_KEY),
        )