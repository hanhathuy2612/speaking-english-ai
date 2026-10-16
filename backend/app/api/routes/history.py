"""Practice history API for the progress page (docs/features/session-history.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import current_user
from app.services import history, recordings

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/sessions")
def list_sessions(user: dict = Depends(current_user)) -> dict:
    return {"enabled": history.enabled(), "sessions": history.list_sessions(user["id"])}


@router.get("/sessions/{session_id}/turns")
def session_turns(session_id: int, user: dict = Depends(current_user)) -> list[dict]:
    """Turns of one of the user's sessions; `audio_url` plays the answer back when its recording was kept."""
    turns = history.session_turns(user["id"], session_id)
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
def turn_audio(name: str, user: dict = Depends(current_user)) -> FileResponse:
    """One of the user's kept recordings (only names the app created, only from SAVE_AUDIO_DIR)."""
    path = recordings.path_for(name)
    if not path or not history.owns_recording(user["id"], name):
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/webm")


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, user: dict = Depends(current_user)) -> dict:
    if not history.delete_session(user["id"], session_id):
        raise HTTPException(404)
    return {"ok": True}
