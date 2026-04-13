<div align="center">

# 🔍 InsightX

**Turn Google Maps Reviews into Business Strategy — Powered by AI**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Language:** 🇺🇸 English | [🇹🇼 繁體中文](README_zh-TW.md)

</div>

---

## What is InsightX?

InsightX takes a Google Maps store URL, scrapes all customer reviews via [Serper API](https://serper.dev/), and uses [Google Gemini](https://ai.google.dev/) to generate actionable insights: sentiment analysis, SWOT breakdown, reply drafts, marketing copy, training scripts, and more.

No browser or headless Chrome needed — everything runs through APIs.

![Hero Section](docs/screenshots/hero-section.png)

---

## Getting Started (3 steps)

### 1. Clone & configure

```bash
git clone https://github.com/yourusername/InsightX.git
cd InsightX
cp .env.example .env
```

Edit `.env` and add your **Gemini API Key** (the Serper key is pre-filled for demo use):

```
GEMINI_API_KEY=your_key_here        # ← Get from https://aistudio.google.com/app/apikey
SERPER_API_KEY=d270c73...           # ← Already included, ready to use
```

### 2. Install dependencies

```bash
# Python (pick one)
pip install -r requirements.txt            # pip
# or: uv sync                              # uv (if you have it)

# Frontend
npm install && npm run build
```

### 3. Run

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**, paste a Google Maps URL, and go.

---

## Docker (alternative)

```bash
cp .env.example .env
# Edit .env with your GEMINI_API_KEY
docker compose up -d
# → http://localhost:8080
```

---

## Features

**Core Analysis** — Paste a Google Maps URL → get categorized positive/negative themes with percentages

**Manager Toolkit** (all generated from your review data):

| Tool | What it does |
|------|-------------|
| SWOT Analysis | Strengths, Weaknesses, Opportunities, Threats |
| Reply Drafts | Professional responses to negative reviews |
| Marketing Copy | Social media posts highlighting your strengths |
| Root Cause Analysis | Deep dive into recurring complaints |
| Weekly Action Plan | Concrete steps for your team |
| Training Script | Employee coaching material |
| Internal Email | Staff announcements about improvement initiatives |
| AI Consultant | Chat with an AI advisor about your results |

**Bonus: Manager Decision Simulator** — An interactive game with 10 real-world scenarios to train management skills.

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/game-start.png" alt="Game Start"/></td>
    <td width="50%"><img src="docs/screenshots/game-question.png" alt="Game Question"/></td>
  </tr>
</table>

---

## How It Works

```
Google Maps URL
      │
      ▼
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Serper API      │ ──▶ │  Gemini AI   │ ──▶ │  Dashboard +     │
│  (scrape reviews │     │  (analyze    │     │  Manager Tools   │
│   with paging)   │     │   sentiment) │     │                  │
└─────────────────┘     └──────────────┘     └──────────────────┘
```

No browser, no Playwright, no Selenium — just HTTP API calls.

---

## API Endpoints

All endpoints are available at `http://localhost:8000/docs` (Swagger UI).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze` | Scrape + analyze (main endpoint) |
| `GET` | `/api/analyze-stream` | SSE streaming version |
| `POST` | `/api/swot` | SWOT analysis |
| `POST` | `/api/reply` | Generate review reply |
| `POST` | `/api/marketing` | Marketing content |
| `POST` | `/api/analyze-issue` | Root cause analysis |
| `POST` | `/api/weekly-plan` | Weekly action plan |
| `POST` | `/api/training-script` | Training script |
| `POST` | `/api/internal-email` | Internal announcement |
| `POST` | `/api/chat` | AI consultant chat |

---

## Project Structure

```
InsightX/
├── src/
│   ├── main.py                  # FastAPI entry point
│   ├── api/routes.py            # All API endpoints
│   ├── services/
│   │   ├── scraper_service.py   # Serper API scraper (zero browser)
│   │   └── llm_service.py       # Gemini AI integration
│   ├── config/
│   │   ├── prompts.py           # AI prompt templates
│   │   └── mock_responses.py    # Demo fallback data
│   └── static/                  # React frontend
├── dev/                         # Test & debug scripts (optional)
├── public/pictures/             # Game assets
├── docs/screenshots/            # README images
├── requirements.txt             # Python dependencies (pip)
├── pyproject.toml               # Python dependencies (uv)
├── package.json                 # Node.js dependencies
├── Dockerfile / compose.yaml    # Docker deployment
└── .env.example                 # Environment template
```

---

## Development

```bash
# Backend with hot reload (Terminal 1)
python -m uvicorn src.main:app --reload --port 8000

# Frontend with HMR (Terminal 2)
npm run dev
# → http://localhost:5173 (proxies API to port 8000)
```

**Diagnostic tool:**
```bash
python dev/test_backend.py    # Check API keys & connectivity
```

---

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `GEMINI_API_KEY` | **Yes** | [Get one here](https://aistudio.google.com/app/apikey) |
| `SERPER_API_KEY` | **Yes** | Demo key included in `.env.example`. [Get your own](https://serper.dev/) for production |
| `ENVIRONMENT` | No | `development` or `production` |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

[Google Gemini](https://ai.google.dev/) · [Serper API](https://serper.dev/) · [FastAPI](https://fastapi.tiangolo.com/) · [React](https://react.dev/) · [Vite](https://vitejs.dev/) · [Tailwind CSS](https://tailwindcss.com/)

</div>
