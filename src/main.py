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

# v4.0.0 UI routing:
#   /         → src/static/v2/ (v2-design Babel-standalone React 單檔 + core/ + hooks/)
#   /legacy/  → src/static/ (v3.x Tailwind HTML，向下相容)
# dist/（v3 Vite 打包後的快照）在 v4.0.0 不再當主入口。如果還在磁碟上，只掛到 /dist-legacy 保底預覽。
V2_DIR = "src/static/v2"
LEGACY_DIR = "src/static"
DIST_DIR = "dist"

# /legacy/ 先 mount（比 / 特殊）；StaticFiles.html=True 會自動對 .html 做目錄 index
app.mount("/legacy", StaticFiles(directory=LEGACY_DIR, html=True), name="legacy")
if os.path.isfile(os.path.join(DIST_DIR, "index.html")):
    app.mount("/dist-legacy", StaticFiles(directory=DIST_DIR, html=True), name="dist_legacy")

# / 最後掛，指到 v2-design
app.mount("/", StaticFiles(directory=V2_DIR, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
