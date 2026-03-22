"""
WebSocket endpoint for full-duplex spoken conversation.

Message protocol
────────────────
Client → Server (JSON):
  {"type": "start",       "topicId": int, "ttsRate": str, "ttsVoice": str, optional "level": str}  -- CEFR or ""; applied before opening TTS
  {"type": "set_level",   "level": "A1"|"A2"|"B1"|"B2"|"C1"|""}  -- real-time level override
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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.services.lm_client import LMStudioClient
from app.services.scoring_service import ScoringService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService

from .conversation_handler import ConversationHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["conversation"])


def _authenticate_ws(token: str) -> int:
    payload = decode_token(token)
    return int(payload.get("sub", 0))


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

    lm = LMStudioClient()
    handler = ConversationHandler(
        send=send,
        user_id=user_id,
        lm=lm,
        stt=STTService(),
        tts=TTSService(),
        scorer=ScoringService(lm),
        max_audio_bytes=max_audio_bytes,
    )

    try:
        await send({"type": "status", "message": "connected"})
        async with AsyncSessionLocal() as db:
            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive(), timeout=300)
                except asyncio.TimeoutError:
                    await send({"type": "status", "message": "idle_timeout"})
                    break

                if raw.get("type") == "websocket.disconnect":
                    break

                if raw.get("bytes") is not None:
                    new_len = len(handler.audio_buffer) + len(raw["bytes"])
                    if new_len > max_audio_bytes:
                        await send({"type": "error", "message": "Audio too long"})
                        handler.audio_buffer.clear()
                        continue
                    handler.audio_buffer.extend(raw["bytes"])
                    continue

                data = json.loads(raw.get("text", "{}"))
                msg_type = data.get("type")

                if msg_type == "start":
                    if await handler.handle_start(db, data):
                        if await handler.needs_opening_message(db):
                            await handler.send_opening_message(db)
                elif msg_type == "set_level":
                    handler.set_level(data.get("level"))
                elif msg_type == "tts_preferences":
                    handler.handle_tts_preferences(data)
                elif msg_type == "audio_end":
                    await handler.handle_audio_end(db)
                elif msg_type == "user_text":
                    await handler.handle_user_text(db, data)
                elif msg_type == "rework":
                    await handler.handle_rework(db, data)
                elif msg_type == "stop":
                    await handler.handle_stop(db)
                    break

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
        try:
            await websocket.send_json(
                {"type": "error", "message": "Something went wrong"}
            )
        except Exception:
            pass
