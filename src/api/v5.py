"""
v5 API router — persistent multi-store insight workspace.

Mounted at /api/v5/* in src/main.py. Uses async SQLAlchemy session via
Depends(get_session_dep). All endpoints write to / read from the v5 tables.
"""
from __future__ import annotations

from typing import Optional

import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


# ────────────────────────────────────────────────────────────────────
# Helper: dev-mode default user
# ────────────────────────────────────────────────────────────────────
async def _get_or_create_default_user(session: AsyncSession) -> User:
    """v5.0.0-alpha 還沒做 auth — dev 模式下用 default user。"""
    result = await session.execute(select(User).where(User.email == "dev@insightx.local"))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email="dev@insightx.local", plan="free")
        session.add(user)
        await session.flush()
    return user


# ────────────────────────────────────────────────────────────────────
# Workspaces
# ────────────────────────────────────────────────────────────────────
@router.post("/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreate,
    session: AsyncSession = Depends(get_session_dep),
) -> WorkspaceOut:
    user = await _get_or_create_default_user(session)
    ws = Workspace(owner_user_id=user.id, name=body.name)
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return WorkspaceOut.model_validate(ws)


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(
    session: AsyncSession = Depends(get_session_dep),
) -> list[WorkspaceOut]:
    user = await _get_or_create_default_user(session)
    result = await session.execute(
        select(Workspace).where(Workspace.owner_user_id == user.id).order_by(Workspace.created_at.desc())
    )
    return [WorkspaceOut.model_validate(w) for w in result.scalars().all()]


# ────────────────────────────────────────────────────────────────────
# Stores
# ────────────────────────────────────────────────────────────────────
@router.post("/stores", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
async def create_store(
    body: StoreCreate,
    session: AsyncSession = Depends(get_session_dep),
) -> StoreOut:
    # 確認 workspace 存在 + 屬於當前 user
    user = await _get_or_create_default_user(session)
    ws = await session.get(Workspace, body.workspace_id)
    if ws is None or ws.owner_user_id != user.id:
        raise HTTPException(404, detail="workspace not found")

    store = Store(
        workspace_id=body.workspace_id,
        name=body.name,
        address=body.address,
        primary_url=body.primary_url,
        platform=body.platform,
    )
    session.add(store)
    await session.commit()
    await session.refresh(store)
    return StoreOut.model_validate(store)


@router.get("/stores", response_model=list[StoreOut])
async def list_stores(
    workspace_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session_dep),
) -> list[StoreOut]:
    user = await _get_or_create_default_user(session)
    stmt = (
        select(Store)
        .join(Workspace, Workspace.id == Store.workspace_id)
        .where(Workspace.owner_user_id == user.id)
        .order_by(Store.created_at.desc())
    )
    if workspace_id is not None:
        stmt = stmt.where(Store.workspace_id == workspace_id)
    result = await session.execute(stmt)
    return [StoreOut.model_validate(s) for s in result.scalars().all()]


@router.get("/stores/{store_id}", response_model=StoreOut)
async def get_store(
    store_id: int,
    session: AsyncSession = Depends(get_session_dep),
) -> StoreOut:
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(404, detail="store not found")
    return StoreOut.model_validate(store)


