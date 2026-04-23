import asyncio
import json
import time
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from src.services.canonicalizer import (
    Platform,
    YtRole,
    attach_metadata,
    canonicalize_yt_role,
    verify_platform_hint,
)
from src.services.llm_service import LLMService
from src.services.scraper_service import ScraperService
from src.config.mock_responses import get_mock_response

router = APIRouter()
scraper = ScraperService()
llm = LLMService()

APP_VERSION = "4.0.0"

# P3.10-2-R3（Codex R2 點 2）：/api/analyze 非 SSE fallback 的 route-level total budget。
# 確保 backend 比 frontend timeout 小（adapters.js 設 90s）。
# 拆分：scraper 30s，剩餘給 LLM（最多 55s），實際運行用 monotonic 時鐘動態計算。
ROUTE_ANALYZE_TOTAL_BUDGET_S = 85.0
ROUTE_ANALYZE_SCRAPER_BUDGET_S = 30.0
ROUTE_ANALYZE_LLM_FLOOR_S = 10.0  # LLM 至少要這麼多時間才有意義；少於就跳過直接回 mock

# P3.10-3-R2 fix #2/#3（Codex round-2 audit）：v4 SSE 路徑也明文化 budget。
# SSE 沒有 frontend AbortController 壓力（EventSource 不受 fetch timeout 控），所以不需要 route
# total budget；但每段仍要 explicit constant，避免 LLM 行為依賴 service 預設、scraper 跟 POST
# 不對稱。決策：scraper 對齊 POST 30s（最大實測 ~16s 已含 8 頁分頁，60s 是 P3.10 前的舊上限），
# LLM 走 analyze_content 明確 55s（gemma 最壞 ~50s + 5s buffer，跟 POST 一致）。
SSE_ANALYZE_SCRAPER_BUDGET_S = 30.0
SSE_ANALYZE_LLM_BUDGET_S = 55.0

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
                target["total_reviews"] = total_reviews

# ---- Request Models ----

class AnalyzeRequest(BaseModel):
    url: str
    platform: Optional[Literal["google", "youtube"]] = None        # v4: optional hint
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None  # v4

