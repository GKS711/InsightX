# Stage 1: Build frontend
FROM node:18-alpine AS frontend
WORKDIR /fe
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.10-slim
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source + built frontend
COPY src ./src
COPY --from=frontend /fe/dist ./dist

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
