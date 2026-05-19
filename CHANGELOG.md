# Changelog

All notable changes to InsightX. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

---

## [6.0.0-alpha] — 2026-05-19

### Stack rewrite (sync everywhere)

Full async→sync conversion of the FastAPI + SQLAlchemy + jobs stack so Turso/libsql can back the DB. `sqlalchemy-libsql` 0.2 is sync-only as of 2026-05; trying `create_async_engine("sqlite+libsql://...")` raises `InvalidRequestError`. Going fully sync was the cheapest path that kept the ORM models, alembic migrations, and v5 schema unchanged.

- **`src/db.py`** — `create_engine` instead of `create_async_engine`; normalizes `libsql://...` to `sqlite+libsql://` + `?secure=true`; lifts `TURSO_AUTH_TOKEN` env into `connect_args`; FK PRAGMA listener for SQLite/libsql.
- **`src/jobs.py`** — threading.Thread daemons + `queue.Queue` (was asyncio.create_task + asyncio.Queue). `_LLM_SEMA` / `_SCRAPER_SEMA` are `threading.Semaphore`. Round-3 cascade-race protection (`_safe_commit_or_log` with narrowed `except (StaleDataError, IntegrityError)`) preserved verbatim. `progress_stream()` rewritten with finally-pop cleanup + heartbeat-based disconnect detection + time-since-last-event idle timeout (Codex round-2 fix).
- **`src/api/v5.py`** — 19 endpoints all sync. DELETE /stores preserves the layer-1 best-effort 409 + layer-2 `_safe_commit_or_log` race design. Report download lazily regenerates if the ephemeral container lost the file (HF Spaces cold-restart fix).
- **`src/api/routes.py`** — v4 routes all sync. `/v4/analyze-stream` uses threading.Thread producer + heartbeat thread + queue.Queue (was asyncio task + queue). Worker checks `done_event.is_set()` between phases so disconnects don't queue wasted scraper/LLM work.
- **`src/services/llm_service.py`** — `client.models.generate_content()` sync; per-call `http_options.timeout` from remaining budget (Codex S1 fix). **Multi-model fallback chain**: `gemma-4-26b-a4b-it` → `gemma-4-31b-it` → `gemini-2.5-flash` → `gemini-2.5-flash-lite`. Falls through on 5xx / RESOURCE_EXHAUSTED / transport errors. ClientError 4xx (not 429) raises immediately.
- **`alembic/env.py`** — `engine_from_config` instead of `async_engine_from_config`; `connect_args` propagated from `src.db._engine_kwargs` so migrations can reach Turso.
- **`requirements.txt`** — added `sqlalchemy-libsql==0.2.0`, `libsql-experimental==0.0.55`, `certifi>=2024.0`. Removed `aiosqlite`, `asyncpg`. libsql pair pinned to exact versions (0.x stability).

### v6 redesign + deployment

- **UI**: Codex img2-generated editorial hero illustration replacing the procedural Constellation neural map. Magazine aesthetic: cream paper + ink + coral + forest green; risograph print texture; Saul Bass × Charley Harper × New Yorker references. Multi-source listening concept (Google Maps star pin + YouTube play + chat bubble + heart + scroll + envelope + microphone all converging on a central sonar receiver). PNG tracked via git-lfs (HF Spaces xet/lfs requirement).
- **Dockerfile**: single-stage `python:3.10-slim`, port 7860, non-root uid=1000 user with `chown -R /home/user` before USER switch (SQLite open-file fix), `--only-binary=:all:` for fail-fast wheel install, `HEALTHCHECK` probe on `/api/meta`, JSON-form CMD with `exec` for proper PID-1 signal handling.
- **`.dockerignore`** expanded (was missing `video/`, `outputs/`, `*.db`, `*.backup.*`, `.pytest_cache/`, etc).
- **`docs/DEPLOY_HF.md`** — full HF Spaces + Turso walkthrough with troubleshooting + cost monitoring.
- **`deploy/hf-space-README.md`** — HF Space repo README template with YAML frontmatter.

