"""Practice history API for the progress page (docs/features/session-history.md)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services import history, recordings

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/sessions")
async def list_sessions() -> dict:
    return {"enabled": history.enabled(), "sessions": history.list_sessions()}


@router.get("/sessions/{session_id}/turns")
async def session_turns(session_id: int) -> list[dict]:
    """Turns of one session; `audio_url` plays the answer back when its recording was kept."""
    turns = history.session_turns(session_id)
    if any(t["source"] == "voice" and not t["audio"] for t in turns):
        # Turns saved before turns.audio existed: link them to their recording once.
        found = recordings.match_turns(turns, recordings.transcripts(), history.turn_audio_names())
        history.set_turn_audio(found)
        for t in turns:
            t["audio"] = t["audio"] or found.get(t["id"])
    for t in turns:
        t["audio_url"] = f"/api/history/audio/{t['audio']}" if recordings.path_for(t["audio"]) else None
    return turns


@router.get("/audio/{name}")
async def turn_audio(name: str) -> FileResponse:
    """A kept recording (only names the app created, only from SAVE_AUDIO_DIR)."""
    path = recordings.path_for(name)
    if not path:
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/webm")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int) -> dict:
    if not history.delete_session(session_id):
        raise HTTPException(404)
    return {"ok": True}
