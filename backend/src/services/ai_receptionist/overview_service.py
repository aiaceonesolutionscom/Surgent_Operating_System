from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_log import AgentLog
from src.models.appointment import Appointment, AppointmentStatus
from src.models.conversation import Conversation
from src.models.message import Message
from src.models.patient import Patient, PatientLifecycleStage
from src.models.practice import Practice
from src.services.agent_costing.agent_costing_services import AgentCostingService
from src.schemas.ai_receptionist import (
    AIReceptionistOverviewResponse,
    ReceptionistActivityEntry,
    ReceptionistChannelStatus,
    ReceptionistHealth,
    ReceptionistPipeline,
)

# Each AgentLog action this module writes maps back to one of the
# pre-existing per-session cost rates (AgentCosting) — those rates predate
# the receptionist/appointment_reminder/multilingual_translation agents
# being merged into this one module, and stay keyed by their original slugs
# since the marketing catalog (frontend/src/data/agents/) still lists them
# separately.
_ACTION_TO_COST_SLUG = {
    "call_handled": "receptionist",
    "message_handled": "receptionist",
    "reminder_sent": "appointment_reminder",
    "message_translated": "multilingual_translation",
}

# Human-readable label + channel inference for the recent-activity feed.
_ACTION_LABELS = {
    "call_handled": "Call handled",
    "message_handled": "Message handled",
    "whatsapp_message_handled": "WhatsApp message handled",
    "whatsapp_ai_escalated": "Escalated to staff",
    "whatsapp_message_received": "WhatsApp message received",
    "whatsapp_message_received_ai_paused": "Received while AI paused",
    "whatsapp_message_received_ai_disabled": "Received while AI off",
    "reminder_sent": "Appointment reminder sent",
    "message_translated": "Message translated",
}
_ACTION_CHANNEL = {
    "call_handled": "phone",
    "message_handled": "whatsapp",
    "whatsapp_message_handled": "whatsapp",
    "whatsapp_ai_escalated": "whatsapp",
    "whatsapp_message_received": "whatsapp",
    "whatsapp_message_received_ai_paused": "whatsapp",
    "whatsapp_message_received_ai_disabled": "whatsapp",
    "reminder_sent": "whatsapp",
    "message_translated": "whatsapp",
}


def _summarize_details(details: dict) -> str | None:
    preview = (details or {}).get("incoming_preview")
    if isinstance(preview, str) and preview.strip():
        return preview[:90]
    return None


def _channel_statuses(settings: dict) -> list[ReceptionistChannelStatus]:
    ga = (settings or {}).get("green_api", {})
    whatsapp_connected = bool(ga.get("instance_id") and ga.get("api_token"))
    return [
        ReceptionistChannelStatus(
            channel="whatsapp",
            connected=whatsapp_connected,
            detail="Green API · Active" if whatsapp_connected else "Green API · not configured",
        ),
        ReceptionistChannelStatus(channel="instagram", connected=False, detail="Not connected yet"),
        ReceptionistChannelStatus(channel="facebook", connected=False, detail="Not connected yet"),
        ReceptionistChannelStatus(channel="phone", connected=False, detail="Twilio · not configured"),
    ]


