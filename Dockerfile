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

# Build deps for sqlalchemy-libsql + libsql-experimental wheels (needs gcc for
# rare arch fallback paths). On amd64 wheels are usually prebuilt; this keeps
# the build resilient.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

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
    pip install --no-cache-dir -r requirements.txt

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

# Entrypoint: migrate DB schema before serving. Failing migrate = container
# exits, HF Spaces will show the log; better than starting a broken app.
# JSON-form CMD + `exec` so uvicorn replaces sh as PID 1 and SIGTERM
# from the orchestrator propagates correctly (no 30s grace-period kill).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
