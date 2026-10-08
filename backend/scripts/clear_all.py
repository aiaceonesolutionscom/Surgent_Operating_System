"""Wipe all practices (and the seed data hanging off them) from a LOCAL dev database.

Refuses to run unless the database is on this machine: pointed at a hosted
database (Neon, ...) this would delete every real clinic.

    python scripts/clear_all.py --yes
"""
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url

from src.config import get_settings
from src.database import async_session_factory

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def _refuse_unless_local() -> None:
    settings = get_settings()
    host = make_url(settings.database_url).host or ""
    if settings.app_env == "production" or host not in _LOCAL_HOSTS:
        sys.exit(
            f"Refusing to clear data: DATABASE_URL points at '{host or 'unknown'}' "
            f"(APP_ENV={settings.app_env}). This script only runs against a local dev database."
        )
    if "--yes" not in sys.argv:
        sys.exit("This deletes ALL practices from the local database. Re-run with --yes to confirm.")


async def clear_all():
    async with async_session_factory() as db:
        # Clear inventory items first (foreign key constraints)
        await db.execute(text('DELETE FROM inventory_items'))
        await db.execute(text('DELETE FROM agent_configs'))
        await db.execute(text('DELETE FROM practices'))
        await db.commit()
        print('Cleared all seed data')


if __name__ == "__main__":
    _refuse_unless_local()
    asyncio.run(clear_all())