class AIReceptionistOverviewService:
    """Real usage + cost analytics for the AI Receptionist, replacing the
    monitor page's old MOCK_RECEPTIONIST_STATS (and the mock-only funnel /
    channel / health / transcript widgets). Practice-scoped."""

    def __init__(self):
        self.costing = AgentCostingService()

    async def get_overview(self, db: AsyncSession, practice_id: UUID) -> AIReceptionistOverviewResponse:
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        day_ago = now - timedelta(days=1)

        all_time_counts = await self._counts_by_action(db, practice_id, since=None)
        recent_counts = await self._counts_by_action(db, practice_id, since=thirty_days_ago)

        rates = {row.agent_slug: float(row.cost_per_session) for row in await self.costing.list_all(db)}

        def total_cost(counts: dict[str, int]) -> float:
            return round(
                sum(counts.get(action, 0) * rates.get(slug, 0.0) for action, slug in _ACTION_TO_COST_SLUG.items()), 2
            )

        return AIReceptionistOverviewResponse(
            calls_handled=all_time_counts.get("call_handled", 0) + all_time_counts.get("message_handled", 0),
            reminders_sent=all_time_counts.get("reminder_sent", 0),
            translations_done=all_time_counts.get("message_translated", 0),
            total_interactions=sum(all_time_counts.values()),
            estimated_cost_total=total_cost(all_time_counts),
            estimated_cost_last_30_days=total_cost(recent_counts),
            pipeline=await self._pipeline(db, practice_id),
            channels=await self._channels(db, practice_id),
            health=await self._health(db, practice_id, day_ago),
            recent_activity=await self._recent_activity(db, practice_id),
        )

    async def _counts_by_action(self, db: AsyncSession, practice_id: UUID, since: datetime | None) -> dict[str, int]:
        query = select(AgentLog.action, func.count()).where(
            AgentLog.practice_id == practice_id, AgentLog.agent_type == "ai_receptionist"
        )
        if since is not None:
            query = query.where(AgentLog.created_at >= since)
        query = query.group_by(AgentLog.action)
        result = await db.execute(query)
        return dict(result.all())

    async def _pipeline(self, db: AsyncSession, practice_id: UUID) -> ReceptionistPipeline:
        total_patients = await db.scalar(
            select(func.count()).select_from(Patient).where(Patient.practice_id == practice_id)
        )
        lost = await db.scalar(
            select(func.count())
            .select_from(Patient)
            .where(Patient.practice_id == practice_id, Patient.lifecycle_stage == PatientLifecycleStage.LOST)
        )
        qualified_leads = (total_patients or 0) - (lost or 0)

        booked = await db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.practice_id == practice_id,
                Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
            )
        )

        # Auto follow-ups are the union of the two real follow-up agents:
        # marketing_followup logs AgentLog rows, lead_nurturing writes
        # outbound Messages on lead_nurturing conversations.
        offers = await db.scalar(
            select(func.count()).select_from(AgentLog).where(
                AgentLog.practice_id == practice_id, AgentLog.agent_type == "marketing_followup"
            )
        )
        nurtures = await db.scalar(
            select(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.practice_id == practice_id, Conversation.agent_type == "lead_nurturing")
        )
        auto_followups = (offers or 0) + (nurtures or 0)

        return ReceptionistPipeline(
            qualified_leads=qualified_leads or 0,
            appointments_scheduled=booked or 0,
            auto_followups_sent=auto_followups,
        )

    async def _channels(self, db: AsyncSession, practice_id: UUID) -> list[ReceptionistChannelStatus]:
        practice = await db.get(Practice, practice_id)
        return _channel_statuses(practice.settings if practice else {})

    async def _health(self, db: AsyncSession, practice_id: UUID, day_ago: datetime) -> ReceptionistHealth:
        last = await db.scalar(
            select(AgentLog.created_at)
            .where(AgentLog.practice_id == practice_id, AgentLog.agent_type == "ai_receptionist")
            .order_by(AgentLog.created_at.desc())
        )
        sessions_24h = await db.scalar(
            select(func.count()).select_from(Conversation).where(
                Conversation.practice_id == practice_id, Conversation.created_at >= day_ago
            )
        )
        interactions_24h = await db.scalar(
            select(func.count())
            .select_from(AgentLog)
            .where(
                AgentLog.practice_id == practice_id,
                AgentLog.agent_type == "ai_receptionist",
                AgentLog.created_at >= day_ago,
            )
        )
        status = "Active" if interactions_24h else ("Standby" if last else "No activity yet")
        return ReceptionistHealth(
            status=status,
            last_activity_at=last.isoformat() if last else None,
            sessions_24h=sessions_24h or 0,
            interactions_24h=interactions_24h or 0,
        )

    async def _recent_activity(self, db: AsyncSession, practice_id: UUID) -> list[ReceptionistActivityEntry]:
        rows = (
            await db.execute(
                select(AgentLog)
                .where(AgentLog.practice_id == practice_id, AgentLog.agent_type == "ai_receptionist")
                .order_by(AgentLog.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        return [
            ReceptionistActivityEntry(
                id=str(row.id),
                label=_ACTION_LABELS.get(row.action, row.action.replace("_", " ")),
                channel=_ACTION_CHANNEL.get(row.action),
                summary=_summarize_details(row.details),
                created_at=row.created_at.isoformat(),
            )
            for row in rows
        ]