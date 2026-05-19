"""
v6 Persistence layer — sync SQLAlchemy 2.0 + sqlalchemy-libsql / Turso.

This is a rewrite of v5's async db.py. Reason: Turso's Python ecosystem
(sqlalchemy-libsql 0.2.0) is sync-only as of 2026-05; SQLAlchemy explicitly
rejects sqlalchemy-libsql in `create_async_engine` with `InvalidRequestError:
The asyncio extension requires an async driver to be used`. Going fully sync
lets us keep the SQLAlchemy ORM models, alembic migrations, and v5 schema
unchanged while using Turso as the backing DB.

DATABASE_URL forms accepted:
  sqlite:///./insightx.db                  ← dev local plain SQLite
  sqlite+libsql:///./local.db              ← dev local using libsql driver
  libsql://<db>-<owner>.turso.io           ← Turso remote (TURSO_AUTH_TOKEN env required)
  sqlite+libsql://<host>?secure=true       ← Turso remote explicit form

For Turso remote, also set TURSO_AUTH_TOKEN env var. The auth token is passed
to the libsql driver via connect_args, not embedded in the URL (URL embedding
would log the token in error messages).
"""
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def _normalize_db_url(raw: str) -> tuple[str, dict]:
    """Normalize Turso-style URLs and lift auth into connect_args.

    Convenience handled:
      - `libsql://<host>`                       → `sqlite+libsql://<host>?secure=true`
      - `sqlite+libsql://<host>` (no secure)    → adds `?secure=true`
      - Auth token from TURSO_AUTH_TOKEN env    → connect_args["auth_token"]

    Local file URLs (`sqlite:///` and `sqlite+libsql:///`) pass through.
    Returns (normalized_url, connect_args).
    """
    url = raw
    connect_args: dict = {}

    # libsql:// → sqlite+libsql:// (SQLAlchemy dialect prefix)
    if url.startswith("libsql://"):
        url = "sqlite+" + url

    is_remote_libsql = (
        url.startswith("sqlite+libsql://")
        and not url.startswith("sqlite+libsql:///")
    )
    if is_remote_libsql:
        if "secure=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}secure=true"
        token = os.getenv("TURSO_AUTH_TOKEN")
        if token:
            connect_args["auth_token"] = token

    return url, connect_args


_raw_url = os.getenv("DATABASE_URL", "sqlite:///./insightx.db")
DATABASE_URL, _connect_args = _normalize_db_url(_raw_url)

# `echo=True` in dev prints SQL; prod must stay off
_echo = os.getenv("DB_ECHO", "0") == "1"

_engine_kwargs: dict = {"echo": _echo}
if _connect_args:
    _engine_kwargs["connect_args"] = _connect_args

# Connection pool config.
#
# sqlalchemy-libsql uses SingletonThreadPool (one connection per thread),
# which doesn't accept QueuePool-only kwargs like pool_size / max_overflow.
# Passing them raises:
#   TypeError: Invalid argument(s) 'max_overflow' sent to create_engine(),
#   using configuration SQLiteDialect_libsql/SingletonThreadPool/Engine.
#
# So we ONLY apply pool_pre_ping for remote libsql (catches stale connections
# after HF Spaces' 48h auto-sleep wake), and never override poolclass — let
# the dialect pick its own.
_is_remote = (
    DATABASE_URL.startswith("sqlite+libsql://")
    and not DATABASE_URL.startswith("sqlite+libsql:///")
)
if _is_remote:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **_engine_kwargs)


# SQLite (and libsql, which is SQLite-compat) FK PRAGMA — required for
# ON DELETE CASCADE to actually fire on local files. For Turso remote,
# FK enforcement is server-side; PRAGMA is harmless / a no-op.
#
# Without this, DELETE /api/v5/stores/{id} would leave orphan rows in
# review_sources / reviews / scrape_jobs / analysis_runs / generated_assets /
# reports.
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_fk_pragma(dbapi_conn, _conn_record):
        try:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
        except Exception:
            # libsql remote may expose cursor() differently; FK is server-side
            # there anyway. Don't crash on connect.
            pass


SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=Session,
)


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a session that auto-rollbacks on exception, commits on success."""
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_session_dep() -> Iterator[Session]:
    """FastAPI Depends(...) version. Caller controls commit/rollback."""
    with SessionLocal() as session:
        yield session
