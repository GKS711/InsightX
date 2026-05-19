"""
InsightX LLM 服務 v3.0.0 — v6 sync edition

所有下游功能支援 platform 參數：
  - platform="google"  → 店家評論分析（餐飲/零售老闆視角）
  - platform="youtube" → 頻道留言分析（YouTuber 視角）

使用 google-genai SDK 同步 API，模型 gemma-4-31b-it。
結構化輸出使用 response_mime_type="application/json"。

v6 sync 轉換：
  - 從 async API (`client.aio.models.generate_content`) 改用同步
    (`client.models.generate_content`)，因為整個 stack 已 sync 化
  - `asyncio.wait_for(coro, timeout=T)` 拿掉 — 改靠 client-level
    http_options timeout + elapsed-budget 追蹤；per-attempt 不再硬切，
    但跨 retry 的 total budget 仍精準執行（用 time.monotonic 計時）
  - `await asyncio.sleep` → `time.sleep`
"""

import os
import json
import re
import time
import random
import logging
import httpx
from google import genai
from google.genai import types, errors as genai_errors
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Multi-model fallback chain — try primary, fall through to alternatives on
# 5xx / RESOURCE_EXHAUSTED. Each model gets its own retry budget; total
# worst-case calls = max_attempts × len(MODEL_CHAIN).
#
# Order (aligned with v5 LINE bot's GEMINI_PRIMARY/FALLBACK pattern):
#   1. gemma-4-26b-a4b-it   — primary, MoE Active 4B params (thinking fast,
#                              best latency on free tier)
#   2. gemma-4-31b-it       — dense 31B fallback (slower because default
#                              thinking is on; higher quality on complex inputs)
#   3. gemini-2.5-flash     — Google GA fallback (higher quota, sometimes
#                              spikes 503 high-demand)
#   4. gemini-2.5-flash-lite — last-resort lighter model
MODEL_CHAIN = [
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]
MODEL = MODEL_CHAIN[0]  # backward-compat alias

# P3.10-2-R2（Codex peer review 後重設計）：
# 前端 per-endpoint timeoutMs 已細分（adapters.js 定義）：
#   chat/reply/marketing  → 45s   |  swot/internal-email → 60-75s
#   training-script       → 110s  |  weekly-plan         → 120s
# 後端必須**比 frontend timeout 略小**，否則 frontend abort 後後端還在跑、燒 quota。
# 後端用 (max_attempts, total_timeout_s) 控制；v6 不再 per-attempt wait_for，
# 而是讓 client http_options.timeout 控單次上限，跨 retry 用 elapsed-budget。
#
# Retry 判斷用 google-genai 的 type-based exception：
#   - errors.ServerError (5xx)            → retry
#   - errors.ClientError code=429/RATE    → retry
#   - 其他 4xx                             → 不 retry（程式邏輯/契約問題）
#   - httpx 的 transport / connection 類  → retry
#
# Backoff：base 0.3s, 0.3*2^(attempt-1) + jitter 0~0.3s

_DEFAULT_MAX_ATTEMPTS = 2
_DEFAULT_TOTAL_BUDGET_S = 60.0  # 各方法呼叫 _generate 時都會明確覆寫，這只是保險預設
_RETRY_BASE_DELAY_S = 0.3
_RETRY_BUFFER_S = 5.0  # retry 前要保留至少 5s 給下一次 attempt 才重試

