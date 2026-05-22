<div align="center">

# 🔍 InsightX V2

**An AI customer-insight platform for managers — one URL, one full strategy report**

[![Live demo](https://img.shields.io/badge/live--demo-Jordan711--insightx__demo.hf.space-FF9D00.svg)](https://Jordan711-insightx-demo.hf.space)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Language:** 🇺🇸 English | [🇹🇼 繁體中文](README_zh-TW.md)

</div>

---

## What is InsightX?

Paste a **Google Maps store URL** or a **YouTube video URL**. Within 60 seconds, you get a full editorial-style report: sentiment summary, themes, SWOT, reply drafts, weekly action plan, marketing copy, training scripts, and an AI consultant who has read all of your reviews. Plus an interactive decision simulator that lets new managers practice on real customer complaints.

🌐 **Try it now**: <https://Jordan711-insightx-demo.hf.space>

---

## Why I built this

Customers leave reviews every day on Google, YouTube, and social media — but those reviews rarely turn into decisions.

- **Too scattered** — Reviews are spread across Google Maps, YouTube, IG, LINE. Nobody has time to read everything.
- **Too many** — 50 reviews is a burden, 500 just gets ignored. You see "lots of people say it's delicious," but miss "the AC is too cold, customers don't want to stay."
- **Pressure when responding** — A negative review goes live, the manager gets emotional, the reply is either too harsh or too soft, and the chance to recover the customer is gone.
- **No practice ground for new managers** — First-time managers learn at the cost of real customers.

InsightX tries to solve all four in one afternoon.

---

## The solution

Tie "read reviews → think strategy → write reply → practice" into one pipeline:

- **Cross-platform scraping, no browser needed** — Google Maps via Serper API, YouTube via the official Data API. Fast, reliable, no anti-bot blocks.
- **9 AI features share one dataset** — Sentiment, SWOT, reply drafts, marketing copy, root-cause analysis, weekly plan, training scripts, internal email, AI consultant. The persona shifts by platform (restaurant / retail / YouTuber).
- **Multi-store workspace** — Each user gets their own workspace with multiple stores and full history. Go back to last month's analysis any time.
- **Decision simulator for managers** — Drop real negative reviews into a game. The AI plays your virtual mentor and grades your response in real time.

---

## The 9 AI features

| # | Feature | What it does |
|---|---|---|
| 01 | Sentiment Analysis | Positive / negative breakdown + theme distribution |
| 02 | SWOT | Auto-generated strategic matrix |
| 03 | Reply Drafts | One draft per negative review |
| 04 | Marketing Copy | Store campaigns or video promotion |
| 05 | Root Cause Analysis | Find the real pain points |
| 06 | Weekly Action Plan | Concrete to-dos for the next 7 days |
| 07 | Training Scripts | Staff / editor training material |
| 08 | Internal Email | Store / team weekly report |
| 09 | AI Consultant | Always-available virtual advisor |

---

## The decision simulator

The most stressful part of a new manager's first weeks: handling complaints. InsightX has a built-in game where you practice on **your own real negative reviews**:

1. **AI generates the scenario** — Turns a real complaint into a situational question.
2. **You pick a response** — Choose from multiple strategies you'd actually use.
3. **AI gives feedback** — Scores your emotional intelligence and explains what would happen.

The tuition fee — without using real customers.

---

## See it in action

### Landing — pick your source
![Landing](docs/screenshots/v4/01-landing.png)

### Two platforms, one button
![Platforms](docs/screenshots/v4/02-platforms.png)

### Real-time progress (no fake spinner)
![Analyzing](docs/screenshots/v4/03-analyzing.png)

### Dashboard hero — full picture at a glance
![Hero](docs/screenshots/v4/04-hero.png)

### What customers really talk about
![Themes](docs/screenshots/v4/05-themes.png)

### SWOT — evidence-backed
![SWOT](docs/screenshots/v4/06-swot.png)

### Original reviews, never lost
![Reviews](docs/screenshots/v4/07-reviews.png)

### Toolbox — actionable this week
![Weekly Plan](docs/screenshots/v4/08-week-plan.png)

### Reply drafts — per complaint, never generic
![Replies](docs/screenshots/v4/09-replies.png)

### AI consultant — chat with someone who read everything
![AI Advisor](docs/screenshots/v4/10-ai-advisor.png)

---

## 3 design choices (and why)

### Multi-user safe by default

The first version had one shared account — anyone could see everyone else's data. Now every visitor gets their own identity (kept in a cookie), and all data is bound to it. No signup, no password, but each user's workspace is fully isolated.

### Doesn't crash when the AI hiccups

Free-tier Gemini chokes at midnight. I built an automatic model-switching chain: use the fast model first, fall back to the bigger one, then Google's flagship, finally the lite model as a safety net. Same request, all the fallbacks happen invisibly.

### Dual-AI code review

When I make a non-trivial change, I have Codex (another AI assistant) review my code. One AI writes, the other looks for bugs. Catches things I'd miss on my own — basically a free reviewer.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · Python 3.10+ |
| Database | Turso · SQLite (libsql) |
| AI | Google Gemini (multi-model fallback chain) |
| Scraping | Serper API + YouTube Data API v3 |
| Frontend | React 18 + Tailwind CSS |
| Deploy | Docker on Hugging Face Spaces (free tier) |

---

## Quick start

**Easiest** — just open the [live demo](https://Jordan711-insightx-demo.hf.space). No install, no signup.

**Run locally:**

```bash
git clone https://github.com/GKS711/InsightX.git
cd InsightX

# Environment
cp .env.example .env
# Fill in GEMINI_API_KEY, SERPER_API_KEY (YOUTUBE_API_KEY optional)

# Dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# DB schema
alembic upgrade head

# Run
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Open <http://localhost:8000>.

**Self-host on Hugging Face Spaces + Turso** — see [`docs/DEPLOY_HF.md`](docs/DEPLOY_HF.md).

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

[Google Gemini](https://ai.google.dev/) · [Serper API](https://serper.dev/) · [YouTube Data API v3](https://developers.google.com/youtube/v3) · [FastAPI](https://fastapi.tiangolo.com/) · [SQLAlchemy](https://www.sqlalchemy.org/) · [Turso](https://turso.tech/) · [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces) · [React](https://react.dev/)
