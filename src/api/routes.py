"""
v4 API routes — v6 sync edition.

Converted from async to sync. SSE generators use threading.Thread + queue.Queue
for producer-consumer pattern (was asyncio.Queue + asyncio.create_task in v5).

Endpoints (mounted at /api/* by main.py):
  POST /analyze              主要分析（scrape + LLM）
  POST /debug-scrape         純爬蟲（debug 用）
  POST /swot                 SWOT 動態生成
  POST /reply                負面意見回覆
  POST /analyze-issue        根源問題分析
  POST /marketing            行銷文案
  POST /weekly-plan          週行動計畫
  POST /training-script      培訓劇本
  POST /internal-email       內部信
  POST /chat                 AI 顧問對話
  GET  /meta                 app metadata + feature flags
  GET  /v4/analyze-stream    v4 結構化 SSE (主要 UI 用)
  GET  /analyze-stream       legacy SSE (v3 /legacy UI 用)
"""

import json
import os
import queue as queue_mod
import threading
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from src.config.mock_responses import get_mock_response
from src.db import SessionLocal
from src.models import (
    AnalysisRun,
    Review,
    ReviewSource,
    ScrapeJob,
    Store,
    User,
    Workspace,
)
from src.services.canonicalizer import (
    Platform,
    attach_metadata,
    canonicalize_yt_role,
    verify_platform_hint,
)
from src.services.llm_service import LLMService
from src.services.scraper_service import ScraperService

router = APIRouter()
scraper = ScraperService()
llm = LLMService()

APP_VERSION = "6.0.0-alpha"

# Route-level budgets (sync edition — service-level timeouts enforce
# per-call limits; these are advisory ceilings for the route as a whole.
# We no longer use asyncio.wait_for to hard-cancel; if a scrape blows
# past budget, the per-request HTTP timeouts inside scraper/llm catch it.)
ROUTE_ANALYZE_LLM_FLOOR_S = 10.0  # 少於這就跳過 LLM 直接回 mock
SSE_ANALYZE_LLM_BUDGET_S = 90.0   # LLM call budget for SSE path


# ────────────────────────────────────────────────────────────────────
# v6 bridge: v4 stateless analyze → v5 workspace persistence
#
# Bug background: v4 /api/analyze and /api/v4/analyze-stream were
# completely stateless — they scrape + run Gemini and return JSON, but
# never wrote to the v5 Turso schema. Result: user analyzes a store on
# the landing page, then opens /workspace/, sees nothing. The two paths
# never met.
#
# This bridge persists every successful v4 analyze as a v5 Store with
# its ReviewSource + ScrapeJob + Reviews + AnalysisRun. Idempotent on
# (workspace, external_url): re-analyzing the same URL refreshes the
# existing Store and appends new ScrapeJob/AnalysisRun rows (audit trail).
#
# ⚠️ DISABLED BY DEFAULT (env-gated)
# ─────────────────────────────────────
# Codex pre-freeze review (task 0d309dd01043) flagged a CRITICAL privacy
# issue: there's no auth yet (v5α dev mode uses a hard-coded default user),
# so on a multi-tenant public demo, EVERY visitor's landing analyzes
# would write into the same shared workspace — User A could open
# /workspace/ and see User B's analyzed URLs / review text / generated
# reports. That's a real data-boundary leak.
#
# Until cookie-based anonymous session scoping lands (planned v6.1), the
# bridge is OFF on public deployments. Set `IX_ENABLE_V4_WORKSPACE_PERSIST=1`
# in your env to enable — appropriate for single-user self-hosting only.
#
# Failure (after the flag check) is NON-FATAL — wrapped in try/except +
# logged. The v4 response is the user-facing result; persistence is
# best-effort.
# ────────────────────────────────────────────────────────────────────

# Codex CRITICAL fix: env flag — explicit opt-in required.
# Default OFF for public-demo safety. Self-hosted single-user: set =1.
_ENABLE_V4_WORKSPACE_PERSIST = os.getenv("IX_ENABLE_V4_WORKSPACE_PERSIST", "0") == "1"

