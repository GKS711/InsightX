"""
v5 Background job runner — asyncio in-process (dev) edition.

Design:
  - API endpoint creates ScrapeJob/AnalysisRun row (status='queued')
  - asyncio.create_task fires off background coroutine
  - Background coroutine uses NEW SessionLocal() (request session is gone)
  - Progress events go to _progress_queues[job_id] (asyncio.Queue)
  - SSE endpoint pulls from queue + sends to client

Prod TODO: replace with RQ + Redis worker pool (same Job interface).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
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
from src.services.llm_gateway import gateway
from src.services.scraper_service import ScraperService

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# In-memory progress queues — keyed by ('scrape', job_id) or ('analysis', run_id)
# ────────────────────────────────────────────────────────────────────
_progress_queues: dict[str, asyncio.Queue] = {}

# Concurrency limit — gemma free tier 抗壓性差，並發限 3
_LLM_SEMA = asyncio.Semaphore(3)
# Scraper 並發限 5（Serper 有 quota）
_SCRAPER_SEMA = asyncio.Semaphore(5)


async def _safe_commit_or_log(session, kind: str, job_id: int) -> bool:
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
        await session.commit()
        return True
    except (StaleDataError, IntegrityError) as exc:
        await session.rollback()
        logger.warning(
            "[jobs] %s commit failed for job_id=%d (likely cascade-deleted by DELETE /stores): %s",
            kind, job_id, str(exc)[:200],
        )
        return False
    except Exception:
        await session.rollback()
        logger.exception(
            "[jobs] %s commit UNEXPECTED failure for job_id=%d (NOT a cascade race)",
            kind, job_id,
        )
        raise


def _qkey(kind: str, job_id: int) -> str:
    return f"{kind}:{job_id}"


def _get_or_create_queue(kind: str, job_id: int) -> asyncio.Queue:
    key = _qkey(kind, job_id)
    if key not in _progress_queues:
        _progress_queues[key] = asyncio.Queue(maxsize=100)
    return _progress_queues[key]


async def _push(kind: str, job_id: int, event: str, data: dict[str, Any]) -> None:
    """Push a progress event to the queue (non-blocking; drop if full)."""
    q = _get_or_create_queue(kind, job_id)
    payload = {"event": event, "data": data, "ts": datetime.now(tz=timezone.utc).isoformat()}
    try:
        q.put_nowait(payload)
    except asyncio.QueueFull:
        logger.warning("[jobs] progress queue full for %s:%d, dropping event", kind, job_id)


async def progress_stream(kind: str, job_id: int, *, idle_timeout_s: float = 60.0):
    """Async generator yielding SSE-formatted progress events.

    Yields strings ready to write to StreamingResponse:
      'event: progress\\ndata: {...}\\n\\n'

    Stops when:
      - 'terminal' event seen (succeeded / failed)
      - idle_timeout_s elapsed without any event (assume worker died)
    """
    q = _get_or_create_queue(kind, job_id)
    while True:
        try:
            payload = await asyncio.wait_for(q.get(), timeout=idle_timeout_s)
        except asyncio.TimeoutError:
            yield f"event: timeout\ndata: {json.dumps({'reason': 'idle'})}\n\n"
            return

        evt = payload.get("event", "progress")
        data = payload.get("data", {})
        yield f"event: {evt}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        if evt in ("succeeded", "failed", "terminal"):
            return


# ────────────────────────────────────────────────────────────────────
# Scrape job runner
# ────────────────────────────────────────────────────────────────────
_scraper = ScraperService()


async def run_scrape_job_bg(job_id: int, source_id: int, external_url: str) -> None:
    """Background scrape — opens own session, updates job + writes reviews."""
    async with _SCRAPER_SEMA:
        async with SessionLocal() as session:
            job = await session.get(ScrapeJob, job_id)
            src = await session.get(ReviewSource, source_id)
            if job is None or src is None:
                logger.error("[jobs] scrape job=%d or source=%d missing", job_id, source_id)
                return

            job.status = "running"
            job.started_at = datetime.now(tz=timezone.utc)
            if not await _safe_commit_or_log(session, "scrape", job_id):
                return
            await _push("scrape", job_id, "progress", {"phase": "scraping", "step": 1, "total": 3, "label": "fetching reviews"})

            try:
                scrape_result = await asyncio.wait_for(
                    _scraper.scrape_url(external_url),
                    timeout=120.0,
                )
                await _push("scrape", job_id, "progress", {"phase": "persisting", "step": 2, "total": 3, "label": "writing to DB"})

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
                if not await _safe_commit_or_log(session, "scrape", job_id):
                    return

                await _push("scrape", job_id, "succeeded", {
                    "phase": "done",
                    "step": 3,
                    "total": 3,
                    "reviews_fetched": job.reviews_fetched_count,
                    "pagination_truncated": job.pagination_truncated,
                })

            except asyncio.TimeoutError:
                job.status = "failed"
                job.finished_at = datetime.now(tz=timezone.utc)
                job.error_class = "TimeoutError"
                job.error_message = "scrape timeout (>120s)"
                if not await _safe_commit_or_log(session, "scrape", job_id):
                    return
                await _push("scrape", job_id, "failed", {"error_class": "TimeoutError", "message": "scrape timeout"})

            except Exception as exc:
                job.status = "failed"
                job.finished_at = datetime.now(tz=timezone.utc)
                job.error_class = type(exc).__name__
                job.error_message = str(exc)[:1000]
                if not await _safe_commit_or_log(session, "scrape", job_id):
                    return
                await _push("scrape", job_id, "failed", {
                    "error_class": type(exc).__name__,
                    "message": str(exc)[:200],
                })


def fire_scrape_job(job_id: int, source_id: int, external_url: str) -> None:
    """Schedule a scrape job to run in the background."""
    asyncio.create_task(run_scrape_job_bg(job_id, source_id, external_url))


# ────────────────────────────────────────────────────────────────────
# Analysis run runner
# ────────────────────────────────────────────────────────────────────
async def run_analysis_bg(
    run_id: int,
    store_id: int,
    ai_function: str,
    inputs: dict[str, Any],
    model_tier: str = "standard",
) -> None:
    """Background analysis — opens own session, dispatches via LLM Gateway."""
    async with _LLM_SEMA:
        async with SessionLocal() as session:
            store = await session.get(Store, store_id)
            run = await session.get(AnalysisRun, run_id)
            if store is None or run is None:
                logger.error("[jobs] analysis run=%d or store=%d missing", run_id, store_id)
                return

            run.status = "running"
            run.started_at = datetime.now(tz=timezone.utc)
            if not await _safe_commit_or_log(session, "analysis", run_id):
                return
            await _push("analysis", run_id, "progress", {"phase": "analyzing", "step": 1, "total": 2, "label": f"calling LLM for {ai_function}"})

            # 把 input 帶到 gateway，再寫一次 run（gateway 內也會更新 run row，但 run row 已是新 session 內 attached）
            try:
                # 由於 gateway 用 session.add(run) — 這會 conflict（run 已存在）。改成直接 inline 跑
                from src.services.llm_service import LLMService
                llm = LLMService()

                output: Any = None
                platform = store.platform or "google"

                if ai_function == "analyze":
                    text = inputs.get("text", "")
                    if not text:
                        raise ValueError("analyze requires 'text' input")
                    output = await llm.analyze_content(text, platform=platform)
                elif ai_function == "swot":
                    output = await llm.generate_swot(inputs.get("good", []), inputs.get("bad", []), platform=platform)
                elif ai_function == "reply":
                    output = await llm.generate_reply(inputs.get("topic", ""), platform=platform)
                elif ai_function == "analyze_issue":
                    output = await llm.generate_root_cause_analysis(inputs.get("topic", ""), platform=platform)
                elif ai_function == "marketing":
                    output = await llm.generate_marketing(inputs.get("strengths", ""), platform=platform)
                elif ai_function == "weekly_plan":
                    output = await llm.generate_weekly_plan(inputs.get("weaknesses", ""), platform=platform)
                elif ai_function == "training_script":
                    output = await llm.generate_training_script(inputs.get("issue", ""), platform=platform)
                elif ai_function == "internal_email":
                    output = await llm.generate_internal_email(
                        inputs.get("strengths", ""), inputs.get("weaknesses", ""), platform=platform,
                    )
                elif ai_function == "chat":
                    output = await llm.chat(inputs.get("message", ""), inputs.get("context", ""), platform=platform)
                else:
                    raise ValueError(f"unknown ai_function: {ai_function}")

                run.output_json = output if isinstance(output, dict) else {"text": output}
                run.status = "succeeded"
                run.finished_at = datetime.now(tz=timezone.utc)
                if not await _safe_commit_or_log(session, "analysis", run_id):
                    return

                await _push("analysis", run_id, "succeeded", {
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
                if not await _safe_commit_or_log(session, "analysis", run_id):
                    return
                await _push("analysis", run_id, "failed", {
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
    """Schedule an analysis run in the background."""
    asyncio.create_task(run_analysis_bg(run_id, store_id, ai_function, inputs, model_tier))
