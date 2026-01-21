FROM ghcr.io/astral-sh/uv:debian-slim

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-install-project

COPY . .
RUN uv sync 

CMD [ "uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0" ]
