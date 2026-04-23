<div align="center">

# 🔍 InsightX

**Turn customer reviews — Google Maps stores or YouTube videos — into AI-powered business strategy**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react)](https://reactjs.org/)
[![Version](https://img.shields.io/badge/version-4.0.0-orange.svg)](#changelog)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Language:** 🇺🇸 English | [🇹🇼 繁體中文](README_zh-TW.md)

</div>

---

## What is InsightX?

InsightX takes a **Google Maps store URL** or a **YouTube video URL**, scrapes the customer reviews / viewer comments via official APIs, and uses [Google Gemini](https://ai.google.dev/) to generate a full editorial-style report: sentiment analysis, theme breakdown, original-quote evidence, SWOT, reply drafts, weekly action plan, training scripts, internal email — and an interactive AI consultant.

**Two operating modes**, sharing the same nine downstream AI features:

| Mode | Source | Scraper | Best for |
|------|--------|---------|----------|
| 🏪 **Store Reviews** | Google Maps URL | [Serper API](https://serper.dev/) (`/maps` + `/reviews`) | Restaurants, retail, service shops |
| 🎬 **YouTube Comments** | YouTube video URL | [YouTube Data API v3](https://developers.google.com/youtube/v3) (+ `youtube-comment-downloader` fallback) | Creators, channel growth, content tuning |

**Zero browser, zero headless Chrome** — everything runs through HTTP APIs. No Playwright, no Selenium.

> Screenshots are being refreshed for v4. The current UI is a single-page React 18 app — fire it up locally to see it (instructions below).

---

## Quick Start (3 steps)

### 1. Clone & configure

```bash
git clone https://github.com/GKS711/InsightX.git
cd InsightX
cp .env.example .env
```

Edit `.env` — minimum required:

```
GEMINI_API_KEY=your_key_here          # https://aistudio.google.com/app/apikey
SERPER_API_KEY=your_key_here          # Required for Google Maps mode (https://serper.dev)
YOUTUBE_API_KEY=your_key_here         # Recommended for YouTube mode (https://console.cloud.google.com → YouTube Data API v3)
```

If `YOUTUBE_API_KEY` is missing, YouTube mode auto-falls back to a free library (no key, no quota).

### 2. Install

```bash
# Python (pick one)
pip install -r requirements.txt
# or: uv sync

# Frontend (only if you want to rebuild assets — pre-built bundle ships in src/static/v2/)
npm install && npm run build
```

### 3. Run

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**, paste a Google Maps URL **or** a YouTube video URL, click **開始分析 / Analyze** — done.

> The v4 React UI is mounted at `/`. The previous v3 HTML build is kept at `/legacy` as a fallback (read-only).

---

## What you get

After analysis, the dashboard renders an editorial-style report (think *The Economist* on a Sunday):

| Section | What it shows |
|---------|---------------|
| §01 Hero | Store / video name, address (or category), rating / like-count, sentiment donut |
| §02 Themes | Top positive & negative themes with quotes |
| §03 SWOT | Strategic posture (Strengths / Weaknesses / Opportunities / Threats) |
| §04 Original Material | Up to 50 raw reviews / comments with sentiment color-coding (or 「♥ N」 likes for YouTube) |
| §05 Weekly Action Plan | Concrete 7-day to-do list per persona (store owner / creator) |
| §06 Marketing | IG/FB-style copy aligned with your strengths |
| §07 Tools | Per-topic reply drafts, root-cause deep-dives, training scripts, internal staff emails |
| §08 AI Consultant | Chat with an AI advisor that knows your data |

**Bonus: Manager Decision Simulator** — interactive game with 10 real-world management scenarios (separate React mini-app).

---

## How it works

```
   Google Maps URL  ─────┐
                         ├─▶ Auto-detect platform ─▶ Scraper ─▶ Gemini analyze ─▶ SSE stream ─▶ Dashboard
   YouTube video URL ────┘                              │
                                                        │
                                              ┌─────────┴─────────┐
                                              │ Serper /reviews   │ (Google Maps)
                                              │ YouTube Data v3   │ (with library fallback)
                                              └───────────────────┘

   Once analysis is "ready", 9 downstream LLM endpoints fire on-demand
   (SWOT, reply, marketing, weekly-plan, root-cause, training, internal-email, chat)
```

The whole pipeline is **zero-browser** — no Chrome, no Playwright, just HTTP.

---

## API Reference

All endpoints are listed at `http://localhost:8000/docs` (Swagger UI). Every endpoint accepts an optional `platform: "google" | "youtube"` field; defaults to `"google"`.

### Bootstrap & Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/meta` | App metadata (version, available platforms, feature flags) |
| `GET` | `/api/v4/analyze-stream?url=...` | **Recommended.** Structured SSE stream with `progress` / `result` / `failed` events |
| `GET` | `/api/analyze-stream?url=...` | Legacy SSE (kept for backwards compatibility) |
| `POST` | `/api/analyze` | Non-SSE fallback for the main analyze flow |

### LLM Feature Endpoints (9)

All POST, all platform-aware, all return JSON:

| Endpoint | Output |
|----------|--------|
| `/api/swot` | SWOT 4-quadrant analysis |
| `/api/reply` | Reply draft for a specific complaint |
| `/api/analyze-issue` | Root-cause deep dive |
| `/api/marketing` | Social-media copy |
| `/api/weekly-plan` | 7-day action plan |
| `/api/training-script` | Staff / editor coaching script |
| `/api/internal-email` | Internal team email |
| `/api/chat` | AI consultant turn |
| `/api/debug-scrape` | Scraper output only (no LLM) — for diagnostics |

---

## Architecture

```
InsightX/
├── src/
│   ├── main.py                  # FastAPI entry; mounts /, /legacy, static
│   ├── api/routes.py            # All HTTP + SSE endpoints
│   ├── services/
│   │   ├── scraper_service.py   # Serper /maps + /reviews + URL dispatcher
│   │   ├── youtube_scraper.py   # YouTube Data API v3 + downloader fallback
│   │   ├── llm_service.py       # 9 Gemini calls (platform-aware persona)
│   │   └── canonicalizer.py     # yt_role canonicalize + metadata wrapper
│   ├── config/
│   │   ├── prompts.py           # AI prompt templates
│   │   └── mock_responses.py    # Demo fallback data (legacy /legacy use only)
│   └── static/
│       ├── v2/                  # ★ v4.0.0 main UI (current) — React 18 + Babel single-file
│       │   ├── index.html       # 3550-line single-file SPA
│       │   ├── bootstrap.js     # ES module → window.IX bridge
│       │   ├── core/            # adapters / api / async / ids
│       │   └── hooks/           # useAppReducer / useAnalyzeStream / useLocalStorage
│       └── index.html           # Legacy v3 HTML (mounted at /legacy)
├── docs/
│   ├── v4-api-contract.md       # API contract spec
│   ├── v4-sse-events.md         # SSE event types
│   ├── v4-view-model.md         # Frontend view-model spec
│   └── v4-smoke-test.md         # Manual E2E checklist
├── outputs/test_reducer.mjs     # 48-case reducer + adapter regression test
├── validate_jsx.cjs             # @babel/parser JSX validator
├── pyproject.toml               # Python deps (uv)
├── requirements.txt             # Python deps (pip, for Docker)
├── package.json                 # Frontend deps
├── Dockerfile / compose.yaml    # Docker deployment
└── .env.example                 # Environment template
```

### Frontend (v4)

The v4 UI is a **single-file React 18 SPA** at `src/static/v2/index.html`, compiled in-browser with `@babel/standalone` — no build step required to ship. Core logic lives in ES modules under `core/` + `hooks/` and is bridged into `window.IX` by `bootstrap.js`.

### Locked invariants

Four rules codified across backend + frontend that any future change must preserve. Concise version:

1. **Frontend `timeoutMs` ≥ Backend `total_timeout_s` + 5s buffer**
2. **Service layer raises on failure** (no silent fallback dict)
3. **Retry by exception type**, never string-match
4. **Prompt skeletons match the `<pre>` renderer** (no markdown — use `【】 ◆　▸` plain-text structure)

Full rationale + historical bug fixes that locked these: [`HANDOFF.md`](HANDOFF.md). API contract / SSE event shapes / view-model: [`docs/v4-*.md`](docs/).

---

## Two platforms — schema notes

YouTube borrows the store-mode JSON schema (so the 9 downstream LLM endpoints stay platform-agnostic), so a few fields **mean different things** depending on `platform`:

| Field | Google mode | YouTube mode |
|-------|-------------|--------------|
| `raw.store_name` | Store name | Video title |
| `raw.review_count` | Reviews scraped (with text) | Comments scraped |
| `raw.rating` | 1–5 star rating | Video like count |
| `raw.rating_count` | Total reviews on Google Maps | View count |
| `raw.address` / `category` | Real values | Empty / "YouTube 影片" |
| `raw.reviews_structured[].rating` | 1–5 star | Comment like count |

The frontend `HeroStat` / `Masthead` / `TopNav` / `ReviewCard` are **platform-aware** and render the correct labels (e.g. `7,381 讚` instead of `7,381 ★`) so users never see a like count masquerading as a five-star rating.

---

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `GEMINI_API_KEY` | **Yes** | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — used for all 10 LLM calls |
| `SERPER_API_KEY` | Store mode | [serper.dev](https://serper.dev/) — Google Maps `/maps` + `/reviews` |
| `YOUTUBE_API_KEY` | YouTube mode (recommended) | [console.cloud.google.com](https://console.cloud.google.com) → enable **YouTube Data API v3** → create API key. Free quota 10,000 units/day. Without it, the library fallback runs (no key, no quota cap, but no `like_count` / `view_count`). |
| `YOUTUBE_FALLBACK_MODE` | No | `auto` (default) / `force-ytdlp` (force library) / `off` (disable fallback) |
| `ENVIRONMENT` | No | `development` or `production` |

---

## Testing & Validation

Three commands cover all automated checks (no API keys needed):

```bash
# Frontend JSX integrity
node validate_jsx.cjs

# Reducer + adapter regression
node outputs/test_reducer.mjs

# Python syntax
python3 -m py_compile src/services/*.py src/api/*.py src/main.py
```

Manual E2E (requires real API keys + uvicorn): see [`docs/v4-smoke-test.md`](docs/v4-smoke-test.md).

---

## Development

```bash
# Backend with hot reload
python -m uvicorn src.main:app --reload --port 8000

# (Optional) Frontend dev with Vite HMR — only if you're modifying React component files
npm run dev
```

The current v4 UI is **single-file** + Babel standalone, so most front-end edits to `src/static/v2/index.html` go live with just a browser hard-reload. No webpack / Vite rebuild needed unless you touch `core/` or `hooks/` ES modules.

---

## Docker

```bash
cp .env.example .env
# Edit .env with your API keys
docker compose up -d
# → http://localhost:8080
```

---

## Changelog

### v4.0.0 (2026-04-23)

UI migrated to a single-file React 18 + `@babel/standalone` SPA at `src/static/v2/`. Added structured `/api/v4/analyze-stream` SSE endpoint, 9 platform-aware LLM feature endpoints, slice reducer with `requestId` stale-discard, four locked invariants spanning backend+frontend, and a 48-case regression test for the reducer/adapter contract. Old v3 HTML kept at `/legacy`.

### v3.0.0 (2026-04-21) — Drop Shopee mode

After 8 evaluation routes, Shopee TW WAF (encrypted `AF-AC-ENC-DAT` header) was confirmed unsolvable under the four constraints **free + customer-hosted + no-human-verification + 20+ products/day**. Codebase reduced from 3 modes back to 2 (Google Maps + YouTube). See [`docs/archive/shopee_evaluation_2026-04-21.md`](docs/archive/shopee_evaluation_2026-04-21.md) for the complete eight-route analysis.

### v2.0.0 — Add YouTube channel mode

Dual-path comment scraper: official YouTube Data API v3 (with quota) + `youtube-comment-downloader` library fallback (no key required).

### v1.x — Initial Google Maps analyzer

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

[Google Gemini](https://ai.google.dev/) · [Serper API](https://serper.dev/) · [YouTube Data API v3](https://developers.google.com/youtube/v3) · [youtube-comment-downloader](https://pypi.org/project/youtube-comment-downloader/) · [FastAPI](https://fastapi.tiangolo.com/) · [React](https://react.dev/) · [@babel/standalone](https://babeljs.io/docs/babel-standalone)