# Client-level single-request HTTP timeout (ms). 留比 total_budget 大的 slack
# 是因為 budget 跨 retry，但單次 request 可能比 budget 還短就回。
# 設 120000ms 是合理上限：weekly_plan budget=115s 最久，120s 就一定回。
_HTTP_TIMEOUT_MS = 120_000


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
            # client-level HTTP timeout 保險（防卡死）
            self.client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=_HTTP_TIMEOUT_MS),
            )

    def _generate(
        self,
        prompt: str,
        json_mode: bool = False,
        *,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        total_timeout_s: float = _DEFAULT_TOTAL_BUDGET_S,
    ) -> str:
        """Sync Gemini API call with multi-model fallback + budget-controlled retry.

        Tries models in MODEL_CHAIN one by one. Each model gets a shared
        budget (the remaining wall-clock time from `total_timeout_s`).
        Falls through to next model on ServerError (5xx), 429 RESOURCE_EXHAUSTED,
        or transport-class errors. ClientError 4xx (non-429) — i.e. our bug —
        raises immediately without trying other models.

        Empirical motivation: deploy to HF Spaces hit a Google AI free-tier
        outage where gemma-4-31b-it and gemini-2.5-flash both returned 5xx
        while gemini-2.5-flash-lite was still serving. Without fallback the
        entire app went red for what was a transient model-side issue.
        """
        if not self.client:
            raise Exception("Gemini client not initialized - check GEMINI_API_KEY")

        started = time.monotonic()
        last_exc: BaseException | None = None

        for model_idx, model in enumerate(MODEL_CHAIN):
            elapsed = time.monotonic() - started
            remaining_budget = total_timeout_s - elapsed
            if remaining_budget <= 1.0:
                logger.warning(
                    "LLM _generate budget exhausted before model %s (%.1fs/%.1fs used)",
                    model, elapsed, total_timeout_s,
                )
                break

            try:
                return self._generate_one_model(
                    model, prompt, json_mode,
                    max_attempts=max_attempts,
                    total_timeout_s=remaining_budget,
                )
            except genai_errors.ClientError as e:
                # 4xx non-429 = our bug (bad prompt, invalid args, auth). Don't
                # waste time trying other models — raise immediately.
                if not _is_retryable_client_error(e):
                    raise
                last_exc = e
            except Exception as e:
                last_exc = e

            if model_idx < len(MODEL_CHAIN) - 1:
                logger.warning(
                    "LLM model %s exhausted (%s), falling back to %s",
                    model, type(last_exc).__name__ if last_exc else "?",
                    MODEL_CHAIN[model_idx + 1],
                )

        # All models in MODEL_CHAIN failed
        raise (last_exc or RuntimeError("MODEL_CHAIN exhausted with no exception"))

    def _generate_one_model(
        self,
        model: str,
        prompt: str,
        json_mode: bool = False,
        *,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        total_timeout_s: float = _DEFAULT_TOTAL_BUDGET_S,
    ) -> str:
        """Single-model variant of _generate (the original retry loop).

        Called by _generate per model in MODEL_CHAIN. Same budget/retry
        semantics as before — only difference is the model is a parameter
        instead of the module-level MODEL constant.
        """
        start = time.monotonic()
        last_exc: BaseException | None = None

        for attempt in range(1, max_attempts + 1):
            remaining = total_timeout_s - (time.monotonic() - start)
            if remaining <= 0:
                logger.warning(
                    "LLM %s budget exhausted before attempt %d (budget=%.1fs)",
                    model, attempt, total_timeout_s,
                )
                raise (last_exc or TimeoutError(
                    f"_generate_one_model({model}) budget {total_timeout_s:.1f}s exhausted after {attempt - 1} attempts"
                ))

            # Per-call http timeout = min(remaining budget, client-level ceiling).
            # genai SDK accepts httpOptions on GenerateContentConfig and forwards
            # to httpx request timeout.
            per_call_timeout_ms = max(
                1_000,  # never go below 1s
                int(min(remaining, _HTTP_TIMEOUT_MS / 1000) * 1000),
            )
            per_call_http_opts = types.HttpOptions(timeout=per_call_timeout_ms)
            if json_mode:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    http_options=per_call_http_opts,
                )
            else:
                config = types.GenerateContentConfig(http_options=per_call_http_opts)

            try:
                # v6: sync call instead of `await self.client.aio.models...`
                response = self.client.models.generate_content(
                    model=model, contents=prompt, config=config,
                )
                if attempt > 1:
                    logger.info(
                        "LLM _generate succeeded on attempt %d/%d (elapsed %.1fs)",
                        attempt, max_attempts, time.monotonic() - start,
                    )
                return response.text

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
                time.sleep(delay)

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
                time.sleep(delay)

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
                time.sleep(delay)

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

    def analyze_content(
        self,
        text_content: str,
        platform: str = "google",
        *,
        total_timeout_s: float = 90.0,
    ) -> dict:
        """
        分析爬蟲拿到的原始文字（評論或留言），回傳好壞主題比例。
        platform: "google"（店家評論）| "youtube"（影片留言）
        """
        if not text_content or len(text_content.strip()) < 50:
            raise ValueError("Not enough content to analyze (text too short)")

        # Truncate 動態 cap：15000 字元，中小店覆蓋已足夠（中文字元 → token 約 0.5 比例）
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

        # JSON parse 失敗或 _generate 失敗一律 raise；route 自己 catch → _fallback:true mock → frontend ErrorVM。
        text = self._generate(prompt, json_mode=True, total_timeout_s=total_timeout_s)
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

    def generate_swot(self, good: list, bad: list, platform: str = "google") -> dict:
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

        # 失敗一律 raise；route catch → fallback mock → frontend ErrorVM
        text = self._generate(prompt, json_mode=True, total_timeout_s=55.0)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
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

    def generate_reply(self, topic: str, platform: str = "google") -> str:
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
        return self._generate(prompt, total_timeout_s=40.0)

    # ══════════════════════════════════════════════════════════════
    #  4. 行銷文案
    # ══════════════════════════════════════════════════════════════

    def generate_marketing(self, strengths: str, platform: str = "google") -> str:
        if self._is_youtube(platform):
            prompt = f"""你是一位專精 YouTube 頻道行銷的社群操盤手。根據以下這支影片/頻道被觀眾稱讚的亮點:{strengths}

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
        return self._generate(prompt, total_timeout_s=40.0)

    # ══════════════════════════════════════════════════════════════
    #  5. 根源問題分析
    # ══════════════════════════════════════════════════════════════

    def generate_root_cause_analysis(self, topic: str, platform: str = "google") -> str:
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
        return self._generate(prompt, total_timeout_s=70.0)

    # ══════════════════════════════════════════════════════════════
    #  6. 週計畫
    # ══════════════════════════════════════════════════════════════

    def generate_weekly_plan(self, weaknesses: str, platform: str = "google") -> str:
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
        return self._generate(prompt, total_timeout_s=115.0)

    # ══════════════════════════════════════════════════════════════
    #  7. 培訓劇本
    # ══════════════════════════════════════════════════════════════

    def generate_training_script(self, issue: str, platform: str = "google") -> str:
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
        return self._generate(prompt, total_timeout_s=105.0)

    # ══════════════════════════════════════════════════════════════
    #  8. 內部信
    # ══════════════════════════════════════════════════════════════

    def generate_internal_email(self, strengths: str, weaknesses: str, platform: str = "google") -> str:
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
        return self._generate(prompt, total_timeout_s=70.0)

    # ══════════════════════════════════════════════════════════════
    #  9. AI 顧問對話
    # ══════════════════════════════════════════════════════════════

    def chat(self, user_message: str, context: str = "", platform: str = "google") -> str:
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
        return self._generate(prompt, total_timeout_s=40.0)
