"""
v6.1 API router — persistent multi-store insight workspace, sync edition.

Mounted at /api/v5/* in src/main.py. Uses sync SQLAlchemy session via
Depends(get_session_dep). All endpoints write to / read from the v5 tables.

v6.1 changes (vs v6.0.0-alpha)
──────────────────────────────
Codex pre-freeze review (task 0d309dd01043) flagged two real boundary
issues in the v5α dev-mode handling:

  #1  Every request was scoped to one hard-coded `dev@insightx.local`
      user, so visitor A could see visitor B's data via /workspace/.
      v6.1 fix: src/auth.py — cookie-based anonymous session scoping.

  #2  Most by-id endpoints called `session.get(X, id)` without joining
      back to Workspace.owner_user_id, so ID-guessing could cross-tenant
      leak even after cookie scoping.
      v6.1 fix: this file — _get_owned_* helpers used everywhere.

v6 → v6.1 ABI delta: zero (frontend doesn't change). The cookie is
set transparently on first response; everything else is implementation
detail.
"""
from __future__ import annotations

import os
from hashlib import sha256
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth import get_current_user
from src.db import get_session_dep
from src.jobs import fire_analysis_run, fire_scrape_job, progress_stream
from src.models import (
    AnalysisRun,
    Report,
    Review,
    ReviewSource,
    ScrapeJob,
    Store,
    User,
    Workspace,
)
from src.schemas import (
    AnalysisRunCreate,
    AnalysisRunOut,
    ReportCreate,
    ReportOut,
    ReviewOut,
    ReviewSourceCreate,
    ReviewSourceOut,
    ScrapeJobOut,
    StoreCompareOut,
    StoreCreate,
    StoreOut,
    WorkspaceCreate,
    WorkspaceOut,
)
from src.services.reports import generate_report

router = APIRouter(prefix="/api/v5", tags=["v5"])

# SSE response headers
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


# ════════════════════════════════════════════════════════════════════
#  v6.1 Ownership-scoping helpers
# ════════════════════════════════════════════════════════════════════
# Every by-id endpoint goes through one of these. The query always
# joins back through Workspace.owner_user_id == user.id so visitors
# cannot read or mutate another visitor's data by guessing IDs.
#
# 404 (not 403) is intentional: don't leak existence of resources
# belonging to other users.


def _get_owned_workspace(session: Session, workspace_id: int, user: User) -> Workspace:
    ws = session.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_user_id == user.id,
        )
    )
    if ws is None:
        raise HTTPException(404, detail="workspace not found")
    return ws


def _get_owned_store(session: Session, store_id: int, user: User) -> Store:
    store = session.scalar(
        select(Store)
        .join(Workspace, Workspace.id == Store.workspace_id)
        .where(Store.id == store_id, Workspace.owner_user_id == user.id)
    )
    if store is None:
        raise HTTPException(404, detail="store not found")
    return store


def _get_owned_job(session: Session, job_id: int, user: User) -> ScrapeJob:
    job = session.scalar(
        select(ScrapeJob)
        .join(ReviewSource, ReviewSource.id == ScrapeJob.source_id)
        .join(Store, Store.id == ReviewSource.store_id)
        .join(Workspace, Workspace.id == Store.workspace_id)
        .where(ScrapeJob.id == job_id, Workspace.owner_user_id == user.id)
    )
    if job is None:
        raise HTTPException(404, detail="job not found")
    return job


def _get_owned_run(session: Session, run_id: int, user: User) -> AnalysisRun:
    run = session.scalar(
        select(AnalysisRun)
        .join(Store, Store.id == AnalysisRun.store_id)
        .join(Workspace, Workspace.id == Store.workspace_id)
        .where(AnalysisRun.id == run_id, Workspace.owner_user_id == user.id)
    )
    if run is None:
        raise HTTPException(404, detail="run not found")
    return run


def _get_owned_report(session: Session, report_id: int, user: User) -> Report:
    rpt = session.scalar(
        select(Report)
        .join(Store, Store.id == Report.store_id)
        .join(Workspace, Workspace.id == Store.workspace_id)
        .where(Report.id == report_id, Workspace.owner_user_id == user.id)
    )
    if rpt is None:
        raise HTTPException(404, detail="report not found")
    return rpt


