"""Turn whatever DATABASE_URL a host hands us into an asyncpg-ready engine
config.

Hosted Postgres (Neon, Supabase, Railway...) gives a libpq-style URL such as

    postgresql://user:pw@ep-x-pooler.eu-central-1.aws.neon.tech/db?sslmode=require&channel_binding=require

which SQLAlchemy's asyncpg driver cannot use as-is: the scheme has no async
driver, and asyncpg raises `TypeError: connect() got an unexpected keyword
argument 'sslmode'`. This module rewrites the URL and moves TLS / pooler
settings into `connect_args`, so the connection string can be pasted from the
provider's dashboard unchanged. Used by both the app engine (database.py) and
Alembic (alembic/env.py) so they cannot disagree.
"""

from __future__ import annotations

import ssl
from uuid import uuid4

from sqlalchemy.engine import URL, make_url

_POSTGRES_DRIVERS = {"postgresql", "postgres", "postgresql+psycopg2", "postgresql+asyncpg", "postgresql+psycopg"}
# libpq query parameters asyncpg does not understand; dropped after being applied.
_LIBPQ_ONLY = {"sslmode", "ssl", "channel_binding", "sslrootcert", "gssencmode", "target_session_attrs"}


def _is_pooled(url: URL) -> bool:
    """True for a transaction-mode pgbouncer endpoint, where asyncpg's
    server-side prepared statements break ("prepared statement ... does not
    exist"). Neon marks its pooler with `-pooler` in the hostname."""
    host = url.host or ""
    return "-pooler" in host or url.port == 6543 or url.query.get("pgbouncer") == "true"


def engine_config(raw_url: str) -> tuple[URL, dict]:
    """(normalized URL, connect_args) for `create_async_engine`."""
    url = make_url(raw_url)
    if url.drivername not in _POSTGRES_DRIVERS:
        return url, {}  # sqlite etc. - nothing to rewrite

    query = dict(url.query)
    sslmode = str(query.get("sslmode", "")).lower()
    ssl_param = str(query.get("ssl", "")).lower()
    connect_args: dict = {}

    if sslmode in {"verify-ca", "verify-full"}:
        connect_args["ssl"] = ssl.create_default_context()
    elif sslmode == "require" or ssl_param in {"require", "true", "1"}:
        connect_args["ssl"] = "require"

    if _is_pooled(url):
        connect_args.update(
            statement_cache_size=0,
            prepared_statement_cache_size=0,
            prepared_statement_name_func=lambda: f"__asyncpg_{uuid4()}__",
        )

    for key in _LIBPQ_ONLY | {"pgbouncer"}:
        query.pop(key, None)
    return url.set(drivername="postgresql+asyncpg", query=query), connect_args
