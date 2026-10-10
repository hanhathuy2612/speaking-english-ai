"""Local English interview practice: STT -> LLM (streamed) -> TTS.

Run from backend/ (LM Studio's local server must be running):
    uvicorn app.main:app --port 8000
Open: http://localhost:8000  (STT read-aloud page: /bench)

Docs: AGENTS.md at the project root, details in docs/.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import bench, history, units, ws
from app.core.config import FRONTEND_DIR
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
app.include_router(history.router)
app.include_router(ws.router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/bench", include_in_schema=False)
async def bench_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "bench.html")


@app.get("/history", include_in_schema=False)
async def history_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "history.html")
