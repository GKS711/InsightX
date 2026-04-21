import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.services.scraper_service import ScraperService
from src.services.llm_service import LLMService
from src.config.mock_responses import get_mock_response

router = APIRouter()
scraper = ScraperService()
llm = LLMService()

# ---- Request Models ----

class AnalyzeRequest(BaseModel):
    url: str

class SwotRequest(BaseModel):
    good: list
    bad: list
    platform: str = "google"

class ReplyRequest(BaseModel):
    topic: str
    platform: str = "google"

class MarketingRequest(BaseModel):
    strengths: str
    platform: str = "google"

class WeeklyPlanRequest(BaseModel):
    weaknesses: str
    platform: str = "google"

class TrainingScriptRequest(BaseModel):
    issue: str
    platform: str = "google"

class InternalEmailRequest(BaseModel):
    strengths: str
    weaknesses: str
    platform: str = "google"

class ChatRequest(BaseModel):
    message: str
    context: str = ""
    platform: str = "google"

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
    主要分析端點（v2.0.0）：
      - URL 自動偵測：YouTube / Google Maps
      - YouTube：YouTube Data API v3 抓留言 → Gemini 分析
      - Google Maps：Serper API 抓評論 → Gemini 分析
    若爬蟲或 AI 失敗，自動退回對應的 Mock 數據。
    """
    try:
        print(f"\n{'='*55}")
        print(f"[INFO] 收到分析請求: {request.url}")

        # 先偵測平台，為 fallback mock 挑對版本
        from src.services.youtube_scraper import is_youtube_url
        if is_youtube_url(request.url):
            platform = "youtube"
        else:
            platform = "google"
        if platform == "youtube":
            mock_fallback = MOCK_ANALYSIS_YOUTUBE
            source_label = "留言"
        else:
            mock_fallback = MOCK_ANALYSIS
            source_label = "評論"

        # Step 1: 爬取內容（ScraperService 內部自動 dispatch）
        print(f"[INFO] Step 1/2 · 爬取{source_label}中...（platform={platform}）")
        raw_text = ""
        scraper_store_name = ""
        scraped_platform = platform
        try:
            scrape_result = await asyncio.wait_for(
                scraper.scrape_url(request.url),
                timeout=60.0
            )
            raw_text = scrape_result.get("raw_text", "")
            scraper_store_name = scrape_result.get("store_name", "")
            review_count = scrape_result.get("review_count", 0)
            # 以爬蟲回傳的 platform 為準（若它有設）
            scraped_platform = scrape_result.get("platform", platform)
            print(f"[INFO] 爬蟲完成 · 標的={scraper_store_name!r} · {review_count} 則{source_label} · {len(raw_text)} 字元")

            # YouTube 爬不到時，提早回報（不退 mock，避免誤導）
            if scraped_platform == "youtube" and scrape_result.get("status") == "error":
                return {
                    "store_name": "",
                    "status": "error",
                    "platform": scraped_platform,
                    "total_reviews": "0",
                    "good": [],
                    "bad": [],
                    "message": scrape_result.get("error") or "YouTube 爬取失敗"
                }
        except asyncio.TimeoutError:
            print("[WARN] 爬蟲超時（>60s）")
        except Exception as e:
            print(f"[WARN] 爬蟲失敗: {e}")

        # Step 2: 若有足夠內容，送 Gemini 分析（帶 platform 參數）
        if raw_text and len(raw_text.strip()) >= 50:
            print(f"[INFO] Step 2/2 · Gemini AI 分析中...（platform={scraped_platform}）")
            result = await llm.analyze_content(raw_text, platform=scraped_platform)

            if "error" not in result:
                if scraper_store_name:
                    result["store_name"] = scraper_store_name
                # 強制以爬蟲的 platform 為準（LLM 可能自行推斷錯）
                result["platform"] = scraped_platform

                has_reviews = result.get("good") or result.get("bad")
                if not has_reviews:
                    print("[WARN] Gemini 未分析到內容，返回 no_reviews 狀態")
                    unknown_label = {
                        "youtube": "未知影片",
                    }.get(scraped_platform, "未知店家")
                    return {
                        "store_name": scraper_store_name or unknown_label,
                        "status": "no_reviews",
                        "platform": scraped_platform,
                        "total_reviews": "0",
                        "good": [],
                        "bad": [],
                        "message": f"找不到「{scraper_store_name}」的{source_label}資料。"
                    }

                print(f"[SUCCESS] 分析完成 · 標的={result.get('store_name', '')!r} · "
                      f"正面={len(result.get('good',[]))} · 負面={len(result.get('bad',[]))}")
                return result
            else:
                print(f"[WARN] Gemini 分析失敗: {result.get('error')}，退回 Mock 數據")
        else:
            print("[WARN] 內容不足，退回 Mock 數據")

        # Fallback：回傳對應平台的 mock
        print(f"[INFO] 返回 Mock 數據（platform={platform}）")
        return mock_fallback

    except Exception as e:
        import traceback
        print(f"[ERROR] 發生未預期錯誤:")
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
    """根據 good/bad 列表，用 Gemini 生成動態 SWOT 分析（支援 platform 切換）"""
    try:
        swot = await llm.generate_swot(request.good, request.bad, platform=request.platform)
        return swot
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reply")
async def generate_reply(request: ReplyRequest):
    """生成對負面意見的回覆（顧客抱怨 or 觀眾留言）"""
    try:
        reply = await llm.generate_reply(request.topic, platform=request.platform)
        return {"reply": reply}
    except Exception as e:
        reply = get_mock_response("reply_to_complaint", topic=request.topic)
        return {"reply": reply}


@router.post("/analyze-issue")
async def analyze_issue(request: ReplyRequest):
    """根源問題分析（店家問題 or 影片/頻道問題）"""
    try:
        analysis = await llm.generate_root_cause_analysis(request.topic, platform=request.platform)
        return {"analysis": analysis}
    except Exception as e:
        analysis = get_mock_response("root_cause_analysis", topic=request.topic)
        return {"analysis": analysis}


@router.post("/marketing")
async def generate_marketing(request: MarketingRequest):
    """生成行銷文案（餐廳 FB/IG 貼文 or YouTube 新片宣傳）"""
    try:
        copy = await llm.generate_marketing(request.strengths, platform=request.platform)
        return {"copy": copy}
    except Exception as e:
        copy = get_mock_response("marketing_copy", strengths=request.strengths)
        return {"copy": copy}


@router.post("/weekly-plan")
async def generate_weekly_plan(request: WeeklyPlanRequest):
    """生成週行動計畫（店家營運 or 頻道成長）"""
    try:
        plan = await llm.generate_weekly_plan(request.weaknesses, platform=request.platform)
        return {"plan": plan}
    except Exception as e:
        plan = get_mock_response("weekly_plan", weaknesses=request.weaknesses)
        return {"plan": plan}


@router.post("/training-script")
async def generate_training_script(request: TrainingScriptRequest):
    """生成培訓劇本（員工 SOP or 剪輯師/團隊 SOP）"""
    try:
        script = await llm.generate_training_script(request.issue, platform=request.platform)
        return {"script": script}
    except Exception as e:
        script = get_mock_response("training_script", issue=request.issue)
        return {"script": script}


@router.post("/internal-email")
async def generate_internal_email(request: InternalEmailRequest):
    """生成內部公告信/週報信（店家員工 or 頻道團隊）"""
    try:
        email = await llm.generate_internal_email(
            request.strengths, request.weaknesses, platform=request.platform
        )
        return {"email": email}
    except Exception as e:
        email = get_mock_response("internal_email",
                                  strengths=request.strengths,
                                  weaknesses=request.weaknesses)
        return {"email": email}


@router.post("/chat")
async def chat(request: ChatRequest):
    """AI 聊天助手（餐廳策略顧問 or 頻道成長顧問，依 platform 切換）"""
    try:
        reply = await llm.chat(request.message, request.context, platform=request.platform)
        return {"reply": reply}
    except Exception as e:
        return {"reply": "抱歉，AI 助手暫時無法回應，請稍後再試。"}


@router.get("/analyze-stream")
async def analyze_stream(url: str):
    """
    SSE 串流端點（v2.0.0）：分析過程即時推送 log 給前端。
    前端用 EventSource('/api/analyze-stream?url=...') 接收。
    自動偵測平台：YouTube → YouTube Data API；Google Maps → Serper API。
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
                result = await llm.analyze_content(raw_text, platform=scraped_platform)

                if "error" not in result:
                    if scraper_store_name:
                        result["store_name"] = scraper_store_name
                    result["platform"] = scraped_platform

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
                else:
                    err_msg = result.get("error", "")[:80]
                    yield log(f"❌ AI 分析失敗：{err_msg}")
                    yield log("📦 回傳 Demo 數據")
                    yield f"event: result\ndata: {json.dumps(mock_fallback, ensure_ascii=False)}\n\n"
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
