# InsightX — HANDOFF

> **Status**: v6.1.0-alpha · 2026-05-20 · live on HF Spaces
> **For**: the next agent / engineer picking this up
> **Read order**: this file → `CHANGELOG.md` v6.1 + v6 sections → `docs/DEPLOY_HF.md` → `CLAUDE.md` (if your env loads project-level rules)

---

## TL;DR

InsightX takes a **Google Maps URL** or a **YouTube video URL**, pulls reviews/comments via public APIs, and uses Google Gemini to generate a magazine-style insight report (sentiment, SWOT, replies, weekly plan, training scripts, internal email, AI consultant chat).

**Live demo**: <https://Jordan711-insightx-demo.hf.space>
**GitHub**: <https://github.com/GKS711/InsightX>
**Tag**: `v6.1.0-alpha` (also: `v6.0.0-alpha`)
**Branch**: `claude/v6-sync-refactor` (NOT merged into `main` — see [§ Branch policy](#branch-policy))

**v6.1 in one sentence**: the 5 known limitations from v6.0-alpha are all resolved — cookie sessions, ownership scoping, schema constraints, review dedupe, model audit. The v4→workspace bridge is no longer env-gated; every visitor gets their own private workspace automatically.

---

## Architecture (one diagram)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         HF Spaces Free (Docker)                      │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     FastAPI (sync, py3.10)                       │ │
│  │                                                                  │ │
│  │   ┌────────────────────────┐  ┌──────────────────────────────┐  │ │
│  │   │ /api/* (v4 stateless)  │  │ /api/v5/* (persistent)       │  │ │
│  │   │  analyze, swot, reply, │  │  workspaces, stores, jobs,   │  │ │
│  │   │  marketing, weekly,    │  │  runs, reports, SSE streams  │  │ │
│  │   │  training, email, chat │  │                              │  │ │
│  │   └─────────────┬──────────┘  └──────────────┬───────────────┘  │ │
│  │                 │                            │                   │ │
│  │                 ▼                            ▼                   │ │
│  │   ┌────────────────────┐         ┌────────────────────┐         │ │
│  │   │   LLMService       │         │  SessionLocal      │         │ │
│  │   │   MODEL_CHAIN      │         │  (sync SQLAlchemy) │         │ │
│  │   │   (multi-fallback) │         │                    │         │ │
│  │   └─────────┬──────────┘         └─────────┬──────────┘         │ │
│  │             │                              │                    │ │
│  │             ▼                              ▼                    │ │
│  │   ┌────────────────────┐         ┌────────────────────┐         │ │
│  │   │ ScraperService     │         │  threading.Thread  │         │ │
│  │   │  (Serper + YT)     │         │  bg workers + SSE  │         │ │
│  │   └─────────┬──────────┘         └────────────────────┘         │ │
│  └─────────────│───────────────────────────────────────────────────┘ │
│                │                                                     │
└────────────────│─────────────────────────────────────────────────────┘
                 │
       ┌─────────┼─────────┐
       │         │         │
       ▼         ▼         ▼
   Google     YouTube    Turso (libsql, remote)
   Maps       Data API    9-table v5 schema
   (Serper)
                 │
                 ▼
              Gemini API
              (gemma-4-26b-a4b-it primary)
```

---

## v6 stack

| Layer | Tech | Why |
|---|---|---|
| Web | FastAPI 0.109+ on Uvicorn | sync routes; threadpool runs them off-loop |
| Persistence | SQLAlchemy 2.0 ORM (sync) + alembic | works with both local SQLite and Turso libsql |
| DB | **Turso (libsql)** remote, or local SQLite for dev | serverless SQLite, 5GB free; pinned to `sqlalchemy-libsql==0.2.0` because `0.x` API moves |
| LLM | Google Gemini API via `google-genai` | free tier; multi-model fallback chain |
| Scrapers | Serper API (Google Maps) + YouTube Data API v3 (+ `youtube-comment-downloader` fallback) | zero browser; HTTP-only |
| Background jobs | `threading.Thread(daemon=True)` + `queue.Queue` + `threading.Semaphore` | in-process; sync stack means no asyncio |
| Frontend | Single-file React + `@babel/standalone` + UMD CDN | no build step; magazine aesthetic |
| Deploy | HF Spaces Docker SDK | free; 16GB RAM, 2 vCPU, port 7860 |

**Why sync everywhere?** `sqlalchemy-libsql` 0.2.0 is sync-only as of 2026-05. `create_async_engine("sqlite+libsql://...")` raises `InvalidRequestError`. Going fully sync was the cheapest path to keep ORM models / alembic / schema unchanged while making Turso work.

---

## How to run locally

```bash
# Clone
git clone https://github.com/GKS711/InsightX.git
cd InsightX

# Python env (uv recommended)
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Env vars
cp .env.example .env
# Then fill in: GEMINI_API_KEY, SERPER_API_KEY, optionally YOUTUBE_API_KEY
# For local dev, leave DATABASE_URL empty (defaults to sqlite:///./insightx.db)

# Schema
alembic upgrade head

# Run
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Open <http://localhost:8000>. Workspace at `/workspace/`. API at `/api/*`.

**To use the workspace bridge locally** (landing analyze auto-saves):
```bash
export IX_ENABLE_V4_WORKSPACE_PERSIST=1
```
See [§ Bridge env flag](#bridge-env-flag) for why this is off by default.

---

## How to deploy

Full step-by-step in **[`docs/DEPLOY_HF.md`](docs/DEPLOY_HF.md)** (Turso DB → HF Space → secrets → push). Quick summary:

1. `turso db create insightx-demo --location nrt` → grab URL + token
2. <https://huggingface.co/new-space> → Docker SDK, CPU basic free, mit license
3. Set Space secrets: `DATABASE_URL`, `TURSO_AUTH_TOKEN`, `GEMINI_API_KEY`, `SERPER_API_KEY` (optional `YOUTUBE_API_KEY`)
4. `git clone https://huggingface.co/spaces/<user>/<space>` to /tmp, `cp` over the source files, `git push`
5. Watch logs; first build ~3min, subsequent ~30s

---

## Key files (the ones you'll actually open)

### Backend

| Path | What it does |
|---|---|
| `src/main.py` | FastAPI app; mounts v4 + v5 routers; serves static UI at `/`, legacy at `/legacy` |
| `src/db.py` | sync `create_engine` + Turso URL normalize + FK PRAGMA listener |
| `src/models.py` | 9-table v5 ORM schema (User/Workspace/Store/ReviewSource/ScrapeJob/Review/AnalysisRun/GeneratedAsset/Report); `passive_deletes=True` on cascades |
| `src/schemas.py` | Pydantic request/response shapes |
| `src/jobs.py` | threading.Thread bg workers + `progress_stream()` SSE generator + `_safe_commit_or_log` race-window protection |
| `src/api/routes.py` | v4 endpoints (POST /api/analyze, GET /api/v4/analyze-stream, etc) + `_persist_v4_analyze_to_workspace` bridge |
| `src/api/v5.py` | v5 endpoints (workspaces, stores, jobs, runs, reports, downloads) |
| `src/services/llm_service.py` | Gemini wrapper with `MODEL_CHAIN` multi-model fallback |
| `src/services/scraper_service.py` | Serper + YouTube dispatcher |
| `src/services/youtube_scraper.py` | Data API v3 + `youtube-comment-downloader` fallback |
| `src/services/reports.py` | PDF/DOCX generation via reportlab + python-docx |

### Frontend

| Path | What it does |
|---|---|
| `src/static/v2/index.html` | **Main UI**. Single-file Babel-standalone React. ~3500 lines JSX inside one `<script type="text/babel">`. Hero uses Codex img2 illustration. |
| `src/static/v2/bootstrap.js` | ES module bridge — exposes `core/` + `hooks/` as `window.IX` for Babel block to consume |
| `src/static/v2/core/*.js` | `adapters` (API I/O), `api`, `async`, `ids` |
| `src/static/v2/hooks/*.js` | `useAppReducer` (slice reducer), `useAnalyzeStream` (SSE client), `useLocalStorage` |
| `src/static/v2/workspace/index.html` | Sidecar workspace UI (mounted at `/workspace/`) — lists stores, drills into store detail |
| `src/static/v2/assets/hero-listening.png` | v6 Codex img2 hero (multi-source convergence illustration, LFS-tracked) |
| `src/static/index.html` | Legacy v3 UI mounted at `/legacy/` — kept for rollback / comparison |

### Infra

| Path | What it does |
|---|---|
| `Dockerfile` | single-stage py3.10-slim, port 7860, alembic-on-boot, HEALTHCHECK, non-root uid=1000 |
| `alembic/versions/578d92de7851_v5_initial_schema.py` | All-in-one schema migration |
| `alembic/env.py` | sync env config; reads DATABASE_URL via src.db; propagates `connect_args` for Turso auth |
| `requirements.txt` + `pyproject.toml` | deps; libsql pair `==`-pinned |
| `.dockerignore` | excludes .venv, .git, video/, *.bak, etc |
| `.gitignore` | adds CLAUDE.md, *.backup.*, video/, etc |
| `deploy/hf-space-README.md` | HF Space repo README template with YAML frontmatter |
| `docs/DEPLOY_HF.md` | full deploy walkthrough |

---

## Cookie session scoping (v6.1)

Every HTTP request goes through `SessionCookieMiddleware` (registered in `src/main.py` before any router). The middleware:

1. Reads `ix_session` cookie if present and well-formed (32-char lowercase hex).
2. Otherwise mints a fresh UUID4 hex sid and marks the request as new.
3. Stashes the sid on `request.state.ix_session_id`.
4. After the route returns, sets `Set-Cookie: ix_session=...; HttpOnly; Secure; SameSite=lax; Max-Age=31536000` on the outgoing response — works uniformly for JSON, `StreamingResponse` (SSE), `FileResponse`, static files.

The cookie IS the identity — no password / login / OAuth. Clearing cookies = losing your workspace (acceptable for an alpha demo; v6.2+ can add real auth if needed).

The v4→workspace bridge (`src/api/routes.py` `_persist_v4_analyze_to_workspace`) now always runs — every visitor gets their landing-page analyses persisted into THEIR OWN private workspace, scoped on the user row keyed off the cookie sid. The old `IX_ENABLE_V4_WORKSPACE_PERSIST` env flag is removed (it was the v6.0-alpha mitigation for the cross-tenant leak; cookie scoping is the proper fix).

For local development / TestClient over plain HTTP, set `IX_COOKIE_SECURE=false` so browsers/httpx don't filter the `Secure` cookie.

---

## Branch policy

> **唯一禁止**: 不要開 PR 把 `claude/v6-sync-refactor` 整批 merge 進 `main`.

(Same policy as v5 had per the now-archived `docs/V5_NOTES.md`. v6 alpha is on its own branch; release-readiness happens via cherry-pick of specific commits, not bulk PR.)

What you CAN do:
- `git push origin claude/v6-sync-refactor` (you've been doing this)
- commit + push on `main` directly
- cherry-pick v6 commits into `main` when going GA
- `Co-Authored-By: Claude` lines if you want (existing commits have them; not required going forward — user explicitly OKed dropping it)

---

## v6.1 punch list — all resolved

The 5 limitations flagged by Codex pre-v6.0-freeze (task `0d309dd01043`) are all fixed in v6.1.0-alpha. Locations + key invariants:

1. ✅ **Cookie session scoping** — `src/auth.py` `SessionCookieMiddleware` + `get_current_user` Depends. Anonymous UUID4 sid per browser. Each visitor maps to `anon-{sid}@insightx.local` User row, committed immediately on first request so the v4 bridge's separate `SessionLocal()` can see it (Codex round 2 fix).
2. ✅ **v5 by-id ownership scoping** — `src/api/v5.py` `_get_owned_workspace` / `_get_owned_store` / `_get_owned_job` / `_get_owned_run` / `_get_owned_report` helpers, used in all 14 by-id endpoints. Cross-tenant ID-guessing → 404 (not 403, to avoid existence leak).
3. ✅ **Store UniqueConstraint** — `src/models.py` `UniqueConstraint("workspace_id", "primary_url", name="uq_stores_workspace_primary_url")`. Migration `alembic/versions/ed45898ffc55_v6_1_store_unique_primary_url.py` uses `batch_alter_table` for SQLite compat. Bridge catches `IntegrityError` → reselects on same-URL race.
4. ✅ **Review external_id dedupe** — `src/api/routes.py` `_review_external_id(source_id, raw)` = `sha256(source_id|author|date|text).hexdigest()[:32]`. Each Review insert wrapped in `session.begin_nested()` SAVEPOINT so a single duplicate-review IntegrityError doesn't wipe the whole bridge transaction (Codex round 1 fix).
5. ✅ **AnalysisRun.model_id audit** — `src/services/llm_service.py` `threading.local()` `_llm_tls.last_used_model` tracks the actually-used model after MODEL_CHAIN fallback. `src/jobs.py` `run_analysis_bg` writes `run.model_id = LLMService.get_last_used_model()` post-call. The audit row reflects what really happened, not the default.

If you're picking this up for v6.2 work, the next-tier ideas are: real auth (passwordless email magic link?), multi-device sync (link multiple cookies to one logical account), account recovery (currently clearing cookies = losing workspace).

---

## How LLM fallback works

`src/services/llm_service.py` exports `MODEL_CHAIN`:

```python
MODEL_CHAIN = [
    "gemma-4-26b-a4b-it",   # primary — MoE Active 4B (fast)
    "gemma-4-31b-it",       # dense 31B fallback
    "gemini-2.5-flash",     # Google GA fallback
    "gemini-2.5-flash-lite",# last resort
]
```

`_generate()` iterates the chain. On `ServerError` (5xx), `RESOURCE_EXHAUSTED` 429, or transport error, falls through to the next model. `ClientError` 4xx non-429 (= our bug) raises immediately — no point trying alternatives.

`_generate_one_model()` is the inner per-model retry loop (max_attempts retries with backoff, shared `total_timeout_s` budget across attempts).

If you see `[gemma-4-26b-a4b-it exhausted (ServerError), falling back to gemma-4-31b-it]` in logs, that's normal during Gemini API spikes. Adjust `MODEL_CHAIN` order if you have a different preference.

---

## SSE / streaming model

Two SSE endpoints:

| Path | Purpose | Mechanism |
|---|---|---|
| `GET /api/v4/analyze-stream` | landing-page analyze stream (used by main UI) | threading.Thread producer + heartbeat thread + queue.Queue + threading.Event done flag |
| `GET /api/v5/jobs/{id}/stream` and `/runs/{id}/stream` | workspace job progress | `progress_stream()` generator in `jobs.py` — polls `queue.Queue` with `: ping\n\n` heartbeats every 5s |

Round-2 Codex review hardened both:
- consumer disconnect → finally block pops the queue from `_progress_queues` (no memory leak)
- producer terminal events (`succeeded` / `failed`) → identity-guarded pop so orphan queues from late pushes don't accumulate
- `idle_timeout_s` measures time-since-last-event, not stream lifetime — long-running but actively-emitting jobs don't get false-positive timeouts

The v4-stream worker thread checks `done_event.is_set()` between phases (before scrape, before LLM) so disconnects don't queue wasted work, although in-flight scraper/LLM calls can't be interrupted (Python threads aren't cancellable).

---

## How `_safe_commit_or_log` works

DELETE /api/v5/stores/{id} cascades through scrape_jobs / analysis_runs / their children. There's a narrow race: DELETE checks 409 (no active job) → user POST /scrape → background scrape commits → DELETE commits → cascade drops the just-inserted scrape_job → background scrape's NEXT commit hits a StaleDataError or IntegrityError.

`src/jobs.py` `_safe_commit_or_log()` catches **only** `(StaleDataError, IntegrityError)`, logs as "cascade-deleted by DELETE /stores", and returns False so the worker bails. Anything else (real DB outage, programmer bug) re-raises with `logger.exception`.

Combined with `passive_deletes=True` on all cascade relationships in `src/models.py`, this gives layered protection without losing data integrity. Codex round 3 verified.

---

## How to add a new analysis function

Existing 9 functions are in `src/services/llm_service.py` (analyze_content, generate_swot, generate_reply, generate_marketing, generate_root_cause_analysis, generate_weekly_plan, generate_training_script, generate_internal_email, chat). To add a 10th:

1. Add the method to `LLMService` — call `self._generate(prompt, json_mode=...)`
2. Add prompt template to `src/config/prompts.py`
3. Add endpoint to `src/api/routes.py` (POST /api/<name>)
4. Update `MODEL_CHAIN` and `_DEFAULT_TOTAL_BUDGET_S` if needed
5. Add the `ai_function` value to `AnalysisRun.ai_function` CHECK constraint via alembic migration if you also want v5 persistence
6. Frontend: extend `src/static/v2/core/adapters.js` to add the fetch wrapper + reducer slice

---

## Codex peer-review history this release

Eleven review rounds across four phases, all reaching APPROVE consensus:

| Round | Task ID | Focus |
|---|---|---|
| Sync refactor R1 | `bf037e60ed0d` | BLOCK — per-call LLM timeout, queue cleanup, SSE worker cancel |
| Sync refactor R2 | `372812acadcf` | APPROVE-WITH-NOTES — needed producer-pop + idle reset |
| Sync refactor R3 | `5c4363726196` | APPROVE — consensus |
| Deploy R1 | `f1fd2145e07e` | NEEDS FIXES — report regen fallback, build-essential bloat, HEALTHCHECK |
| Deploy R2 | `6dbd19a04ca3` | APPROVE-WITH-NOTES — initial recipe missing .dockerignore |
| Deploy R3 | `f2221cacf342` | APPROVE — clean |
| Full project R1 | `0d309dd01043` | BLOCK — multi-tenant privacy leak via bridge |
| Full project R2 | `263e6a5d30c3` | APPROVE-WITH-NOTES — deferred items now in CHANGELOG |
| v6.1 R1 | `7e98b9ab6b41` | NEEDS FIXES — 2 SERIOUS (SSE cookie, savepoint dedupe) + 1 MINOR (user race) |
| v6.1 R2 | `6c1f6a95a2da` | NEEDS FIXES — user row commit, APP_VERSION mismatch, race-retry None |
| v6.1 R3 | `b7976b616e07` | APPROVE — consensus on v6.1.0-alpha |

The full prompts + responses are documented inline in each commit message that addresses a Codex finding.

---

## v4-era invariants (still apply)

Carry-overs from v4 that are still load-bearing in v6 — don't break these without re-reviewing:

1. **frontend `timeoutMs` ≥ backend `total_timeout_s` + 5s buffer** (Codex P3.10). Per-endpoint table in `src/static/v2/core/adapters.js`. Otherwise frontend abort leaves backend burning quota.
2. **Service-layer failures `raise`, no fallback dict** (Codex P3.10). Mock fallback only lives at route layer behind `_fallback:true` flag. Service-level silent degradation makes the route think it succeeded and ships fake data to UI.
3. **Retry judgment is type-based** (`genai_errors.ServerError` / 429 / `httpx.NetworkError`). No string-substring matching on error messages.
4. **Prompt skeletons align with UI renderer** (Codex P3.11). v4 UI uses `<pre>` direct-print, NOT markdown. Prompts use 【】◆ ▸ structure — no `##` / `**`. If you re-introduce markdown render anywhere, also update prompts.
5. **Scraping is uncapped on backend; UI applies display cap** (Codex P3.12). `src/static/v2/index.html` ReviewsSection slices to 50 with caption explaining "本次分析了 N · 顯示 50 則樣本". LLM still sees everything.

These were established through 6 rounds of dual-AI consensus before v6 even started.

---

## Smoke test recipe

```bash
# Local — sets IX_COOKIE_SECURE=false so plain-HTTP TestClient cookies aren't filtered
DATABASE_URL='sqlite:///./test.db' alembic upgrade head
IX_COOKIE_SECURE=false DATABASE_URL='sqlite:///./test.db' python -c "
from fastapi.testclient import TestClient
from src.main import app
c = TestClient(app, base_url='http://testserver')
assert c.get('/api/meta').json()['appVersion'] == '6.1.0-alpha'
# First request mints a fresh anonymous session cookie
r = c.get('/api/v5/workspaces')
assert r.status_code == 200
assert 'ix_session' in c.cookies
# A fresh client gets its own isolated workspace
c2 = TestClient(app, base_url='http://testserver')
assert c2.get('/api/v5/workspaces').json() == []  # B sees 0
print('OK')
"

# Live HF Space
SPACE=https://Jordan711-insightx-demo.hf.space
curl -s $SPACE/api/meta | jq .appVersion       # → "6.1.0-alpha"
curl -s -I $SPACE/api/meta | grep -i set-cookie  # → ix_session=...; HttpOnly; Secure
```

For end-to-end with real LLM, paste a Google Maps URL into the live UI's "Google 評論" card and hit 開始分析.

---

## Test scripts (frozen)

| Path | What it does |
|---|---|
| `outputs/test_reducer.mjs` | 48-case regression for v4 reducer + adapter + SSE lifecycle. **Run before any reducer/adapter change**. |
| `validate_jsx.cjs` | `@babel/parser` validates the entire `src/static/v2/index.html` Babel block. **Run after any UI edit**. |

Both should still pass on v6.1.0-alpha HEAD. If they don't, something regressed.

---

## When you next pick this up

Start here:

1. Read `CHANGELOG.md` v6.1 + v6 entries to see what landed
2. Skim this file (you're reading it)
3. The v6.1 punch list is complete (cookie sessions + ownership + dedupe + audit). Next work is v6.2 territory — only pursue if there's a real user need:
   - Real auth (passwordless email magic link?) so users don't lose data when clearing cookies
   - Multi-device sync (link multiple cookies to one logical account)
   - Account recovery flow
   - Convert the alembic `*.bak-*` editor backups under `src/static/v2/` to a non-tracked dir (HF Space mirror still has them)
4. Hit the live demo URL to see current behavior
5. Run `git log --oneline -20` to see recent commits
6. If the Space is in error state, check `https://huggingface.co/spaces/Jordan711/insightx_demo/logs` for runtime traceback

The hardest things are already done (async→sync, Turso wire-up, multi-model fallback, HF Spaces deploy, multi-tenant safety, three rounds of Codex review consensus on v6.1). v6.1.0-alpha is the first version of InsightX that's actually safe to put in front of multiple visitors at once.

Good luck.
