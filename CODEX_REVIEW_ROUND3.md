# Codex Round 3 Review — InsightX v5 Store Deletion

**Date**: 2026-05-19 ~02:50 GMT+8
**Task ID**: `703ed1911b8d` (codex-bridge)
**Branch**: `claude/distracted-roentgen-e83b40`
**Commits**: `5a9f756` (DELETE + db.py FK PRAGMA + jobs.py safe-commit) / `b604568` (sidebar UX) / `b197160` (DangerZone UI)
**Diff source**: `/tmp/insightx_v5_delete.diff` (369 lines, 17KB)
**Round positioning**: Round 1+2 already done; this is final pass for residual issues.

---

## Deploy Verdict: **GO**

No BLOCKER / HIGH findings.

---

## MED Findings (4)

### M1 — `src/jobs.py:135` scrape `running` commit unprotected
- `_safe_commit_or_log` only wraps **post-IO** commits in `run_scrape_job_bg`
- Race window: DELETE guard passes → new scrape job created → worker picks up → initial `running` state commit (line 135) — parent store could be cascade-deleted by then → `StaleDataError`
- **Fix**: wrap line 135 with `_safe_commit_or_log` too; on failure return early without push event

### M2 — `src/jobs.py:221` analysis `running` commit same race hole
- Identical window in `run_analysis_bg`
- **Fix**: line 221 → `_safe_commit_or_log(session, "analysis", run_id)`

### M3 — `src/models.py:121` ORM cascade missing `passive_deletes=True`
- Relationships using ORM cascade: `Store.sources/analysis_runs/reports`, `ReviewSource.reviews/scrape_jobs`, `AnalysisRun.generated_assets`
- On Postgres with FK cascade: SQLAlchemy loads + deletes children row-by-row instead of letting DB do it → slow on large stores
- **Fix**: add `passive_deletes=True` to relationships OR switch to bulk delete
- Alpha not blocking; **prod-volume caveat**

### M4 — `src/jobs.py:47` broad `except` swallows real bugs
- Current behavior: catches anything, logs as "likely cascade-deleted", does **not** push failed event
- Real bugs hidden: duplicate, constraint violation, DB outage → job stuck in `running` forever
- **Fix**: catch only `StaleDataError` or `IntegrityError where parent confirmed gone`; everything else re-raise or `logger.exception`
- Observability degraded if not fixed

## LOW Findings (2)

### L1 — `src/static/v2/workspace/index.html:716` raw JSON error display
- 409 currently surfaces raw `{"detail":"..."}` to user
- **Fix**: parse JSON, display `detail` field (or Chinese-translated)

### L2 — `src/static/v2/workspace/index.html:720` unconditional navigate
- After successful DELETE, user always pulled back to `#/` even if they navigated away to `#/reports`
- **Fix**: record originating route before DELETE; only navigate if still on same store route

---

## Verified OK (not findings)
- SQLite async `engine.sync_engine` connect listener usage correct
- Schema/migration FK cascade/SET NULL paths verified across `review_sources` / `reviews` / `scrape_jobs` / `analysis_runs` / `generated_assets` / `reports`

---

## Recommended Next Steps

1. **Before next deploy** (~30-60 min work, all in `src/jobs.py` + `src/models.py`):
   - Fix M1 + M2 (wrap `running` commits with `_safe_commit_or_log`)
   - Fix M4 (narrow exception scope)
   - Fix M3 (add `passive_deletes=True`)
2. **LOW issues**: batch with next UI iteration
3. **Re-test** after fixes:
   - DELETE while scrape just-started (race window M1)
   - DELETE while analysis just-started (race window M2)
   - DELETE large store, measure latency (M3 effect)
