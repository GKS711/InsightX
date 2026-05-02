"""
Alembic env.py — async, connects via src.db.engine, target metadata = src.models.Base.

v5 InsightX: 2026-05-02
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

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

from src.db import DATABASE_URL  # noqa: E402
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


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite 不支援部分 ALTER；用 batch 模式（render_as_batch）讓 alter 走 copy-table
        render_as_batch=DATABASE_URL.startswith("sqlite"),
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine and associate a connection with the context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
