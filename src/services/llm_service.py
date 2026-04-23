"""
InsightX LLM 服務 v3.0.0（Shopee 模組已於 2026-04-21 移除）

所有下游功能支援 platform 參數：
  - platform="google"  → 店家評論分析（餐飲/零售老闆視角）
  - platform="youtube" → 頻道留言分析（YouTuber 視角）

使用 google-genai SDK，模型 gemma-4-31b-it。
結構化輸出使用 response_mime_type="application/json"。
"""

import os
import json
import re
import time
import random
import asyncio
import logging
import httpx
from google import genai
from google.genai import types, errors as genai_errors
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "gemma-4-31b-it"

# P3.10-2-R2（Codex peer review 後重設計）：
# 前端 per-endpoint timeoutMs 已細分（adapters.js 定義）：
#   chat/reply/marketing  → 45s   |  swot/internal-email → 60-75s
#   training-script       → 110s  |  weekly-plan         → 120s
# 後端必須**比 frontend timeout 略小**，否則 frontend abort 後後端還在跑、燒 quota。
# 後端用 (max_attempts, total_timeout_s) 控制，per-attempt timeout = 剩餘 budget。
#
# Retry 判斷改用 google-genai 的 type-based exception，不再用脆弱的字串 substring：
#   - errors.ServerError (5xx)            → retry
#   - errors.ClientError code=429/RATE    → retry
#   - 其他 4xx                             → 不 retry（這是程式邏輯/契約問題）
#   - httpx 的 transport / connection 類  → retry
#   - asyncio.TimeoutError（我們自己的 wait_for） → 不 retry，budget 用完
#
# Backoff：base 0.3s, 0.3*2^(attempt-1) + jitter 0~0.3s（短一點，對 UX 較友善）

_DEFAULT_MAX_ATTEMPTS = 2
_DEFAULT_TOTAL_BUDGET_S = 60.0  # 各方法呼叫 _generate 時都會明確覆寫，這只是保險預設
_RETRY_BASE_DELAY_S = 0.3
_RETRY_BUFFER_S = 5.0  # retry 前要保留至少 5s 給下一次 attempt 才重試

# P3.10-3-R2 fix #7（Codex round-2 audit）：Python 3.11+ 起 `asyncio.TimeoutError` 是
# `TimeoutError` 的 alias。我們的 wait_for budget 用完會丟它，但 SDK / httpx 內部也可能丟
# plain `TimeoutError`（非 budget exhausted），現在會被誤判成 budget exhausted、不 retry。
# 解法：catch 住之後比對 elapsed vs budget，差距 > epsilon 就視為 transport timeout 走 retry。
_BUDGET_TIMEOUT_EPSILON_S = 1.0


def _backoff_delay(attempt: int) -> float:
    """attempt=1 → ~0.3s, attempt=2 → ~0.6s, attempt=3 → ~1.2s（含 jitter）"""
    base = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
    return base + random.uniform(0.0, 0.3)


def _is_retryable_client_error(exc: genai_errors.ClientError) -> bool:
    """4xx 只有 429 / RESOURCE_EXHAUSTED 可重試。"""
    code = getattr(exc, "code", None)
    status = (getattr(exc, "status", None) or "").upper()
    return code == 429 or status == "RESOURCE_EXHAUSTED" or status == "RATE_LIMIT_EXCEEDED"


def _is_retryable_transport_error(exc: BaseException) -> bool:
    """httpx 的 TimeoutException / ConnectError / NetworkError 系列都可重試。"""
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError, ConnectionError))


