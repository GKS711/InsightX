"""
InsightX LLM 服務 v2.0.0

v2 變更：所有下游功能支援 platform 參數
  - platform="google"  → 店家評論分析（餐飲/零售老闆視角）
  - platform="youtube" → 頻道留言分析（YouTuber 視角）

使用 google-genai SDK，模型 gemma-4-31b-it。
結構化輸出使用 response_mime_type="application/json"。
"""

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

    # ══════════════════════════════════════════════════════════════
    #  Persona 工具：根據 platform 決定 AI 扮演什麼角色
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _is_youtube(platform: str) -> bool:
        return (platform or "").lower() == "youtube"

    # ══════════════════════════════════════════════════════════════
    #  1. 核心分析
    # ══════════════════════════════════════════════════════════════

    async def analyze_content(self, text_content: str, platform: str = "google") -> dict:
        """
        分析爬蟲拿到的原始文字（評論或留言），回傳好壞主題比例。
        platform: "google"（店家評論）| "youtube"（影片留言）
        """
        if not text_content or len(text_content.strip()) < 50:
            return {"error": "Not enough content to analyze"}

        truncated = text_content[:15000]

        if self._is_youtube(platform):
            prompt = f"""你是一位專業的 YouTube 內容分析師，擅長分析觀眾留言的情緒與主題。請分析以下 YouTube 影片的觀眾留言。

原始留言：
{truncated}

任務：
1. 推斷這支影片的主題或頻道類型（從影片標題、留言內容）
2. 分析觀眾情緒（正面/負面），提取關鍵主題
3. 估算前三大正面主題（例如：內容有料、剪輯流暢、主持人幽默、資訊實用）與前三大負面主題（例如：太冗長、聲音品質差、標題殺人、偏見重）的提及比例

請用以下 JSON 格式輸出（不要有 markdown、代碼塊或任何其他文字）：
{{
    "store_name": "影片標題或頻道名稱（從留言推斷）",
    "platform": "youtube",
    "total_reviews": "共分析約 N 則留言",
    "good": [
        {{"label": "正面主題1（觀眾稱讚什麼）", "value": 30}},
        {{"label": "正面主題2", "value": 20}},
        {{"label": "正面主題3", "value": 10}}
    ],
    "bad": [
        {{"label": "負面主題1（觀眾抱怨或建議什麼）", "value": 40}},
        {{"label": "負面主題2", "value": 20}},
        {{"label": "負面主題3", "value": 10}}
    ]
}}"""
        else:
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
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            return {"error": "Failed to parse AI response as JSON"}
        except Exception as e:
            return {"error": str(e)}

    # ══════════════════════════════════════════════════════════════
    #  2. SWOT 分析
    # ══════════════════════════════════════════════════════════════

    async def generate_swot(self, good: list, bad: list, platform: str = "google") -> dict:
        """SWOT 分析。YouTube 版本聚焦在頻道經營，Google 版本聚焦在店家經營。"""
        good_str = "、".join([f"{i['label']}({i['value']}%)" for i in good])
        bad_str = "、".join([f"{i['label']}({i['value']}%)" for i in bad])

        if self._is_youtube(platform):
            prompt = f"""你是一位專業的 YouTube 頻道成長顧問。根據以下影片/頻道的觀眾回饋數據，生成 SWOT 分析（繁體中文）。

觀眾喜歡的（正面）：{good_str}
觀眾不滿或建議的（負面）：{bad_str}

請從「頻道經營」的角度思考，strengths 是頻道目前做對的事、weaknesses 是需要改善的製作或內容問題、opportunities 是下一步可以嘗試的成長方向、threats 是演算法/競爭/觀眾流失等外部風險。

請輸出以下 JSON 格式（不要有 markdown 或代碼塊）：
{{
    "strengths": [
        {{"point": "優勢標題（頻道做對什麼）", "detail": "含數據的具體說明"}},
        {{"point": "優勢標題2", "detail": "含數據的具體說明"}}
    ],
    "weaknesses": [
        {{"point": "劣勢標題（製作/內容需改善）", "detail": "含數據的具體說明"}},
        {{"point": "劣勢標題2", "detail": "含數據的具體說明"}}
    ],
    "opportunities": [
        {{"point": "機會標題（下一步成長方向）", "detail": "可執行的具體建議"}},
        {{"point": "機會標題2", "detail": "可執行的具體建議"}}
    ],
    "threats": [
        {{"point": "威脅標題（演算法/競爭/留存風險）", "detail": "潛在風險說明"}},
        {{"point": "威脅標題2", "detail": "潛在風險說明"}}
    ]
}}"""
        else:
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
            return {
                "strengths": [
                    {"point": good[0]["label"] if good else "內容力強",
                     "detail": f"觀眾好評率 {good[0]['value']}%，為核心競爭優勢" if good else "持續保持品質"},
                    {"point": good[1]["label"] if len(good) > 1 else "觀眾體驗",
                     "detail": f"{good[1]['value']}% 觀眾正面提及" if len(good) > 1 else ""}
                ],
                "weaknesses": [
                    {"point": bad[0]["label"] if bad else "待改善",
                     "detail": f"{bad[0]['value']}% 觀眾提及，為最大痛點" if bad else "持續改善"},
                    {"point": bad[1]["label"] if len(bad) > 1 else "次要問題",
                     "detail": f"{bad[1]['value']}% 觀眾提及" if len(bad) > 1 else ""}
                ],
                "opportunities": [
                    {"point": "製作優化", "detail": f"針對{bad[0]['label']}改善，可快速提升觀眾滿意度" if bad else "持續優化"},
                    {"point": "口碑擴散", "detail": f"善用{good[0]['label']}優勢，強化社群宣傳" if good else "加強行銷"}
                ],
                "threats": [
                    {"point": "觀眾流失風險", "detail": f"{bad[0]['label']}問題若未解決，可能流失訂閱" if bad else "持續監控"},
                    {"point": "競爭加劇", "detail": "同類頻道競爭壓力，需持續優化內容"}
                ]
            }

    # ══════════════════════════════════════════════════════════════
    #  3. 回覆負面意見
    # ══════════════════════════════════════════════════════════════

    async def generate_reply(self, topic: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位經驗豐富的 YouTuber 社群經理，負責回覆觀眾留言。觀眾對影片提出了不滿或批評：「{topic}」。

請撰寫一則誠懇、有建設性的繁體中文回覆留言。
要求：
1. 感謝觀眾花時間寫下回饋
2. 不找藉口但說明你的思考或創作考量
3. 點出你會如何在下一支影片改進（具體動作）
4. 語氣親切、平視觀眾，不自貶也不防禦
5. 控制在 150 字以內，適合直接貼到留言區

請直接輸出回覆內容，不要標題或額外說明。"""
        else:
            prompt = f"""你是一位專業的餐廳公關經理。請針對顧客抱怨「{topic}」，撰寫一段誠懇、專業的繁體中文回覆。
回覆需包含：
1. 感謝顧客提供寶貴意見
2. 誠摯道歉
3. 說明具體改善措施
4. 邀請顧客再次光臨

請直接輸出回覆內容，不需要標題或格式標記。"""
        return await self._generate(prompt)

    # ══════════════════════════════════════════════════════════════
    #  4. 行銷文案
    # ══════════════════════════════════════════════════════════════

    async def generate_marketing(self, strengths: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位專精 YouTube 頻道行銷的社群操盤手。根據以下這支影片/頻道被觀眾稱讚的亮點：{strengths}

請撰寫一則新影片宣傳貼文（IG/Threads/X 都可用，繁體中文）。
要求：
- 點出影片最核心的 hook（3 秒內抓住注意力）
- 暗示影片能解決/滿足的需求
- 加入相關 emoji，增加視覺吸引力
- 3-5 個相關 hashtag（含頻道類型 + 主題關鍵字）
- 結尾 CTA 引導觀眾點擊影片
- 不超過 150 字"""
        else:
            prompt = f"""你是一位專業的社群媒體行銷專家。根據以下餐廳優勢：{strengths}

請撰寫一篇吸引人的 Facebook/Instagram 行銷貼文（繁體中文）。
要求：
- 加入相關 emoji，增加視覺吸引力
- 加入 3-5 個相關 hashtag
- 語氣親切自然、有感染力
- 不超過 200 字"""
        return await self._generate(prompt)

    # ══════════════════════════════════════════════════════════════
    #  5. 根源問題分析
    # ══════════════════════════════════════════════════════════════

    async def generate_root_cause_analysis(self, topic: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位資深 YouTube 頻道經營顧問。觀眾持續反映的問題是：「{topic}」。

請進行深度根源分析（繁體中文）。

## 根源問題分析：{topic}

### 🔍 直接原因
（這支影片或這類內容在製作層面的立即原因，例如剪輯節奏、腳本結構、配樂、片長）

### ⚙️ 創作流程原因
（前製、拍攝、後製的流程或工具鏈問題。例如腳本不到位、拍攝現場沒捕捉到重點、剪輯時間不夠）

### 📊 內容策略原因
（定位、選題方向、觀眾期待落差。這題特別重要，因為往往不是技術問題而是策略問題）

## 建議改善方案

### ⚡ 短期措施（下一支影片就能做）
1. ...
2. ...

### 📅 中期措施（本季度 3 支影片內驗證）
1. ...
2. ...

### 🎯 長期措施（3 個月以上的內容調整）
1. ...
2. ..."""
        else:
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

    # ══════════════════════════════════════════════════════════════
    #  6. 週計畫
    # ══════════════════════════════════════════════════════════════

    async def generate_weekly_plan(self, weaknesses: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位 YouTube 頻道成長教練。根據以下需要改善的項目：{weaknesses}

請制定一份「頻道下一週行動計畫」（繁體中文）。目標是用一週把這些弱點轉換成具體的創作動作。

## 頻道本週行動計畫

### 週一（規劃日）
- **任務**：...
- **產出**：...
- **預期結果**：...

### 週二（製作日）
- **任務**：...
- **產出**：...
- **預期結果**：...

（請為週一到週日，每天 2-3 個具體可執行的創作任務，不要寫空泛目標。包含前製/拍攝/剪輯/社群/數據分析等。以 Markdown 格式呈現）"""
        else:
            prompt = f"""你是一位餐廳營運顧問。根據以下需要改善的項目：{weaknesses}

請制定一份詳細的週行動計畫（繁體中文）。

## 本週改善行動計畫

### 週一
- **任務**：...
- **負責人**：...
- **預期結果**：...

（請為週一到週日，每天列出 2-3 個具體且可執行的任務，以 Markdown 格式呈現）"""
        return await self._generate(prompt)

    # ══════════════════════════════════════════════════════════════
    #  7. 培訓劇本（YouTube 版：剪輯師/團隊成員溝通範本）
    # ══════════════════════════════════════════════════════════════

    async def generate_training_script(self, issue: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位 YouTube 頻道製作人。請針對「{issue}」這個觀眾回饋問題，撰寫一份給「剪輯師/企劃/外包合作夥伴」的溝通訓練範本（繁體中文）。

目的：把觀眾回饋轉成可落地的製作 SOP，避免下次影片再犯。

## 製作 SOP：{issue}

### ❌ 常見做法（會導致這個問題）
**情境**：...
**做法**：...
**為什麼不行**：...

### ✅ 改進做法
**情境**：...
**做法**：...
**為什麼這樣做**：...

### 📝 給剪輯師/企劃的檢查清單
1. ...
2. ...
3. ...

### 💡 容易誤解的地方
- ...

要求：語氣專業但不官腔，讓合作夥伴看完就知道怎麼做。"""
        else:
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

    # ══════════════════════════════════════════════════════════════
    #  8. 內部信（YouTube 版：給團隊/合作夥伴的週報）
    # ══════════════════════════════════════════════════════════════

    async def generate_internal_email(self, strengths: str, weaknesses: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位 YouTube 頻道主理人。請撰寫一封給團隊成員（剪輯師、企劃、攝影、社群小編）的週報信（繁體中文）。

本週數據：
- 觀眾正面提及：{strengths}
- 觀眾負面提及：{weaknesses}

信件需包含：
1. 肯定團隊本週做對的事（引用正面數據）
2. 誠實指出需要改善的製作問題（客觀、不責備）
3. 下週具體的製作行動（分配給相關角色，例如剪輯師要做什麼、企劃要調整什麼）
4. 鼓勵性結語（強調我們是一起做內容的團隊）

**格式要求**：正式但不冰冷，像資深製作人跟夥伴溝通的語氣。"""
        else:
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

    # ══════════════════════════════════════════════════════════════
    #  9. AI 顧問對話
    # ══════════════════════════════════════════════════════════════

    async def chat(self, user_message: str, context: str = "", platform: str = "google") -> str:
        if self._is_youtube(platform):
            system = (
                "你是一位專業的 YouTube 頻道成長 AI 顧問，擅長觀眾留言分析、內容策略、頻道差異化定位、"
                "演算法友善程度評估、標題/縮圖優化。請以繁體中文回答，語氣像一位懂 YouTube 生態的資深"
                "前輩跟創作者聊天，專業但平視。回答簡潔有重點（150 字以內）。"
            )
        else:
            system = (
                "你是一位專業的 AI 餐廳策略顧問，擅長顧客回饋分析、餐廳營運改善、行銷策略規劃。"
                "請以繁體中文回答，語氣專業且親切，回答簡潔有重點（150字以內）。"
            )
        if context:
            system += f"\n\n【當前分析報告】\n{context}"

        prompt = f"{system}\n\n用戶詢問：{user_message}\n\nAI 顧問："
        return await self._generate(prompt)
