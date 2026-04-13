import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
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

class ReplyRequest(BaseModel):
    topic: str

class MarketingRequest(BaseModel):
    strengths: str

class WeeklyPlanRequest(BaseModel):
    weaknesses: str

class TrainingScriptRequest(BaseModel):
    issue: str

class InternalEmailRequest(BaseModel):
    strengths: str
    weaknesses: str

class ChatRequest(BaseModel):
    message: str
    context: str = ""

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

# ---- Endpoints ----

@router.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """
    主要分析端點（v13.1）：Serper API 爬取評論 → Gemini AI 分析
    流程：店名解析 → Serper /maps + /reviews → Gemini 分析
    若爬蟲或 AI 失敗，自動退回 Mock 數據。
    """
    try:
        print(f"\n{'='*55}")
        print(f"[INFO] 收到分析請求: {request.url}")

        # Step 1: 爬取評論（內部自動：店名解析 → Serper /maps → /reviews 分頁）
        print("[INFO] Step 1/2 · 爬取評論中...")
        raw_text = ""
        scraper_store_name = ""
        try:
            scrape_result = await asyncio.wait_for(
                scraper.scrape_url(request.url),
                timeout=60.0
            )
            raw_text = scrape_result.get("raw_text", "")
            scraper_store_name = scrape_result.get("store_name", "")
            review_count = scrape_result.get("review_count", 0)
            print(f"[INFO] 爬蟲完成 · 店家={scraper_store_name!r} · {review_count} 則評論 · {len(raw_text)} 字元")
        except asyncio.TimeoutError:
            print("[WARN] 爬蟲超時（>60s）")
        except Exception as e:
            print(f"[WARN] 爬蟲失敗: {e}")

        # Step 2: 若有足夠內容，送 Gemini 分析
        if raw_text and len(raw_text.strip()) >= 50:
            print("[INFO] Step 2/2 · Gemini AI 分析中...")
            result = await llm.analyze_content(raw_text)

            if "error" not in result:
                if scraper_store_name:
                    result["store_name"] = scraper_store_name

                has_reviews = result.get("good") or result.get("bad")
                if not has_reviews:
                    print("[WARN] Gemini 未分析到任何評論內容，返回 no_reviews 狀態")
                    return {
                        "store_name": scraper_store_name or "未知店家",
                        "status": "no_reviews",
                        "platform": "google",
                        "total_reviews": "0",
                        "good": [],
                        "bad": [],
                        "message": f"在網路上找不到「{scraper_store_name}」的顧客評論資料。"
                    }

                print(f"[SUCCESS] 分析完成 · 店家={result.get('store_name', '')!r} · "
                      f"正面={len(result.get('good',[]))} · 負面={len(result.get('bad',[]))}")
                return result
            else:
                print(f"[WARN] Gemini 分析失敗: {result.get('error')}，退回 Mock 數據")
        else:
            print("[WARN] 評論內容不足，退回 Mock 數據")

        # Fallback
        print("[INFO] 返回 Mock 數據")
        return MOCK_ANALYSIS

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
            "store_name": scrape_result.get("store_name", ""),
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
    """根據 good/bad 列表，用 Gemini 生成動態 SWOT 分析"""
    try:
        swot = await llm.generate_swot(request.good, request.bad)
        return swot
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reply")
async def generate_reply(request: ReplyRequest):
    """生成對負面評論的回覆"""
    try:
        reply = await llm.generate_reply(request.topic)
        return {"reply": reply}
    except Exception as e:
        # fallback to mock
        reply = get_mock_response("reply_to_complaint", topic=request.topic)
        return {"reply": reply}


@router.post("/analyze-issue")
async def analyze_issue(request: ReplyRequest):
    """根源問題分析"""
    try:
        analysis = await llm.generate_root_cause_analysis(request.topic)
        return {"analysis": analysis}
    except Exception as e:
        analysis = get_mock_response("root_cause_analysis", topic=request.topic)
        return {"analysis": analysis}


@router.post("/marketing")
async def generate_marketing(request: MarketingRequest):
    """生成 FB/IG 行銷貼文"""
    try:
        copy = await llm.generate_marketing(request.strengths)
        return {"copy": copy}
    except Exception as e:
        copy = get_mock_response("marketing_copy", strengths=request.strengths)
        return {"copy": copy}


