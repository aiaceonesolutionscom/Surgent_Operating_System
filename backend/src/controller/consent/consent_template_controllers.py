from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.consent_template import (
    CreateConsentTemplateRequest,
    UpdateConsentTemplateRequest,
    ConsentTemplateResponse,
)
from src.services.consent.consent_template_services import ConsentTemplateService


class ConsentTemplateController:
    def __init__(self):
        self.service = ConsentTemplateService()

    async def create_template(self, db: AsyncSession, user: User, data: CreateConsentTemplateRequest) -> ConsentTemplateResponse:
        template = await self.service.create_template(db, user.practice_id, data.document_type, data.body, data.sections)
        return ConsentTemplateResponse.model_validate(template)

    async def list_templates(self, db: AsyncSession, user: User) -> list[ConsentTemplateResponse]:
        templates = await self.service.list_templates(db, user.practice_id)
        return [ConsentTemplateResponse.model_validate(t) for t in templates]

    async def update_template(
        self, db: AsyncSession, user: User, template_id: UUID, data: UpdateConsentTemplateRequest
    ) -> ConsentTemplateResponse:
        template = await self.service.update_template(
            db, user.practice_id, template_id, data.body, data.is_active, data.sections
        )
        return ConsentTemplateResponse.model_validate(template)
