"""
v5 Persistence layer — async SQLAlchemy 2.0 + aiosqlite (dev) / asyncpg (prod).

Switch driver via DATABASE_URL env var:
  - sqlite+aiosqlite:///./insightx.db   ← default for dev
  - postgresql+asyncpg://user:pass@host/db   ← prod

Both share the same Alembic migrations + ORM models.
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./insightx.db",
)

# `echo=True` 在 dev 下 print SQL，prod 必關
_echo = os.getenv("DB_ECHO", "0") == "1"

# pool_pre_ping: 自動偵測 dead connection 重連（postgres 必備）
_engine_kwargs = {"echo": _echo}
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

# SQLite 預設不執行 FK ON DELETE CASCADE，要手動 PRAGMA。
# 影響：DELETE /stores/{id} 要 cascade 砍 review_sources / reviews /
# scrape_jobs / analysis_runs / generated_assets / reports；沒這段
# orphan rows 會留下。Postgres / 其他 dialect 不需要這段。
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_fk_pragma(dbapi_conn, _conn_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a session that auto-rollbacks on exception, commits on success."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session_dep() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends(...) version. Caller controls commit/rollback."""
    async with SessionLocal() as session:
        yield session
