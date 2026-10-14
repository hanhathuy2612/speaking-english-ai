"""WebSocket /ws: one practice session per connection. Protocol: docs/architecture.md."""

from __future__ import annotations

import asyncio
import json
import time

from app.api.deps import ws_user
from app.core.config import STT_CHECK_LANGUAGE, STT_VOCAB
from app.interview.session import Session, progress
from app.interview.retell import handle_retell
from app.interview.shadow import handle_shadow
from app.interview.turn import handle_user_input, start_session
from app.interview.units import units_by_id
from app.services import history, stt, tts
from app.utils.ws import Conn
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    user = ws_user(ws)
    await ws.accept()
    if not user:
        await ws.close(code=4401, reason="login required")  # the page sends the user to /login
        return
    conn = Conn(ws)
    session: Session | None = None
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("text") is not None:
                session = await _on_text(conn, user, session, json.loads(msg["text"]))
            elif msg.get("bytes") is not None and session:
                await _on_audio(conn, session, msg["bytes"])
    except WebSocketDisconnect:
        pass


async def _on_text(conn: Conn, user: dict, session: Session | None, data: dict) -> Session | None:
    kind = data.get("type")
    if kind == "start" and data.get("unit") in units_by_id:
        return await start_session(conn, units_by_id[data["unit"]], user["id"])
    if kind == "text" and session and data.get("text", "").strip():
        session.retell = False  # a typed message is always an interview answer
        await handle_user_input(
            conn, session, data["text"].strip(), [], time.monotonic(), None
        )
    elif kind == "undo" and session:
        if session.prev is not None:
            history.delete_turn(session.last_turn_id)
            session.restore(session.prev)
            session.prev, session.last_turn_id = None, None
            session.retell_base, session.retell = None, False
            history.set_completed(session.history_id, session.done)
            await conn.json({"type": "undone", "used": sorted(session.used)})
            await conn.json(progress(session))
        await conn.json({"type": "turn_done", "can_undo": False})
    elif kind == "shadow" and session and data.get("text", "").strip():
        session.shadow_target = data["text"].strip()  # the next recording is a shadowing attempt
    elif kind == "retell" and session and session.retell_base:
        session.retell = True  # the next recording answers the last question again
    elif kind == "say_it" and data.get("text", "").strip():
        text = data["text"].strip()
        await conn.audio(text, await tts.tts_bytes(text), role="model")
    return session


async def _on_audio(conn: Conn, session: Session, data: bytes) -> None:
    t0 = time.monotonic()
    await conn.json({"type": "status", "msg": "transcribing"})
    path = stt.save_recording(data)
    # No vocabulary prompt when shadowing: it would bias Whisper towards the reference words
    # and hide exactly the pronunciation mistakes we want to show.
    prompt = "" if session.shadow_target else f"{STT_VOCAB} {session.unit.get('vocab', '')}".strip()
    try:
        check = STT_CHECK_LANGUAGE and not session.shadow_target  # shadowing reads English text
        result = await asyncio.to_thread(stt.transcribe, path, prompt, check)
    except Exception as e:  # noqa: BLE001
        stt.finish_recording(path, None)
        await conn.json({"type": "error", "msg": f"STT: {e}"})
        await conn.json({"type": "turn_done", "can_undo": False})
        return
    stt.finish_recording(path, result["text"])
    t_stt = time.monotonic()
    print(
        f"STT logprob={result['avg_logprob']} no_speech={result['no_speech']} "
        f"lang={result['language']}: {result['text']}"
    )
    if not result["text"]:
        session.shadow_target, session.retell = None, False
        await conn.json(
            {"type": "error", "msg": "Không nghe rõ, hãy nói lại gần micro hơn."}
        )
        await conn.json({"type": "turn_done", "can_undo": session.prev is not None})
        return
    if session.shadow_target:
        await handle_shadow(conn, session, result, round((t_stt - t0) * 1000))
        return
    if session.retell:
        await handle_retell(conn, session, result, round((t_stt - t0) * 1000))
        return
    result["recording"] = stt.kept_name(path)  # stored with the turn, for "Nghe lại" later
    await handle_user_input(
        conn, session, result["text"], result["words"], t0, t_stt, result
    )
