#!/bin/bash
cd "$(dirname "$0")"
source ../venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