class SwotRequest(BaseModel):
    good: list
    bad: list
    platform: Literal["google", "youtube"]                         # v4: no default
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
async def analyze(request: AnalyzeRequest):
    """
    主要分析端點（v4.0.0）：
      - URL 自動偵測：YouTube / Google Maps
      - `platform` 為 optional hint；與 URL 偵測結果衝突 → 422
      - `yt_role`：YouTube 模式下 canonicalize（預設 "creator"）；Google 模式下忽略
      - 回傳統一帶 `effective_yt_role` / `_fallback` / `warnings` metadata
    """
    from src.services.youtube_scraper import is_youtube_url

    warnings: list = []

    # Platform 偵測 + hint 驗證
    detected_platform: Platform = "youtube" if is_youtube_url(request.url) else "google"
    verify_platform_hint(detected_platform, request.platform)

    # yt_role canonicalization（warnings 會被 mutate）
    effective_yt_role = canonicalize_yt_role(detected_platform, request.yt_role, warnings)

    # P3.10-2-R3：route-level total budget tracking
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

        # Step 1: 爬取內容（timeout 從 60s 收緊到 30s — 對齊 route total budget 85s）
        print(f"[INFO] Step 1/2 · 爬取{source_label}中...")
        raw_text = ""
        scraper_store_name = ""
        scraped_platform: Platform = detected_platform
        try:
            scrape_result = await asyncio.wait_for(
                scraper.scrape_url(request.url),
                timeout=ROUTE_ANALYZE_SCRAPER_BUDGET_S,
            )
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
        except asyncio.TimeoutError:
            print(f"[WARN] 爬蟲超時（>{ROUTE_ANALYZE_SCRAPER_BUDGET_S:.0f}s）")
            warnings.append(f"scraper timeout (>{ROUTE_ANALYZE_SCRAPER_BUDGET_S:.0f}s)")
        except Exception as e:
            print(f"[WARN] 爬蟲失敗: {e}")
            warnings.append(f"scraper error: {str(e)[:80]}")

        # Step 2: Gemini 分析（用 route 剩餘 budget 動態壓縮 LLM timeout）
        if raw_text and len(raw_text.strip()) >= 50:
            elapsed = time.monotonic() - route_start
            llm_budget = ROUTE_ANALYZE_TOTAL_BUDGET_S - elapsed
            if llm_budget < ROUTE_ANALYZE_LLM_FLOOR_S:
                # 預算用太多在 scraper 上了，跳過 LLM 直接回 mock + warning
                warnings.append(
                    f"insufficient route budget for LLM "
                    f"(elapsed={elapsed:.1f}s, remaining={llm_budget:.1f}s < floor {ROUTE_ANALYZE_LLM_FLOOR_S}s)"
                )
                print(f"[WARN] 預算不足走 LLM（剩 {llm_budget:.1f}s），返回 Mock 數據")
                return attach_metadata(
                    mock_fallback,
                    effective_yt_role=effective_yt_role,
                    fallback=True,
                    warnings=warnings,
                )
            llm_budget = min(55.0, llm_budget)  # 不超過 analyze_content 預設上限
            print(f"[INFO] Step 2/2 · Gemini AI 分析中...（platform={scraped_platform}, llm_budget={llm_budget:.1f}s）")
            # P3.10-3-R2 fix #1（Codex round-2 audit）：analyze_content 改 raise 後，這裡需要
            # 局部 try/except 才能落到 fallback mock + _fallback:true，否則會被外層 except
            # 包成 HTTP 500（前端會渲染成「Network request failed」而不是 ErrorVM 的「AI 暫時無法產生」）。
            try:
                result = await llm.analyze_content(
                    raw_text, platform=scraped_platform, total_timeout_s=llm_budget,
                )
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
                return attach_metadata(
                    result,
                    effective_yt_role=effective_yt_role,
                    fallback=False,
                    warnings=warnings,
                )
            # 落到 fallback mock（warnings 已 append 過）
        else:
            warnings.append("insufficient scraped content (<50 chars)")
            print("[WARN] 內容不足，退回 Mock 數據")

        # Fallback：回傳對應平台的 mock
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
async def debug_scrape(request: AnalyzeRequest):
    """
    純爬蟲測試端點，不呼叫 AI，直接回傳爬取結果。
    用途：在 Terminal 確認爬蟲是否正常工作。
    """
    try:
        scrape_result = await asyncio.wait_for(
            scraper.scrape_url(request.url),
            timeout=120.0
        )
        raw_text = scrape_result.get("raw_text", "")
        return {
            "status": scrape_result.get("status"),
            "platform": scrape_result.get("platform", ""),
            "store_name": scrape_result.get("store_name", ""),
            "review_count": scrape_result.get("review_count", 0),
            "source": scrape_result.get("video_data", {}).get("source", ""),  # v2.0.1: 標記 official_api / yt-dlp
            "char_count": len(raw_text),
            "preview": raw_text[:500] if raw_text else "",
            "error": scrape_result.get("error", None),
        }
    except asyncio.TimeoutError:
        return {"status": "timeout", "char_count": 0, "preview": "", "store_name": "", "error": "Timeout >120s"}
    except Exception as e:
        return {"status": "error", "char_count": 0, "preview": "", "store_name": "", "error": str(e)}


