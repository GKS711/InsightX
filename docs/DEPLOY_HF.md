# Deploy InsightX v6 to Hugging Face Spaces + Turso

> Audience: 自己（你部署）和未來接手的人。一次性 setup ~30 分鐘，之後 push 即部署。

This walks you through deploying InsightX v6.0.0-alpha as a **free** live demo using:

- **Hugging Face Spaces (Free, Docker SDK)** — hosting (16GB RAM, 2 vCPU, no request timeout, 48h sleep after inactivity)
- **Turso (Starter Free)** — serverless SQLite DB (500 DB, 5GB total, 1B row reads/mo)
- **Google Gemini Free Tier** — LLM (10 RPM / 1500 RPD on `gemma-4-26b-a4b-it`, the v6 primary model; multi-model fallback chain auto-rotates to `gemma-4-31b-it` → `gemini-2.5-flash` → `gemini-2.5-flash-lite` on 5xx/quota errors)
- **Serper Free Tier** — Google Maps scraping (2500 free credits one-time + 100 free queries one-time on signup; ~50 queries/day budget)

Total cost: **$0/month** as long as you stay under free tier limits.

---

## Prerequisites

```bash
# macOS / Linux
brew install turso huggingface-cli  # or use the install scripts on each site
huggingface-cli login                # https://huggingface.co/settings/tokens (write scope)
turso auth login                     # https://turso.tech (Google sign-in)
```

You also need accounts on:
- https://aistudio.google.com (for `GEMINI_API_KEY`)
- https://serper.dev (for `SERPER_API_KEY`)
- (Optional) Google Cloud Console with YouTube Data API v3 enabled for `YOUTUBE_API_KEY` — without it the YouTube path falls back to `youtube-comment-downloader` (unlimited but slower)

---

## Step 1 · Provision the Turso DB

```bash
# Create a fresh DB for the demo (keep it separate from any kitjob/etc DBs)
turso db create insightx-demo --location nrt  # nrt = Tokyo; pick closest to your users

# Get the libsql URL — use this as DATABASE_URL
turso db show insightx-demo --url
# Expected: libsql://insightx-demo-<your-org>.turso.io

# Mint an auth token (long-lived; rotate if leaked)
turso db tokens create insightx-demo
# Expected: eyJhbGc...long-jwt-blob...
```

Copy both values somewhere safe — you'll paste them into HF Space secrets in Step 3.

**Don't put the token in `DATABASE_URL`**. The `src/db.py` normalizer lifts `TURSO_AUTH_TOKEN` env into `connect_args` so it doesn't get logged in error messages.

---

## Step 2 · Create the Hugging Face Space

1. Go to <https://huggingface.co/new-space>
2. Owner: your account
3. Space name: e.g. `insightx-demo`
4. License: **mit** (lowercase — HF 接受的是 SPDX identifier；大寫 "MIT" 會被擋下，error: "The license you specified does not exist")
5. SDK: **Docker** (NOT Streamlit/Gradio/Static)
6. Hardware: **CPU basic (free)** — 16GB RAM, 2 vCPU is enough for the alpha
7. Visibility: Public
8. Click **Create Space**

The Space starts empty. Next step uploads code.

---

## Step 3 · Set secrets

In the Space settings → **Variables and secrets**:

| Name | Value source |
|---|---|
| `DATABASE_URL` | from Step 1 `turso db show ... --url` (the `libsql://` URL) |
| `TURSO_AUTH_TOKEN` | from Step 1 `turso db tokens create ...` |
| `GEMINI_API_KEY` | from <https://aistudio.google.com/apikey> |
| `SERPER_API_KEY` | from <https://serper.dev/api-key> |
| `YOUTUBE_API_KEY` | (optional) Google Cloud Console |
| `IX_ENABLE_V4_WORKSPACE_PERSIST` | **leave UNSET** on public demo (see warning below) |

Mark each provided key as **Secret** (not Variable) so they're masked in logs. `YOUTUBE_API_KEY` is optional — omit it entirely if you don't have one (the YouTube path will fall back to `youtube-comment-downloader` which needs no API key).

> ⚠️ **`IX_ENABLE_V4_WORKSPACE_PERSIST` privacy gate** — When set to `1`, every landing-page analyze gets written to the v5 Turso schema and shows up under `/workspace/`. **Until cookie-based anonymous session scoping ships in v6.1, all visitors share the same `dev@insightx.local` user, so visitor A can see visitor B's analyzed URLs / reviews / reports.** Keep this var unset (or `0`) on any public demo. Self-hosted single-user setups can set it to `1`.

---

## Step 4 · Push the code

You have two options:

### Option A — Direct push (cleanest)

```bash
# Clone the empty HF Space as a sibling repo
cd /tmp
git clone https://huggingface.co/spaces/<your-username>/insightx-demo
cd insightx-demo

# Copy needed files from your InsightX repo
INSIGHTX=/Users/gankaisheng/VScode/Claude實作/InsightX
cp $INSIGHTX/Dockerfile .
cp $INSIGHTX/.dockerignore .
cp $INSIGHTX/requirements.txt .
cp $INSIGHTX/alembic.ini .
cp -r $INSIGHTX/src .
cp -r $INSIGHTX/alembic .
cp $INSIGHTX/deploy/hf-space-README.md README.md

# Push
git add .
git commit -m "Initial deploy: InsightX v6.0.0-alpha"
git push origin main
```

