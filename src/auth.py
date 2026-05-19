"""
InsightX v6.1 — Cookie-based anonymous session scoping.

The v5α `_get_or_create_default_user` helper used a single hard-coded
`dev@insightx.local` user for every request. On the v6.0.0-alpha public
demo this meant any visitor's data showed up in every other visitor's
`/workspace/` view — Codex flagged it CRITICAL and we env-gated the
bridge as the immediate fix (IX_ENABLE_V4_WORKSPACE_PERSIST=0).

This module is the proper v6.1 fix. Each visitor gets:
  - An `ix_session` cookie (UUID4, HttpOnly + Secure + SameSite=Lax,
    1-year max-age, set on first request)
  - Their own anon-{sid}@insightx.local user row in the DB
  - Workspace + stores + analyses scoped to that user

## Why middleware (not Depends(get_current_user) cookie minting)

v6.1 Codex round 1 review (task 7e98b9ab6b41) caught: a FastAPI-injected
`Response` mutation inside `Depends(get_current_user)` does NOT propagate
when the route returns a concrete `StreamingResponse` (used by all SSE
endpoints). Fresh visitors hitting `/api/v4/analyze-stream` first would
never get a `Set-Cookie` header → next request mints another fresh user →
the landing analysis appears lost when they open `/workspace/`.

The fix is middleware: it owns cookie generation and applies `Set-Cookie`
to whatever response object FastAPI actually returns (regular or
StreamingResponse). Dependencies just read `request.state.session_id`.

No password / login / OAuth — completely anonymous. The cookie IS the
identity. Clearing cookies = losing access to your workspace (acceptable
for an alpha demo; v6.2 can add real auth if/when needed).

Threat model addressed:
  - Visitor A cannot read Visitor B's workspace via /api/v5/workspaces
  - Direct ID-guessing on /api/v5/stores/{id} still needs ownership scope
    enforcement at each endpoint (see _get_owned_store etc. in v5.py)

NOT addressed (leave for later if real auth is needed):
  - Session hijacking (someone steals your cookie via XSS — mitigated by
    HttpOnly + Secure but not bulletproof)
  - Multi-device sync (cookies are per-browser)
  - Account recovery (lose cookie = lose workspace, no password reset)
"""
from __future__ import annotations

import os
import re
import uuid

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.db import get_session_dep
from src.models import User


# ────────────────────────────────────────────────────────────────────
# Cookie config
# ────────────────────────────────────────────────────────────────────
COOKIE_NAME = "ix_session"
COOKIE_MAX_AGE_SECS = 365 * 86400  # 1 year
COOKIE_PATH = "/"
COOKIE_SAMESITE = "lax"  # blocks third-party POST CSRF; allows top-level nav
COOKIE_HTTPONLY = True   # no JS access; mitigates XSS theft

# Secure: cookie only sent over HTTPS. Production HF Space serves over HTTPS,
# so this stays True there. For local dev + TestClient (http://testserver),
# httpx filters Secure cookies → repeated requests look like fresh visitors.
# Set IX_COOKIE_SECURE=false (or 0) when running locally on plain http.
COOKIE_SECURE = os.getenv("IX_COOKIE_SECURE", "true").lower() not in ("0", "false", "no")

# Session ID format check — uuid4().hex is 32 lowercase hex chars.
_SID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────
def _new_session_id() -> str:
    """Cryptographically random UUID4 in hex. 128 bits of entropy."""
    return uuid.uuid4().hex


def _email_for_session(sid: str) -> str:
    """Synthesize a unique email for the anon user keyed on session ID.

    Format `anon-<sid>@insightx.local` — `.local` is RFC 2606 reserved
    so it never resolves DNS-wise. Keeps the existing User.email schema
    (which already has a UNIQUE index) without needing to introduce a
    separate session_id column.
    """
    return f"anon-{sid}@insightx.local"