### Bug fixes during deploy

- **`src/db.py`** Codex hot-fix: dropped `pool_size` / `max_overflow` from engine kwargs — `sqlalchemy-libsql` uses `SingletonThreadPool` which only accepts `pool_pre_ping`. Build broke until this was removed.
- **`src/api/routes.py`** v4→workspace bridge — landing-page analyze now persists to v5 schema (Store + ReviewSource + ScrapeJob + Reviews + AnalysisRun) so the store shows up under `/workspace/`. Idempotent on ReviewSource.external_url. Gated behind `IX_ENABLE_V4_WORKSPACE_PERSIST=1` env flag (default OFF) — see Known Limitations.
- **`src/models.py`** AnalysisRun.model_id default updated from `gemma-4-31b-it` to `gemma-4-26b-a4b-it` to match the new MODEL_CHAIN[0].
- **Frontend** version-label fallback `4.0.0` → `6.0.0-alpha` in header + footer of `src/static/v2/index.html`.

### Codex peer review

Three review cycles reached APPROVE consensus:
- Sync refactor (tasks `bf037e60ed0d` → `372812acadcf` → `5c4363726196`) — found per-call LLM timeout regression, queue cleanup gaps, SSE worker cancellation; all fixed.
- Deploy artifacts (tasks `f1fd2145e07e` → `6dbd19a04ca3` → `f2221cacf342`) — found ephemeral report file vanish-on-restart (regenerate fallback), build-essential bloat (removed), missing HEALTHCHECK (added); all fixed.
- Final pre-freeze pass (tasks `0d309dd01043` → `263e6a5d30c3`) — found multi-tenant privacy issue with bridge auto-persist (env-gated); approved.

### Known limitations (tracked for v6.1)

1. **No auth / no session scoping** — v5α uses a single hard-coded default user (`dev@insightx.local`). Bridge auto-persist is therefore DISABLED on the public demo via `IX_ENABLE_V4_WORKSPACE_PERSIST=0`. Self-hosted single-user setups can set it to `1`.
2. **v5 by-id endpoints not ownership-scoped** — `session.get(Store, store_id)`, `session.get(AnalysisRun, run_id)`, etc, don't filter by workspace owner. Combined with #1, this is currently latent (no auth → no users to cross-leak), but must be fixed alongside cookie session auth.
3. **No `UniqueConstraint(workspace_id, primary_url)` on Store** — concurrent same-URL analyzes (rare in single-user demo) can race to create duplicate Store rows. Will be added via alembic migration in v6.1.
4. **Review dedupe via `external_id`** — schema has `UniqueConstraint(source_id, external_id)` but bridge inserts Review rows with NULL `external_id`. Re-scrape of the same URL appends the same reviews again, which can bias subsequent analysis. Fix: compute stable `external_id = sha256(source_id|author|date|text)` and let the unique constraint dedupe.
5. **`AnalysisRun.model_id` records the default**, not the actually-used model after fallback chain rotation. Tracked: return `(text, model_used)` from `LLMService._generate()` and persist accurately.

These were flagged by Codex's final pre-freeze review (task `0d309dd01043`) and explicitly deferred — they're real but low-probability on a single-user alpha demo where the bridge is OFF. The proper fix is bundled with cookie-based anonymous session scoping in v6.1.

---

## [5.0.0] — 2026-05-19

V5 makes InsightX a **persistent, multi-store workspace** rather than a stateless single-shot demo. Major back-end rewrite (async SQLAlchemy 2.0 ORM, 9-table schema, environment-aware DB driver), new parallel frontend (Vite + React + TypeScript), and a full store-deletion workflow with cascade integrity.

V4 UI is preserved at `/legacy-v4` for regression comparison.

