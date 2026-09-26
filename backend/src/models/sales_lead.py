import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class SalesLeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    LOST = "lost"


class SalesLeadSource(str, enum.Enum):
    ARIA_LANDING_CHAT = "aria_landing_chat"
    DEMO_FORM = "demo_form"
    BOOK_CONSULTATION = "book_consultation"


class SalesLead(Base):
    """Platform-level lead: a clinic owner/buyer who reached the Aiaceone
    sales team through the marketing site's AI chat (Aria). Deliberately NOT
    practice-scoped — this is the platform's own pipeline, not a clinic's
    patient lead (which stays a Patient row belonging to the demo practice)."""

    __tablename__ = "sales_leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=True)
    # Concise summary of what the buyer is looking for (chosen plan/integration
    # questions/team size). Written by Aria from the chat.
    message: Mapped[str] = mapped_column(Text, nullable=True)
    source: Mapped[SalesLeadSource] = mapped_column(
        Enum(SalesLeadSource), nullable=False, default=SalesLeadSource.ARIA_LANDING_CHAT
    )
    status: Mapped[SalesLeadStatus] = mapped_column(
        Enum(SalesLeadStatus), nullable=False, default=SalesLeadStatus.NEW
    )
    # The landing-chat conversation thread this lead came from.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # SLA tracking: 24-hour response commitment from sales team
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())