"""
Conversation WebSocket logic: streaming helpers + session handler.

Used by conversation_ws in conversation.py.
"""

import asyncio
import base64
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.conversation import ConversationSession, Topic, Turn, TurnScore
from app.services.lm_client import LMStudioClient
from app.services.scoring_service import ScoringService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)

AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)

_BATCH_CHARS = 12
_BATCH_INTERVAL = 0.04
_TTS_BATCH_BYTES = 4000
_TTS_BATCH_INTERVAL = 0.05


async def stream_llm(
    send: Callable[[dict], Any],
    lm: LMStudioClient,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> str:
    """Stream LLM response to client via assistant_partial; return full text."""
    full = ""
    batch = ""
    last_sent = time.monotonic()
    async for chunk in lm.generate_stream(
        messages, temperature=temperature, max_tokens=max_tokens
    ):
        full += chunk
        batch += chunk
        now = time.monotonic()
        if (
            len(batch) >= _BATCH_CHARS
            or "\n" in batch
            or (now - last_sent) >= _BATCH_INTERVAL
        ):
            if batch:
                await send({"type": "assistant_partial", "text": batch, "done": False})
                await asyncio.sleep(0.02)
            batch = ""
            last_sent = now
    if batch:
        await send({"type": "assistant_partial", "text": batch, "done": False})
    await send({"type": "assistant_partial", "text": "", "done": True})
    return full


async def stream_tts(
    send: Callable[[dict], Any],
    tts: TTSService,
    text: str,
    *,
    voice: str | None = None,
    rate: str | None = None,
) -> bytes:
    """Stream TTS to client via assistant_audio_chunk; return full audio bytes."""
    out = bytearray()
    batch = bytearray()
    last_sent = time.monotonic()
    try:
        async for chunk in tts.synthesize_stream(text, voice=voice, rate=rate):
            out.extend(chunk)
            batch.extend(chunk)
            now = time.monotonic()
            if (
                len(batch) >= _TTS_BATCH_BYTES
                or (now - last_sent) >= _TTS_BATCH_INTERVAL
            ):
                if batch:
                    await send(
                        {
                            "type": "assistant_audio_chunk",
                            "data": base64.b64encode(bytes(batch)).decode(),
                        }
                    )
                    batch.clear()
                    last_sent = now
                await asyncio.sleep(0.03)
        if batch:
            await send(
                {
                    "type": "assistant_audio_chunk",
                    "data": base64.b64encode(bytes(batch)).decode(),
                }
            )
    except Exception as e:
        logger.warning("TTS failed: %s", e)
        await send({"type": "status", "message": "tts_unavailable"})
    await send({"type": "assistant_audio_end"})
    return bytes(out)


class ConversationHandler:
    """Handles one WebSocket conversation: session state + start / turn / stop."""

    def __init__(
        self,
        send: Callable[[dict], Any],
        user_id: int,
        lm: LMStudioClient,
        stt: STTService,
        tts: TTSService,
        scorer: ScoringService,
        max_audio_bytes: int,
    ) -> None:
        self._send = send
        self._user_id = user_id
        self._lm = lm
        self._stt = stt
        self._tts = tts
        self._scorer = scorer
        self._max_audio_bytes = max_audio_bytes
        settings = get_settings()
        self._tts_rate: str = settings.tts_rate
        self._tts_voice: str = settings.tts_voice
        self.session_id: int | None = None
        self.topic: Topic | None = None
        self.level_override: str | None = None  # real-time override from client; None = use topic.level
        self.history: list[dict[str, str]] = []
        self.turn_index = 0
        self.audio_buffer = bytearray()
        self.utterance_start: float = 0.0

    def _effective_level(self) -> str | None:
        """Level for next reply: override if set, else topic level."""
        if self.level_override is not None:
            return self.level_override.strip() or None
        if self.topic and self.topic.level:
            return self.topic.level.strip() or None
        return None

    def set_level(self, level: str | None) -> None:
        """Set real-time level override (e.g. from client dropdown). '' or None = use topic level."""
        s = (level or "").strip()
        self.level_override = s if s else None

    async def handle_start(self, db: AsyncSession, data: dict) -> bool:
        """
        Start or resume a session.
        - If sessionId is provided and valid: load session, send history, return True (caller should NOT send opening).
        - Else: create new session, return True (caller should send opening).
        """
        try:
            topic_id = int(data.get("topicId", 0))
        except (TypeError, ValueError):
            await self._send({"type": "error", "message": "Invalid topicId"})
            return False
        if topic_id <= 0:
            await self._send({"type": "error", "message": "Invalid topicId"})
            return False

        session_id_raw = data.get("sessionId")
        if session_id_raw is not None:
            try:
                resume_id = int(session_id_raw)
            except (TypeError, ValueError):
                resume_id = 0
        else:
            resume_id = 0

        if resume_id > 0:
            # Resume existing session: must belong to user and match topic
            sess_q = await db.execute(
                select(ConversationSession)
                .where(
                    ConversationSession.id == resume_id,
                    ConversationSession.user_id == self._user_id,
                )
                .options(selectinload(ConversationSession.topic))
            )
            sess = sess_q.scalar_one_or_none()
            if not sess or sess.topic_id != topic_id:
                await self._send({"type": "error", "message": "Session not found"})
                return False
            topic = sess.topic
            turns_q = await db.execute(
                select(Turn)
                .where(Turn.session_id == sess.id)
                .order_by(Turn.index_in_session)
            )
            turns = list(turns_q.scalars().all())
            history = []
            for t in turns:
                history.append({"role": "user", "content": t.user_text})
                history.append({"role": "assistant", "content": t.assistant_text})

            self.session_id = sess.id
            self.topic = topic
            self.history = history
            self.turn_index = len(turns)
            self.audio_buffer = bytearray()

            if data.get("ttsRate") is not None:
                self._tts_rate = str(data["ttsRate"])
            if data.get("ttsVoice"):
                self._tts_voice = str(data["ttsVoice"])
            await self._send(
                {
                    "type": "status",
                    "message": "session_started",
                    "topicId": topic_id,
                    "sessionId": self.session_id,
                    "topicLevel": topic.level,
                }
            )
            history_payload = []
            for t in turns:
                history_payload.append({"role": "user", "text": t.user_text})
                history_payload.append({
                    "role": "assistant",
                    "text": t.assistant_text,
                    "turnId": t.id,
                    "guideline": t.guideline,
                })
            await self._send({"type": "history", "messages": history_payload})
            return True

        # New session
        topic_q = await db.execute(select(Topic).where(Topic.id == topic_id))
        topic = topic_q.scalar_one_or_none()
        if not topic:
            await self._send({"type": "error", "message": "Topic not found"})
            return False

        sess = ConversationSession(user_id=self._user_id, topic_id=topic_id)
        db.add(sess)
        await db.commit()
        await db.refresh(sess)

        self.session_id = sess.id
        self.topic = topic
        self.history = []
        self.turn_index = 0
        self.audio_buffer = bytearray()
        if data.get("ttsRate") is not None:
            self._tts_rate = str(data["ttsRate"])
        if data.get("ttsVoice"):
            self._tts_voice = str(data["ttsVoice"])

        await self._send(
            {
                "type": "status",
                "message": "session_started",
                "topicId": topic_id,
                "sessionId": self.session_id,
                "topicLevel": topic.level,
            }
        )
        return True

    def handle_tts_preferences(self, data: dict) -> None:
        """Update TTS rate/voice from client (takes effect on next speech)."""
        if data.get("ttsRate") is not None:
            self._tts_rate = str(data["ttsRate"])
        if data.get("ttsVoice"):
            self._tts_voice = str(data["ttsVoice"])

    async def send_opening_message(self) -> None:
        """Generate and stream AI opening (greeting/question); append to history and stream TTS."""
        if not self.topic:
            return
        effective = self._effective_level() or ""
        level_key = effective.strip().lower()
        prompt = (
            f"[Start the conversation about: {self.topic.title}. "
            "Say a short greeting or one opening question to get the learner to speak. "
            "One or two sentences only, in English.]"
        )
        messages = self._lm.build_messages(
            [{"role": "user", "content": prompt}],
            topic_context=self.topic.title,
            topic_level=effective or None,
        )
        max_open_tokens = 80 if level_key in ("a1", "a2") else 120
        try:
            opening_text = await stream_llm(
                self._send, self._lm, messages, temperature=0.7, max_tokens=max_open_tokens
            )
        except Exception as e:
            logger.warning("Opening message failed: %s", e)
            opening_text = (
                f"Hi! Let's talk about {self.topic.title}. What would you like to say?"
            )
            await self._send(
                {
                    "type": "assistant_partial",
                    "text": opening_text,
                    "done": True,
                }
            )
        self.history.append({"role": "assistant", "content": opening_text})
        if opening_text:
            await stream_tts(
                self._send,
                self._tts,
                opening_text,
                voice=self._tts_voice,
                rate=self._tts_rate,
            )

    async def handle_audio_end(self, db: AsyncSession) -> bool:
        """Transcribe, get AI reply, TTS, score, persist turn. Return True on success."""
        if not self.session_id or not self.topic:
            await self._send({"type": "error", "message": "Send 'start' first"})
            return False
        if not self.audio_buffer:
            await self._send({"type": "error", "message": "No audio received"})
            return False

        duration = time.time() - self.utterance_start
        user_dir = AUDIO_DIR / str(self._user_id) / str(self.session_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        audio_path = user_dir / f"turn_{self.turn_index}_user.webm"
        audio_path.write_bytes(bytes(self.audio_buffer))
        self.audio_buffer = bytearray()

        try:
            stt_result = await asyncio.to_thread(self._stt.transcribe, audio_path)
            user_text: str = stt_result["text"] or "(inaudible)"
        except Exception:
            logger.exception("STT failed")
            await self._send({"type": "error", "message": "Transcription failed"})
            return False

        await self._send({"type": "user_transcript", "text": user_text})
        self.history.append({"role": "user", "content": user_text})
        effective = self._effective_level() or ""
        messages = self._lm.build_messages(
            self.history,
            topic_context=self.topic.title,
            topic_level=effective or None,
        )
        settings = get_settings()
        level_key = effective.strip().lower()
        max_tokens = settings.lm_conversation_max_tokens
        if level_key == "a1":
            max_tokens = min(max_tokens, 80)
        elif level_key == "a2":
            max_tokens = min(max_tokens, 120)

        try:
            assistant_text = await stream_llm(
                self._send,
                self._lm,
                messages,
                temperature=0.7,
                max_tokens=max_tokens,
            )
        except Exception:
            logger.exception("LM generate failed")
            await self._send({"type": "error", "message": "AI unavailable"})
            return False

        self.history.append({"role": "assistant", "content": assistant_text})

        tts_path = user_dir / f"turn_{self.turn_index}_ai.mp3"
        tts_bytes = await stream_tts(
            self._send,
            self._tts,
            assistant_text,
            voice=self._tts_voice,
            rate=self._tts_rate,
        )
        if tts_bytes:
            tts_path.write_bytes(tts_bytes)

        score = await self._scorer.score(user_text, self.topic.title, duration)
        turn = Turn(
            session_id=self.session_id,
            index_in_session=self.turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
            user_audio_path=str(audio_path),
            assistant_audio_path=str(tts_path),
        )
        db.add(turn)
        await db.commit()
        await db.refresh(turn)
        db.add(
            TurnScore(
                turn_id=turn.id,
                fluency=score.get("fluency", 5),
                vocabulary=score.get("vocabulary", 5),
                grammar=score.get("grammar", 5),
                overall=score.get("overall", 5),
                feedback=score.get("feedback"),
            )
        )
        await db.commit()
        await self._send(
            {
                "type": "turn_score",
                "turnId": turn.id,
                "fluency": score.get("fluency", 5),
                "vocabulary": score.get("vocabulary", 5),
                "grammar": score.get("grammar", 5),
                "overall": score.get("overall", 5),
                "feedback": score.get("feedback", ""),
            }
        )
        self.turn_index += 1
        return True

    async def handle_user_text(self, db: AsyncSession, data: dict) -> bool:
        """Handle a text message from the user (no audio)."""
        if not self.session_id or not self.topic:
            await self._send({"type": "error", "message": "Send 'start' first"})
            return False

        raw = str(data.get("text") or "").strip()
        if not raw:
            await self._send({"type": "error", "message": "Empty message"})
            return False

        user_text = raw
        await self._send({"type": "user_transcript", "text": user_text})
        self.history.append({"role": "user", "content": user_text})

        effective = self._effective_level() or ""
        messages = self._lm.build_messages(
            self.history,
            topic_context=self.topic.title,
            topic_level=effective or None,
        )
        settings = get_settings()
        level_key = effective.strip().lower()
        max_tokens = settings.lm_conversation_max_tokens
        if level_key == "a1":
            max_tokens = min(max_tokens, 80)
        elif level_key == "a2":
            max_tokens = min(max_tokens, 120)

        try:
            assistant_text = await stream_llm(
                self._send,
                self._lm,
                messages,
                temperature=0.7,
                max_tokens=max_tokens,
            )
        except Exception:
            logger.exception("LM generate failed (text turn)")
            await self._send({"type": "error", "message": "AI unavailable"})
            return False

        self.history.append({"role": "assistant", "content": assistant_text})

        user_dir = AUDIO_DIR / str(self._user_id) / str(self.session_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        tts_path = user_dir / f"turn_{self.turn_index}_ai.mp3"
        tts_bytes = await stream_tts(
            self._send,
            self._tts,
            assistant_text,
            voice=self._tts_voice,
            rate=self._tts_rate,
        )
        if tts_bytes:
            tts_path.write_bytes(tts_bytes)

        # Duration is unknown for text-only; pass 0 so scorer can still work.
        score = await self._scorer.score(user_text, self.topic.title, 0.0)
        turn = Turn(
            session_id=self.session_id,
            index_in_session=self.turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
            user_audio_path=None,
            assistant_audio_path=str(tts_path) if tts_bytes else None,
        )
        db.add(turn)
        await db.commit()
        await db.refresh(turn)
        db.add(
            TurnScore(
                turn_id=turn.id,
                fluency=score.get("fluency", 5),
                vocabulary=score.get("vocabulary", 5),
                grammar=score.get("grammar", 5),
                overall=score.get("overall", 5),
                feedback=score.get("feedback"),
            )
        )
        await db.commit()
        await self._send(
            {
                "type": "turn_score",
                "turnId": turn.id,
                "fluency": score.get("fluency", 5),
                "vocabulary": score.get("vocabulary", 5),
                "grammar": score.get("grammar", 5),
                "overall": score.get("overall", 5),
                "feedback": score.get("feedback", ""),
            }
        )
        self.turn_index += 1
        return True

    async def handle_stop(self, db: AsyncSession) -> None:
        """Mark session ended and send session_stopped."""
        if self.session_id:
            sess_q = await db.execute(
                select(ConversationSession).where(
                    ConversationSession.id == self.session_id
                )
            )
            sess = sess_q.scalar_one_or_none()
            if sess:
                sess.ended_at = datetime.now(timezone.utc)
                await db.commit()
        await self._send({"type": "status", "message": "session_stopped"})
