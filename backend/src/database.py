from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings
from src.db_url import engine_config
from src.server.runtime_metrics import install_query_timing

settings = get_settings()

_url, _connect_args = engine_config(settings.database_url)
_engine_kwargs: dict = {"echo": settings.debug, "connect_args": _connect_args}
if _url.get_backend_name() != "sqlite":
    # Serverless Postgres (Neon) drops idle connections when the compute
    # suspends. pre_ping revalidates a pooled connection before use and
    # recycle retires old ones, so the first request after an idle spell
    # doesn't fail on a dead socket.
    _engine_kwargs.update(pool_pre_ping=True, pool_recycle=300)
engine = create_async_engine(_url, **_engine_kwargs)

# Times every SQL statement so the Super Admin panel can report slow queries.
install_query_timing(engine.sync_engine)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
