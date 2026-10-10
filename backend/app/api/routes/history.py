"""Practice history API for the progress page (docs/features/session-history.md)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import history

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/sessions")
async def list_sessions() -> dict:
    return {"enabled": history.enabled(), "sessions": history.list_sessions()}


@router.get("/sessions/{session_id}/turns")
async def session_turns(session_id: int) -> list[dict]:
    return history.session_turns(session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int) -> dict:
    if not history.delete_session(session_id):
        raise HTTPException(404)
    return {"ok": True}