# ════════════════════════════════════════════════════════════════════
#  Workspaces
# ════════════════════════════════════════════════════════════════════
@router.post("/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    body: WorkspaceCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> WorkspaceOut:
    ws = Workspace(owner_user_id=user.id, name=body.name)
    session.add(ws)
    session.commit()
    session.refresh(ws)
    return WorkspaceOut.model_validate(ws)


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> list[WorkspaceOut]:
    result = session.execute(
        select(Workspace)
        .where(Workspace.owner_user_id == user.id)
        .order_by(Workspace.created_at.desc())
    )
    return [WorkspaceOut.model_validate(w) for w in result.scalars().all()]


# ════════════════════════════════════════════════════════════════════
#  Stores
# ════════════════════════════════════════════════════════════════════
@router.post("/stores", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(
    body: StoreCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> StoreOut:
    _get_owned_workspace(session, body.workspace_id, user)  # 404 if not owned

    store = Store(
        workspace_id=body.workspace_id,
        name=body.name,
        address=body.address,
        primary_url=body.primary_url,
        platform=body.platform,
    )
    session.add(store)
    try:
        session.commit()
    except IntegrityError:
        # v6.1 #3: Store has UniqueConstraint(workspace_id, primary_url) —
        # concurrent same-URL POST races to one winner; we surface 409 so
        # the caller can re-GET the existing store instead of seeing a 500.
        session.rollback()
        raise HTTPException(409, detail="store with same primary_url already exists in this workspace")
    session.refresh(store)
    return StoreOut.model_validate(store)


@router.get("/stores", response_model=list[StoreOut])
def list_stores(
    workspace_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> list[StoreOut]:
    stmt = (
        select(Store)
        .join(Workspace, Workspace.id == Store.workspace_id)
        .where(Workspace.owner_user_id == user.id)
        .order_by(Store.created_at.desc())
    )
    if workspace_id is not None:
        stmt = stmt.where(Store.workspace_id == workspace_id)
    result = session.execute(stmt)
    return [StoreOut.model_validate(s) for s in result.scalars().all()]


@router.get("/stores/{store_id}", response_model=StoreOut)
def get_store(
    store_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> StoreOut:
    return StoreOut.model_validate(_get_owned_store(session, store_id, user))


@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store(
    store_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> None:
    """刪除店家 + cascade 砍掉 sources / jobs / reviews / runs / reports。

    Layered race protection (v5 Round 3, still in force):
      - API layer 409 if there's an active scrape/analysis (best-effort).
      - Worker layer `_safe_commit_or_log` in jobs.py catches the post-
        cascade IntegrityError if the race fires anyway.
      - Plus `passive_deletes=True` on every cascade relationship in
        src/models.py so the DB does the cascade in one statement.
    """
    store = _get_owned_store(session, store_id, user)  # 404 if not owned

    active_scrape = session.scalar(
        select(ScrapeJob.id)
        .join(ReviewSource, ReviewSource.id == ScrapeJob.source_id)
        .where(
            ReviewSource.store_id == store_id,
            ScrapeJob.status.in_(("queued", "running")),
        )
        .limit(1)
    )
    active_run = session.scalar(
        select(AnalysisRun.id)
        .where(
            AnalysisRun.store_id == store_id,
            AnalysisRun.status.in_(("queued", "running")),
        )
        .limit(1)
    )
    if active_scrape is not None or active_run is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="store has active scrape or analysis jobs",
        )

    session.delete(store)
    session.commit()


# ════════════════════════════════════════════════════════════════════
#  Review sources
# ════════════════════════════════════════════════════════════════════
@router.post("/stores/{store_id}/sources", response_model=ReviewSourceOut, status_code=status.HTTP_201_CREATED)
def add_source(
    store_id: int,
    body: ReviewSourceCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> ReviewSourceOut:
    _get_owned_store(session, store_id, user)  # 404 if not owned

    src = ReviewSource(
        store_id=store_id,
        source_type=body.source_type,
        external_url=body.external_url,
    )
    session.add(src)
    session.commit()
    session.refresh(src)
    return ReviewSourceOut.model_validate(src)


# ════════════════════════════════════════════════════════════════════
#  Scrape jobs (sync trigger; actual scrape runs in daemon thread)
# ════════════════════════════════════════════════════════════════════
@router.post("/stores/{store_id}/scrape", response_model=ScrapeJobOut, status_code=status.HTTP_202_ACCEPTED)
def trigger_scrape(
    store_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> ScrapeJobOut:
    """觸發 background scrape job。立刻回 job (status=queued)，client 用 GET /jobs/{id} 或 SSE 看進度。"""
    _get_owned_store(session, store_id, user)  # 404 if not owned

    # 取第一個 source（v5α 簡化：每個 store 一個 source）
    result = session.execute(
        select(ReviewSource).where(ReviewSource.store_id == store_id).limit(1)
    )
    src = result.scalar_one_or_none()
    if src is None:
        raise HTTPException(400, detail="store has no review_source — POST /sources first")

    job = ScrapeJob(source_id=src.id, status="queued")
    session.add(job)
    session.commit()
    session.refresh(job)

    fire_scrape_job(job.id, src.id, src.external_url)

    return ScrapeJobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=ScrapeJobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> ScrapeJobOut:
    return ScrapeJobOut.model_validate(_get_owned_job(session, job_id, user))


@router.get("/jobs/{job_id}/stream")
def stream_job(
    job_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> StreamingResponse:
    """SSE: 推 scrape job 進度 events 直到 succeeded/failed/timeout。

    v6.1: ownership-scoped — 404 if job belongs to another user.
    """
    _get_owned_job(session, job_id, user)  # 404 if not owned
    return StreamingResponse(
        progress_stream("scrape", job_id, idle_timeout_s=180.0),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/runs/{run_id}/stream")
def stream_run(
    run_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> StreamingResponse:
    """SSE: 推 analysis run 進度 events 直到 succeeded/failed/timeout。

    v6.1: ownership-scoped — 404 if run belongs to another user.
    """
    _get_owned_run(session, run_id, user)  # 404 if not owned
    return StreamingResponse(
        progress_stream("analysis", run_id, idle_timeout_s=180.0),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ════════════════════════════════════════════════════════════════════
#  Reviews
# ════════════════════════════════════════════════════════════════════
@router.get("/stores/{store_id}/reviews", response_model=list[ReviewOut])
def list_reviews(
    store_id: int,
    limit: int = 100,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> list[ReviewOut]:
    """列指定 store 的最近 reviews（across all sources）。"""
    _get_owned_store(session, store_id, user)  # 404 if not owned

    stmt = (
        select(Review)
        .join(ReviewSource, ReviewSource.id == Review.source_id)
        .where(ReviewSource.store_id == store_id)
        .order_by(Review.id.desc())
        .limit(min(limit, 500))
    )
    result = session.execute(stmt)
    return [ReviewOut.model_validate(r) for r in result.scalars().all()]


# ════════════════════════════════════════════════════════════════════
#  Analysis runs
# ════════════════════════════════════════════════════════════════════
@router.post("/stores/{store_id}/analyze", response_model=AnalysisRunOut, status_code=status.HTTP_202_ACCEPTED)
def trigger_analysis(
    store_id: int,
    body: AnalysisRunCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> AnalysisRunOut:
    """觸發 background analysis run。立刻回 run (status=queued)，client 用 GET /runs/{id} 或 SSE 看進度。"""
    store = _get_owned_store(session, store_id, user)  # 404 if not owned

    inputs = dict(body.inputs)

    # 若 ai_function == 'analyze' 且沒帶 text，從 store 的 reviews 組
    if body.ai_function == "analyze" and not inputs.get("text"):
        result = session.execute(
            select(Review)
            .join(ReviewSource, ReviewSource.id == Review.source_id)
            .where(ReviewSource.store_id == store_id)
            .order_by(Review.id.desc())
            .limit(300)
        )
        reviews = result.scalars().all()
        if not reviews:
            raise HTTPException(400, detail="store has no reviews — trigger /scrape first")

        lines = [f"【店家：{store.name}】顧客評論："]
        review_ids = []
        for r in reviews:
            star = f"（{r.rating}星）" if r.rating else ""
            lines.append(f"顧客評論{star}：{r.text}")
            review_ids.append(r.id)
        inputs["text"] = "\n\n".join(lines)
        inputs["input_review_ids"] = review_ids

    from src.services.llm_gateway import LLMGateway
    from src.services.llm_service import MODEL_CHAIN

    run = AnalysisRun(
        store_id=store_id,
        ai_function=body.ai_function,
        prompt_version=LLMGateway.PROMPT_VERSION,
        # v6.1 #5: model_id default tracks MODEL_CHAIN[0] (gemma-4-26b-a4b-it).
        # The worker (src/jobs.py run_analysis_bg) overwrites this with the
        # actual model that returned the successful response, captured from
        # LLMService._generate() returning (text, model_used). See models.py.
        model_id=MODEL_CHAIN[0],
        input_review_ids=inputs.get("input_review_ids"),
        status="queued",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    fire_analysis_run(run.id, store_id, body.ai_function, inputs, body.model_tier)

    return AnalysisRunOut.model_validate(run)


@router.get("/stores/{store_id}/runs", response_model=list[AnalysisRunOut])
def list_runs(
    store_id: int,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> list[AnalysisRunOut]:
    _get_owned_store(session, store_id, user)  # 404 if not owned

    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.store_id == store_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(min(limit, 200))
    )
    result = session.execute(stmt)
    return [AnalysisRunOut.model_validate(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}", response_model=AnalysisRunOut)
def get_run(
    run_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> AnalysisRunOut:
    return AnalysisRunOut.model_validate(_get_owned_run(session, run_id, user))


# ════════════════════════════════════════════════════════════════════
#  Compare (multi-store)
# ════════════════════════════════════════════════════════════════════
@router.get("/stores/{store_id}/compare", response_model=StoreCompareOut)
def compare_stores(
    store_id: int,
    other: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> StoreCompareOut:
    a = _get_owned_store(session, store_id, user)
    b = _get_owned_store(session, other, user)

    def latest_analyze(sid: int) -> Optional[AnalysisRun]:
        stmt = (
            select(AnalysisRun)
            .where(
                AnalysisRun.store_id == sid,
                AnalysisRun.ai_function == "analyze",
                AnalysisRun.status == "succeeded",
            )
            .order_by(AnalysisRun.created_at.desc())
            .limit(1)
        )
        return session.execute(stmt).scalar_one_or_none()

    return StoreCompareOut(
        store_a=StoreOut.model_validate(a),
        store_b=StoreOut.model_validate(b),
        latest_analyze_a=AnalysisRunOut.model_validate(latest_analyze(store_id)) if latest_analyze(store_id) else None,
        latest_analyze_b=AnalysisRunOut.model_validate(latest_analyze(other)) if latest_analyze(other) else None,
        summary=None,
    )


# ════════════════════════════════════════════════════════════════════
#  Reports (PDF / DOCX export)
# ════════════════════════════════════════════════════════════════════
@router.post("/stores/{store_id}/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    store_id: int,
    body: ReportCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> ReportOut:
    """同步生成報表（PDF or DOCX），寫到 outputs/reports/。"""
    store = _get_owned_store(session, store_id, user)  # 404 if not owned

    report = Report(
        store_id=store_id,
        period_start=body.period_start,
        period_end=body.period_end,
        format=body.format,
        status="running",
    )
    session.add(report)
    session.flush()  # get id

    generate_report(session, store, report)
    session.commit()
    session.refresh(report)
    return ReportOut.model_validate(report)


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> ReportOut:
    return ReportOut.model_validate(_get_owned_report(session, report_id, user))


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dep),
) -> FileResponse:
    """Download generated report (PDF or DOCX).

    v6.0 deploy-review fix (CRITICAL): on HF Spaces free tier the container
    is ephemeral — after the 48h auto-sleep + restart cycle, the Report row
    still exists in Turso but `outputs/reports/store{id}_*.{ext}` is gone.
    Instead of returning 410, regenerate the file lazily on download.

    v6.1: ownership-scoped — _get_owned_report 404s on cross-tenant access.
    """
    rpt = _get_owned_report(session, report_id, user)
    if rpt.file_path is None:
        raise HTTPException(404, detail="report file not ready")

    if not os.path.isfile(rpt.file_path):
        # Cold-restart fallback: file vanished with the ephemeral container.
        # We already know the store is owned via the join in _get_owned_report.
        store = session.get(Store, rpt.store_id)
        if store is None:
            raise HTTPException(
                410, detail="report file missing and source store deleted"
            )
        generate_report(session, store, rpt)
        session.commit()
        session.refresh(rpt)
        if rpt.status != "succeeded" or not rpt.file_path or not os.path.isfile(rpt.file_path):
            raise HTTPException(
                500, detail="report regeneration failed; see server logs"
            )

    media = "application/pdf" if rpt.format == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    fname = os.path.basename(rpt.file_path)
    return FileResponse(rpt.file_path, media_type=media, filename=fname)
