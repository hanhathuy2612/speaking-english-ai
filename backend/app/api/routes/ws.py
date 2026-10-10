"""WebSocket /ws: one practice session per connection. Protocol: docs/architecture.md."""

from __future__ import annotations

import asyncio
import json
import time

from app.core.config import STT_VOCAB
from app.interview.session import Session, progress
from app.interview.turn import handle_user_input, start_session
from app.interview.units import units_by_id
from app.services import history, stt, tts
from app.utils.ws import Conn
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    conn = Conn(ws)
    session: Session | None = None
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("text") is not None:
                session = await _on_text(conn, session, json.loads(msg["text"]))
            elif msg.get("bytes") is not None and session:
                await _on_audio(conn, session, msg["bytes"])
    except WebSocketDisconnect:
        pass


async def _on_text(conn: Conn, session: Session | None, data: dict) -> Session | None:
    kind = data.get("type")
    if kind == "start" and data.get("unit") in units_by_id:
        return await start_session(conn, units_by_id[data["unit"]])
    if kind == "text" and session and data.get("text", "").strip():
        await handle_user_input(
            conn, session, data["text"].strip(), [], time.monotonic(), None
        )
    elif kind == "undo" and session:
        if session.prev is not None:
            history.delete_turn(session.last_turn_id)
            session.restore(session.prev)
            session.prev, session.last_turn_id = None, None
            history.set_completed(session.history_id, session.done)
            await conn.json({"type": "undone", "used": sorted(session.used)})
            await conn.json(progress(session))
        await conn.json({"type": "turn_done", "can_undo": False})
    elif kind == "say_it" and data.get("text", "").strip():
        text = data["text"].strip()
        await conn.audio(text, await tts.tts_bytes(text), role="model")
    return session


async def _on_audio(conn: Conn, session: Session, data: bytes) -> None:
    t0 = time.monotonic()
    await conn.json({"type": "status", "msg": "transcribing"})
    path = stt.save_recording(data)
    prompt = f"{STT_VOCAB} {session.unit.get('vocab', '')}".strip()
    try:
        result = await asyncio.to_thread(stt.transcribe, path, prompt)
    except Exception as e:  # noqa: BLE001
        stt.finish_recording(path, None)
        await conn.json({"type": "error", "msg": f"STT: {e}"})
        await conn.json({"type": "turn_done", "can_undo": False})
        return
    stt.finish_recording(path, result["text"])
    t_stt = time.monotonic()
    print(
        f"STT logprob={result['avg_logprob']} no_speech={result['no_speech']}: {result['text']}"
    )
    if not result["text"]:
        await conn.json(
            {"type": "error", "msg": "Không nghe rõ, hãy nói lại gần micro hơn."}
        )
        await conn.json({"type": "turn_done", "can_undo": False})
        return
    await handle_user_input(
        conn, session, result["text"], result["words"], t0, t_stt, result
    )
