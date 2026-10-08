import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import get_settings
from src.database import Base
from src.db_url import engine_config
import src.models  # noqa: F401 — registers every model on Base.metadata before autogenerate compares against it

settings = get_settings()

config = context.config
# Migrations use MIGRATION_DATABASE_URL when set: on a pooled host (Neon) the
# app runs through the pooler but DDL needs the direct endpoint.
_url, _connect_args = engine_config(settings.migration_database_url or settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=_url.render_as_string(hide_password=False), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = create_async_engine(_url, poolclass=pool.NullPool, connect_args=_connect_args)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