def _get_or_create_default_user(session) -> User:
    """v5α dev mode — same default user as src/api/v5.py uses. Duplicated
    here (not imported) to keep route modules import-independent."""
    result = session.execute(select(User).where(User.email == "dev@insightx.local"))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email="dev@insightx.local", plan="free")
        session.add(user)
        session.flush()
    return user


def _persist_v4_analyze_to_workspace(
    url: str,
    platform: str,
    scrape_result: dict,
    analysis_result: Optional[dict],
) -> None:
    """Bridge v4 analyze → v5 workspace. Idempotent on external_url; non-fatal.

    Called after a successful (or partially successful) v4 analyze. Always
    swallows exceptions — the v4 user-facing response must not break because
    of a DB hiccup. Logs warnings on failure for debugging.

    Gated by IX_ENABLE_V4_WORKSPACE_PERSIST env flag (see module-level
    constant comment). On public multi-tenant demos this MUST stay disabled
    until cookie-based session scoping is implemented.
    """
    if not _ENABLE_V4_WORKSPACE_PERSIST:
        return  # multi-tenant safety: bridge disabled by default
    try:
        with SessionLocal() as session:
            user = _get_or_create_default_user(session)

            # 1. Default workspace per user (create on first analyze)
            ws = session.scalar(
                select(Workspace)
                .where(Workspace.owner_user_id == user.id)
                .order_by(Workspace.id)
                .limit(1)
            )
            if ws is None:
                ws = Workspace(owner_user_id=user.id, name="我的分析")
                session.add(ws)
                session.flush()

            # 2. Find existing ReviewSource for this URL within the workspace
            src = session.scalar(
                select(ReviewSource)
                .join(Store, Store.id == ReviewSource.store_id)
                .where(
                    Store.workspace_id == ws.id,
                    ReviewSource.external_url == url,
                )
                .limit(1)
            )

            now = datetime.now(tz=timezone.utc)
            source_type = "youtube" if platform == "youtube" else "google_maps"
            store_name = (scrape_result.get("store_name") or "").strip() or "Untitled"
            address = scrape_result.get("address") or None
            review_count = scrape_result.get("review_count") or 0
            if not isinstance(review_count, int):
                review_count = 0

            if src is None:
                # New store + new source
                store = Store(
                    workspace_id=ws.id,
                    name=store_name[:255],
                    address=(address or "")[:500] or None,
                    primary_url=url[:2000],
                    platform=platform if platform in ("google", "youtube") else "google",
                )
                session.add(store)
                session.flush()

                src = ReviewSource(
                    store_id=store.id,
                    source_type=source_type,
                    external_url=url[:2000],
                    last_scraped_at=now,
                    total_reviews_estimated=review_count,
                )
                session.add(src)
                session.flush()
            else:
                # Existing store — refresh metadata + reuse source
                store = session.get(Store, src.store_id)
                if store is not None:
                    if store_name and store.name != store_name:
                        store.name = store_name[:255]
                    if address and store.address != address:
                        store.address = address[:500]
                    if store.primary_url != url:
                        store.primary_url = url[:2000]
                src.last_scraped_at = now
                if review_count:
                    src.total_reviews_estimated = review_count

            # 3. New ScrapeJob (succeeded — we already have data in hand)
            job = ScrapeJob(
                source_id=src.id,
                status="succeeded",
                started_at=now,
                finished_at=now,
                reviews_fetched_count=review_count,
                pagination_truncated=bool(scrape_result.get("pagination_truncated", False)),
            )
            session.add(job)
            session.flush()

            # 4. Reviews (if structured list present)
            structured = scrape_result.get("reviews_structured") or []
            if isinstance(structured, list):
                for r in structured:
                    if not isinstance(r, dict):
                        continue
                    text = (r.get("text") or "").strip()
                    if not text:
                        continue
                    rev = Review(
                        source_id=src.id,
                        scrape_job_id=job.id,
                        author=(r.get("author") or None),
                        rating=r.get("rating") if isinstance(r.get("rating"), int) else None,
                        text=text,
                    )
                    session.add(rev)

            # 5. AnalysisRun (if LLM produced a result dict)
            if isinstance(analysis_result, dict):
                run = AnalysisRun(
                    store_id=store.id,
                    ai_function="analyze",
                    status="succeeded",
                    started_at=now,
                    finished_at=now,
                    output_json=analysis_result,
                )
                session.add(run)

            session.commit()
            print(
                f"[v6|persist] saved store_id={store.id} source_id={src.id} "
                f"job_id={job.id} reviews={len(structured)} url={url[:60]}",
                flush=True,
            )
    except Exception as exc:
        # Non-fatal — analyze response is the user-facing result.
        import traceback
        print(
            f"[v6|persist] WARN: failed to persist v4 analyze to workspace: {exc}",
            flush=True,
        )
        traceback.print_exc()


