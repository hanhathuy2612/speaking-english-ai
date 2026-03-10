"""
WebSocket endpoint for full-duplex spoken conversation.

Message protocol
────────────────
Client → Server (JSON):
  {"type": "start",       "topicId": int, "difficulty": str}
  {"type": "audio_end"}   -- client signals end of utterance; binary audio frames were sent as raw bytes before this
  {"type": "stop"}        -- end session

Client → Server (binary):
  Raw PCM/WebM audio bytes (accumulated until audio_end arrives)

Server → Client (JSON):
  {"type": "status",               "message": str}
  {"type": "user_transcript",      "text": str}
  {"type": "assistant_partial",    "text": str, "done": bool}
  {"type": "assistant_audio_chunk","data": <base64 str>}
  {"type": "turn_score",           "fluency": float, "vocabulary": float, "grammar": float, "overall": float, "feedback": str}
  {"type": "error",                "message": str}
"""

import asyncio
import base64
import io
import time
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.security import decode_token
from app.db.session import get_db, AsyncSessionLocal
from app.models.conversation import ConversationSession, Topic, Turn, TurnScore
from app.models.user import User
from app.services.lm_client import LMStudioClient
from app.services.scoring_service import ScoringService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService

router = APIRouter(prefix="/ws", tags=["conversation"])

_AUDIO_DIR = Path("audio")
_AUDIO_DIR.mkdir(exist_ok=True)


def _authenticate_ws(token: str) -> int:
    """Return user_id from JWT or raise ValueError."""
    payload = decode_token(token)
    return int(payload.get("sub", 0))


@router.websocket("/conversation")
async def conversation_ws(websocket: WebSocket) -> None:
    # ── 1. Auth via query param ──────────────────────────────────────────────
    token = websocket.query_params.get("token", "")
    try:
        user_id = _authenticate_ws(token)
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    settings = get_settings()
    lm = LMStudioClient()
    stt = STTService()
    tts = TTSService()
    scorer = ScoringService(lm)

    session_id: int | None = None
    topic: Topic | None = None
    history: list[dict[str, str]] = []
    turn_index = 0
    audio_buffer = bytearray()
    utterance_start: float = 0.0

    async def send(data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    try:
        await send({"type": "status", "message": "connected"})

        async with AsyncSessionLocal() as db:
            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive(), timeout=300)
                except asyncio.TimeoutError:
                    await send({"type": "status", "message": "idle_timeout"})
                    break

                # ── Binary audio frame ──────────────────────────────────────
                if raw.get("bytes") is not None:
                    if not audio_buffer:
                        utterance_start = time.time()
                    audio_buffer.extend(raw["bytes"])
                    continue

                # ── JSON control messages ───────────────────────────────────
                import json as _json
                data = _json.loads(raw.get("text", "{}"))
                msg_type = data.get("type")

                if msg_type == "start":
                    topic_id: int = int(data.get("topicId", 0))
                    topic_q = await db.execute(select(Topic).where(Topic.id == topic_id))
                    topic = topic_q.scalar_one_or_none()
                    if not topic:
                        await send({"type": "error", "message": "Topic not found"})
                        continue

                    sess = ConversationSession(user_id=user_id, topic_id=topic_id)
                    db.add(sess)
                    await db.commit()
                    await db.refresh(sess)
                    session_id = sess.id
                    turn_index = 0
                    history = []
                    audio_buffer = bytearray()

                    await send({"type": "status", "message": "session_started", "topicId": topic_id, "sessionId": session_id})

                elif msg_type == "audio_end":
                    if not session_id or not topic:
                        await send({"type": "error", "message": "Send 'start' first"})
                        continue
                    if not audio_buffer:
                        await send({"type": "error", "message": "No audio received"})
                        continue

                    duration = time.time() - utterance_start

                    # ── STT ──────────────────────────────────────────────────
                    user_dir = _AUDIO_DIR / str(user_id) / str(session_id)
                    user_dir.mkdir(parents=True, exist_ok=True)
                    audio_path = user_dir / f"turn_{turn_index}_user.webm"
                    audio_path.write_bytes(bytes(audio_buffer))
                    audio_buffer = bytearray()

                    try:
                        stt_result = stt.transcribe(audio_path)
                        user_text: str = stt_result["text"] or "(inaudible)"
                    except Exception as exc:
                        await send({"type": "error", "message": f"STT error: {exc}"})
                        continue

                    await send({"type": "user_transcript", "text": user_text})

                    # ── LM Studio stream ─────────────────────────────────────
                    history.append({"role": "user", "content": user_text})
                    messages = lm.build_messages(history, topic_context=topic.title)

                    assistant_text = ""
                    async for chunk in lm.generate_stream(messages):
                        assistant_text += chunk
                        await send({"type": "assistant_partial", "text": chunk, "done": False})
                    await send({"type": "assistant_partial", "text": "", "done": True})
                    history.append({"role": "assistant", "content": assistant_text})

                    # ── TTS stream ───────────────────────────────────────────
                    tts_path = user_dir / f"turn_{turn_index}_ai.mp3"
                    tts_bytes = bytearray()
                    async for chunk in tts.synthesize_stream(assistant_text):
                        tts_bytes.extend(chunk)
                        await send({
                            "type": "assistant_audio_chunk",
                            "data": base64.b64encode(chunk).decode(),
                        })
                    tts_path.write_bytes(bytes(tts_bytes))

                    # ── Scoring ──────────────────────────────────────────────
                    score = await scorer.score(user_text, topic.title, duration)
                    await send({
                        "type": "turn_score",
                        "fluency": score.get("fluency", 5),
                        "vocabulary": score.get("vocabulary", 5),
                        "grammar": score.get("grammar", 5),
                        "overall": score.get("overall", 5),
                        "feedback": score.get("feedback", ""),
                    })

                    # ── Persist Turn + Score ──────────────────────────────────
                    turn = Turn(
                        session_id=session_id,
                        index_in_session=turn_index,
                        user_text=user_text,
                        assistant_text=assistant_text,
                        user_audio_path=str(audio_path),
                        assistant_audio_path=str(tts_path),
                    )
                    db.add(turn)
                    await db.commit()
                    await db.refresh(turn)

                    ts = TurnScore(
                        turn_id=turn.id,
                        fluency=score.get("fluency", 5),
                        vocabulary=score.get("vocabulary", 5),
                        grammar=score.get("grammar", 5),
                        overall=score.get("overall", 5),
                        feedback=score.get("feedback"),
                    )
                    db.add(ts)
                    await db.commit()
                    turn_index += 1

                elif msg_type == "stop":
                    if session_id:
                        sess_q = await db.execute(
                            select(ConversationSession).where(ConversationSession.id == session_id)
                        )
                        sess = sess_q.scalar_one_or_none()
                        if sess:
                            sess.ended_at = datetime.utcnow()
                            await db.commit()
                    await send({"type": "status", "message": "session_stopped"})
                    break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
