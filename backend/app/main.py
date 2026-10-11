"""Local English interview practice: STT -> LLM (streamed) -> TTS.

Run from backend/ (LM Studio's local server must be running):
    uvicorn app.main:app --port 8000
Open: http://localhost:8000 (build the React app first: cd frontend && npm run build)

Docs: AGENTS.md at the project root, details in docs/.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import bench, check, drills, fluency, history, review, units, ws
from app.core.config import FRONTEND_DIST
from app.services import history as history_store
from app.services import stt

# Non-ASCII logs (transcripts, "·") would crash on cp1252 when output is redirected on Windows.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    history_store.init()  # create the SQLite tables if needed
    stt.load()  # load Whisper once at startup
    yield


app = FastAPI(title="Speaking demo", lifespan=lifespan)
app.include_router(units.router)
app.include_router(bench.router)
app.include_router(check.router)
app.include_router(drills.router)
app.include_router(fluency.router)
app.include_router(review.router)
app.include_router(history.router)
app.include_router(ws.router)
# The React app (frontend/, built into frontend/dist) is a single page: every page route returns
# index.html and React Router picks the view. Hashed JS/CSS bundles are served from /assets.
SPA_ROUTES = ["/", "/review", "/roadmap", "/sounds", "/fluency", "/check", "/history", "/bench"]
NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Chưa build giao diện</title>
<body style="font-family:system-ui;max-width:640px;margin:48px auto;padding:0 16px;line-height:1.6">
<h1>Chưa build giao diện</h1>
<p>Chạy một lần (cần Node 22.12+):</p>
<pre>cd frontend
npm install
npm run build</pre>
<p>rồi tải lại trang. Khi phát triển giao diện, dùng <code>npm run dev</code> và mở http://localhost:5173.</p>"""

# check_dir=False: building the app after the server started works without a restart.
app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets", check_dir=False), name="assets")


async def spa_page() -> Response:
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        return HTMLResponse(NOT_BUILT, status_code=503)
    return FileResponse(index)


for _route in SPA_ROUTES:
    app.add_api_route(_route, spa_page, include_in_schema=False)
