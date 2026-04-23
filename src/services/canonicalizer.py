"""
共用 canonicalize / validation 邏輯。

P1-1 實作，供 routes.py 11 個 endpoint（/analyze + 8 AI + /meta + legacy/v4 SSE）共用。
定義見 docs/v4-api-contract.md §1.2（yt_role canonicalization）、§1.5（422 body shape）。
"""

from typing import Literal, Optional

from fastapi import HTTPException

Platform = Literal["google", "youtube"]
YtRole = Literal["creator", "shop", "brand"]


def raise_422(loc: list, msg: str, err_type: str) -> None:
    """統一 422 body shape。見 docs/v4-api-contract.md §1.5。"""
    raise HTTPException(
        status_code=422,
        detail=[{"loc": loc, "msg": msg, "type": err_type}],
    )


def canonicalize_yt_role(
    platform: Platform,
    yt_role: Optional[YtRole],
    warnings: list,
) -> Optional[YtRole]:
    """
    依 docs/v4-api-contract.md §1.2 做 canonicalization。

    回傳 effective_yt_role：
      - platform="youtube" + yt_role 有值 → 照用
      - platform="youtube" + yt_role None → "creator"（加 warning）
      - platform="google" + yt_role 有值 → None（忽略，加 warning）
      - platform="google" + yt_role None → None

    warnings list 以 mutation 方式加入訊息（由 caller 傳入同一 list）。
    """
    if platform == "youtube":
        if yt_role is None:
            warnings.append("yt_role defaulted to 'creator' for youtube")
            return "creator"
        return yt_role
    # platform == "google"
    if yt_role is not None:
        warnings.append("yt_role ignored when platform=google")
    return None


def verify_platform_hint(
    detected_platform: Platform,
    hint: Optional[Platform],
) -> None:
    """
    /analyze 與 /api/v4/analyze-stream 用：若 client 傳的 platform hint
    與 URL 偵測結果衝突 → raise 422（body shape 見 §1.5）。

    hint=None 或等同 detected → 不做事。
    """
    if hint is not None and hint != detected_platform:
        raise_422(
            loc=["body", "__root__"],
            msg=f"platform hint '{hint}' conflicts with detected '{detected_platform}' from url",
            err_type="value_error.platform_conflict",
        )


def attach_metadata(
    result: dict,
    *,
    effective_yt_role: Optional[YtRole],
    fallback: bool,
    warnings: list,
) -> dict:
    """
    所有 endpoint 回傳前呼叫一次，統一塞 3 個 metadata 欄位。

    會覆寫既有同名欄位（canonicalize 結果為準）。回傳同一 dict（原地修改）。
    """
    result["effective_yt_role"] = effective_yt_role
    result["_fallback"] = fallback
    result["warnings"] = list(warnings)  # defensive copy
    return result
