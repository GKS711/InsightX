"""
v6 Background job runner — threading in-process (dev/portfolio) edition.

Rewritten from v5's asyncio model. Reason: Turso's Python ecosystem
(sqlalchemy-libsql) is sync-only, so the whole stack is sync now. Background
tasks use daemon threads instead of asyncio.create_task.

Design:
  - API endpoint creates ScrapeJob/AnalysisRun row (status='queued')
  - threading.Thread(daemon=True) fires off background work
  - Background thread uses NEW SessionLocal() (request session is gone)
  - Progress events go to _progress_queues[job_id] (queue.Queue, thread-safe)
  - SSE endpoint pulls from queue + sends to client (sync generator)

Prod TODO: replace with RQ + Redis worker pool (same Job interface).
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Generator

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from src.db import SessionLocal
from src.models import (
    AnalysisRun,
    Review,
    ReviewSource,
    ScrapeJob,
    Store,
)
from src.services.scraper_service import ScraperService

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# In-memory progress queues — keyed by ('scrape', job_id) or ('analysis', run_id)
# Note: queue.Queue is internally thread-safe; we only lock the dict for
# the create-if-missing race.
# ────────────────────────────────────────────────────────────────────
_progress_queues: dict[str, queue.Queue] = {}
_queues_lock = threading.Lock()

# Concurrency limits — gemma free tier 抗壓性差，並發限 3
_LLM_SEMA = threading.Semaphore(3)
# Scraper 並發限 5（Serper 有 quota）
_SCRAPER_SEMA = threading.Semaphore(5)


def _safe_commit_or_log(session, kind: str, job_id: int) -> bool:
    """Commit session; rollback + log on failure. Caller should return early
    on False — pushing further state to a deleted row is pointless.

    Why this exists: DELETE /api/v5/stores/{id} cascades to scrape_jobs /
    analysis_runs / their children. v5.py 已 409-block DELETE 當有 active
    job 時，但仍有 narrow race window：DELETE 檢查通過 → 使用者立刻 POST
    /scrape → 背景任務開跑 → DELETE commit → cascade 砍剛建的 job → 背景
    任務 60s 後想 commit success/failure → StaleDataError 或 IntegrityError。

    Only race-related exceptions are swallowed (StaleDataError + IntegrityError).
    Anything else (constraint violation in normal flow, DB outage, programmer
    bug) re-raises with logger.exception so the worker fails loudly and the
    caller's outer try/except handles it.
    """
    try:
        session.commit()
        return True
    except (StaleDataError, IntegrityError) as exc:
        session.rollback()
        logger.warning(
            "[jobs] %s commit failed for job_id=%d (likely cascade-deleted by DELETE /stores): %s",
            kind, job_id, str(exc)[:200],
        )
        return False
    except Exception:
        session.rollback()
        logger.exception(
            "[jobs] %s commit UNEXPECTED failure for job_id=%d (NOT a cascade race)",
            kind, job_id,
        )
        raise


def _qkey(kind: str, job_id: int) -> str:
    return f"{kind}:{job_id}"


def _get_or_create_queue(kind: str, job_id: int) -> queue.Queue:
    key = _qkey(kind, job_id)
    with _queues_lock:
        if key not in _progress_queues:
            _progress_queues[key] = queue.Queue(maxsize=100)
        return _progress_queues[key]


_TERMINAL_EVENTS = ("succeeded", "failed", "terminal")


def _push(kind: str, job_id: int, event: str, data: dict[str, Any]) -> None:
    """Push a progress event to the queue (non-blocking; drop if full).

    Codex round 2 fix (S2 follow-up): on terminal events, also remove the
    queue from _progress_queues *after* enqueueing so an orphan queue isn't
    left in the dict if no consumer is attached. Active consumers still hold
    a local reference to the queue (refcount keeps it alive) and will drain
    the terminal event normally; the dict entry just stops being reachable
    to new producers/consumers.
    """
    key = _qkey(kind, job_id)
    q = _get_or_create_queue(kind, job_id)
    payload = {"event": event, "data": data, "ts": datetime.now(tz=timezone.utc).isoformat()}
    try:
        q.put_nowait(payload)
    except queue.Full:
        logger.warning("[jobs] progress queue full for %s:%d, dropping event", kind, job_id)
    if event in _TERMINAL_EVENTS:
        with _queues_lock:
            # Identity check: only pop if the entry is still the queue we used.
            # If a consumer's finally already popped and a different producer
            # recreated under same key, we'd otherwise drop their fresh queue.
            if _progress_queues.get(key) is q:
                _progress_queues.pop(key, None)


def progress_stream(
    kind: str,
    job_id: int,
    *,
    idle_timeout_s: float = 60.0,
    poll_interval_s: float = 5.0,
) -> Generator[str, None, None]:
    """Sync generator yielding SSE-formatted progress events.

    Yields strings ready to write to StreamingResponse:
      'event: progress\\ndata: {...}\\n\\n'

    Stops when:
      - 'terminal' event seen (succeeded / failed)
      - idle_timeout_s elapsed without any event (assume worker died)

    Codex round 2 fix (S2+S3):
      - finally block pops queue from _progress_queues to plug memory leak
        (every stream subscription would otherwise leave a dict entry forever).
      - q.get() loops on short poll_interval_s with `: ping\\n\\n` heartbeats so
        client disconnects propagate as GeneratorExit within ~5s instead of
        pinning a threadpool worker for up to idle_timeout_s.
      - idle_timeout_s = time-since-last-event (NOT total stream lifetime).
        Reset last_event_at after each received payload so a long-running
        but actively-emitting job doesn't get killed at the wall-clock mark.
      - finally pop guarded by identity check so we don't accidentally remove
        a fresh queue created by a producer that came in after our cleanup.
    """
    import time as _time
    key = _qkey(kind, job_id)
    q = _get_or_create_queue(kind, job_id)
    last_event_at = _time.monotonic()
    try:
        while True:
            elapsed_since_event = _time.monotonic() - last_event_at
            if elapsed_since_event >= idle_timeout_s:
                yield f"event: timeout\ndata: {json.dumps({'reason': 'idle'})}\n\n"
                return
            try:
                payload = q.get(timeout=min(poll_interval_s, idle_timeout_s - elapsed_since_event))
            except queue.Empty:
                # heartbeat — SSE comment line; client ignores, server detects
                # closed connection on yield (GeneratorExit propagates to finally)
                yield ": ping\n\n"
                continue

            # Got an event — reset idle timer
            last_event_at = _time.monotonic()

            evt = payload.get("event", "progress")
            data = payload.get("data", {})
            yield f"event: {evt}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            if evt in _TERMINAL_EVENTS:
                return
    finally:
        # Pop queue to free memory regardless of how we exited (terminal /
        # timeout / GeneratorExit on client disconnect). Identity check
        # prevents stomping a fresh queue created post-cleanup.
        with _queues_lock:
            if _progress_queues.get(key) is q:
                _progress_queues.pop(key, None)


# ────────────────────────────────────────────────────────────────────
# Scrape job runner
# ────────────────────────────────────────────────────────────────────
_scraper = ScraperService()


def run_scrape_job_bg(job_id: int, source_id: int, external_url: str) -> None:
    """Background scrape — opens own session, updates job + writes reviews.

    Scrape timeout is enforced inside scraper_service via HTTP client
    timeout config. No outer wait_for needed in v6 sync mode.
    """
    with _SCRAPER_SEMA:
        with SessionLocal() as session:
            job = session.get(ScrapeJob, job_id)
            src = session.get(ReviewSource, source_id)
            if job is None or src is None:
                logger.error("[jobs] scrape job=%d or source=%d missing", job_id, source_id)
                return

            job.status = "running"
            job.started_at = datetime.now(tz=timezone.utc)
            if not _safe_commit_or_log(session, "scrape", job_id):
                return
            _push("scrape", job_id, "progress", {"phase": "scraping", "step": 1, "total": 3, "label": "fetching reviews"})

            try:
                scrape_result = _scraper.scrape_url(external_url)
                _push("scrape", job_id, "progress", {"phase": "persisting", "step": 2, "total": 3, "label": "writing to DB"})

                structured = scrape_result.get("reviews_structured", []) or []
                # bulk insert reviews
                for r in structured:
                    review = Review(
                        source_id=source_id,
                        scrape_job_id=job_id,
                        author=r.get("author") or None,
                        rating=r.get("rating") if isinstance(r.get("rating"), int) else None,
                        text=r.get("text", ""),
                    )
                    session.add(review)

                job.status = "succeeded"
                job.finished_at = datetime.now(tz=timezone.utc)
                job.reviews_fetched_count = len(structured)
                job.pagination_truncated = bool(scrape_result.get("pagination_truncated", False))
                src.last_scraped_at = datetime.now(tz=timezone.utc)
                if not _safe_commit_or_log(session, "scrape", job_id):
                    return

                _push("scrape", job_id, "succeeded", {
                    "phase": "done",
                    "step": 3,
                    "total": 3,
                    "reviews_fetched": job.reviews_fetched_count,
                    "pagination_truncated": job.pagination_truncated,
                })

            except TimeoutError:
                # Raised by scraper_service when its HTTP client timeout fires.
                job.status = "failed"
                job.finished_at = datetime.now(tz=timezone.utc)
                job.error_class = "TimeoutError"
                job.error_message = "scrape timeout"
                if not _safe_commit_or_log(session, "scrape", job_id):
                    return
                _push("scrape", job_id, "failed", {"error_class": "TimeoutError", "message": "scrape timeout"})

            except Exception as exc:
                job.status = "failed"
                job.finished_at = datetime.now(tz=timezone.utc)
                job.error_class = type(exc).__name__
                job.error_message = str(exc)[:1000]
                if not _safe_commit_or_log(session, "scrape", job_id):
                    return
                _push("scrape", job_id, "failed", {
                    "error_class": type(exc).__name__,
                    "message": str(exc)[:200],
                })


def fire_scrape_job(job_id: int, source_id: int, external_url: str) -> None:
    """Schedule a scrape job in a daemon background thread."""
    t = threading.Thread(
        target=run_scrape_job_bg,
        args=(job_id, source_id, external_url),
        daemon=True,
        name=f"scrape-{job_id}",
    )
    t.start()


# ────────────────────────────────────────────────────────────────────
# Analysis run runner
# ────────────────────────────────────────────────────────────────────
def run_analysis_bg(
    run_id: int,
    store_id: int,
    ai_function: str,
    inputs: dict[str, Any],
    model_tier: str = "standard",
) -> None:
    """Background analysis — opens own session, dispatches via LLM Service."""
    with _LLM_SEMA:
        with SessionLocal() as session:
            store = session.get(Store, store_id)
            run = session.get(AnalysisRun, run_id)
            if store is None or run is None:
                logger.error("[jobs] analysis run=%d or store=%d missing", run_id, store_id)
                return

            run.status = "running"
            run.started_at = datetime.now(tz=timezone.utc)
            if not _safe_commit_or_log(session, "analysis", run_id):
                return
            _push("analysis", run_id, "progress", {"phase": "analyzing", "step": 1, "total": 2, "label": f"calling LLM for {ai_function}"})

            try:
                # llm_service is sync in v6 (was async in v5)
                from src.services.llm_service import LLMService
                llm = LLMService()

                output: Any = None
                platform = store.platform or "google"

                if ai_function == "analyze":
                    text = inputs.get("text", "")
                    if not text:
                        raise ValueError("analyze requires 'text' input")
                    output = llm.analyze_content(text, platform=platform)
                elif ai_function == "swot":
                    output = llm.generate_swot(inputs.get("good", []), inputs.get("bad", []), platform=platform)
                elif ai_function == "reply":
                    output = llm.generate_reply(inputs.get("topic", ""), platform=platform)
                elif ai_function == "analyze_issue":
                    output = llm.generate_root_cause_analysis(inputs.get("topic", ""), platform=platform)
                elif ai_function == "marketing":
                    output = llm.generate_marketing(inputs.get("strengths", ""), platform=platform)
                elif ai_function == "weekly_plan":
                    output = llm.generate_weekly_plan(inputs.get("weaknesses", ""), platform=platform)
                elif ai_function == "training_script":
                    output = llm.generate_training_script(inputs.get("issue", ""), platform=platform)
                elif ai_function == "internal_email":
                    output = llm.generate_internal_email(
                        inputs.get("strengths", ""), inputs.get("weaknesses", ""), platform=platform,
                    )
                elif ai_function == "chat":
                    output = llm.chat(inputs.get("message", ""), inputs.get("context", ""), platform=platform)
                else:
                    raise ValueError(f"unknown ai_function: {ai_function}")

                run.output_json = output if isinstance(output, dict) else {"text": output}
                run.status = "succeeded"
                run.finished_at = datetime.now(tz=timezone.utc)
                if not _safe_commit_or_log(session, "analysis", run_id):
                    return

                _push("analysis", run_id, "succeeded", {
                    "phase": "done",
                    "step": 2,
                    "total": 2,
                    "ai_function": ai_function,
                })

            except Exception as exc:
                run.status = "failed"
                run.error_class = type(exc).__name__
                run.error_message = str(exc)[:1000]
                run.finished_at = datetime.now(tz=timezone.utc)
                if not _safe_commit_or_log(session, "analysis", run_id):
                    return
                _push("analysis", run_id, "failed", {
                    "error_class": type(exc).__name__,
                    "message": str(exc)[:200],
                })


def fire_analysis_run(
    run_id: int,
    store_id: int,
    ai_function: str,
    inputs: dict[str, Any],
    model_tier: str = "standard",
) -> None:
    """Schedule an analysis run in a daemon background thread."""
    t = threading.Thread(
        target=run_analysis_bg,
        args=(run_id, store_id, ai_function, inputs, model_tier),
        daemon=True,
        name=f"analysis-{run_id}",
    )
    t.start()
