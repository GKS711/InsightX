"""
v5 ORM models — SQLAlchemy 2.0 declarative.

9 tables (Codex consensus + DBA review):
  users → workspaces → stores → review_sources → scrape_jobs → reviews
  stores → analysis_runs → generated_assets
  stores → reports

DBA notes:
  - All foreign keys indexed (avoid full table scan on JOIN)
  - Soft delete via `deleted_at IS NULL` partial index where applicable
  - Composite indexes for common (filter + sort) query patterns
  - JSON / JSONB for evolving payload (output_json, raw_metadata)
  - Timestamps in UTC (timezone-aware), DEFAULT NOW()
  - Status enums implemented as String + CHECK constraint (portable across SQLite/PG)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Declarative base. All v5 models inherit from this."""
    pass


# ────────────────────────────────────────────────────────────────────
# users
# ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("plan IN ('free', 'pro', 'enterprise')", name="ck_users_plan"),
    )


# ────────────────────────────────────────────────────────────────────
# workspaces
# ────────────────────────────────────────────────────────────────────
class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="workspaces")
    stores: Mapped[list["Store"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True
    )


# ────────────────────────────────────────────────────────────────────
# stores
# ────────────────────────────────────────────────────────────────────
class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    primary_url: Mapped[Optional[str]] = mapped_column(String(2000))
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="stores")
    sources: Mapped[list["ReviewSource"]] = relationship(
        back_populates="store", cascade="all, delete-orphan", passive_deletes=True
    )
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="store", cascade="all, delete-orphan", passive_deletes=True
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="store", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "platform IN ('google', 'youtube')", name="ck_stores_platform"
        ),
    )


# ────────────────────────────────────────────────────────────────────
# review_sources
# ────────────────────────────────────────────────────────────────────
class ReviewSource(Base):
    __tablename__ = "review_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_reviews_estimated: Mapped[Optional[int]] = mapped_column(Integer)

    store: Mapped[Store] = relationship(back_populates="sources")
    scrape_jobs: Mapped[list["ScrapeJob"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", passive_deletes=True
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('google_maps', 'youtube')",
            name="ck_review_sources_type",
        ),
    )


# ────────────────────────────────────────────────────────────────────
# scrape_jobs
# ────────────────────────────────────────────────────────────────────
class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("review_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_class: Mapped[Optional[str]] = mapped_column(String(128))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviews_fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pagination_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    source: Mapped[ReviewSource] = relationship(back_populates="scrape_jobs")
    reviews: Mapped[list["Review"]] = relationship(back_populates="scrape_job")

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_scrape_jobs_status",
        ),
        # 找正在跑的 job
        Index("ix_scrape_jobs_source_status", "source_id", "status"),
    )


# ────────────────────────────────────────────────────────────────────
# reviews
# ────────────────────────────────────────────────────────────────────
class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("review_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scrape_job_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("scrape_jobs.id", ondelete="SET NULL"),
        index=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(256))
    author: Mapped[Optional[str]] = mapped_column(String(255))
    rating: Mapped[Optional[int]] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    raw_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    source: Mapped[ReviewSource] = relationship(back_populates="reviews")
    scrape_job: Mapped[Optional[ScrapeJob]] = relationship(back_populates="reviews")

    __table_args__ = (
        # 列最近評論（descending by published_at within source）
        Index("ix_reviews_source_published", "source_id", "published_at"),
        # 同一 source 內 external_id dedupe
        UniqueConstraint("source_id", "external_id", name="uq_reviews_source_external"),
    )


# ────────────────────────────────────────────────────────────────────
# analysis_runs
# ────────────────────────────────────────────────────────────────────
class AnalysisRun(Base):
    """One analysis_run = 一次 AI 功能呼叫 + result 紀錄。

    Codex critical insight: must record prompt_version + model + input_review_ids
    so future debug 'why this conclusion changed' is possible.
    """
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ai_function: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    model_id: Mapped[str] = mapped_column(String(128), nullable=False, default="gemma-4-31b-it")
    # SQLite 沒 ARRAY；用 JSON list of ints。Postgres 也 work via JSON.
    input_review_ids: Mapped[Optional[list[int]]] = mapped_column(JSON)
    output_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    cost_cents: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error_class: Mapped[Optional[str]] = mapped_column(String(128))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    store: Mapped[Store] = relationship(back_populates="analysis_runs")
    generated_assets: Mapped[list["GeneratedAsset"]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_analysis_runs_status",
        ),
        CheckConstraint(
            "ai_function IN ('analyze', 'swot', 'reply', 'analyze_issue', "
            "'marketing', 'weekly_plan', 'training_script', 'internal_email', 'chat')",
            name="ck_analysis_runs_function",
        ),
        # 列分析歷史（store_id 內依 created_at desc）
        Index("ix_analysis_runs_store_created", "store_id", "created_at"),
    )


# ────────────────────────────────────────────────────────────────────
# generated_assets
# ────────────────────────────────────────────────────────────────────
class GeneratedAsset(Base):
    __tablename__ = "generated_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content_md: Mapped[Optional[str]] = mapped_column(Text)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="generated_assets")


# ────────────────────────────────────────────────────────────────────
# reports
# ────────────────────────────────────────────────────────────────────
class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="pdf")
    file_path: Mapped[Optional[str]] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    store: Mapped[Store] = relationship(back_populates="reports")

    __table_args__ = (
        CheckConstraint("format IN ('pdf', 'docx')", name="ck_reports_format"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_reports_status",
        ),
    )


__all__ = [
    "Base",
    "User",
    "Workspace",
    "Store",
    "ReviewSource",
    "ScrapeJob",
    "Review",
    "AnalysisRun",
    "GeneratedAsset",
    "Report",
]