@router.post("/swot")
async def generate_swot(request: SwotRequest):
    """
    根據 good/bad 列表，用 Gemini 生成動態 SWOT 分析（v4：統一 metadata）。
    """
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    # 空 SWOT source 沒有任何訊號可推論，直接短路回空結果，避免把空 prompt 丟給 LLM
    # 導致無意義 JSON / timeout，最後被前端誤判成「AI 暫時無法生成」。
    if not request.good and not request.bad:
        warnings.append("swot skipped: empty good/bad")
        return attach_metadata(
            {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    try:
        swot = await llm.generate_swot(request.good, request.bad, platform=request.platform)
        return attach_metadata(
            swot if isinstance(swot, dict) else {"swot": swot},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        # SWOT 沒有傳統 mock response，這裡回空殼 + _fallback=True
        return attach_metadata(
            {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/reply")
async def generate_reply(request: ReplyRequest):
    """生成對負面意見的回覆（顧客抱怨 or 觀眾留言）"""
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        reply = await llm.generate_reply(request.topic, platform=request.platform)
        return attach_metadata(
            {"reply": reply},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        reply = get_mock_response("reply_to_complaint", topic=request.topic)
        return attach_metadata(
            {"reply": reply},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/analyze-issue")
async def analyze_issue(request: ReplyRequest):
    """根源問題分析（店家問題 or 影片/頻道問題）"""
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        analysis = await llm.generate_root_cause_analysis(request.topic, platform=request.platform)
        return attach_metadata(
            {"analysis": analysis},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        analysis = get_mock_response("root_cause_analysis", topic=request.topic)
        return attach_metadata(
            {"analysis": analysis},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/marketing")
async def generate_marketing(request: MarketingRequest):
    """生成行銷文案（餐廳 FB/IG 貼文 or YouTube 新片宣傳）"""
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        copy = await llm.generate_marketing(request.strengths, platform=request.platform)
        return attach_metadata(
            {"copy": copy},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        copy = get_mock_response("marketing_copy", strengths=request.strengths)
        return attach_metadata(
            {"copy": copy},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/weekly-plan")
async def generate_weekly_plan(request: WeeklyPlanRequest):
    """生成週行動計畫（店家營運 or 頻道成長）"""
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        plan = await llm.generate_weekly_plan(request.weaknesses, platform=request.platform)
        return attach_metadata(
            {"plan": plan},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        plan = get_mock_response("weekly_plan", weaknesses=request.weaknesses)
        return attach_metadata(
            {"plan": plan},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/training-script")
async def generate_training_script(request: TrainingScriptRequest):
    """生成培訓劇本（員工 SOP or 剪輯師/團隊 SOP）"""
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        script = await llm.generate_training_script(request.issue, platform=request.platform)
        return attach_metadata(
            {"script": script},
            effective_yt_role=effective_yt_role,
            fallback=False,
            warnings=warnings,
        )
    except Exception as e:
        warnings.append(f"llm error: {str(e)[:80]}")
        script = get_mock_response("training_script", issue=request.issue)
        return attach_metadata(
            {"script": script},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/internal-email")
async def generate_internal_email(request: InternalEmailRequest):
    """生成內部公告信/週報信（店家員工 or 頻道團隊）"""
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        email = await llm.generate_internal_email(
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
        email = get_mock_response("internal_email",
                                  strengths=request.strengths,
                                  weaknesses=request.weaknesses)
        return attach_metadata(
            {"email": email},
            effective_yt_role=effective_yt_role,
            fallback=True,
            warnings=warnings,
        )


@router.post("/chat")
async def chat(request: ChatRequest):
    """AI 聊天助手（餐廳策略顧問 or 頻道成長顧問，依 platform 切換）"""
    warnings: list = []
    effective_yt_role = canonicalize_yt_role(request.platform, request.yt_role, warnings)
    try:
        reply = await llm.chat(request.message, request.context, platform=request.platform)
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
async def get_meta():
    """
    回傳 app 版本 + 支援平台 + feature flags（docs/v4-api-contract.md §2.12）。
    前端 bootstrap 時呼叫一次，用來決定 UI 要不要顯示某些功能、或警示使用者需要升級 client。
    """
    return {
        "appVersion": APP_VERSION,
        "availablePlatforms": ["google", "youtube"],
        "availableYtRoles": ["creator", "shop", "brand"],
        "featureFlags": {
            "sse_v4": True,                # /api/v4/analyze-stream 已上線（P1-2）
            "chat_history_persist": False, # 聊天記錄持久化（尚未實作）
        },
        "_fallback": False,
        "warnings": [],
    }


# ---- v4 結構化 SSE ----

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _sse_event(event: str, payload: dict) -> str:
    """
    把 dict 序列化成一個 SSE event frame。單行 JSON + 空行結尾（docs/v4-sse-events.md §1）。
    """
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/v4/analyze-stream")
async def analyze_stream_v4(
    url: str = Query(..., min_length=1),
    platform: Optional[Literal["google", "youtube"]] = Query(None),
    yt_role: Optional[Literal["creator", "shop", "brand"]] = Query(None),
):
    """
    v4 結構化 SSE（docs/v4-sse-events.md）：
      - 事件：progress（1..N）+ terminal result|failed（恰好 1）
      - 4 步驟：connected(0) → scraping(1,2) → analyzing(3) → finalizing(4)
      - 心跳：: ping 每 15 秒
      - 無 Last-Event-ID resume；失敗就整個重跑
      - Query param 驗證失敗 → HTTP 422 不進 stream（EventSource onerror 只拿 readyState=CLOSED）
    """
    from src.services.youtube_scraper import is_youtube_url

    # ----- Pre-stream validation (HTTP 422, 不進 stream) -----
    detected_platform: Platform = "youtube" if is_youtube_url(url) else "google"
    verify_platform_hint(detected_platform, platform)

    warnings: list = []
    effective_yt_role = canonicalize_yt_role(detected_platform, yt_role, warnings)

    total_steps = 4
    started = time.monotonic()

    async def event_generator():
        """
        producer-consumer（Codex review 修過）：
          - worker 正常 / 失敗結束都 put ("terminal", frame)，不再用 sentinel
          - heartbeat 用 done_event 控制，terminal 一到就停，避免 ping 插在 terminal 之後
          - worker 遇 CancelledError → raise，不再嘗試通知 consumer
          - finally 裡取消 task + 1 秒 budget，log 沒停止的 task 方便排查
        """
        import logging
        logger = logging.getLogger("insightx.sse")

        queue: asyncio.Queue = asyncio.Queue()
        done_event = asyncio.Event()

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

        async def heartbeat():
            # done_event 一 set 就 return；沒 set 就每 15s 送 ping
            try:
                while not done_event.is_set():
                    try:
                        await asyncio.wait_for(done_event.wait(), timeout=15.0)
                        return
                    except asyncio.TimeoutError:
                        await queue.put(("raw", ": ping\n\n"))
            except asyncio.CancelledError:
                raise

        async def worker():
            try:
                # step 0: connected
                await queue.put(("event", _sse_event("progress", progress(
                    "connected", 0, "Connected. Waiting for server to start analysis.",
                    0.0, include_platform=False,
                ))))

                # 插 cancellation point
                await asyncio.sleep(0)

                # step 1 / 2: scraping
                if detected_platform == "youtube":
                    label1 = "Resolving video metadata…"
                    label2 = "Fetching comments…"
                else:
                    label1 = "Resolving store URL…"
                    label2 = "Fetching reviews via Serper…"
                await queue.put(("event", _sse_event("progress", progress(
                    "scraping", 1, label1, 0.2, include_platform=True,
                ))))
                await queue.put(("event", _sse_event("progress", progress(
                    "scraping", 2, label2, 0.4, include_platform=True,
                ))))

                raw_text = ""
                scraper_store_name = ""
                scraped_platform: Platform = detected_platform
                try:
                    scrape_result = await asyncio.wait_for(
                        scraper.scrape_url(url),
                        timeout=SSE_ANALYZE_SCRAPER_BUDGET_S,
                    )
                    raw_text = scrape_result.get("raw_text", "")
                    scraper_store_name = scrape_result.get("store_name", "")
                    scraped_platform = scrape_result.get("platform", detected_platform)

                    scrape_err = scrape_result.get("error")
                    if scrape_result.get("status") == "error" and scrape_err:
                        await queue.put(("terminal", failed_frame(
                            "VALIDATION_ERROR", scrape_err[:200], retryable=False,
                        )))
                        return
                except asyncio.CancelledError:
                    raise
                except asyncio.TimeoutError:
                    warnings.append(f"scraper timeout (>{SSE_ANALYZE_SCRAPER_BUDGET_S:.0f}s)")
                    await queue.put(("terminal", failed_frame(
                        "SCRAPER_ERROR",
                        f"Scraper timed out after {SSE_ANALYZE_SCRAPER_BUDGET_S:.0f} seconds.",
                        retryable=True, retry_after_secs=30,
                    )))
                    return
                except Exception as e:
                    warnings.append(f"scraper error: {str(e)[:80]}")
                    await queue.put(("terminal", failed_frame(
                        "SCRAPER_ERROR", f"Scraper failed: {str(e)[:180]}",
                        retryable=True,
                    )))
                    return

                # cancellation point
                await asyncio.sleep(0)

                # step 3: analyzing
                await queue.put(("event", _sse_event("progress", progress(
                    "analyzing", 3, "Running Gemini analysis…", 0.7,
                    include_platform=True,
                ))))

                if not raw_text or len(raw_text.strip()) < 50:
                    await queue.put(("terminal", failed_frame(
                        "VALIDATION_ERROR",
                        "Insufficient content scraped (< 50 chars). URL may be a deleted video / closed store.",
                        retryable=False,
                    )))
                    return

                # P3.10-3-R2 fix #2（Codex round-2 audit）：傳明確 SSE_ANALYZE_LLM_BUDGET_S，
                # 不靠 analyze_content 預設。analyze_content 改 raise 後 `if "error" in analysis`
                # 變 dead branch，移除。
                try:
                    analysis = await llm.analyze_content(
                        raw_text,
                        platform=scraped_platform,
                        total_timeout_s=SSE_ANALYZE_LLM_BUDGET_S,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    await queue.put(("terminal", failed_frame(
                        "LLM_ERROR", f"LLM call failed: {str(e)[:180]}",
                        retryable=True, retry_after_secs=10,
                    )))
                    return

                # cancellation point
                await asyncio.sleep(0)

                # step 4: finalizing
                await queue.put(("event", _sse_event("progress", progress(
                    "finalizing", 4, "Packaging result…", 1.0,
                    include_platform=True,
                ))))

                # 組 AnalyzeResponse（與 POST /analyze 一致）
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
                await queue.put(("terminal", _sse_event("result", {
                    "platform": detected_platform,
                    "effective_yt_role": effective_yt_role,
                    "durationMs": duration_ms(),
                    "data": data,
                })))
            except asyncio.CancelledError:
                # client disconnect 或 consumer teardown；不再寫 queue
                raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                await queue.put(("terminal", failed_frame(
                    "UNKNOWN_ERROR", f"Unexpected server error: {str(e)[:180]}",
                    retryable=False,
                )))

        hb_task = asyncio.create_task(heartbeat())
        worker_task = asyncio.create_task(worker())

        try:
            while True:
                kind, payload = await queue.get()
                if kind == "terminal":
                    done_event.set()
                    yield payload
                    break
                yield payload
        finally:
            done_event.set()
            hb_task.cancel()
            worker_task.cancel()
            _, pending = await asyncio.wait(
                {hb_task, worker_task},
                timeout=1.0,
            )
            for t in pending:
                logger.warning("SSE child task still pending after stream cleanup: %r", t)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/analyze-stream")
async def analyze_stream(url: str):
    """
    [DEPRECATED · v3 legacy SSE]
    SSE 串流端點（v2.0.0）：分析過程即時推送 log 給前端。
    自動偵測平台：YouTube → YouTube Data API；Google Maps → Serper API。

    **使用情境**：只剩 `/legacy` HTML 在用。新 v4 UI 走 `/api/v4/analyze-stream`（結構化
    progress/result/failed events，見 docs/v4-sse-events.md）。本端點不接受新功能；P3.10
    timeout / budget invariant 不適用此路徑（保留 60s scraper、analyze_content 預設 55s
    LLM budget），避免動到 v3 已驗證行為。
    若要刪除，先確認 `src/static/index.html` 是否還掛在 `/legacy` 並且有真實流量。
    """
    from src.services.youtube_scraper import is_youtube_url

    async def event_generator():
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

            # Step 1: 爬取（ScraperService 內部 dispatch）
            yield log(f"⏳ Step 1/2 · {api_label} 爬取{source_label}中...")
            raw_text = ""
            scraper_store_name = ""
            scraped_platform = platform
            scrape_error = None
            try:
                scrape_result = await asyncio.wait_for(
                    scraper.scrape_url(url), timeout=60.0
                )
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
            except asyncio.TimeoutError:
                yield log("⚠️ 爬蟲超時 (>60s)")
            except Exception as e:
                yield log(f"⚠️ 爬蟲失敗：{str(e)[:60]}")

            # Step 2: Gemini AI 分析（帶 platform）
            if raw_text and len(raw_text.strip()) >= 50:
                yield log(f"🤖 Step 2/2 · Gemini AI 分析中（{platform}）...")
                # P3.10-3-R3 fix：analyze_content 現在 raise 不回 error dict，legacy 路徑
                # 也要 local try/except 才能走 mock fallback（不然外層 except 只吐 error event）。
                result = None
                try:
                    result = await llm.analyze_content(raw_text, platform=scraped_platform)
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
                        yield f"event: result\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
                # else: result is None → mock_fallback 已在上面 except 分支 yield，這裡無事可做
            else:
                # 爬蟲出錯且是 YouTube 場景要提早回報清楚的錯誤
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
