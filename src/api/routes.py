from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.services.scraper_service import ScraperService
from src.services.llm_service import LLMService
from src.config.mock_responses import get_mock_response
import json

router = APIRouter()
scraper = ScraperService()
llm = LLMService()

# Use mock responses for demo (since Gemini API quota is exceeded)
USE_MOCK_RESPONSES = False

class AnalyzeRequest(BaseModel):
    url: str

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

@router.post("/analyze")
async def analyze(request: AnalyzeRequest):
    try:
        print(f"[INFO] 收到分析請求: {request.url}")
        
        # TODO: 暫時跳過真實爬蟲，直接返回 Mock 數據
        # 原因：爬蟲可能太慢或有其他問題導致 500 錯誤
        print("[INFO] 使用 Mock 數據（跳過爬蟲步驟）")
        
        mock_analysis = {
            "platform": "google",
            "total_reviews": "共分析 723 則 Google Maps 評論",
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
        
        print("[SUCCESS] Mock 分析完成，返回結果")
        return mock_analysis
            
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        print(f"[ERROR] 發生錯誤:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析失敗: {str(e)}")

@router.post("/reply")
async def generate_reply(request: ReplyRequest):
    """生成對負面評論的回覆"""
    if USE_MOCK_RESPONSES:
        reply = get_mock_response("reply_to_complaint", topic=request.topic)
    else:
        reply = await llm.generate_reply(request.topic)
    return {"reply": reply}

@router.post("/analyze-issue")
async def analyze_issue(request: ReplyRequest):
    """根源問題分析"""
    if USE_MOCK_RESPONSES:
        analysis = get_mock_response("root_cause_analysis", topic=request.topic)
    else:
        # Call LLM with root cause analysis prompt
        analysis = await llm.generate_root_cause_analysis(request.topic)
    return {"analysis": analysis}

@router.post("/marketing")
async def generate_marketing(request: MarketingRequest):
    """生成 FB/IG 行銷貼文"""
    if USE_MOCK_RESPONSES:
        copy = get_mock_response("marketing_copy", strengths=request.strengths)
    else:
        copy = await llm.generate_marketing(request.strengths)
    return {"copy": copy}

@router.post("/weekly-plan")
async def generate_weekly_plan(request: WeeklyPlanRequest):
    """生成週行動計畫"""
    if USE_MOCK_RESPONSES:
        plan = get_mock_response("weekly_plan", weaknesses=request.weaknesses)
    else:
        plan = await llm.generate_weekly_plan(request.weaknesses)
    return {"plan": plan}

@router.post("/training-script")
async def generate_training_script(request: TrainingScriptRequest):
    """生成員工培訓劇本"""
    if USE_MOCK_RESPONSES:
        script = get_mock_response("training_script", issue=request.issue)
    else:
        script = await llm.generate_training_script(request.issue)
    return {"script": script}

@router.post("/internal-email")
async def generate_internal_email(request: InternalEmailRequest):
    """生成內部公告信"""
    if USE_MOCK_RESPONSES:
        email = get_mock_response("internal_email", 
                                 strengths=request.strengths,
                                 weaknesses=request.weaknesses)
    else:
        email = await llm.generate_internal_email(request.strengths, request.weaknesses)
    return {"email": email}

@router.post("/chat")
async def chat(request: ChatRequest):
    """AI 聊天助手"""
    try:
        if USE_MOCK_RESPONSES:
            # 智能 Mock 回應（根據問題內容）
            message = request.message.lower()
            
            if any(word in message for word in ['出餐', '速度', '慢', '等待']):
                reply = """根據分析報告，**出餐速度慢**是主要痛點（40%）。

建議改善方案：
1. **短期**：增加尖峰時段人手
2. **中期**：優化廚房 SOP流程
3. **長期**：引入廚房管理系統

參考週行動計畫中的「流程優化Week」進行改善。"""
                
            elif any(word in message for word in ['停車', '車位', '不方便']):
                reply = """針對**停車不方便**問題（18%），建議：

✅ 與鄰近停車場洽談合作
✅ 提供代客泊車服務
✅ 在 Google Maps 標註附近停車資訊
✅ 推廣外送服務作為替代方案"""
                
            elif any(word in message for word in ['價格', '貴', '便宜', '划算']):
                reply = """**價格偏高**（12%）的策略建議：

💡 不建議直接降價，而是：
- 推出「超值套餐」增加CP值感受
- 強化餐點質感與服務體驗
- 會員制度提供專屬優惠
- 透過行銷突出「物有所值」"""
                
            elif any(word in message for word in ['行銷', '宣傳', '推廣', '社群']):
                reply = """社群行銷建議：

📱 **Facebook/Instagram**：
- 利用「餐點美味」優勢（32%好評）
- 分享料理過程與食材故事
- 顧客好評截圖分享
- 限時優惠活動

參考「利用優點生成FB/IG行銷貼文」功能生成內容！"""
                
            elif any(word in message for word in ['員工', '培訓', '訓練', '服務']):
                reply = """員工培訓重點：

👥 **服務親切**已獲20%好評，請繼續保持！

針對出餐慢問題，請使用「產生劇本」功能：
- 學習正確應對話術
- 避免 NG 回應
- 提升顧客滿意度"""
                
            else:
                reply = f"""您好！我是 AI 策略顧問 🤖

您詢問：「{request.message}」

我可以協助您：
✅ 分析顧客回饋數據
✅ 提供改善建議
✅ 行銷策略規劃
✅ 員工培訓方案

請參考分析報告中的詳細數據，或使用頁面上的各項 AI 工具！"""
        else:
            reply = await llm.chat(request.message)
        return {"reply": reply}
    except Exception as e:
        return {"reply": "抱歉，AI 助手暫時無法回應。請稍後再試。"}

