import sys
import asyncio
import os

# Windows 需要 ProactorEventLoop 以支援 subprocess
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.api.routes import router
import uvicorn

app = FastAPI(title="InsightX API")

# API first (important)
app.include_router(router, prefix="/api")

# Prefer dist if built artifacts exist
DIST_DIR = "dist"
if os.path.isfile(os.path.join(DIST_DIR, "index.html")):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="static")
else:
    # Dev fallback: serve plain static (only works if your src/static is usable as static HTML)
    # If you rely on React/TSX, you should use Vite dev server instead.
    app.mount("/", StaticFiles(directory="src/static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
