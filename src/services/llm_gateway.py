"""
LLM Gateway — 統一 entry point 給所有 9 個 AI function。

Codex consensus design (2026-05-02):
  - 把 LLMService 的 9 個方法改成「prompt 模板 + Gateway 統一執行」
  - Gateway 負責：
    * 寫 AnalysisRun row（status=running）
    * 呼叫底層 LLM
    * 紀錄 prompt_version + model_id + tokens + cost
    * 寫回結果（status=succeeded/failed + output_json）
    * 未來換模型只動一處（model_tier='standard' vs 'premium'）

Why this matters:
  - Without versioning, debug「為什麼這次結論不同」就死了
  - 多店並發時統一 quota / rate-limit 管控
  - LLM provider abstraction（之後加 Claude / GPT 不用改 9 處）
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AnalysisRun, Review, ReviewSource, Store
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# 目前支援的 model tier
ModelTier = Literal["standard", "premium"]

# tier → model_id mapping
_TIER_TO_MODEL = {
    "standard": "gemma-4-31b-it",
    # premium 暫時 fallback 到 standard，未來接 Claude / GPT
    "premium": "gemma-4-31b-it",
}


class LLMGateway:
    """All v5 AI calls go through here. Records to analysis_runs table."""

    PROMPT_VERSION = "v5.0.0-alpha"

    def __init__(self) -> None:
        self._llm = LLMService()

    async def run(
        self,
        *,
        session: AsyncSession,
        store: Store,
        ai_function: str,
        inputs: dict[str, Any],
        model_tier: ModelTier = "standard",
    ) -> AnalysisRun:
        """Execute one AI function call + persist as AnalysisRun.

        Args:
            session: live AsyncSession
            store: which store the run is associated with
            ai_function: 'analyze' | 'swot' | 'reply' | ...
            inputs: payload depending on ai_function
                    e.g. analyze: {} (uses store reviews)
                         swot: {'good': [...], 'bad': [...]}
                         reply: {'topic': '出餐速度慢'}
            model_tier: 'standard' (gemma) or 'premium' (TBD)

        Returns:
            AnalysisRun (already committed, with output_json or error fields populated)
        """
        model_id = _TIER_TO_MODEL.get(model_tier, _TIER_TO_MODEL["standard"])
        platform = store.platform or "google"

        # 1) create run row (status=running)
        run = AnalysisRun(
            store_id=store.id,
            ai_function=ai_function,
            prompt_version=self.PROMPT_VERSION,
            model_id=model_id,
            input_review_ids=inputs.get("input_review_ids"),
            status="running",
            started_at=datetime.now(tz=timezone.utc),
        )
        session.add(run)
        await session.flush()
        run_id = run.id

        t0 = time.monotonic()
        try:
            # 2) dispatch to LLMService method
            output = await self._dispatch(ai_function, inputs, platform)
            run.output_json = output if isinstance(output, dict) else {"text": output}
            run.status = "succeeded"
            run.finished_at = datetime.now(tz=timezone.utc)
            elapsed = time.monotonic() - t0
            logger.info(
                "[LLMGateway] run_id=%s function=%s tier=%s elapsed=%.1fs OK",
                run_id, ai_function, model_tier, elapsed,
            )
        except Exception as exc:
            run.status = "failed"
            run.error_class = type(exc).__name__
            run.error_message = str(exc)[:1000]
            run.finished_at = datetime.now(tz=timezone.utc)
            elapsed = time.monotonic() - t0
            logger.warning(
                "[LLMGateway] run_id=%s function=%s tier=%s elapsed=%.1fs FAILED: %s",
                run_id, ai_function, model_tier, elapsed, exc,
            )

        return run

    async def _dispatch(
        self,
        ai_function: str,
        inputs: dict[str, Any],
        platform: str,
    ) -> Any:
        """Dispatch to LLMService method based on ai_function."""
        if ai_function == "analyze":
            text = inputs.get("text", "")
            if not text:
                raise ValueError("analyze requires 'text' input")
            return await self._llm.analyze_content(text, platform=platform)

        if ai_function == "swot":
            good = inputs.get("good", [])
            bad = inputs.get("bad", [])
            return await self._llm.generate_swot(good, bad, platform=platform)

        if ai_function == "reply":
            topic = inputs.get("topic", "")
            if not topic:
                raise ValueError("reply requires 'topic' input")
            return await self._llm.generate_reply(topic, platform=platform)

        if ai_function == "analyze_issue":
            topic = inputs.get("topic", "")
            if not topic:
                raise ValueError("analyze_issue requires 'topic' input")
            return await self._llm.generate_root_cause_analysis(topic, platform=platform)

        if ai_function == "marketing":
            strengths = inputs.get("strengths", "")
            return await self._llm.generate_marketing(strengths, platform=platform)

        if ai_function == "weekly_plan":
            weaknesses = inputs.get("weaknesses", "")
            return await self._llm.generate_weekly_plan(weaknesses, platform=platform)

        if ai_function == "training_script":
            issue = inputs.get("issue", "")
            return await self._llm.generate_training_script(issue, platform=platform)

        if ai_function == "internal_email":
            strengths = inputs.get("strengths", "")
            weaknesses = inputs.get("weaknesses", "")
            return await self._llm.generate_internal_email(strengths, weaknesses, platform=platform)

        if ai_function == "chat":
            message = inputs.get("message", "")
            context = inputs.get("context", "")
            return await self._llm.chat(message, context, platform=platform)

        raise ValueError(f"unknown ai_function: {ai_function}")


# singleton
gateway = LLMGateway()