def _attach_scrape_context(target: dict, scrape_result: dict, platform: str) -> None:
    if not isinstance(target, dict) or not isinstance(scrape_result, dict):
        return

    for key in ("address", "category", "rating", "rating_count"):
        value = scrape_result.get(key)
        if value:
            target[key] = value

    reviews_structured = scrape_result.get("reviews_structured")
    if isinstance(reviews_structured, list):
        target["reviews_structured"] = reviews_structured

    review_count = scrape_result.get("review_count")
    if isinstance(review_count, int) and review_count > 0:
        target["review_count"] = review_count
        target["reviews_analyzed"] = review_count
        if platform == "youtube":
            target["total_reviews"] = f"共分析 {review_count} 則觀眾留言"
        else:
            total_reviews = scrape_result.get("total_reviews") or scrape_result.get("rating_count")
            if total_reviews not in (None, ""):
                if isinstance(total_reviews, int):
                    target["total_reviews"] = f"Google Maps 共 {total_reviews} 則評分"
                else:
                    target["total_reviews"] = total_reviews

# ---- Request Models ----


class AnalyzeRequest(BaseModel):
    url: str
    platform: Optional[Literal["google", "youtube"]] = None
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


class SwotRequest(BaseModel):
    good: list
    bad: list
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


class ReplyRequest(BaseModel):
    topic: str
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


class MarketingRequest(BaseModel):
    strengths: str
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


class WeeklyPlanRequest(BaseModel):
    weaknesses: str
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


class TrainingScriptRequest(BaseModel):
    issue: str
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


class InternalEmailRequest(BaseModel):
    strengths: str
    weaknesses: str
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


class ChatRequest(BaseModel):
    message: str
    context: str = ""
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None


# ---- Mock fallback data ----

MOCK_ANALYSIS = {
    "store_name": "",
    "platform": "google",
    "total_reviews": "共分析 723 則 Google Maps 評論（Demo 數據）",
    "good": [
        {"label": "餐點美味", "value": 32},
        {"label": "環境舒適", "value": 25},
        {"label": "服務親切", "value": 20}
    ],
    "bad": [
        {"label": "出餐速度慢", "value": 40},
        {"label": "停車不方便", "value": 18},
        {"label": "價格偏高", "value": 12}
    ]
}

MOCK_ANALYSIS_YOUTUBE = {
    "store_name": "",
    "platform": "youtube",
    "total_reviews": "共分析 186 則觀眾留言（Demo 數據）",
    "good": [
        {"label": "資訊實用、節奏明快", "value": 34},
        {"label": "剪輯流暢、視覺乾淨", "value": 22},
        {"label": "主持人有個人魅力", "value": 18}
    ],
    "bad": [
        {"label": "開頭鋪陳太久", "value": 35},
        {"label": "音量/配樂不平衡", "value": 20},
        {"label": "標題與內容落差", "value": 14}
    ]
}

# ---- Endpoints ----


