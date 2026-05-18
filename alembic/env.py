"""
Alembic env.py — sync edition (v6).

Connects via src.db.engine (now sync), target metadata = src.models.Base.

v6 InsightX: rewritten from async (asyncpg/aiosqlite) to sync (libsql/Turso),
so alembic also runs synchronously now.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 把專案根加進 sys.path，讓 alembic 能 import src.*
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 載入 .env（讓 alembic CLI 也能讀 DATABASE_URL）
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

from src.db import DATABASE_URL, _engine_kwargs  # noqa: E402
from src.models import Base  # noqa: E402

config = context.config

# 從 src.db 拿 DATABASE_URL，覆寫 alembic.ini 內的 sqlalchemy.url
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate target — Base.metadata 包含 9 個 v5 tables
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mode — emit SQL without DB connection."""
    url = config.get_main_option("sqlalchemy.url") or DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (sync engine + Turso connect_args)."""
    # alembic.ini's sqlalchemy.* keys + connect_args from src.db._engine_kwargs
    # so libsql auth_token / ssl options propagate to the migration connection.
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_engine_kwargs.get("connect_args") or {},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=DATABASE_URL.startswith("sqlite"),
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
