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

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    """Look up the anon user for this session; create on first request."""
    email = _email_for_session(sid)
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, plan="free")
        session.add(user)
        session.flush()  # populate user.id within the same transaction
    return user


# ────────────────────────────────────────────────────────────────────
# FastAPI dependency
# ────────────────────────────────────────────────────────────────────
def get_current_user(
    request: Request,
    response: Response,
    session: Session = Depends(get_session_dep),
) -> User:
    """FastAPI Depends — returns the User for this visitor's session.

    Reads `ix_session` cookie. If missing or malformed, mints a new UUID
    and sets the cookie on the outgoing response (FastAPI propagates
    Response mutations to the actual HTTP response even when the route
    returns a different type like JSONResponse or StreamingResponse).
    """
    sid = request.cookies.get(COOKIE_NAME)
    if not sid or not _SID_PATTERN.match(sid):
        sid = _new_session_id()
        response.set_cookie(
            key=COOKIE_NAME,
            value=sid,
            max_age=COOKIE_MAX_AGE_SECS,
            path=COOKIE_PATH,
            secure=COOKIE_SECURE,
            httponly=COOKIE_HTTPONLY,
            samesite=COOKIE_SAMESITE,
        )
    return _get_or_create_user_for_session(session, sid)


def get_current_user_id_from_request(request: Request, session: Session) -> int | None:
    """Plain-function variant for code paths that don't use FastAPI Depends
    (e.g. background jobs / inside `event_generator` closures).

    Returns the user's id if a valid session cookie is present, else None.
    NEVER mints a new cookie (no Response to set it on) — that has to
    happen on a real request edge via get_current_user().
    """
    sid = request.cookies.get(COOKIE_NAME)
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
