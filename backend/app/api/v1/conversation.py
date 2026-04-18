"""
WebSocket endpoint for full-duplex spoken conversation.

Message protocol
────────────────
Client → Server (JSON):
  {"type": "start",       "topicId": int, "ttsRate": str, "ttsVoice": str, optional "level": str}  -- omit or "" = use topic’s DB default band; set to override header band before opening TTS
  {"type": "set_level",   "level": str}  -- IELTS Speaking target band (4–9, half bands) or "" for topic default
  {"type": "tts_preferences", "ttsRate": str, "ttsVoice": str}
  {"type": "audio_end"}   -- after binary audio frames (voice turn)
  {"type": "user_text",   "text": str}                           -- text-only turn
  {"type": "rework",      "turnIndex": int}                      -- drop from this turn onward; redo from here
  {"type": "stop"}        -- end session

Server → Client: status, history, user_transcript, assistant_partial, assistant_audio_chunk,
  assistant_audio_end, session_scores (when session ends), error.
"""

import asyncio
import json
import logging
from typing import Any, Callable

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.services.lm_client import LMStudioClient
from app.services.scoring_service import ScoringService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .conversation_handler import ConversationHandler

logger = logging.getLogger(__name__)

router = APIRouter()

WS_EVENT_DISCONNECT = "websocket.disconnect"
WS_TYPE_STATUS = "status"
WS_TYPE_ERROR = "error"
WS_STATUS_CONNECTED = "connected"
WS_STATUS_IDLE_TIMEOUT = "idle_timeout"
WS_STATUS_PONG = "pong"
WS_ERROR_AUDIO_TOO_LONG = "Audio too long"
WS_ERROR_UNKNOWN = "Something went wrong"

CLIENT_MSG_START = "start"
CLIENT_MSG_SET_LEVEL = "set_level"
CLIENT_MSG_TTS_PREFERENCES = "tts_preferences"
CLIENT_MSG_AUDIO_END = "audio_end"
CLIENT_MSG_USER_TEXT = "user_text"
CLIENT_MSG_REWORK = "rework"
CLIENT_MSG_PING = "ping"
CLIENT_MSG_STOP = "stop"


def _authenticate_ws(token: str) -> int:
    payload = decode_token(token)
    return int(payload.get("sub", 0))


def _create_handler(
    send: Callable[[dict], Any],
    user_id: int,
    max_audio_bytes: int,
) -> ConversationHandler:
    lm = LMStudioClient()
    return ConversationHandler(
        send=send,
        user_id=user_id,
        lm=lm,
        stt=STTService(),
        tts=TTSService(),
        scorer=ScoringService(lm),
        max_audio_bytes=max_audio_bytes,
    )


async def _handle_client_message(
    handler: ConversationHandler,
    db,
    data: dict,
    send,
) -> bool:
    """
    Process one JSON client message.
    Returns True when the WS loop should stop.
    """
    msg_type = data.get("type")
    if msg_type == CLIENT_MSG_START:
        if await handler.handle_start(db, data) and await handler.needs_opening_message(
            db
        ):
            await handler.send_opening_message(db)
        return False
    if msg_type == CLIENT_MSG_SET_LEVEL:
        handler.set_level(data.get("level"))
        return False
    if msg_type == CLIENT_MSG_TTS_PREFERENCES:
        handler.handle_tts_preferences(data)
        return False
    if msg_type == CLIENT_MSG_AUDIO_END:
        await handler.handle_audio_end(db)
        return False
    if msg_type == CLIENT_MSG_USER_TEXT:
        await handler.handle_user_text(db, data)
        return False
    if msg_type == CLIENT_MSG_REWORK:
        await handler.handle_rework(db, data)
        return False
    if msg_type == CLIENT_MSG_PING:
        await send({"type": WS_TYPE_STATUS, "message": WS_STATUS_PONG})
        return False
    if msg_type == CLIENT_MSG_STOP:
        await handler.handle_stop(db)
        return True
    return False


async def _handle_incoming_ws_frame(
    raw: dict,
    *,
    handler: ConversationHandler,
    max_audio_bytes: int,
    db,
    send,
) -> bool:
    """
    Handle one websocket frame.
    Returns True when the WS loop should stop.
    """
    if raw.get("type") == WS_EVENT_DISCONNECT:
        return True

    chunk = raw.get("bytes")
    if chunk is not None:
        new_len = len(handler.audio_buffer) + len(chunk)
        if new_len > max_audio_bytes:
            await send({"type": WS_TYPE_ERROR, "message": WS_ERROR_AUDIO_TOO_LONG})
            handler.audio_buffer.clear()
            return False
        handler.audio_buffer.extend(chunk)
        return False

    data = json.loads(raw.get("text", "{}"))
    return await _handle_client_message(handler, db, data, send)


@router.websocket("/conversation")
async def conversation_ws(websocket: WebSocket) -> None:
    try:
        user_id = _authenticate_ws(websocket.query_params.get("token", ""))
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    settings = get_settings()
    max_audio_bytes = settings.max_audio_upload_mb * 1024 * 1024

    async def send(data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    handler = _create_handler(send, user_id, max_audio_bytes)

    try:
        await send({"type": WS_TYPE_STATUS, "message": WS_STATUS_CONNECTED})
        idle_sec = max(30, int(settings.websocket_idle_timeout_seconds))
        async with AsyncSessionLocal() as db:
            while True:
                try:
                    raw = await asyncio.wait_for(
                        websocket.receive(), timeout=float(idle_sec)
                    )
                except asyncio.TimeoutError:
                    await send(
                        {"type": WS_TYPE_STATUS, "message": WS_STATUS_IDLE_TIMEOUT}
                    )
                    break

                should_stop = await _handle_incoming_ws_frame(
                    raw,
                    handler=handler,
                    max_audio_bytes=max_audio_bytes,
                    db=db,
                    send=send,
                )
                if should_stop:
                    break

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
        try:
            await websocket.send_json(
                {"type": WS_TYPE_ERROR, "message": WS_ERROR_UNKNOWN}
            )
        except Exception:
            pass
