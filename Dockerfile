# InsightX v6.0.0-alpha — single-stage Python image for HF Spaces (Docker SDK).
#
# Why single-stage:
#   - v4+ UI is `src/static/v2/index.html` (single-file React + Babel-standalone,
#     no npm build needed). The old `npm run build` stage was for v3 Vite + a
#     side `insightx-game` and is no longer required for the main app.
#
# Runtime:
#   - Port 7860 (HF Spaces default; can be overridden via PORT env or README's
#     app_port frontmatter).
#   - On startup: `alembic upgrade head` materializes the v5 schema on the
#     Turso/SQLite DB pointed to by DATABASE_URL, then exec uvicorn.
#   - Recommended HF Space secrets (set in Space settings):
#       DATABASE_URL=libsql://<your-db>-<owner>.turso.io
#       TURSO_AUTH_TOKEN=<from `turso db tokens create <db-name>`>
#       GEMINI_API_KEY=<google-ai-studio-key>
#       SERPER_API_KEY=<for Google Maps scraping>
#       YOUTUBE_API_KEY=<optional; YouTube Data API v3>

FROM python:3.10-slim

# Codex deploy-review fix (SERIOUS): build-essential removed. amd64 binary
# wheels exist for libsql-experimental (cp310 manylinux2014); --only-binary
# below forces wheel-only install and fails fast if a wheel goes missing
# upstream (better than silently switching to a Rust-toolchain source build
# that would need build-essential + maturin + cargo).

# HF Spaces runs containers as user `user` (uid 1000). We need a writable
# WORKDIR. /home/user is conventional. Important: chown the workdir BEFORE
# switching to USER user, otherwise SQLite (local dev) can't create files
# in cwd — WORKDIR creates dirs as root by default.
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/app && \
    chown -R user:user /home/user
WORKDIR /home/user/app

# Install Python deps first for layer caching (as root, system-wide install)
COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --only-binary=:all: -r requirements.txt

# Copy backend source + alembic + static UI
COPY --chown=user:user src ./src
COPY --chown=user:user alembic ./alembic
COPY --chown=user:user alembic.ini ./

# HF Spaces convention: run as non-root
USER user

# Port 7860 = HF Spaces Docker SDK default
ENV PORT=7860
ENV PYTHONUNBUFFERED=1
EXPOSE 7860

# Codex deploy-review fix (SERIOUS): HEALTHCHECK so docker / HF can tell
# uvicorn is actually serving requests, not just listening. start-period 60s
# gives alembic upgrade head time to finish on first boot before the probe
# starts counting failures.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"7860\")}/api/meta', timeout=3)" || exit 1

# Entrypoint: migrate DB schema before serving. Failing migrate = container
# exits, HF Spaces will show the log; better than starting a broken app.
# JSON-form CMD + `exec` so uvicorn replaces sh as PID 1 and SIGTERM
# from the orchestrator propagates correctly (no 30s grace-period kill).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
