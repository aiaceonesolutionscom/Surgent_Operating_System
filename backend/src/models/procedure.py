import uuid
from datetime import datetime

from sqlalchemy import String, Text, Numeric, DateTime, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    # Duration of ONE session/visit — a 6-session laser package and a single
    # Botox visit both just set this to their own per-visit length; the
    # number of visits lives in `default_session_count` below.
    duration_minutes: Mapped[int] = mapped_column(nullable=True)
    # How many visits this procedure normally takes to complete (hair
    # transplant, laser hair removal, a multi-syringe filler course, ...).
    # 1 = the common case, a single-visit procedure — every existing row
    # defaults here, so nothing already in the system needs to change
    # behavior. When a TreatmentPlanItem is created for this procedure, this
    # value seeds `TreatmentPlanItem.sessions_total`, which a doctor can
    # still adjust per-patient afterward.
    default_session_count: Mapped[int] = mapped_column(Integer, default=1)
    # Template pre-visit checklist — list of plain strings (e.g. "Confirm no
    # recent Accutane use", "Numbing cream applied") — copied onto every new
    # SessionVisit.checklist as {item, checked: False, checked_by: None,
    # checked_at: None} when a session is created, same shape as
    # Surgery.pre_op_checklist. Empty by default; a practice that never
    # bothers to configure one just gets sessions with no checklist, not an
    # error.
    default_checklist: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    practice = relationship("Practice", back_populates="procedures")