@router.post("/weekly-plan")
async def generate_weekly_plan(request: WeeklyPlanRequest):
    """生成週行動計畫"""
    try:
        plan = await llm.generate_weekly_plan(request.weaknesses)
        return {"plan": plan}
    except Exception as e:
        plan = get_mock_response("weekly_plan", weaknesses=request.weaknesses)
        return {"plan": plan}


@router.post("/training-script")
async def generate_training_script(request: TrainingScriptRequest):
    """生成員工培訓劇本"""
    try:
        script = await llm.generate_training_script(request.issue)
        return {"script": script}
    except Exception as e:
        script = get_mock_response("training_script", issue=request.issue)
        return {"script": script}


@router.post("/internal-email")
async def generate_internal_email(request: InternalEmailRequest):
    """生成內部公告信"""
    try:
        email = await llm.generate_internal_email(request.strengths, request.weaknesses)
        return {"email": email}
    except Exception as e:
        email = get_mock_response("internal_email",
                                  strengths=request.strengths,
                                  weaknesses=request.weaknesses)
        return {"email": email}


@router.post("/chat")
async def chat(request: ChatRequest):
    """AI 聊天助手（支援分析報告 context）"""
    try:
        reply = await llm.chat(request.message, request.context)
        return {"reply": reply}
    except Exception as e:
        return {"reply": "抱歉，AI 助手暫時無法回應，請稍後再試。"}


@router.get("/analyze-stream")
async def analyze_stream(url: str):
    """
    SSE 串流端點（v13.1）：分析過程即時推送 log 給前端。
    前端用 EventSource('/api/analyze-stream?url=...') 接收。
    流程：Serper API 爬取評論 → Gemini AI 分析（2 步驟）
    """
    async def event_generator():
        def log(msg: str):
            return f"data: {msg}\n\n"

        try:
            yield log("🔍 收到分析請求")

            # Step 1: Serper API 爬取評論（含店名解析 + /maps + /reviews 分頁）
            yield log("⏳ Step 1/2 · Serper API 爬取評論中...")
            raw_text = ""
            scraper_store_name = ""
            try:
                scrape_result = await asyncio.wait_for(
                    scraper.scrape_url(url), timeout=60.0
                )
                raw_text = scrape_result.get("raw_text", "")
                scraper_store_name = scrape_result.get("store_name", "")
                review_count = scrape_result.get("review_count", 0)
                chars = len(raw_text.strip())

                if chars >= 50:
                    store_label = scraper_store_name or "未知店家"
                    yield log(f"✅ 爬蟲成功 · 店家：{store_label} · {review_count} 則評論 · {chars} 字元")
                else:
                    yield log(f"⚠️ 爬蟲僅取得 {chars} 字元（內容不足）")
            except asyncio.TimeoutError:
                yield log("⚠️ 爬蟲超時 (>60s)")
            except Exception as e:
                yield log(f"⚠️ 爬蟲失敗：{str(e)[:60]}")

            # Step 2: Gemini AI 分析
            if raw_text and len(raw_text.strip()) >= 50:
                yield log("🤖 Step 2/2 · Gemini AI 分析中...")
                result = await llm.analyze_content(raw_text)

                if "error" not in result:
                    if scraper_store_name:
                        result["store_name"] = scraper_store_name

                    has_reviews = result.get("good") or result.get("bad")
                    if not has_reviews:
                        yield log(f"⚠️ AI 未分析到評論內容")
                        no_review_result = {
                            "store_name": scraper_store_name or "未知店家",
                            "status": "no_reviews",
                            "platform": "google",
                            "total_reviews": "0",
                            "good": [],
                            "bad": [],
                            "message": f"在網路上找不到「{scraper_store_name}」的顧客評論資料。"
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
                    yield f"event: result\ndata: {json.dumps(MOCK_ANALYSIS, ensure_ascii=False)}\n\n"
            else:
                yield log("⚠️ 評論內容不足，回傳 Demo 數據")
                yield f"event: result\ndata: {json.dumps(MOCK_ANALYSIS, ensure_ascii=False)}\n\n"

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