### Added — Backend
- **`POST /api/v5/workspaces`** + list / get endpoints — persistent workspace as a top-level container for stores
- **`POST /api/v5/stores`** + list / get / **DELETE** — multi-store per workspace
- **`DELETE /api/v5/stores/{store_id}`** with 3 layers of integrity:
  - **Ownership scope**: JOIN `Workspace.owner_user_id == current_user`, so deletion can't be wider than `list_stores`
  - **409 race guard**: returns conflict when active `scrape_jobs` OR `analysis_runs` exist
  - **Cascade cleanup**: cascades to `review_sources` / `reviews` / `scrape_jobs` / `analysis_runs` / `generated_assets` / `reports` — verified zero orphan rows post-deletion
- **Async SQLAlchemy 2.0 ORM** (`src/models.py`, 9 tables) — typed `Mapped[]` columns, declarative base
- **Async DB engine** (`src/db.py`):
  - Dev: SQLite + aiosqlite, foreign keys enforced via PRAGMA event listener (cascade was silently no-op without this)
  - Prod: Postgres 16 via docker-compose, shared Alembic migrations
- **Background job queue** (`src/jobs.py`):
  - `run_scrape_job_bg` — `asyncio` + `_SCRAPER_SEMA` (limit 5), 120s timeout, SSE progress events
  - `run_analysis_bg` — `asyncio` + `_LLM_SEMA` (limit 3 for Gemma free tier), 9 AI function dispatch
  - `_safe_commit_or_log` helper — race-safe commits at all 7 commit sites; swallows only `StaleDataError` / `IntegrityError`; re-raises other exceptions with `logger.exception` so DB outages and constraint bugs aren't lied about
- **`src/api/v5.py`** — workspace + store CRUD, schema-typed via Pydantic v2
- **`src/services/reports.py`** — analysis report generation
- **`src/services/llm_gateway.py`** — model gateway layer (dispatch + retry)
- **Alembic migrations** (`alembic/versions/578d92de7851_v5_initial_schema.py`) — initial v5 schema as the migration starting point

### Added — Frontend
- **Workspace SPA** at `/workspace/` (`src/static/v2/workspace/index.html`, 795 lines) — Babel-Standalone React layered with the existing v4 visual system. Dashboard + StoreDetail pages. Polling-based job progress.
- **DangerZone component** on StoreDetail — red-bordered card with explicit cascade copy ("會一併刪除所有評論、抓取紀錄、AI 分析、報表，無法復原"), confirm-then-fetch, busy-state blocks double-click
- **New parallel frontend** in `frontend/` (Vite + React 18 + TypeScript + Tailwind) — Dashboard + StoreDetail target. Built fresh rather than rewriting v4 UI.
- **Type-safe API client** (`frontend/src/api/client.ts` + `hooks.ts`) — React Query

### Added — Docs
- `DESIGN.md` (367 lines) — Linear-inspired design system spec (dark-mode-native, Inter Variable, achromatic + signature indigo accent)
- `docs/V5_NOTES.md` — v5 development policy (only constraint: no bulk-merge PR `claude/... → main`; cherry-pick is the release path)
- `CODEX_REVIEW_ROUND3.md` — third-pass Codex review findings and remediation log

### Changed
- **Scraper timeouts**: SSE scrape budget 40s → **60s** for 500-review big stores (commit `da67169`)
- **Analyze timeout**: default 55s → **90s** for big-store background jobs (commit `6f89798`)
- **Sidebar label**: `回 v4 主站` → `回主頁面` (commit `b604568`) — v4 was an implementation detail leaking to users
- **Nav merge**: Dashboard + Stores merged into single "店家" entry (both pointed to `#/`); Reports renumbered 01 → 02
- **`get_mock_response`** in `src/config/mock_responses.py` now accepts `platform` argument — YouTube mode returns platform-neutral placeholder instead of restaurant-style mock content
- **scraper SSL** — `certifi`-backed SSL context for macOS `uv` Python (commit `d5718b9`)
- **`requirements.txt` / `pyproject.toml`** — adds `sqlalchemy[asyncio]`, `aiosqlite`, `asyncpg`, `alembic`, `pydantic v2`

