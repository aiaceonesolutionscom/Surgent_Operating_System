from sqlalchemy import text
from src.database import async_session_factory
import asyncio


async def add_column():
    async with async_session_factory() as db:
        # Check if column exists
        result = await db.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'inventory_items' AND column_name = 'unit_cost'
        """))
        if result.fetchone():
            print('unit_cost column already exists')
        else:
            await db.execute(text('ALTER TABLE inventory_items ADD COLUMN unit_cost NUMERIC(10, 2)'))
            await db.commit()
            print('unit_cost column added successfully')


asyncio.run(add_column())