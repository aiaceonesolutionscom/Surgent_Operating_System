"""DATABASE_URL handling for hosted Postgres (Neon).

The connection string a provider shows in its dashboard is libpq-flavoured and
cannot be given to SQLAlchemy's asyncpg driver as-is. These pin the rewrite so
a pasted Neon URL keeps working - the failure mode otherwise is a TypeError at
first connect, in production, with no data yet to hint at why.
"""

import ssl

from src.db_url import engine_config

NEON_DIRECT = "postgresql://owner:pw@ep-cool-sky-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
NEON_POOLED = "postgresql://owner:pw@ep-cool-sky-123456-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"


def test_plain_postgres_scheme_gets_the_asyncpg_driver():
    url, _ = engine_config(NEON_DIRECT)
    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "ep-cool-sky-123456.eu-central-1.aws.neon.tech"
    assert url.database == "neondb"


def test_libpq_only_parameters_are_removed_and_ssl_moves_to_connect_args():
    url, connect_args = engine_config(NEON_DIRECT)
    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert connect_args["ssl"] == "require"


def test_direct_endpoint_keeps_prepared_statements():
    _, connect_args = engine_config(NEON_DIRECT)
    assert "statement_cache_size" not in connect_args


def test_pooled_endpoint_disables_prepared_statement_caching():
    """Neon's pooler is pgbouncer in transaction mode; asyncpg's prepared
    statements die there with 'prepared statement does not exist'."""
    _, connect_args = engine_config(NEON_POOLED)
    assert connect_args["statement_cache_size"] == 0
    assert connect_args["prepared_statement_cache_size"] == 0
    names = {connect_args["prepared_statement_name_func"]() for _ in range(3)}
    assert len(names) == 3  # unique per statement, so two clients never collide


def test_verify_full_uses_a_verifying_context():
    _, connect_args = engine_config("postgresql://u:p@db.example.com/app?sslmode=verify-full")
    assert isinstance(connect_args["ssl"], ssl.SSLContext)
    assert connect_args["ssl"].check_hostname is True


def test_already_asyncpg_urls_pass_through_unchanged():
    url, connect_args = engine_config("postgresql+asyncpg://u:p@localhost:5432/app")
    assert url.drivername == "postgresql+asyncpg"
    assert connect_args == {}


def test_password_with_special_characters_survives():
    url, _ = engine_config("postgresql://u:p%40ss%25word@db.example.com/app")
    assert url.password == "p@ss%word"


def test_sqlite_is_left_alone():
    url, connect_args = engine_config("sqlite+aiosqlite:///:memory:")
    assert url.drivername == "sqlite+aiosqlite"
    assert connect_args == {}