@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(
    store_id: int,
    session: AsyncSession = Depends(get_session_dep),
) -> None:
    """刪除店家 + cascade 砍掉 sources / jobs / reviews / runs / reports。

    - Ownership scoped: JOIN Workspace.owner_user_id == current user
      （配合 list_stores 的 pattern；v5α 還沒 auth、目前用 default user，
      但 endpoint 不能比 list 還寬鬆。）
    - 409 if active scrape/analysis exists: 避免 background worker await
      完外部 IO 後 commit 到 cascade-deleted row（jobs.py 也加了 _safe_commit
      容錯，但 API 層先擋是主防線）。
    - SQLite 需 PRAGMA foreign_keys=ON（src/db.py 已處理）；Postgres 直接走
      ondelete='CASCADE'。
    - 不刪 outputs/reports/ 下的實體 PDF/DOCX 檔（audit trail，之後再加清理 job）。
    """
    user = await _get_or_create_default_user(session)
    result = await session.execute(
        select(Store)
        .join(Workspace, Workspace.id == Store.workspace_id)
        .where(Store.id == store_id, Workspace.owner_user_id == user.id)
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise HTTPException(404, detail="store not found")

    active_scrape = await session.scalar(
        select(ScrapeJob.id)
        .join(ReviewSource, ReviewSource.id == ScrapeJob.source_id)
        .where(
            ReviewSource.store_id == store_id,
            ScrapeJob.status.in_(("queued", "running")),
        )
        .limit(1)
    )
    active_run = await session.scalar(
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

    await session.delete(store)
    await session.commit()


# ────────────────────────────────────────────────────────────────────
# Review sources
# ────────────────────────────────────────────────────────────────────
@router.post("/stores/{store_id}/sources", response_model=ReviewSourceOut, status_code=status.HTTP_201_CREATED)
async def add_source(
    store_id: int,
    body: ReviewSourceCreate,
    session: AsyncSession = Depends(get_session_dep),
) -> ReviewSourceOut:
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(404, detail="store not found")

    src = ReviewSource(
        store_id=store_id,
        source_type=body.source_type,
        external_url=body.external_url,
    )
    session.add(src)
    await session.commit()
    await session.refresh(src)
    return ReviewSourceOut.model_validate(src)


# ────────────────────────────────────────────────────────────────────
# Scrape jobs (Phase 3 同步版；Phase 4 改 background)
# ────────────────────────────────────────────────────────────────────
@router.post("/stores/{store_id}/scrape", response_model=ScrapeJobOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_scrape(
    store_id: int,
    session: AsyncSession = Depends(get_session_dep),
) -> ScrapeJobOut:
    """觸發 background scrape job。立刻回 job (status=queued)，client 用 GET /jobs/{id} 或 SSE 看進度。"""
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(404, detail="store not found")

    # 取第一個 source（v5.0.0-alpha 簡化：每個 store 一個 source）
    result = await session.execute(
        select(ReviewSource).where(ReviewSource.store_id == store_id).limit(1)
    )
    src = result.scalar_one_or_none()
    if src is None:
        raise HTTPException(400, detail="store has no review_source — POST /sources first")

    # 建 job row (status='queued')
    job = ScrapeJob(source_id=src.id, status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # fire-and-forget background task
    fire_scrape_job(job.id, src.id, src.external_url)

    return ScrapeJobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=ScrapeJobOut)
async def get_job(
    job_id: int,
    session: AsyncSession = Depends(get_session_dep),
) -> ScrapeJobOut:
    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(404, detail="job not found")
    return ScrapeJobOut.model_validate(job)


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: int) -> StreamingResponse:
    """SSE: 推 scrape job 進度 events 直到 succeeded/failed/timeout。"""
    return StreamingResponse(
        progress_stream("scrape", job_id, idle_timeout_s=180.0),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int) -> StreamingResponse:
    """SSE: 推 analysis run 進度 events 直到 succeeded/failed/timeout。"""
    return StreamingResponse(
        progress_stream("analysis", run_id, idle_timeout_s=180.0),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ────────────────────────────────────────────────────────────────────
# Reviews
# ────────────────────────────────────────────────────────────────────
@router.get("/stores/{store_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(
    store_id: int,
    limit: int = 100,
    session: AsyncSession = Depends(get_session_dep),
) -> list[ReviewOut]:
    """列指定 store 的最近 reviews（across all sources）。"""
    stmt = (
        select(Review)
        .join(ReviewSource, ReviewSource.id == Review.source_id)
        .where(ReviewSource.store_id == store_id)
        .order_by(Review.id.desc())
        .limit(min(limit, 500))
    )
    result = await session.execute(stmt)
    return [ReviewOut.model_validate(r) for r in result.scalars().all()]


# ────────────────────────────────────────────────────────────────────
# Analysis runs
# ────────────────────────────────────────────────────────────────────
@router.post("/stores/{store_id}/analyze", response_model=AnalysisRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    store_id: int,
    body: AnalysisRunCreate,
    session: AsyncSession = Depends(get_session_dep),
) -> AnalysisRunOut:
    """觸發 background analysis run。立刻回 run (status=queued)，client 用 GET /runs/{id} 或 SSE 看進度。"""
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(404, detail="store not found")

    inputs = dict(body.inputs)

    # 若 ai_function == 'analyze' 且沒帶 text，從 store 的 reviews table 組
    if body.ai_function == "analyze" and not inputs.get("text"):
        result = await session.execute(
            select(Review)
            .join(ReviewSource, ReviewSource.id == Review.source_id)
            .where(ReviewSource.store_id == store_id)
            .order_by(Review.id.desc())
            .limit(300)
        )
        reviews = result.scalars().all()
        if not reviews:
            raise HTTPException(400, detail="store has no reviews — trigger /scrape first")

        # 組 raw_text 給 LLM (mimics scraper output)
        lines = [f"【店家：{store.name}】顧客評論："]
        review_ids = []
        for r in reviews:
            star = f"（{r.rating}星）" if r.rating else ""
            lines.append(f"顧客評論{star}：{r.text}")
            review_ids.append(r.id)
        inputs["text"] = "\n\n".join(lines)
        inputs["input_review_ids"] = review_ids

    # 建 run row (status='queued')，fire background
    from src.services.llm_gateway import LLMGateway

    run = AnalysisRun(
        store_id=store_id,
        ai_function=body.ai_function,
        prompt_version=LLMGateway.PROMPT_VERSION,
        model_id="gemma-4-31b-it",
        input_review_ids=inputs.get("input_review_ids"),
        status="queued",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    fire_analysis_run(run.id, store_id, body.ai_function, inputs, body.model_tier)

    return AnalysisRunOut.model_validate(run)


@router.get("/stores/{store_id}/runs", response_model=list[AnalysisRunOut])
async def list_runs(
    store_id: int,
    limit: int = 50,
    session: AsyncSession = Depends(get_session_dep),
) -> list[AnalysisRunOut]:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.store_id == store_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(min(limit, 200))
    )
    result = await session.execute(stmt)
    return [AnalysisRunOut.model_validate(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}", response_model=AnalysisRunOut)
async def get_run(
    run_id: int,
    session: AsyncSession = Depends(get_session_dep),
) -> AnalysisRunOut:
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, detail="run not found")
    return AnalysisRunOut.model_validate(run)


# ────────────────────────────────────────────────────────────────────
# Compare (multi-store)
# ────────────────────────────────────────────────────────────────────
@router.get("/stores/{store_id}/compare", response_model=StoreCompareOut)
async def compare_stores(
    store_id: int,
    other: int,
    session: AsyncSession = Depends(get_session_dep),
) -> StoreCompareOut:
    a = await session.get(Store, store_id)
    b = await session.get(Store, other)
    if a is None or b is None:
        raise HTTPException(404, detail="one or both stores not found")

    async def latest_analyze(sid: int) -> Optional[AnalysisRun]:
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
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    run_a = await latest_analyze(store_id)
    run_b = await latest_analyze(other)

    return StoreCompareOut(
        store_a=StoreOut.model_validate(a),
        store_b=StoreOut.model_validate(b),
        latest_analyze_a=AnalysisRunOut.model_validate(run_a) if run_a else None,
        latest_analyze_b=AnalysisRunOut.model_validate(run_b) if run_b else None,
        summary=None,  # Phase 6 stretch: LLM 生成 prose comparison
    )


# ────────────────────────────────────────────────────────────────────
# Reports (PDF / DOCX export)
# ────────────────────────────────────────────────────────────────────
@router.post("/stores/{store_id}/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    store_id: int,
    body: ReportCreate,
    session: AsyncSession = Depends(get_session_dep),
) -> ReportOut:
    """同步生成報表（PDF or DOCX），寫到 outputs/reports/。"""
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(404, detail="store not found")

    report = Report(
        store_id=store_id,
        period_start=body.period_start,
        period_end=body.period_end,
        format=body.format,
        status="running",
    )
    session.add(report)
    await session.flush()  # get id

    await generate_report(session, store, report)
    await session.commit()
    await session.refresh(report)
    return ReportOut.model_validate(report)


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: int,
    session: AsyncSession = Depends(get_session_dep),
) -> ReportOut:
    rpt = await session.get(Report, report_id)
    if rpt is None:
        raise HTTPException(404, detail="report not found")
    return ReportOut.model_validate(rpt)


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: int,
    session: AsyncSession = Depends(get_session_dep),
) -> FileResponse:
    rpt = await session.get(Report, report_id)
    if rpt is None or rpt.file_path is None:
        raise HTTPException(404, detail="report file not ready")
    if not os.path.isfile(rpt.file_path):
        raise HTTPException(410, detail="report file missing on disk")
    media = "application/pdf" if rpt.format == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    fname = os.path.basename(rpt.file_path)
    return FileResponse(rpt.file_path, media_type=media, filename=fname)
