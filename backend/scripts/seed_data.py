"""
Seed script to populate initial data (agent configs, default practice)
Usage: python scripts/seed_data.py
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_factory
from src.models.practice import Practice
from src.models.agent_config import AgentConfig


AGENT_TYPES = [
    "receptionist", "appointment_reminder",
    "lead_qualification", "patient_intake", "consultation_assistant",
    "post_op_recovery", "marketing_retention",
    "finance_agent", "main_agent",
]


async def seed():
    async with async_session_factory() as session:
        practice = Practice(
            name="Demo Aesthetic Practice",
            email="demo@aesthetixai.com",
            phone="+1234567890",
        )
        session.add(practice)
        await session.flush()

        for agent_type in AGENT_TYPES:
            config = AgentConfig(
                practice_id=practice.id,
                agent_type=agent_type,
                enabled=True,
                config={"tone": "professional", "language": "en"},
            )
            session.add(config)

        await session.commit()
        print(f"Seeded 1 practice and {len(AGENT_TYPES)} agent configs")


if __name__ == "__main__":
    asyncio.run(seed())
