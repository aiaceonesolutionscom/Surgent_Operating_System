from sqlalchemy import text
from src.database import async_session_factory
import asyncio


async def clear_all():
    async with async_session_factory() as db:
        # Clear inventory items first (foreign key constraints)
        await db.execute(text('DELETE FROM inventory_items'))
        await db.execute(text('DELETE FROM agent_configs'))
        await db.execute(text('DELETE FROM practices'))
        await db.commit()
        print('Cleared all seed data')


asyncio.run(clear_all())