def _get_or_create_user_for_session(session: Session, sid: str) -> User:
    """Look up the anon user for this session; create on first request.

    v6.1 Codex round 1 MINOR fix: catches IntegrityError from concurrent
    same-cookie races (two parallel requests arriving with the same
    brand-new sid before either has committed the User row).
    """
    email = _email_for_session(sid)
    user = session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    # Try to create. If we lose the race, reselect.
    user = User(email=email, plan="free")
    session.add(user)
    try:
        session.flush()
        return user
    except IntegrityError:
        session.rollback()
        return session.scalar(select(User).where(User.email == email))


# ════════════════════════════════════════════════════════════════════
#  Middleware — owns cookie lifecycle
# ════════════════════════════════════════════════════════════════════
class SessionCookieMiddleware(BaseHTTPMiddleware):
    """Ensures every request has an ix_session UUID + sets Set-Cookie on
    the outgoing response.

    Why middleware: works uniformly for JSONResponse / StreamingResponse /
    FileResponse / static files. The previous Depends-on-Response approach
    only worked for routes that returned a serialised payload (FastAPI
    rewrites the response then) — StreamingResponse bypassed it.

    Reads + writes use `request.state.ix_session_id` so the downstream
    `get_current_user` dependency just looks at request.state.
    """

    async def dispatch(self, request: Request, call_next):
        existing = request.cookies.get(COOKIE_NAME)
        is_new = not existing or not _SID_PATTERN.match(existing)
        sid = _new_session_id() if is_new else existing
        # Stash on request.state so downstream Depends() can read it
        request.state.ix_session_id = sid
        request.state.ix_session_is_new = is_new

        response = await call_next(request)

        # On a brand-new session, bake Set-Cookie onto whatever response
        # type the route returned (StreamingResponse included — its
        # set_cookie() method exists via starlette.responses.Response base).
        if is_new:
            response.set_cookie(
                key=COOKIE_NAME,
                value=sid,
                max_age=COOKIE_MAX_AGE_SECS,
                path=COOKIE_PATH,
                secure=COOKIE_SECURE,
                httponly=COOKIE_HTTPONLY,
                samesite=COOKIE_SAMESITE,
            )
        return response


# ════════════════════════════════════════════════════════════════════
#  FastAPI dependency
# ════════════════════════════════════════════════════════════════════
def get_current_user(
    request: Request,
    session: Session = Depends(get_session_dep),
) -> User:
    """FastAPI Depends — returns the User for this visitor's session.

    The cookie has already been read / created by `SessionCookieMiddleware`,
    which stored the sid on `request.state.ix_session_id`. This dependency
    just looks up / creates the matching User row.

    No Response parameter needed — the middleware handles Set-Cookie for
    every response type uniformly (StreamingResponse included).
    """
    sid = getattr(request.state, "ix_session_id", None)
    if not sid or not _SID_PATTERN.match(sid):
        # Should never happen if middleware is registered; defensive fallback.
        sid = _new_session_id()
        request.state.ix_session_id = sid
        request.state.ix_session_is_new = True
    return _get_or_create_user_for_session(session, sid)


def get_current_user_id_from_request(request: Request, session: Session) -> int | None:
    """Plain-function variant for code paths that don't use FastAPI Depends
    (e.g. background jobs / inside `event_generator` closures).

    Returns the user's id if a valid session is present, else None.
    """
    sid = getattr(request.state, "ix_session_id", None)
    if not sid or not _SID_PATTERN.match(sid):
        return None
    user = session.scalar(
        select(User).where(User.email == _email_for_session(sid))
    )
    return user.id if user else None


# ────────────────────────────────────────────────────────────────────
# Legacy fallback (kept for tests / scripts that don't have a request)
# ────────────────────────────────────────────────────────────────────
_LEGACY_DEFAULT_EMAIL = "dev@insightx.local"


def get_legacy_default_user(session: Session) -> User:
    """The pre-v6.1 dev-mode default user. Avoid in HTTP-handler code —
    use `get_current_user` instead. Kept for:
      - Test fixtures that don't go through FastAPI
      - Migration scripts / one-off ops
    """
    user = session.scalar(select(User).where(User.email == _LEGACY_DEFAULT_EMAIL))
    if user is None:
        user = User(email=_LEGACY_DEFAULT_EMAIL, plan="free")
        session.add(user)
        session.flush()
    return user
