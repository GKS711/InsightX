import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemma-4-31b-it"


class LLMService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    async def _generate(self, prompt: str, json_mode: bool = False) -> str:
        """Async Gemini API call using the official async client."""
        if not self.client:
            raise Exception("Gemini client not initialized - check GEMINI_API_KEY")

        config = None
        if json_mode:
            config = types.GenerateContentConfig(response_mime_type="application/json")

        response = await self.client.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=config,
        )
        return response.text

    async def analyze_content(self, text_content: str) -> dict:
        """
        Analyzes scraped review text using Gemini.
        Returns a dict compatible with the frontend format.
        """
        if not text_content or len(text_content.strip()) < 50:
            return {"error": "Not enough content to analyze"}

        truncated = text_content[:15000]

        prompt = f"""你是一位專業的商業分析師，擅長分析顧客評論。請分析以下從網站爬取的顧客回饋文字。

原始文字：
{truncated}

任務：
1. 判斷評論來自哪個平台（"google"、"facebook"、"line" 或 "other"）
2. 分析情緒（正面/負面），提取關鍵主題
3. 估算前三大正面主題與前三大負面主題的提及比例

請用以下 JSON 格式輸出（不要有 markdown、代碼塊或任何其他文字）：
{{
    "store_name": "從文字中推斷的店家名稱（若無法判斷則留空字串）",
    "platform": "google",
    "total_reviews": "共分析約 N 則評論",
    "good": [
        {{"label": "主題1", "value": 30}},
        {{"label": "主題2", "value": 20}},
        {{"label": "主題3", "value": 10}}
    ],
    "bad": [
        {{"label": "主題1", "value": 40}},
        {{"label": "主題2", "value": 20}},
        {{"label": "主題3", "value": 10}}
    ]
}}"""

        try:
            text = await self._generate(prompt, json_mode=True)
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            return {"error": "Failed to parse AI response as JSON"}
        except Exception as e:
            return {"error": str(e)}

    async def generate_swot(self, good: list, bad: list) -> dict:
        """Generate dynamic SWOT analysis from good/bad feedback data."""
        good_str = "、".join([f"{i['label']}({i['value']}%)" for i in good])
        bad_str = "、".join([f"{i['label']}({i['value']}%)" for i in bad])

        prompt = f"""你是一位專業的餐飲業 AI 顧問。根據以下顧客回饋數據，生成 SWOT 分析（繁體中文）。

正面回饋：{good_str}
負面回饋：{bad_str}

請輸出以下 JSON 格式（不要有 markdown 或代碼塊）：
{{
    "strengths": [
        {{"point": "優勢標題", "detail": "含數據的具體說明"}},
        {{"point": "優勢標題2", "detail": "含數據的具體說明"}}
    ],
    "weaknesses": [
        {{"point": "劣勢標題", "detail": "含數據的具體說明"}},
        {{"point": "劣勢標題2", "detail": "含數據的具體說明"}}
    ],
    "opportunities": [
        {{"point": "機會標題", "detail": "可執行的具體建議"}},
        {{"point": "機會標題2", "detail": "可執行的具體建議"}}
    ],
    "threats": [
        {{"point": "威脅標題", "detail": "潛在風險說明"}},
        {{"point": "威脅標題2", "detail": "潛在風險說明"}}
    ]
}}"""

        try:
            text = await self._generate(prompt, json_mode=True)
            return json.loads(text)
        except Exception:
            # Structured fallback
            return {
                "strengths": [
                    {"point": good[0]["label"] if good else "產品力強",
                     "detail": f"顧客好評率 {good[0]['value']}%，為核心競爭優勢" if good else "持續保持品質"},
                    {"point": good[1]["label"] if len(good) > 1 else "顧客體驗",
                     "detail": f"{good[1]['value']}% 顧客正面提及" if len(good) > 1 else ""}
                ],
                "weaknesses": [
                    {"point": bad[0]["label"] if bad else "待改善",
                     "detail": f"{bad[0]['value']}% 顧客抱怨，為最大痛點" if bad else "持續改善"},
                    {"point": bad[1]["label"] if len(bad) > 1 else "次要問題",
                     "detail": f"{bad[1]['value']}% 顧客提及" if len(bad) > 1 else ""}
                ],
                "opportunities": [
                    {"point": "流程優化", "detail": f"針對{bad[0]['label']}改善，可快速提升顧客滿意度" if bad else "持續優化"},
                    {"point": "口碑行銷", "detail": f"善用{good[0]['label']}優勢，強化社群宣傳" if good else "加強行銷"}
                ],
                "threats": [
                    {"point": "顧客流失風險", "detail": f"{bad[0]['label']}問題若未解決，可能流失回頭客" if bad else "持續監控"},
                    {"point": "競爭加劇", "detail": "同業競爭壓力，需持續優化顧客體驗"}
                ]
            }

    async def generate_reply(self, topic: str) -> str:
        prompt = f"""你是一位專業的餐廳公關經理。請針對顧客抱怨「{topic}」，撰寫一段誠懇、專業的繁體中文回覆。
回覆需包含：
1. 感謝顧客提供寶貴意見
2. 誠摯道歉
3. 說明具體改善措施
4. 邀請顧客再次光臨

請直接輸出回覆內容，不需要標題或格式標記。"""
        return await self._generate(prompt)

    async def generate_marketing(self, strengths: str) -> str:
        prompt = f"""你是一位專業的社群媒體行銷專家。根據以下餐廳優勢：{strengths}

請撰寫一篇吸引人的 Facebook/Instagram 行銷貼文（繁體中文）。
要求：
- 加入相關 emoji，增加視覺吸引力
- 加入 3-5 個相關 hashtag
- 語氣親切自然、有感染力
- 不超過 200 字"""
        return await self._generate(prompt)

    async def generate_root_cause_analysis(self, topic: str) -> str:
        prompt = f"""你是一位餐飲業管理顧問。請針對顧客持續反映的問題「{topic}」進行深度根源分析（繁體中文）。

請使用以下結構：

## 根源問題分析：{topic}

### 🔍 直接原因
（操作層面的立即原因）

### ⚙️ 系統性原因
（流程、制度、資源層面的深層原因）

### 👥 管理層面原因
（人員管理、培訓、文化層面的原因）

## 建議改善方案

### ⚡ 短期措施（1週內可執行）
1. ...
2. ...

### 📅 中期措施（1個月內）
1. ...
2. ...

### 🎯 長期措施（3個月以上）
1. ...
2. ..."""
        return await self._generate(prompt)

    async def generate_weekly_plan(self, weaknesses: str) -> str:
        prompt = f"""你是一位餐廳營運顧問。根據以下需要改善的項目：{weaknesses}

請制定一份詳細的週行動計畫（繁體中文）。

## 本週改善行動計畫

### 週一
- **任務**：...
- **負責人**：...
- **預期結果**：...

（請為週一到週日，每天列出 2-3 個具體且可執行的任務，以 Markdown 格式呈現）"""
        return await self._generate(prompt)

    async def generate_training_script(self, issue: str) -> str:
        prompt = f"""你是一位餐廳員工培訓專家。請針對「{issue}」問題，撰寫一份角色扮演培訓劇本（繁體中文）。

## 培訓情境：{issue}

### ❌ NG 示範（錯誤應對）
**顧客：** ...
**員工（NG）：** ...
**問題分析：** ...

### ✅ OK 示範（正確應對）
**顧客：** ...
**員工（OK）：** ...
**重點說明：** ...

### 📝 關鍵話術整理
1. ...
2. ...
3. ...

### 💡 常見誤區提醒
- ..."""
        return await self._generate(prompt)

    async def generate_internal_email(self, strengths: str, weaknesses: str) -> str:
        prompt = f"""你是一位餐廳的管理者。請撰寫一封給全體員工的內部公告信（繁體中文）。

本週數據：
- 顧客正向回饋：{strengths}
- 需要改善：{weaknesses}

信件需包含：
1. 感謝員工的辛勤付出（引用正向數據）
2. 點出需改善的問題（客觀陳述）
3. 本週具體的改善行動要求
4. 鼓勵性的結語

**格式要求**：正式書信格式，語氣正式但親切，展現領導力。"""
        return await self._generate(prompt)

    async def chat(self, user_message: str, context: str = "") -> str:
        system = "你是一位專業的 AI 餐廳策略顧問，擅長顧客回饋分析、餐廳營運改善、行銷策略規劃。請以繁體中文回答，語氣專業且親切，回答簡潔有重點（150字以內）。"
        if context:
            system += f"\n\n【當前分析報告】\n{context}"

        prompt = f"{system}\n\n用戶詢問：{user_message}\n\nAI 顧問："
        return await self._generate(prompt)
