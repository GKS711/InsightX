# frontend builder
FROM node:18-alpine AS frontend
WORKDIR /fe
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# python runtime
FROM ghcr.io/astral-sh/uv:debian-slim
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --frozen

COPY src ./src
COPY --from=frontend /fe/dist ./dist
RUN uv sync --frozen

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]