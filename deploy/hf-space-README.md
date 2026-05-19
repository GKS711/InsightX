---
title: InsightX
emoji: 🔍
colorFrom: indigo
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI-powered Google Maps reviews + YouTube comments insight
---

# InsightX (Hugging Face Spaces demo)

Live demo of [InsightX v6.0.0-alpha](https://github.com/GKS711/InsightX) — turns Google Maps store reviews and YouTube video comments into AI-powered business insight reports.

## How it runs here

- **Backend**: FastAPI 0.109+ on Python 3.10 (sync stack, sqlalchemy-libsql 0.2)
- **DB**: Turso (libsql, serverless SQLite) — `DATABASE_URL` and `TURSO_AUTH_TOKEN` are set as Space secrets
- **LLM**: Google Gemini API — multi-model fallback chain `gemma-4-26b-a4b-it` → `gemma-4-31b-it` → `gemini-2.5-flash` → `gemini-2.5-flash-lite`
- **Scrapers**: Serper API (Google Maps) + YouTube Data API v3 / youtube-comment-downloader fallback

The container runs `alembic upgrade head` on every boot to ensure the v5 schema is materialized on the Turso DB. After that, uvicorn serves on port 7860 (mapped to the Space's public URL).

## Required Space secrets

| Secret | Required | Source |
|---|---|---|
| `DATABASE_URL` | yes | `libsql://<your-db>-<owner>.turso.io` from `turso db show <db-name>` |
| `TURSO_AUTH_TOKEN` | yes | `turso db tokens create <db-name>` |
| `GEMINI_API_KEY` | yes | https://aistudio.google.com/apikey |
| `SERPER_API_KEY` | yes (for Maps mode) | https://serper.dev/ |
| `YOUTUBE_API_KEY` | optional | Google Cloud Console → YouTube Data API v3 |

## Links

- Source: <https://github.com/GKS711/InsightX>
- Changelog: see [CHANGELOG.md](https://github.com/GKS711/InsightX/blob/main/CHANGELOG.md)
- Deployment guide: [docs/DEPLOY_HF.md](https://github.com/GKS711/InsightX/blob/main/docs/DEPLOY_HF.md)