### Option B — Connect Space to GitHub (auto-sync)

In Space settings → **Repository** → connect to GitHub repo `GKS711/InsightX` and pick a branch. Every push to that branch triggers a Space rebuild.

**Caveat**: HF Space's README.md must be the one at the repo root with the frontmatter. Currently `deploy/hf-space-README.md` is separate so the GitHub repo's main README stays clean. If you want auto-sync, either (i) merge the frontmatter into the main `README.md` (ugly on GitHub) or (ii) maintain a dedicated branch like `hf-space-main` that has the modified README.

For v6.0.0-alpha I'd recommend **Option A** — fewer moving parts.

---

## Step 5 · Watch the build

In the Space "Logs" tab you should see:

```
===== Build =====
#1 [internal] load build definition from Dockerfile
...
#10 RUN pip install --no-cache-dir -r requirements.txt
... 90s ...

===== Container =====
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, ...
INFO  [alembic.runtime.migration] Running upgrade 0001_initial -> 0002_..., ...
INFO  Started server process [1]
INFO  Application startup complete.
INFO  Uvicorn running on http://0.0.0.0:7860
```

First boot: ~3-5 minutes (image build + migration). Subsequent boots: ~30s (cached image, migration is no-op).

---

## Step 6 · Smoke test the live URL

The Space URL is `https://<username>-insightx-demo.hf.space`. Test:

```bash
SPACE=https://<your-username>-insightx-demo.hf.space

# Metadata
curl -s $SPACE/api/meta | jq
# Expected: {"appVersion":"6.0.0-alpha", ...}

# Create a workspace
curl -s -X POST $SPACE/api/v5/workspaces \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo"}'
# Expected: {"id":1,"name":"demo",...}

# Open the UI
open $SPACE
```

UI loads at root → `src/static/v2/index.html` (Babel-standalone React).

---

## Updating the deployment

After making local changes to InsightX, redeploy with:

```bash
# Re-run the cp commands from Step 4 Option A
cd /tmp/insightx-demo
INSIGHTX=/Users/gankaisheng/VScode/Claude實作/InsightX
cp $INSIGHTX/Dockerfile .
cp $INSIGHTX/requirements.txt .
cp $INSIGHTX/alembic.ini .
cp $INSIGHTX/.dockerignore .
cp -r $INSIGHTX/src .
cp -r $INSIGHTX/alembic .
git add .
git commit -m "Update to ..."
git push origin main
```

> Codex deploy-review fix (MINOR): added `alembic.ini` and `.dockerignore` to the update recipe — they were missing in the initial draft, so future Alembic config or build-context changes would silently fall behind.

HF Space auto-rebuilds on push.

---

## Cost monitoring

| Service | Free tier | Risk |
|---|---|---|
| HF Spaces | unlimited (free hardware, 48h auto-sleep) | none |
| Turso | 5GB storage, 1B row reads/mo | unlikely to hit unless you store every scrape result long-term |
| Gemini | 1500 req/day, 10 RPM (`gemma-4-26b-a4b-it` primary, free) | hit `429 RESOURCE_EXHAUSTED` if a demo session burns >10 calls in 60s — `_generate()` multi-model fallback rotates through `MODEL_CHAIN` automatically |
| Serper | 2500 free credits one-time + 100 free queries one-time | runs out fast in dev; add their $50/mo plan only when promoting publicly |
| YouTube Data API | 10,000 units/day | comments costs ~3-10 units per video, so ~1000+ videos/day |

If any service hits its quota during a demo, the user-facing UI shows a friendly error and Gemini/scraper fall back to mock data (see `MOCK_ANALYSIS` in `src/api/routes.py`).

---

## Troubleshooting

| Symptom | First action |
|---|---|
| Build fails on `libsql-experimental` | Add `--platform linux/amd64` to local builds; HF Spaces' default amd64 wheel works |
| `alembic upgrade head` fails on first boot | Check `DATABASE_URL` + `TURSO_AUTH_TOKEN` are set in Space secrets, not env Variables |
| 401 from Turso | Token expired or DB renamed; mint new token via `turso db tokens create` |
| `429` from Gemini | Wait 60s; `_generate()` retry logic will recover. If sustained, check Google AI Studio quota dashboard |
| Slow first request after 48h sleep | Expected — HF Spaces auto-sleeps free tier. First hit wakes the container (~10s cold start) |

---

## Architecture notes (why these choices)

- **Why Docker SDK over Gradio SDK**: InsightX is FastAPI + custom React UI, not a Gradio app. Docker SDK is the only way to keep that stack intact on HF Spaces Free.
- **Why Turso over Neon**: Turso's libsql is SQLite-compatible (matches the local dev DB), zero-config, and v6 already targets it. Neon would require a Postgres dialect switch (asyncpg/psycopg) which we explicitly avoided in v6.
- **Why port 7860**: HF Spaces Docker SDK default. The `deploy/hf-space-README.md` template includes `app_port: 7860` explicitly as documentation — the Space would auto-detect this even without the line, but pinning it makes the contract obvious.
- **Why CMD-based alembic upgrade vs entrypoint**: simpler, no extra script file; failed migration kills the container which surfaces in Space Logs.

For the v5 → v6 sync refactor reasoning (asyncpg → sqlalchemy-libsql), see `CHANGELOG.md` v6.0.0-alpha section.
