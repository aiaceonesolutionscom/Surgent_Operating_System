from sqlalchemy import text
from src.database import async_session_factory
import asyncio


async def clear_and_reseed():
    async with async_session_factory() as db:
        # Clear existing inventory items
        await db.execute(text('DELETE FROM inventory_items'))
        await db.commit()
        print('Cleared existing inventory items')


asyncio.run(clear_and_reseed())