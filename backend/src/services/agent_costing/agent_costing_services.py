from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_costing import AgentCosting

# Per-session cost, tiered by what the agent actually does — vision/real-time
# agents (consultation) cost the most, simple rule-based ones (reminders) the
# least. Mirrors the consolidated 9-clinic-agent roster in
# frontend/src/data/agents/index.ts / plan_capabilities.py's AGENT_CATEGORIES —
# if an agent is added/renamed there, update here too.
DEFAULT_COSTS: dict[str, float] = {
    # Front Desk & Intake — high-volume, cheap
    "receptionist": 0.12,
    "appointment_reminder": 0.06,
    # Consultation & Screening — multi-turn / dictation agents cost the most
    "lead_qualification": 0.20,
    "patient_intake": 0.25,
    "consultation_assistant": 0.85,
    # Post-Op Care & Retention
    "post_op_recovery": 0.25,
    "marketing_retention": 0.18,
    # Business & Operations — finance/command
    "finance_agent": 0.30,
    "main_agent": 0.10,
}


class AgentCostingService:
    async def list_all(self, db: AsyncSession) -> list[AgentCosting]:
        result = await db.execute(select(AgentCosting))
        rows = result.scalars().all()
        if not rows:
            # Self-seeding on first read — no separate seed script to remember
            # to run, matches this app's "just works" pattern elsewhere
            # (useDoctors.ts/usePracticeProfile.ts seed their own defaults too).
            rows = await self._seed_defaults(db)
        return list(rows)

    async def _seed_defaults(self, db: AsyncSession) -> list[AgentCosting]:
        rows = [AgentCosting(agent_slug=slug, cost_per_session=cost, is_active=True) for slug, cost in DEFAULT_COSTS.items()]
        db.add_all(rows)
        await db.flush()
        return rows
