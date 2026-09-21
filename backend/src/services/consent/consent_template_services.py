from __future__ import annotations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.consent_document import ConsentTemplate
from src.server.exceptions import NotFoundException


def flatten_sections_to_text(sections: dict) -> str:
    """Renders a ConsentTemplate.sections JSONB structure into plain text —
    used to keep `body` in sync whenever `sections` is written, so any code
    still reading `.body` directly (previews, search) never breaks even once
    a template has moved to the structured, admin-configurable shape."""
    lines: list[str] = []
    for section in sections.get("treatment_sections") or []:
        lines.append(str(section.get("treatment_type") or "Treatment"))
        for group in section.get("clause_groups") or []:
            lines.append(str(group.get("heading") or ""))
            for clause in group.get("clauses") or []:
                lines.append(f"- {clause}")
        lines.append("")
    photography = sections.get("photography_consent") or {}
    if photography.get("records_consent_clause"):
        lines.append("Consent to medical photography")
        lines.append(str(photography["records_consent_clause"]))
        lines.append("")
    statement = sections.get("patient_statement") or {}
    if statement.get("clauses"):
        lines.append("Patient statement")
        for clause in statement["clauses"]:
            lines.append(f"- {clause}")
    return "\n".join(lines).strip()


class ConsentTemplateService:
    """The LIVE, editable wording behind each consent type — see
    models/consent_document.py's ConsentTemplate docstring for why editing
    never touches an already-signed ConsentDocument's own snapshot."""

    async def create_template(
        self, db: AsyncSession, practice_id: UUID, document_type: str, body: str, sections: dict | None = None
    ) -> ConsentTemplate:
        # `sections`, when given, is the source of truth — `body` is derived
        # from it so anything still reading `.body` keeps working. An empty
        # `body` with real `sections` is filled in automatically rather than
        # left blank.
        if sections and not body.strip():
            body = flatten_sections_to_text(sections)
        template = ConsentTemplate(practice_id=practice_id, document_type=document_type, body=body, sections=sections, version=1)
        db.add(template)
        await db.flush()
        await db.refresh(template)
        return template

    async def list_templates(self, db: AsyncSession, practice_id: UUID) -> list[ConsentTemplate]:
        result = await db.execute(
            select(ConsentTemplate)
            .where(ConsentTemplate.practice_id == practice_id)
            .order_by(ConsentTemplate.document_type, ConsentTemplate.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_template(self, db: AsyncSession, practice_id: UUID, template_id: UUID) -> ConsentTemplate:
        result = await db.execute(
            select(ConsentTemplate).where(ConsentTemplate.id == template_id, ConsentTemplate.practice_id == practice_id)
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise NotFoundException("Consent template not found")
        return template

    async def get_active_for_type(self, db: AsyncSession, practice_id: UUID, document_type: str) -> ConsentTemplate | None:
        result = await db.execute(
            select(ConsentTemplate)
            .where(
                ConsentTemplate.practice_id == practice_id,
                ConsentTemplate.document_type == document_type,
                ConsentTemplate.is_active == True,  # noqa: E712
            )
            .order_by(ConsentTemplate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_template(
        self,
        db: AsyncSession,
        practice_id: UUID,
        template_id: UUID,
        body: str | None,
        is_active: bool | None,
        sections: dict | None = None,
    ) -> ConsentTemplate:
        template = await self.get_template(db, practice_id, template_id)
        # Editing the body OR sections is what versions — bumping the
        # counter in place rather than inserting a new row, since
        # ConsentDocument already snapshots content+sections+version
        # permanently at document-creation time (that's what makes an edit
        # here safe in the first place).
        changed = False
        if sections is not None and sections != template.sections:
            template.sections = sections
            body = body if body is not None else flatten_sections_to_text(sections)
            changed = True
        if body is not None and body != template.body:
            template.body = body
            changed = True
        if changed:
            template.version += 1
        if is_active is not None:
            template.is_active = is_active
        await db.flush()
        await db.refresh(template)
        return template
