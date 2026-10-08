import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, func, Boolean, false
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

import enum


class ConversationChannel(str, enum.Enum):
    PHONE = "phone"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WEB_CHAT = "web_chat"
    EMAIL = "email"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    NEEDS_ATTENTION = "needs_attention"
    RESOLVED = "resolved"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable: platform landing-chat (Aria) sales conversations aren't scoped
    # to any clinic's practice — a clinic-buyer chat is the platform's own.
    practice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[ConversationChannel] = mapped_column(Enum(ConversationChannel), nullable=False)
    channel_conversation_id: Mapped[str] = mapped_column(String(255), nullable=True)
    # Drives the dashboard's "Agent Sessions" / "Needs attention" split
    # (frontend/src/app/dashboard/sessions/) — an agent sets NEEDS_ATTENTION
    # when it escalates to a human (see emergency_triage_agent/README.md),
    # staff resolve it back down via POST /conversations/{id}/resolve.
    status: Mapped[ConversationStatus] = mapped_column(Enum(ConversationStatus), default=ConversationStatus.ACTIVE)
    # Named `extra_data`, not `metadata` — `metadata` is a reserved attribute
    # name on SQLAlchemy's Declarative Base (it's the MetaData registry) and
    # raises InvalidRequestError at class-definition time if used as a column.
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    # True for demo rows seeded into a new practice (services/demo/
    # sample_data_service.py). Every pre-existing row is real (the column was
    # added NOT NULL DEFAULT false), and "clear sample data" only ever deletes
    # rows with this flag set.
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    patient = relationship("Patient", back_populates="conversations")