@router.post("/analyze")
def analyze(request: AnalyzeRequest):
    """主要分析端點（v4.0.0，v6 sync）。"""
    from src.services.youtube_scraper import is_youtube_url

    warnings: list = []

    detected_platform: Platform = "youtube" if is_youtube_url(request.url) else "google"
    verify_platform_hint(detected_platform, request.platform)

    effective_yt_role = canonicalize_yt_role(detected_platform, request.yt_role, warnings)

    route_start = time.monotonic()

    try:
        print(f"\n{'='*55}")
        print(f"[INFO] 收到分析請求: {request.url}（platform={detected_platform}, yt_role={effective_yt_role}）")

        if detected_platform == "youtube":
            mock_fallback = dict(MOCK_ANALYSIS_YOUTUBE)
            source_label = "留言"
        else:
            mock_fallback = dict(MOCK_ANALYSIS)
            source_label = "評論"

        # Step 1: 爬取（service 層自己有 timeout，不再外包 asyncio.wait_for）
        print(f"[INFO] Step 1/2 · 爬取{source_label}中...")
        raw_text = ""
        scraper_store_name = ""
        scraped_platform: Platform = detected_platform
        scrape_result: dict = {}
        try:
            scrape_result = scraper.scrape_url(request.url)
            raw_text = scrape_result.get("raw_text", "")
            scraper_store_name = scrape_result.get("store_name", "")
            review_count = scrape_result.get("review_count", 0)
            scraped_platform = scrape_result.get("platform", detected_platform)
            print(f"[INFO] 爬蟲完成 · 標的={scraper_store_name!r} · {review_count} 則{source_label} · {len(raw_text)} 字元")

            if scraped_platform == "youtube" and scrape_result.get("status") == "error":
                err_result = {
                    "store_name": "",
                    "status": "error",
                    "platform": scraped_platform,
                    "total_reviews": "0",
                    "good": [],
                    "bad": [],
                    "message": scrape_result.get("error") or "YouTube 爬取失敗",
                }
                return attach_metadata(
                    err_result,
                    effective_yt_role=effective_yt_role,
                    fallback=False,
                    warnings=warnings,
                )
        except Exception as e:
            print(f"[WARN] 爬蟲失敗: {e}")
            warnings.append(f"scraper error: {str(e)[:80]}")

        # Step 2: Gemini 分析
        if raw_text and len(raw_text.strip()) >= 50:
            elapsed = time.monotonic() - route_start
            print(f"[INFO] Step 2/2 · Gemini AI 分析中...（platform={scraped_platform}, elapsed={elapsed:.1f}s）")
            try:
                # LLM service 自己控 timeout
                result = llm.analyze_content(raw_text, platform=scraped_platform)
            except Exception as llm_exc:
                warnings.append(f"gemini error: {str(llm_exc)[:80]}")
                print(f"[WARN] Gemini 分析失敗: {llm_exc}，退回 Mock 數據")
                result = None

            if result is not None:
                if scraper_store_name:
                    result["store_name"] = scraper_store_name
                result["platform"] = scraped_platform

                _attach_scrape_context(result, scrape_result, scraped_platform)

                has_reviews = result.get("good") or result.get("bad")
                if not has_reviews:
                    print("[WARN] Gemini 未分析到內容，返回 no_reviews 狀態")
                    unknown_label = "未知影片" if scraped_platform == "youtube" else "未知店家"
                    no_review_result = {
                        "store_name": scraper_store_name or unknown_label,
                        "status": "no_reviews",
                        "platform": scraped_platform,
                        "total_reviews": "0",
                        "good": [],
                        "bad": [],
                        "message": f"找不到「{scraper_store_name}」的{source_label}資料。",
                    }
                    return attach_metadata(
                        no_review_result,
                        effective_yt_role=effective_yt_role,
                        fallback=False,
                        warnings=warnings,
                    )

                print(f"[SUCCESS] 分析完成 · 標的={result.get('store_name', '')!r} · "
                      f"正面={len(result.get('good', []))} · 負面={len(result.get('bad', []))}")

                # v6 bridge: persist this successful analyze to /workspace/
                # so the store shows up after the user finishes here.
                _persist_v4_analyze_to_workspace(
                    url=request.url,
                    platform=scraped_platform,
                    scrape_result=scrape_result,
                    analysis_result=result,
                )

                return attach_metadata(
                    result,
                    effective_yt_role=effective_yt_role,
                    fallback=False,
                    warnings=warnings,
                )
        else:
            warnings.append("insufficient scraped content (<50 chars)")
            print("[WARN] 內容不足，退回 Mock 數據")

        # Fallback
        print(f"[INFO] 返回 Mock 數據（platform={detected_platform}）")
        return attach_metadata(
            mock_fallback,
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("[ERROR] 發生未預期錯誤:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析失敗: {str(e)}")


@router.post("/debug-scrape")
def debug_scrape(request: AnalyzeRequest):
    """純爬蟲測試端點，不呼叫 AI，直接回傳爬取結果。"""
    try:
        scrape_result = scraper.scrape_url(request.url)
        raw_text = scrape_result.get("raw_text", "")
        return {
            "status": scrape_result.get("status"),
            "platform": scrape_result.get("platform", ""),
            "store_name": scrape_result.get("store_name", ""),
            "review_count": scrape_result.get("review_count", 0),
            "source": scrape_result.get("video_data", {}).get("source", ""),
            "char_count": len(raw_text),
            "preview": raw_text[:500] if raw_text else "",
            "error": scrape_result.get("error", None),
        }
    except Exception as e:
        return {"status": "error", "char_count": 0, "preview": "", "store_name": "", "error": str(e)}


@router.post("/swot")
def generate_swot(request: SwotRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    if not request.good and not request.bad:
        warnings.append("swot skipped: empty good/bad")
        return attach_metadata(
            {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    try:
        swot = llm.generate_swot(request.good, request.bad, platform=request.platform)
        return attach_metadata(
            swot if isinstance(swot, dict) else {"swot": swot},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        return attach_metadata(
            {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/reply")
def generate_reply(request: ReplyRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        reply = llm.generate_reply(request.topic, platform=request.platform)
        return attach_metadata(
            {"reply": reply},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        reply = get_mock_response("reply_to_complaint", topic=request.topic, platform=request.platform)
        return attach_metadata(
            {"reply": reply},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/analyze-issue")
def analyze_issue(request: ReplyRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        analysis = llm.generate_root_cause_analysis(request.topic, platform=request.platform)
        return attach_metadata(
            {"analysis": analysis},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        analysis = get_mock_response("root_cause_analysis", topic=request.topic, platform=request.platform)
        return attach_metadata(
            {"analysis": analysis},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/marketing")
def generate_marketing(request: MarketingRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        copy = llm.generate_marketing(request.strengths, platform=request.platform)
        return attach_metadata(
            {"copy": copy},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        copy = get_mock_response("marketing_copy", strengths=request.strengths, platform=request.platform)
        return attach_metadata(
            {"copy": copy},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/weekly-plan")
def generate_weekly_plan(request: WeeklyPlanRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        plan = llm.generate_weekly_plan(request.weaknesses, platform=request.platform)
        return attach_metadata(
            {"plan": plan},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        plan = get_mock_response("weekly_plan", weaknesses=request.weaknesses, platform=request.platform)
        return attach_metadata(
            {"plan": plan},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/training-script")
def generate_training_script(request: TrainingScriptRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        script = llm.generate_training_script(request.issue, platform=request.platform)
        return attach_metadata(
            {"script": script},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        script = get_mock_response("training_script", issue=request.issue, platform=request.platform)
        return attach_metadata(
            {"script": script},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/internal-email")
def generate_internal_email(request: InternalEmailRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        email = llm.generate_internal_email(
            request.strengths, request.weaknesses, platform=request.platform
        )
        return attach_metadata(
            {"email": email},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        email = get_mock_response(
            "internal_email",
            strengths=request.strengths,
            weaknesses=request.weaknesses,
            platform=request.platform,
        )
        return attach_metadata(
            {"email": email},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/chat")
def chat(request: ChatRequest):
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        reply = llm.chat(request.message, request.context, platform=request.platform)
        return attach_metadata(
            {"reply": reply},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        return attach_metadata(
            {"reply": "抱歉，AI 助手暫時無法回應，請稍後再試。"},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.get("/meta")
def get_meta():
    return {
        "appVersion": APP_VERSION,
        "availablePlatforms": ["google", "youtube"],
        "availableYtRoles": ["creator", "shop", "brand"],
        "featureFlags": {
            "sse_v4": True,
            "chat_history_persist": False,
        },
        "_fallback": False,
        "warnings": [],
    }


# ---- v4 結構化 SSE (sync edition using threading + queue.Queue) ----

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/v4/analyze-stream")
def analyze_stream_v4(
    url: str = Query(..., min_length=1),
    platform: Optional[Literal["google", "youtube"]] = Query(None),
    yt_role: Optional[Literal["creator", "shop", "brand"]] = Query(None),
):
    """v4 結構化 SSE。v6 sync 改用 threading + queue.Queue."""
    from src.services.youtube_scraper import is_youtube_url

    # Pre-stream validation (HTTP 422, 不進 stream)
    detected_platform: Platform = "youtube" if is_youtube_url(url) else "google"
    verify_platform_hint(detected_platform, platform)

    warnings: list = []
    effective_yt_role = canonicalize_yt_role(detected_platform, yt_role, warnings)

    total_steps = 4
    started = time.monotonic()

    def event_generator():
        """Sync generator. producer (worker thread) + heartbeat thread + consumer (this)."""
        import logging
        logger = logging.getLogger("insightx.sse")

        event_q: queue_mod.Queue = queue_mod.Queue()
        done_event = threading.Event()

        def duration_ms() -> int:
            return int((time.monotonic() - started) * 1000)

        def progress(phase: str, step: int, label: str, prog: float,
                     include_platform: bool) -> dict:
            return {
                "phase": phase,
                "step": step,
                "totalSteps": total_steps,
                "label": label,
                "progress": prog,
                "platform": detected_platform if include_platform else None,
                "effective_yt_role": effective_yt_role if include_platform else None,
            }

        def failed_frame(code: str, message: str, *, retryable: bool,
                         retry_after_secs: Optional[int] = None) -> str:
            payload = {
                "code": code,
                "message": message,
                "retryable": retryable,
                "platform": detected_platform,
                "effective_yt_role": effective_yt_role,
                "durationMs": duration_ms(),
            }
            if retry_after_secs is not None:
                payload["retry_after_secs"] = retry_after_secs
            return _sse_event("failed", payload)

        def heartbeat():
            """Send : ping every 15s until done_event is set."""
            while not done_event.is_set():
                # wait returns True if event set, False if timeout
                if done_event.wait(timeout=15.0):
                    return
                try:
                    event_q.put_nowait(("raw", ": ping\n\n"))
                except queue_mod.Full:
                    pass

        def worker():
            # Codex C2 fix: check done_event between phases so client-disconnect
            # cleanup stops scheduling wasted scrape/LLM work. Cannot interrupt
            # an in-flight sync HTTP call (Python threads aren't cancellable),
            # but bounded by the service-level http timeouts (~30s scrape, ~90s LLM).
            try:
                # step 0: connected
                event_q.put(("event", _sse_event("progress", progress(
                    "connected", 0, "Connected. Waiting for server to start analysis.",
                    0.0, include_platform=False,
                ))))

                # step 1 / 2: scraping
                if detected_platform == "youtube":
                    label1 = "Resolving video metadata…"
                    label2 = "Fetching comments…"
                else:
                    label1 = "Resolving store URL…"
                    label2 = "Fetching reviews via Serper…"
                event_q.put(("event", _sse_event("progress", progress(
                    "scraping", 1, label1, 0.2, include_platform=True,
                ))))
                event_q.put(("event", _sse_event("progress", progress(
                    "scraping", 2, label2, 0.4, include_platform=True,
                ))))

                if done_event.is_set():
                    return  # client disconnected before scrape

                raw_text = ""
                scraper_store_name = ""
                scraped_platform: Platform = detected_platform
                scrape_result: dict = {}
                try:
                    scrape_result = scraper.scrape_url(url)
                    raw_text = scrape_result.get("raw_text", "")
                    scraper_store_name = scrape_result.get("store_name", "")
                    scraped_platform = scrape_result.get("platform", detected_platform)

                    scrape_err = scrape_result.get("error")
                    if scrape_result.get("status") == "error" and scrape_err:
                        event_q.put(("terminal", failed_frame(
                            "VALIDATION_ERROR", scrape_err[:200], retryable=False,
                        )))
                        return
                except Exception as e:
                    warnings.append(f"scraper error: {str(e)[:80]}")
                    event_q.put(("terminal", failed_frame(
                        "SCRAPER_ERROR", f"Scraper failed: {str(e)[:180]}",
                        retryable=True,
                    )))
                    return

                if done_event.is_set():
                    return  # client disconnected between scrape and LLM

                # step 3: analyzing
                event_q.put(("event", _sse_event("progress", progress(
                    "analyzing", 3, "Running Gemini analysis…", 0.7,
                    include_platform=True,
                ))))

                if not raw_text or len(raw_text.strip()) < 50:
                    event_q.put(("terminal", failed_frame(
                        "VALIDATION_ERROR",
                        "Insufficient content scraped (< 50 chars). URL may be a deleted video / closed store.",
                        retryable=False,
                    )))
                    return

                try:
                    analysis = llm.analyze_content(
                        raw_text,
                        platform=scraped_platform,
                        total_timeout_s=SSE_ANALYZE_LLM_BUDGET_S,
                    )
                except Exception as e:
                    import traceback as _tb
                    err_type = type(e).__name__
                    err_msg = str(e) or "(no message)"
                    full_tb = _tb.format_exc()
                    print(f"[v4-sse] LLM_ERROR {err_type}: {err_msg}\n{full_tb}", flush=True)
                    event_q.put(("terminal", failed_frame(
                        "LLM_ERROR",
                        f"LLM call failed ({err_type}): {err_msg[:160]}",
                        retryable=True, retry_after_secs=10,
                    )))
                    return

                # step 4: finalizing
                event_q.put(("event", _sse_event("progress", progress(
                    "finalizing", 4, "Packaging result…", 1.0,
                    include_platform=True,
                ))))

                if scraper_store_name:
                    analysis["store_name"] = scraper_store_name
                analysis["platform"] = scraped_platform

                _attach_scrape_context(analysis, scrape_result, scraped_platform)

                has_reviews = analysis.get("good") or analysis.get("bad")
                if not has_reviews:
                    unknown_label = "未知影片" if scraped_platform == "youtube" else "未知店家"
                    analysis = {
                        "store_name": scraper_store_name or unknown_label,
                        "status": "no_reviews",
                        "platform": scraped_platform,
                        "total_reviews": "0",
                        "good": [],
                        "bad": [],
                        "message": f"找不到「{scraper_store_name}」的內容。",
                    }

                data = attach_metadata(
                    analysis,
                    effective_yt_role=effective_yt_role,
                    fallback=False,
                    warnings=warnings,
                )

                # v6 bridge: persist this successful SSE analyze to /workspace/
                # (only when we have real reviews — skip no_reviews fallback case).
                if analysis.get("good") or analysis.get("bad"):
                    _persist_v4_analyze_to_workspace(
                        url=url,
                        platform=scraped_platform,
                        scrape_result=scrape_result,
                        analysis_result=analysis,
                    )

                event_q.put(("terminal", _sse_event("result", {
                    "platform": detected_platform,
                    "effective_yt_role": effective_yt_role,
                    "durationMs": duration_ms(),
                    "data": data,
                })))
            except Exception as e:
                import traceback
                traceback.print_exc()
                event_q.put(("terminal", failed_frame(
                    "UNKNOWN_ERROR", f"Unexpected server error: {str(e)[:180]}",
                    retryable=False,
                )))

        hb_thread = threading.Thread(target=heartbeat, daemon=True, name="sse-heartbeat")
        worker_thread = threading.Thread(target=worker, daemon=True, name="sse-worker")
        hb_thread.start()
        worker_thread.start()

        try:
            while True:
                kind, payload = event_q.get()
                if kind == "terminal":
                    done_event.set()
                    yield payload
                    break
                yield payload
        finally:
            # signal both threads to stop. daemon=True ensures process exit
            # won't be blocked if they linger (e.g. mid HTTP call).
            done_event.set()
            # Best-effort short join; warn if still alive
            hb_thread.join(timeout=1.0)
            worker_thread.join(timeout=1.0)
            if worker_thread.is_alive():
                logger.warning("SSE worker thread still alive after stream cleanup")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/analyze-stream")
def analyze_stream(url: str):
    """
    [DEPRECATED · v3 legacy SSE]
    使用情境：只剩 `/legacy` HTML 在用。新 v4 UI 走 `/api/v4/analyze-stream`.
    v6 sync 簡化版：純 sync generator，不用 producer-consumer。
    """
    from src.services.youtube_scraper import is_youtube_url

    def event_generator():
        def log(msg: str):
            return f"data: {msg}\n\n"

        try:
            yield log("🔍 收到分析請求")
            is_yt = is_youtube_url(url)
            if is_yt:
                platform = "youtube"
                source_label = "留言"
                target_label = "影片"
                api_label = "YouTube Data API"
                mock_fallback = MOCK_ANALYSIS_YOUTUBE
            else:
                platform = "google"
                source_label = "評論"
                target_label = "店家"
                api_label = "Serper API"
                mock_fallback = MOCK_ANALYSIS
            yield log(f"🎯 平台偵測：{platform}")

            # Step 1: 爬取
            yield log(f"⏳ Step 1/2 · {api_label} 爬取{source_label}中...")
            raw_text = ""
            scraper_store_name = ""
            scraped_platform = platform
            scrape_error = None
            scrape_result: dict = {}
            try:
                scrape_result = scraper.scrape_url(url)
                raw_text = scrape_result.get("raw_text", "")
                scraper_store_name = scrape_result.get("store_name", "")
                review_count = scrape_result.get("review_count", 0)
                scraped_platform = scrape_result.get("platform", platform)
                chars = len(raw_text.strip())
                scrape_error = scrape_result.get("error")

                if chars >= 50:
                    label = scraper_store_name or f"未知{target_label}"
                    yield log(f"✅ 爬蟲成功 · {target_label}：{label} · {review_count} 則{source_label} · {chars} 字元")
                elif scrape_error:
                    yield log(f"❌ 爬蟲錯誤：{scrape_error[:120]}")
                else:
                    yield log(f"⚠️ 爬蟲僅取得 {chars} 字元（內容不足）")
            except Exception as e:
                yield log(f"⚠️ 爬蟲失敗：{str(e)[:60]}")

            # Step 2: Gemini AI 分析
            if raw_text and len(raw_text.strip()) >= 50:
                yield log(f"🤖 Step 2/2 · Gemini AI 分析中（{platform}）...")
                result = None
                try:
                    result = llm.analyze_content(raw_text, platform=scraped_platform)
                except Exception as _llm_exc:
                    err_msg = str(_llm_exc)[:80]
                    yield log(f"❌ AI 分析失敗：{err_msg}")
                    yield log("📦 回傳 Demo 數據")
                    yield f"event: result\ndata: {json.dumps(mock_fallback, ensure_ascii=False)}\n\n"

                if result is not None:
                    if scraper_store_name:
                        result["store_name"] = scraper_store_name
                    result["platform"] = scraped_platform

                    _attach_scrape_context(result, scrape_result, scraped_platform)

                    has_reviews = result.get("good") or result.get("bad")
                    if not has_reviews:
                        yield log(f"⚠️ AI 未分析到{source_label}內容")
                        no_review_result = {
                            "store_name": scraper_store_name or f"未知{target_label}",
                            "status": "no_reviews",
                            "platform": scraped_platform,
                            "total_reviews": "0",
                            "good": [],
                            "bad": [],
                            "message": f"找不到「{scraper_store_name}」的{source_label}資料。"
                        }
                        yield f"event: result\ndata: {json.dumps(no_review_result, ensure_ascii=False)}\n\n"
                    else:
                        good_count = len(result.get("good", []))
                        bad_count = len(result.get("bad", []))
                        yield log(f"✅ 分析完成！正面 {good_count} 項 · 負面 {bad_count} 項")

                        # v6 bridge: persist legacy /analyze-stream success too
                        _persist_v4_analyze_to_workspace(
                            url=url,
                            platform=scraped_platform,
                            scrape_result=scrape_result,
                            analysis_result=result,
                        )

                        yield f"event: result\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
            else:
                if is_yt and scrape_error:
                    yield log(f"❌ {scrape_error[:120]}")
                    err_result = {
                        "store_name": "",
                        "status": "error",
                        "platform": platform,
                        "total_reviews": "0",
                        "good": [],
                        "bad": [],
                        "message": scrape_error
                    }
                    yield f"event: result\ndata: {json.dumps(err_result, ensure_ascii=False)}\n\n"
                else:
                    yield log(f"⚠️ {source_label}內容不足，回傳 Demo 數據")
                    yield f"event: result\ndata: {json.dumps(mock_fallback, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield log(f"❌ 發生錯誤：{str(e)[:100]}")
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

        yield "event: done\ndata: done\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