class LLMService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    async def _generate(
        self,
        prompt: str,
        json_mode: bool = False,
        *,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        total_timeout_s: float = _DEFAULT_TOTAL_BUDGET_S,
    ) -> str:
        """Async Gemini API call with budget-controlled retry.

        Args:
            prompt: LLM input
            json_mode: 走 application/json response
            max_attempts: 最大嘗試次數（含第一次），預設 2
            total_timeout_s: server-side wall-clock budget；超過後直接 raise，
                            不會把 client 已 abort 的 request 留著燒 quota。
                            呼叫方應傳「比對應 frontend apiFetch timeoutMs 略小」的值。
        """
        if not self.client:
            raise Exception("Gemini client not initialized - check GEMINI_API_KEY")

        config = None
        if json_mode:
            config = types.GenerateContentConfig(response_mime_type="application/json")

        start = time.monotonic()
        last_exc: BaseException | None = None

        for attempt in range(1, max_attempts + 1):
            remaining = total_timeout_s - (time.monotonic() - start)
            if remaining <= 0:
                logger.warning(
                    "LLM _generate budget exhausted before attempt %d (budget=%.1fs)",
                    attempt, total_timeout_s,
                )
                raise (last_exc or asyncio.TimeoutError(
                    f"_generate budget {total_timeout_s:.1f}s exhausted after {attempt - 1} attempts"
                ))
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=MODEL, contents=prompt, config=config,
                    ),
                    timeout=remaining,
                )
                if attempt > 1:
                    logger.info(
                        "LLM _generate succeeded on attempt %d/%d (elapsed %.1fs)",
                        attempt, max_attempts, time.monotonic() - start,
                    )
                return response.text

            except (asyncio.TimeoutError, TimeoutError) as exc:
                # P3.10-3-R2 fix #7（Codex round-2 audit）：Python 3.11+ `asyncio.TimeoutError`
                # 是 `TimeoutError` 的 alias。SDK / httpx 內部可能丟 plain `TimeoutError`
                # (e.g. socket connect timeout)，不一定是我們 wait_for budget 用完。
                # 如果 elapsed 還沒逼近 total_timeout_s，視為 transport timeout → 走 retry；
                # 只有真的 budget 用完才 raise。
                elapsed = time.monotonic() - start
                budget_exhausted = elapsed >= (total_timeout_s - _BUDGET_TIMEOUT_EPSILON_S)
                if budget_exhausted:
                    logger.warning(
                        "LLM _generate budget timeout on attempt %d (used %.1fs / budget %.1fs)",
                        attempt, elapsed, total_timeout_s,
                    )
                    raise
                # SDK-side timeout，當成 transport error 處理
                last_exc = exc
                if attempt >= max_attempts:
                    logger.warning(
                        "LLM _generate transport timeout on attempt %d — max attempts reached "
                        "(used %.1fs / budget %.1fs)", attempt, elapsed, total_timeout_s,
                    )
                    raise
                delay = _backoff_delay(attempt)
                remaining_after = total_timeout_s - elapsed - delay - _RETRY_BUFFER_S
                if remaining_after <= 0:
                    logger.warning(
                        "LLM _generate transport timeout but no budget for retry: used %.1fs",
                        elapsed,
                    )
                    raise
                logger.info(
                    "LLM _generate transport timeout attempt %d/%d (used %.1fs/%.1fs), "
                    "retrying in %.1fs", attempt, max_attempts, elapsed, total_timeout_s, delay,
                )
                await asyncio.sleep(delay)

            except genai_errors.ServerError as exc:
                last_exc = exc
                if attempt >= max_attempts:
                    raise
                delay = _backoff_delay(attempt)
                remaining_after = total_timeout_s - (time.monotonic() - start) - delay - _RETRY_BUFFER_S
                if remaining_after <= 0:
                    logger.warning(
                        "LLM _generate ServerError but no budget for retry (need %.1f+%.1f, "
                        "remaining %.1fs): %s",
                        delay, _RETRY_BUFFER_S, total_timeout_s - (time.monotonic() - start), exc,
                    )
                    raise
                logger.info(
                    "LLM _generate ServerError attempt %d/%d (code=%s status=%s), "
                    "retrying in %.1fs (%.1fs budget left after retry)",
                    attempt, max_attempts, getattr(exc, "code", "?"),
                    getattr(exc, "status", "?"), delay, remaining_after,
                )
                await asyncio.sleep(delay)

            except genai_errors.ClientError as exc:
                last_exc = exc
                if not _is_retryable_client_error(exc) or attempt >= max_attempts:
                    # 4xx 非 429 不該 retry — 是契約 / 程式邏輯問題
                    logger.warning(
                        "LLM _generate ClientError attempt %d (code=%s status=%s) — not retrying",
                        attempt, getattr(exc, "code", "?"), getattr(exc, "status", "?"),
                    )
                    raise
                delay = _backoff_delay(attempt)
                remaining_after = total_timeout_s - (time.monotonic() - start) - delay - _RETRY_BUFFER_S
                if remaining_after <= 0:
                    logger.warning("LLM _generate rate-limited but no budget for retry: %s", exc)
                    raise
                logger.info(
                    "LLM _generate rate limited attempt %d/%d, retrying in %.1fs",
                    attempt, max_attempts, delay,
                )
                await asyncio.sleep(delay)

            except Exception as exc:
                last_exc = exc
                if not _is_retryable_transport_error(exc) or attempt >= max_attempts:
                    logger.warning(
                        "LLM _generate non-retryable %s on attempt %d: %s",
                        type(exc).__name__, attempt, str(exc)[:120],
                    )
                    raise
                delay = _backoff_delay(attempt)
                remaining_after = total_timeout_s - (time.monotonic() - start) - delay - _RETRY_BUFFER_S
                if remaining_after <= 0:
                    raise
                logger.info(
                    "LLM _generate transport %s attempt %d/%d, retrying in %.1fs",
                    type(exc).__name__, attempt, max_attempts, delay,
                )
                await asyncio.sleep(delay)

        # 理論不可達（上面 raise 過了），保險起見：
        raise last_exc if last_exc else RuntimeError("LLM _generate unreachable")

    # ══════════════════════════════════════════════════════════════
    #  Persona 工具：根據 platform 決定 AI 扮演什麼角色
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _is_youtube(platform: str) -> bool:
        return (platform or "").lower() == "youtube"

    # ══════════════════════════════════════════════════════════════
    #  1. 核心分析
    # ══════════════════════════════════════════════════════════════

    async def analyze_content(
        self,
        text_content: str,
        platform: str = "google",
        *,
        total_timeout_s: float = 55.0,
    ) -> dict:
        """
        分析爬蟲拿到的原始文字（評論或留言），回傳好壞主題比例。
        platform: "google"（店家評論）| "youtube"（影片留言）

        P3.10-2-R3（Codex R2 點 2）：caller 可傳 total_timeout_s 覆寫預設 budget，
        讓 /api/analyze route 可以根據「scraper 已用掉多少時間」動態壓縮 LLM budget，
        確保 route total 不超出 ROUTE_TOTAL_BUDGET_S。
        """
        # P3.10-3-R3 fix（Codex round-2 leftover）：原本短 text 回 `{"error": ...}` dict，
        # 違反 invariant ②「service 層 raise 不回 fallback dict」。route 那邊會把 dict 當
        # 成正常 result 寫進下游資料→ UI 顯示「Not enough content to analyze」字樣當分析結果。
        # 改成 raise ValueError，讓 route 的 except 統一走 failed 路徑。
        if not text_content or len(text_content.strip()) < 50:
            raise ValueError("Not enough content to analyze (text too short)")

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

        # P3.10-3-R2 fix #1（Codex round-2 audit）：原本 try/except 把所有錯吞掉、回 {"error": ...}
        # dict 給 caller 自己判斷。這違反 invariant ②（service 層失敗一律 raise）也跟 generate_swot
        # 改 raise 後的 convention 不一致。改法：JSON parse 失敗或 _generate 失敗一律 raise；route
        # 自己 catch → _fallback:true mock → frontend ErrorVM。
        # analyze_content：~600 tokens JSON，gemma 實測 20-40s；budget 由 caller 控（預設 55s）
        text = await self._generate(prompt, json_mode=True, total_timeout_s=total_timeout_s)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 二次救援：response 可能包了 markdown 代碼塊，正則撈 {...}
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            raise ValueError(f"analyze_content response not valid JSON: {text[:200]}")

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

        # generate_swot：~400 tokens JSON，gemma 實測 15-30s；budget 55s（frontend 60s - 5s buffer）
        # P3.10-2-R3（Codex R2 點 1）：原本這裡有 try/except 吞掉所有錯誤、回看起來合理的 fallback
        # SWOT，但 routes.py 只在自己 catch 後才 set _fallback:true，所以 service 層的 fallback
        # 會被 route 當成「成功」回給 frontend，造成 silent degradation。
        # 修法：service 層失敗就 raise，讓 route 的 except → mock + _fallback:true → frontend
        # apiFetch 偵測到 _fallback:true → ErrorVM → reducer FAILED → UI 顯示「AI 暫時無法產生」。
        # 只 salvage 真的能 parse 的 JSON。
        text = await self._generate(prompt, json_mode=True, total_timeout_s=55.0)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 二次救援：response 包了 markdown / 多餘文字，正則撈 {...}
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            raise ValueError(f"SWOT response not valid JSON: {text[:200]}")

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
        # generate_reply：~150 字短文，gemma 實測 5-15s；budget 40s（frontend 45s - 5s buffer）
        return await self._generate(prompt, total_timeout_s=40.0)

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
        # generate_marketing：~200 字貼文，gemma 實測 8-20s；budget 40s（frontend 45s - 5s buffer）
        return await self._generate(prompt, total_timeout_s=40.0)

    # ══════════════════════════════════════════════════════════════
    #  5. 根源問題分析
    # ══════════════════════════════════════════════════════════════

    async def generate_root_cause_analysis(self, topic: str, platform: str = "google") -> str:
        # P3.11 fix：v4 UI 用 <pre> 純文字渲染，不可用 markdown 標記（## ** ###）。
        # 改用全形空白縮排 + ▸◆ 符號做結構化純文字。
        if self._is_youtube(platform):
            prompt = f"""你是一位資深 YouTube 頻道經營顧問。觀眾持續反映的問題是：「{topic}」。

請進行深度根源分析（繁體中文，純文字輸出，不要使用 # * - 等 markdown 標記）。
照以下結構回答：

【根源問題分析：{topic}】

◆ 直接原因（製作層面）
　▸ ...（剪輯節奏／腳本結構／配樂／片長等）
　▸ ...

◆ 創作流程原因（前製／拍攝／後製）
　▸ ...（腳本不到位／現場沒捕捉重點／剪輯時間不夠等）
　▸ ...

◆ 內容策略原因（定位／選題／觀眾期待）
　▸ ...（這題往往不是技術問題，而是策略問題）
　▸ ...

【建議改善方案】

◆ 短期措施（下一支影片就能做）
　▸ ...
　▸ ...

◆ 中期措施（本季度 3 支影片內驗證）
　▸ ...
　▸ ...

◆ 長期措施（3 個月以上的內容調整）
　▸ ...
　▸ ..."""
        else:
            prompt = f"""你是一位餐飲業管理顧問。請針對顧客持續反映的問題「{topic}」進行深度根源分析（繁體中文，純文字輸出，不要使用 # * - 等 markdown 標記）。

照以下結構回答：

【根源問題分析：{topic}】

◆ 直接原因（操作層面）
　▸ ...
　▸ ...

◆ 系統性原因（流程／制度／資源）
　▸ ...
　▸ ...

◆ 管理層面原因（人員／培訓／文化）
　▸ ...
　▸ ...

【建議改善方案】

◆ 短期措施（1 週內可執行）
　▸ ...
　▸ ...

◆ 中期措施（1 個月內）
　▸ ...
　▸ ...

◆ 長期措施（3 個月以上）
　▸ ...
　▸ ..."""
        # generate_root_cause_analysis：~500 tokens 純文字結構，gemma 實測 25-50s；budget 70s（frontend 75s - 5s buffer）
        return await self._generate(prompt, total_timeout_s=70.0)

    # ══════════════════════════════════════════════════════════════
    #  6. 週計畫
    # ══════════════════════════════════════════════════════════════

    async def generate_weekly_plan(self, weaknesses: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位 YouTube 頻道成長教練。根據以下需要改善的項目：{weaknesses}

請制定一份「頻道下一週行動計畫」（繁體中文）。目標是用一週把這些弱點轉換成具體的創作動作。

純文字輸出，不要使用 # * - 等 markdown 標記。請完全比照下面的格式骨架填入內容：

【頻道本週行動計畫】

◆ 週一（規劃日）
　▸ 任務：...
　▸ 產出：...
　▸ 預期結果：...

◆ 週二（製作日）
　▸ 任務：...
　▸ 產出：...
　▸ 預期結果：...

（請為週一到週日，每天 2-3 個具體可執行的創作任務，不要寫空泛目標。涵蓋前製／拍攝／剪輯／社群／數據分析等。每天都用 ◆ 開頭、條列用 　▸ 開頭，純文字，不要 markdown）"""
        else:
            prompt = f"""你是一位餐廳營運顧問。根據以下需要改善的項目：{weaknesses}

請制定一份詳細的週行動計畫（繁體中文）。

純文字輸出，不要使用 # * - 等 markdown 標記。請完全比照下面的格式骨架填入內容：

【本週改善行動計畫】

◆ 週一
　▸ 任務：...
　▸ 負責人：...
　▸ 預期結果：...

◆ 週二
　▸ 任務：...
　▸ 負責人：...
　▸ 預期結果：...

（請為週一到週日，每天列出 2-3 個具體且可執行的任務。每天都用 ◆ 開頭、條列用 　▸ 開頭，純文字，不要 markdown）"""
        # generate_weekly_plan：7 天 × 3 任務純文字結構，~900 tokens，gemma 實測 50-75s；
        # budget 115s（frontend 120s - 5s buffer），這是 9 個 endpoint 裡最慢的
        return await self._generate(prompt, total_timeout_s=115.0)

    # ══════════════════════════════════════════════════════════════
    #  7. 培訓劇本（YouTube 版：剪輯師/團隊成員溝通範本）
    # ══════════════════════════════════════════════════════════════

    async def generate_training_script(self, issue: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位 YouTube 頻道製作人。請針對「{issue}」這個觀眾回饋問題，撰寫一份給「剪輯師/企劃/外包合作夥伴」的溝通訓練範本（繁體中文）。

目的：把觀眾回饋轉成可落地的製作 SOP，避免下次影片再犯。

純文字輸出，不要使用 # * - 等 markdown 標記。請完全比照下面的格式骨架填入內容：

【製作 SOP：{issue}】

◆ 常見做法（會導致這個問題）
　▸ 情境：...
　▸ 做法：...
　▸ 為什麼不行：...

◆ 改進做法
　▸ 情境：...
　▸ 做法：...
　▸ 為什麼這樣做：...

◆ 給剪輯師／企劃的檢查清單
　▸ 1. ...
　▸ 2. ...
　▸ 3. ...

◆ 容易誤解的地方
　▸ ...
　▸ ...

要求：語氣專業但不官腔，讓合作夥伴看完就知道怎麼做。每段用 ◆ 開頭、條列用 　▸ 開頭，純文字，不要 markdown。"""
        else:
            prompt = f"""你是一位餐廳員工培訓專家。請針對「{issue}」問題，撰寫一份角色扮演培訓劇本（繁體中文）。

純文字輸出，不要使用 # * - 等 markdown 標記。請完全比照下面的格式骨架填入內容：

【培訓情境：{issue}】

◆ NG 示範（錯誤應對）
　▸ 顧客：...
　▸ 員工（NG）：...
　▸ 問題分析：...

◆ OK 示範（正確應對）
　▸ 顧客：...
　▸ 員工（OK）：...
　▸ 重點說明：...

◆ 關鍵話術整理
　▸ 1. ...
　▸ 2. ...
　▸ 3. ...

◆ 常見誤區提醒
　▸ ...
　▸ ...

要求：每段用 ◆ 開頭、條列用 　▸ 開頭，純文字，不要 markdown。"""
        # generate_training_script：完整 SOP 純文字結構，~700 tokens，gemma 實測 45-65s；
        # budget 105s（frontend 110s - 5s buffer），第 2 慢的 endpoint
        return await self._generate(prompt, total_timeout_s=105.0)

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

格式要求：純文字書信（不要 markdown 標記，不要 ** 粗體、不要 ## 標題），語氣正式但不冰冷，像資深製作人跟夥伴溝通。"""
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

格式要求：純文字書信格式（不要 markdown 標記，不要 ** 粗體、不要 ## 標題），語氣正式但親切，展現領導力。"""
        # generate_internal_email：~400 字信件，gemma 實測 25-45s；budget 70s（frontend 75s - 5s buffer）
        return await self._generate(prompt, total_timeout_s=70.0)

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
        # chat：150 字以內短回覆，gemma 實測 5-15s；budget 40s（frontend 45s - 5s buffer）
        return await self._generate(prompt, total_timeout_s=40.0)
