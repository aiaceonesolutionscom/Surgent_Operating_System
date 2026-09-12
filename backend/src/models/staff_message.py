import uuid
from datetime import datetime

from sqlalchemy import Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class StaffConversation(Base):
    """A one-to-one chat between any two active users of a practice
    (Owner, Doctor, Receptionist, ...). Participants are stored in canonical
    order (user_a_id < user_b_id) so the conversation is unique no matter
    which side started it."""

    __tablename__ = "staff_conversations"
    __table_args__ = (
        UniqueConstraint("practice_id", "user_a_id", "user_b_id", name="uq_staff_conversations_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    user_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    practice = relationship("Practice", back_populates="staff_conversations")
    messages = relationship(
        "StaffMessage", back_populates="conversation", cascade="all, delete-orphan",
        order_by="StaffMessage.created_at",
    )


class StaffMessage(Base):
    """One message inside a StaffConversation — `conversation_id` says which
    thread it belongs to, `sender_id` who wrote it."""

    __tablename__ = "staff_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_conversations.id"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="text")
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    practice = relationship("Practice", back_populates="staff_messages")
    conversation = relationship("StaffConversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])