### Fixed — Round 1 + Round 2 (pre-beta.2)
- Race window between `DELETE` 409 guard and concurrent `POST /scrape` — `_safe_commit_or_log` wraps post-IO commits
- Ownership scoping in DELETE matches `list_stores` JOIN pattern

### Fixed — Round 3 (commit `4c7e2f5`, this release)
- **M1** — `run_scrape_job_bg` initial `running` state commit (line 148) was bare; now wrapped with `_safe_commit_or_log`
- **M2** — same race window for `run_analysis_bg` initial `running` commit (line 235)
- **M3** — `passive_deletes=True` on all 8 ORM relationships using `ON DELETE CASCADE`; previously SQLAlchemy was loading + deleting each child row in Python (Postgres-volume latency hit)
- **M4** — `_safe_commit_or_log` narrowed from `except Exception` to `except (StaleDataError, IntegrityError)`; bare except was lying about "cascade-deleted" for constraint violations / DB outages / programmer bugs. Now those re-raise with `logger.exception`

### Verified
- `DELETE /api/v5/stores/9999` → 404 "store not found"
- `DELETE` while analyze running → 409 "store has active scrape or analysis jobs"
- Cascade integrity post-deletion: **zero orphan rows** across `review_sources` / `reviews` / `scrape_jobs` / `analysis_runs` / `generated_assets` / `reports`
- `py_compile` passes on `src/jobs.py`, `src/models.py`, `src/db.py`, `src/api/v5.py`
- SQLAlchemy mapper introspection confirms `passive_deletes=True` on 8/8 cascading relationships
- 7/7 callsites of `_safe_commit_or_log` verified by source inspection

### Known Issues (deferred to next release)
- **LOW**: `src/static/v2/workspace/index.html:716` — 409 error displays raw `{"detail":"..."}` JSON instead of parsing the `detail` field for human-readable display
- **LOW**: `src/static/v2/workspace/index.html:720` — DELETE success always `navigate("#/")`, doesn't preserve user's current route

---

## [4.1.0] — 2026-05-02

### Fixed
- Backend bug fixes (3 issues found during static code review)
- Scraper / LLM optimization

> Note: `v4.1.0` tag exists locally only — never pushed to GitHub origin. Promoted to `main` as part of the v5.0.0 release path.

---

## [4.0.0] — earlier 2026

### Added
- Single-file React 18 SPA frontend at `src/static/v2/index.html` (Babel-Standalone)
- 4 architectural invariants (documented in DESIGN.md / HANDOFF.md)
- Dual platform support: Google Maps reviews + YouTube channel comments
- SSE event streaming for `/api/v4/analyze-stream`
- 9 AI feature endpoints (analyze / swot / reply / analyze-issue / marketing / weekly-plan / training-script / internal-email / chat) with platform-aware prompt switching
- Canonicalizer service (yt_role normalization + metadata wrapping)
- View-model layer + slice reducer + requestId stale-discard

### Changed
- React UI migration to `src/static/v2/` (replaces v3 plain-HTML + Tailwind CDN)
- v3 legacy UI moved to `/legacy` for fallback / regression comparison

---

## [3.0.0]

### Removed
- Shopee mode — fully dropped after evaluating 8 routes (WAF encryption unsolvable). See `docs/archive/shopee_evaluation_2026-04-21.md`.

### Changed
- Version alignment across stack

---

## [2.0.0]

### Added
- YouTube channel mode with dual-path comment scraper (YouTube Data API v3 main / `youtube-comment-downloader` fallback)
- Platform-aware prompt persona (餐廳/零售 vs 創作者/頻道)

---

## [1.0.0]

Initial public release. Google Maps review scraping + Gemini analysis + single-page React frontend.
