"""
v5 Pydantic schemas — request/response models for /api/v5/* endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ────────────────────────────────────────────────────────────────────
# Workspaces
# ────────────────────────────────────────────────────────────────────
class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_user_id: int
    name: str
    created_at: datetime


# ────────────────────────────────────────────────────────────────────
# Stores
# ────────────────────────────────────────────────────────────────────
class StoreCreate(BaseModel):
    workspace_id: int
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = None
    primary_url: Optional[str] = None
    platform: Literal["google", "youtube"] = "google"


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workspace_id: int
    name: str
    address: Optional[str] = None
    primary_url: Optional[str] = None
    platform: str
    created_at: datetime


# ────────────────────────────────────────────────────────────────────
# Review sources
# ────────────────────────────────────────────────────────────────────
class ReviewSourceCreate(BaseModel):
    source_type: Literal["google_maps", "youtube"]
    external_url: str


class ReviewSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    store_id: int
    source_type: str
    external_url: str
    last_scraped_at: Optional[datetime] = None
    total_reviews_estimated: Optional[int] = None


# ────────────────────────────────────────────────────────────────────
# Scrape jobs
# ────────────────────────────────────────────────────────────────────
class ScrapeJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    attempt_number: int
    reviews_fetched_count: int
    pagination_truncated: bool


# ────────────────────────────────────────────────────────────────────
# Analysis runs
# ────────────────────────────────────────────────────────────────────
AiFunction = Literal[
    "analyze",
    "swot",
    "reply",
    "analyze_issue",
    "marketing",
    "weekly_plan",
    "training_script",
    "internal_email",
    "chat",
]


class AnalysisRunCreate(BaseModel):
    ai_function: AiFunction
    # 額外輸入（依 ai_function 不同）：topic, strengths, weaknesses, issue, message ...
    inputs: dict[str, Any] = Field(default_factory=dict)
    model_tier: Literal["standard", "premium"] = "standard"


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    store_id: int
    ai_function: str
    prompt_version: str
    model_id: str
    output_json: Optional[dict[str, Any]] = None
    tokens_used: Optional[int] = None
    cost_cents: Optional[int] = None
    status: str
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime


# ────────────────────────────────────────────────────────────────────
# Reviews
# ────────────────────────────────────────────────────────────────────
class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    scrape_job_id: Optional[int] = None
    author: Optional[str] = None
    rating: Optional[int] = None
    text: str
    published_at: Optional[datetime] = None


# ────────────────────────────────────────────────────────────────────
# Reports
# ────────────────────────────────────────────────────────────────────
class ReportCreate(BaseModel):
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    format: Literal["pdf", "docx"] = "pdf"


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    store_id: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    format: str
    file_path: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: datetime


# ────────────────────────────────────────────────────────────────────
# Compare
# ────────────────────────────────────────────────────────────────────
class StoreCompareOut(BaseModel):
    """A vs B 多店對照結果 — 並列兩家 store 的最近一次 analyze 結果。"""
    store_a: StoreOut
    store_b: StoreOut
    latest_analyze_a: Optional[AnalysisRunOut] = None
    latest_analyze_b: Optional[AnalysisRunOut] = None
    summary: Optional[str] = None  # LLM-generated 比較摘要（可選）
