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

import app.services.topic_roadmap_service as roadmap_svc
from app.core.config import get_settings
from app.core.ielts_levels import resolve_ielts_band
from app.models.session import Session
from app.models.session_message import SessionMessage
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.services.conversation_session_finalize import finalize_session_scoring
from app.services.lm_client import LMStudioClient, transcript_normalization_plausible
from app.services.scoring_service import ScoringService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


def _unescape_chat_newlines(s: str) -> str:
    """Turn literal \\n / \\r from LLM, STT, or over-escaped JSON into real newlines."""
    if "\\" not in s:
        return s
    return s.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")


def _opening_max_tokens(level_raw: str) -> int:
    n = resolve_ielts_band(level_raw)
    if n is None:
        return 120
    if n <= 5.0:
        return 80
    if n <= 6.5:
        return 100
    return 120


def _lm_max_reply_tokens(base: int, level_raw: str) -> int:
    n = resolve_ielts_band(level_raw)
    if n is None:
        return base
    if n <= 5.0:
        return min(base, 85)
    if n <= 6.0:
        return min(base, 120)
    if n <= 7.0:
        return min(base, 150)
    return min(base, 180)


AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)

_BATCH_CHARS = 12
_BATCH_INTERVAL = 0.04
_TTS_BATCH_BYTES = 4000
_TTS_BATCH_INTERVAL = 0.05
_TEXT_BASE_CHARS_PER_SEC = 18.0
_TEXT_MIN_CHARS_PER_SEC = 6.0
_TEXT_MAX_CHARS_PER_SEC = 42.0
_MIN_VALID_WEBM_BYTES = 64
_WEBM_EBML_HEADER = b"\x1a\x45\xdf\xa3"

# When the tutor LM fails after the user's line was shown, we still persist a chat message so end-session scoring can run.
_AI_UNAVAILABLE_ASSISTANT_TEXT = (
    "Sorry — I couldn't reply just now. Your answer was still saved for this session."
)


async def generate_llm_text(
    lm: LMStudioClient,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> str:
    """Get full assistant text first (no incremental WS text frames)."""
    return await lm.generate_text(
        messages, temperature=temperature, max_tokens=max_tokens
    )


def _tts_rate_to_multiplier(rate: str | None) -> float:
    """
    Map Azure-like TTS rate string (e.g. '+20%', '-10%') into a speed multiplier.
    Falls back to 1.0 when parsing fails.
    """
    if rate is None:
        return 1.0
    s = str(rate).strip()
    if s == "":
        return 1.0
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        pct = float(s)
    except ValueError:
        return 1.0
    mult = 1.0 + (pct / 100.0)
    return max(0.35, min(mult, 3.0))


def _paced_chars_per_second(rate: str | None) -> float:
    cps = _TEXT_BASE_CHARS_PER_SEC * _tts_rate_to_multiplier(rate)
    return max(_TEXT_MIN_CHARS_PER_SEC, min(cps, _TEXT_MAX_CHARS_PER_SEC))


async def emit_text_chunks(
    send: Callable[[dict], Any], text: str, *, rate: str | None = None
) -> None:
    """Send assistant text in paced chunks after audio is fully sent."""
    cps = _paced_chars_per_second(rate)
    batch = ""
    last_sent = time.monotonic()
    for ch in text:
        batch += ch
        now = time.monotonic()
        if (
            len(batch) >= _BATCH_CHARS
            or "\n" in batch
            or (now - last_sent) >= _BATCH_INTERVAL
        ):
            out = batch
            await send({"type": "assistant_partial", "text": out, "done": False})
            batch = ""
            last_sent = now
            await asyncio.sleep(max(0.015, min(len(out) / cps, 0.30)))
    if batch:
        out = batch
        await send({"type": "assistant_partial", "text": out, "done": False})
        await asyncio.sleep(max(0.015, min(len(out) / cps, 0.30)))
    await send({"type": "assistant_partial", "text": "", "done": True})


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
        self.topic_unit: TopicUnit | None = None
        self.level_override: str | None = (
            None  # real-time override from client; None = use topic.level
        )
        self.history: list[dict[str, str]] = []
        self.turn_index = 0
        self.audio_buffer = bytearray()
        # Opening line for new sessions (not persisted as a Turn); kept for rework rebuilds.
        self._opening_text: str | None = None
        self._opening_audio_path: str | None = None

    def _effective_level(self) -> str | None:
        """Level for next reply: override if set, else topic level."""
        if self.level_override is not None:
            return self.level_override.strip() or None
        if self.topic and self.topic.level:
            return self.topic.level.strip() or None
        return None

    def set_level(self, level: str | None) -> None:
        """Set real-time IELTS band override (from client dropdown). '' or None = use topic level."""
        s = (level or "").strip()
        self.level_override = s if s else None

    async def _topic_context_for_llm(self, db: AsyncSession) -> str | None:
        if not self.topic:
            return None
        parts: list[str] = [self.topic.title]
        u = self.topic_unit
        if u is not None:
            parts.append(f"Step: {u.title}. Learner goal: {u.objective}")
            if (u.prompt_hint or "").strip():
                parts.append(f"Tutor focus: {u.prompt_hint.strip()}")
            if self.session_id is not None:
                n = await roadmap_svc.count_turns_in_session(db, self.session_id)
                prog_bits: list[str] = [
                    f"Learner practice turns so far in this session: {n}. "
                    "(Each turn is one learner utterance plus your reply; scoring runs when the session ends.)"
                ]
                if u.min_turns_to_complete is not None:
                    prog_bits.append(
                        f"The step auto-completes after at least {u.min_turns_to_complete} "
                        "such turns in this session once scores are computed (and any average-score rule below)."
                    )
                if u.min_avg_overall is not None:
                    prog_bits.append(
                        f"When the turn count is met, average overall score for the session "
                        f"must be at least {u.min_avg_overall}."
                    )
                parts.append(" ".join(prog_bits))
                parts.append(
                    "Stay focused on the learner goal; keep replies concise. "
                    "If the learner is close to finishing the required practice, end naturally with brief encouragement."
                )
        return " ".join(parts)

    async def _attach_topic_unit_ws_meta(
        self, db: AsyncSession, status_payload: dict[str, Any]
    ) -> None:
        if self.topic_unit is None or self.session_id is None:
            return
        u = self.topic_unit
        n = await roadmap_svc.count_scored_turns_in_session(db, self.session_id)
        status_payload["topicUnit"] = {
            "id": u.id,
            "title": u.title,
            "objective": u.objective,
            "minTurnsToComplete": u.min_turns_to_complete,
            "minAvgOverall": u.min_avg_overall,
            "maxScoredTurns": u.max_scored_turns,
            "scoredTurnsSoFar": n,
        }

    async def _reject_if_max_scored_turns(self, db: AsyncSession) -> bool:
        """True if we should abort the new turn (limit reached)."""
        if not self.session_id or not self.topic_unit:
            return False
        cap = self.topic_unit.max_scored_turns
        if cap is None:
            return False
        n = await roadmap_svc.count_turns_in_session(db, self.session_id)
        if n < cap:
            return False
        await self._send({"type": "error", "message": "max_unit_turns_reached"})
        return True

    def _rebuild_lm_history_from_messages(self, messages: list[SessionMessage]) -> None:
        h: list[dict[str, str]] = []
        if self._opening_text:
            h.append({"role": "assistant", "content": self._opening_text})
        for m in messages:
            if m.role not in ("user", "assistant"):
                continue
            if m.kind == "score_feedback":
                continue
            h.append({"role": m.role, "content": m.text})
        self.history = h

    def _client_history_messages_from_messages(
        self, messages: list[SessionMessage]
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if self._opening_text:
            omsg: dict[str, Any] = {
                "role": "assistant",
                "text": self._opening_text,
                "isOpening": True,
            }
            if self._opening_audio_path and str(self._opening_audio_path).strip():
                omsg["hasAssistantAudio"] = True
            out.append(omsg)
        for m in messages:
            if m.role not in ("user", "assistant"):
                continue
            row: dict[str, Any] = {
                "role": m.role,
                "text": m.text,
                "turnId": m.id,
                "guideline": m.guideline,
            }
            if m.role == "user" and m.audio_path and str(m.audio_path).strip():
                row["hasUserAudio"] = True
            if m.role == "assistant" and m.audio_path and str(m.audio_path).strip():
                row["hasAssistantAudio"] = True
            out.append(row)
        return out

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
                select(Session)
                .where(
                    Session.id == resume_id,
                    Session.user_id == self._user_id,
                )
                .options(
                    selectinload(Session.topic),
                    selectinload(Session.topic_unit),
                )
            )
            sess = sess_q.scalar_one_or_none()
            if not sess or sess.topic_id != topic_id:
                await self._send({"type": "error", "message": "Session not found"})
                return False
            topic = sess.topic
            msg_q = await db.execute(
                select(SessionMessage)
                .where(
                    SessionMessage.session_id == sess.id,
                    SessionMessage.kind != "score_feedback",
                )
                .order_by(SessionMessage.index_in_session, SessionMessage.id)
            )
            messages = list(msg_q.scalars().all())
            self.session_id = sess.id
            self.topic = topic
            self.topic_unit = sess.topic_unit
            raw_opening = sess.opening_message
            self._opening_text = (
                raw_opening.strip()
                if isinstance(raw_opening, str) and raw_opening.strip()
                else None
            )
            oap = sess.opening_audio_path
            self._opening_audio_path = (
                oap.strip() if isinstance(oap, str) and oap.strip() else None
            )
            self._rebuild_lm_history_from_messages(messages)
            self.turn_index = len([m for m in messages if m.role == "user"])
            self.audio_buffer = bytearray()

            if data.get("ttsRate") is not None:
                self._tts_rate = str(data["ttsRate"])
            if data.get("ttsVoice"):
                self._tts_voice = str(data["ttsVoice"])
            if "level" in data:
                lv = data["level"]
                self.set_level(str(lv) if lv is not None else None)
            status_payload: dict = {
                "type": "status",
                "message": "session_started",
                "topicId": topic_id,
                "sessionId": self.session_id,
                "topicLevel": topic.level,
            }
            if sess.topic_unit_id is not None:
                status_payload["topicUnitId"] = sess.topic_unit_id
            await self._attach_topic_unit_ws_meta(db, status_payload)
            await self._send(status_payload)
            await self._send(
                {
                    "type": "history",
                    "messages": self._client_history_messages_from_messages(messages),
                }
            )
            return True

        # New session
        topic_q = await db.execute(select(Topic).where(Topic.id == topic_id))
        topic = topic_q.scalar_one_or_none()
        if not topic:
            await self._send({"type": "error", "message": "Topic not found"})
            return False

        topic_unit_id: int | None = None
        unit: TopicUnit | None = None
        raw_uid = data.get("unitId")
        if raw_uid is not None:
            try:
                uid = int(raw_uid)
            except (TypeError, ValueError):
                uid = 0
            if uid <= 0:
                await self._send({"type": "error", "message": "Invalid unitId"})
                return False
            unit = await db.get(TopicUnit, uid)
            if not unit or unit.topic_id != topic_id:
                await self._send({"type": "error", "message": "Topic unit not found"})
                return False
            if not await roadmap_svc.is_unit_unlocked_for_user(db, self._user_id, unit):
                await self._send({"type": "error", "message": "This step is locked"})
                return False
            await roadmap_svc.ensure_unit_started(db, self._user_id, uid)
            topic_unit_id = uid

        sess = Session(
            user_id=self._user_id,
            topic_id=topic_id,
            topic_unit_id=topic_unit_id,
        )
        db.add(sess)
        await db.commit()
        await db.refresh(sess)

        self.session_id = sess.id
        self.topic = topic
        self.topic_unit = unit
        self.history = []
        self.turn_index = 0
        self.audio_buffer = bytearray()
        self._opening_text = None
        self._opening_audio_path = None
        if data.get("ttsRate") is not None:
            self._tts_rate = str(data["ttsRate"])
        if data.get("ttsVoice"):
            self._tts_voice = str(data["ttsVoice"])
        if "level" in data:
            lv = data["level"]
            self.set_level(str(lv) if lv is not None else None)

        status_payload: dict = {
            "type": "status",
            "message": "session_started",
            "topicId": topic_id,
            "sessionId": self.session_id,
            "topicLevel": topic.level,
        }
        if topic_unit_id is not None:
            status_payload["topicUnitId"] = topic_unit_id
        await self._attach_topic_unit_ws_meta(db, status_payload)
        await self._send(status_payload)
        return True

    def handle_tts_preferences(self, data: dict) -> None:
        """Update TTS rate/voice from client (takes effect on next speech)."""
        if data.get("ttsRate") is not None:
            self._tts_rate = str(data["ttsRate"])
        if data.get("ttsVoice"):
            self._tts_voice = str(data["ttsVoice"])

    async def needs_opening_message(self, db: AsyncSession) -> bool:
        """True when the session has no stored opening and no chat messages."""
        if not self.session_id:
            return False
        sess = await db.get(Session, self.session_id)
        if sess is None:
            return False
        om = sess.opening_message
        if isinstance(om, str) and om.strip():
            return False
        r = await db.execute(
            select(func.count())
            .select_from(SessionMessage)
            .where(
                SessionMessage.session_id == self.session_id,
                SessionMessage.kind == "chat",
            )
        )
        return (r.scalar() or 0) == 0

    async def send_opening_message(self, db: AsyncSession) -> None:
        """Generate and stream AI opening (greeting/question); append to history and stream TTS."""
        if not self.topic:
            return
        if not self.session_id:
            return
        sess_row = await db.get(Session, self.session_id)
        if sess_row is not None:
            existing = sess_row.opening_message
            if isinstance(existing, str) and existing.strip():
                return
        effective = self._effective_level() or ""
        ctx = await self._topic_context_for_llm(db)
        if self.topic_unit is not None:
            u = self.topic_unit
            prompt = (
                f'[Start a guided speaking step titled "{u.title}". '
                f"Learner goal: {u.objective} "
                "The learner will have several scored speaking turns in this session toward this step. "
                "Give a short greeting or one opening question that fits this goal. "
                "One or two sentences only, in English.]"
            )
        else:
            prompt = (
                f"[Start the conversation about: {self.topic.title}. "
                "Say a short greeting or one opening question to get the learner to speak. "
                "One or two sentences only, in English.]"
            )
        messages = self._lm.build_messages(
            [{"role": "user", "content": prompt}],
            topic_context=ctx,
            topic_level=effective or None,
        )
        max_open_tokens = _opening_max_tokens(effective)
        try:
            opening_text = await generate_llm_text(
                self._lm,
                messages,
                temperature=0.7,
                max_tokens=max_open_tokens,
            )
        except Exception as e:
            logger.warning("Opening message failed: %s", e)
            opening_text = (
                f"Hi! Let's work on {self.topic_unit.title}. What would you like to say?"
                if self.topic_unit
                else f"Hi! Let's talk about {self.topic.title}. What would you like to say?"
            )
        self.history.append({"role": "assistant", "content": opening_text})
        self._opening_text = opening_text or None
        tts_bytes = b""
        if opening_text:
            tts_bytes = await stream_tts(
                self._send,
                self._tts,
                opening_text,
                voice=self._tts_voice,
                rate=self._tts_rate,
            )
            await emit_text_chunks(self._send, opening_text, rate=self._tts_rate)
        opening_audio_path: str | None = None
        if opening_text and self.session_id:
            user_dir = AUDIO_DIR / str(self._user_id) / str(self.session_id)
            user_dir.mkdir(parents=True, exist_ok=True)
            if tts_bytes:
                opath = user_dir / "opening_ai.mp3"
                opath.write_bytes(tts_bytes)
                opening_audio_path = str(opath)
            self._opening_audio_path = opening_audio_path
            await db.execute(
                update(Session)
                .where(Session.id == self.session_id)
                .values(
                    opening_message=opening_text,
                    opening_audio_path=opening_audio_path,
                )
            )
            await db.commit()

    async def handle_audio_end(self, db: AsyncSession) -> bool:
        """Transcribe, get AI reply, TTS, persist turn (scoring runs at session end). Return True on success."""
        if not self.session_id or not self.topic:
            await self._send({"type": "error", "message": "Send 'start' first"})
            return False
        if not self.audio_buffer:
            await self._send({"type": "error", "message": "No audio received"})
            return False
        raw_audio = bytes(self.audio_buffer)
        if len(raw_audio) < _MIN_VALID_WEBM_BYTES or not raw_audio.startswith(
            _WEBM_EBML_HEADER
        ):
            self.audio_buffer = bytearray()
            await self._send(
                {
                    "type": "error",
                    "message": "Recording invalid or too short. Please hold to speak a bit longer and try again.",
                }
            )
            return False

        if await self._reject_if_max_scored_turns(db):
            self.audio_buffer.clear()
            return False

        user_dir = AUDIO_DIR / str(self._user_id) / str(self.session_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        audio_path = user_dir / f"turn_{self.turn_index}_user.webm"
        audio_path.write_bytes(raw_audio)
        self.audio_buffer = bytearray()

        await self._send({"type": "status", "message": "transcribing"})
        try:
            stt_result = await asyncio.to_thread(self._stt.transcribe, audio_path)
            raw_stt: str = stt_result["text"] or "(inaudible)"
        except Exception:
            logger.exception("STT failed")
            await self._send({"type": "error", "message": "Transcription failed"})
            return False

        settings = get_settings()
        effective = self._effective_level() or ""
        ctx = await self._topic_context_for_llm(db)

        user_text = raw_stt
        if (
            settings.lm_normalize_transcript
            and raw_stt.strip()
            and raw_stt != "(inaudible)"
        ):
            await self._send({"type": "status", "message": "normalizing"})
            try:
                normalized = await self._lm.normalize_transcript(
                    raw_stt,
                    topic_context=ctx,
                )
                if normalized.strip():
                    cand = normalized.strip()
                    min_sim = float(settings.lm_normalize_min_similarity)
                    if transcript_normalization_plausible(
                        raw_stt, cand, min_similarity=min_sim
                    ):
                        user_text = cand
                        if user_text != raw_stt.strip():
                            logger.info(
                                "Transcript normalized: %r -> %r",
                                raw_stt,
                                user_text,
                            )
                    else:
                        logger.warning(
                            "Normalized transcript rejected (unlike raw STT): %r -> %r",
                            raw_stt,
                            cand,
                        )
                        user_text = raw_stt
                else:
                    user_text = raw_stt
            except Exception:
                logger.exception("Transcript normalization failed; using raw STT")
                user_text = raw_stt

        user_text = _unescape_chat_newlines(user_text)
        await self._send({"type": "user_transcript", "text": user_text})
        self.history.append({"role": "user", "content": user_text})
        messages = self._lm.build_messages(
            self.history,
            topic_context=ctx,
            topic_level=effective or None,
        )
        max_tokens = _lm_max_reply_tokens(
            settings.lm_conversation_max_tokens, effective
        )

        try:
            assistant_text = await generate_llm_text(
                self._lm,
                messages,
                temperature=0.7,
                max_tokens=max_tokens,
            )
        except Exception:
            logger.exception("LM generate failed")
            assistant_text = _AI_UNAVAILABLE_ASSISTANT_TEXT
            await self._send({"type": "error", "message": "AI unavailable"})

        self.history.append({"role": "assistant", "content": assistant_text})

        user_msg = SessionMessage(
            session_id=self.session_id,
            index_in_session=self.turn_index * 2,
            role="user",
            kind="chat",
            text=user_text,
            audio_path=str(audio_path),
        )
        db.add(user_msg)
        await db.commit()
        assistant_msg = SessionMessage(
            session_id=self.session_id,
            index_in_session=self.turn_index * 2 + 1,
            role="assistant",
            kind="chat",
            text=assistant_text,
            audio_path=None,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(user_msg)
        await db.refresh(assistant_msg)

        tts_path = user_dir / f"turn_{self.turn_index}_ai.mp3"
        tts_bytes = await stream_tts(
            self._send,
            self._tts,
            assistant_text,
            voice=self._tts_voice,
            rate=self._tts_rate,
        )
        await emit_text_chunks(self._send, assistant_text, rate=self._tts_rate)
        await self._send(
            {
                "type": "turn_saved",
                "turnId": assistant_msg.id,
                "userMessageId": user_msg.id,
                "hasUserAudio": bool(
                    user_msg.audio_path and str(user_msg.audio_path).strip()
                ),
                "indexInSession": self.turn_index,
            }
        )
        if tts_bytes:
            tts_path.write_bytes(tts_bytes)
            assistant_msg.audio_path = str(tts_path)
            await db.commit()
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

        if await self._reject_if_max_scored_turns(db):
            return False

        user_text = _unescape_chat_newlines(raw)
        await self._send({"type": "user_transcript", "text": user_text})
        self.history.append({"role": "user", "content": user_text})

        effective = self._effective_level() or ""
        ctx = await self._topic_context_for_llm(db)
        messages = self._lm.build_messages(
            self.history,
            topic_context=ctx,
            topic_level=effective or None,
        )
        settings = get_settings()
        max_tokens = _lm_max_reply_tokens(
            settings.lm_conversation_max_tokens, effective
        )

        try:
            assistant_text = await generate_llm_text(
                self._lm,
                messages,
                temperature=0.7,
                max_tokens=max_tokens,
            )
        except Exception:
            logger.exception("LM generate failed (text turn)")
            assistant_text = _AI_UNAVAILABLE_ASSISTANT_TEXT
            await self._send({"type": "error", "message": "AI unavailable"})

        self.history.append({"role": "assistant", "content": assistant_text})

        user_msg = SessionMessage(
            session_id=self.session_id,
            index_in_session=self.turn_index * 2,
            role="user",
            kind="chat",
            text=user_text,
            audio_path=None,
        )
        db.add(user_msg)
        await db.commit()
        assistant_msg = SessionMessage(
            session_id=self.session_id,
            index_in_session=self.turn_index * 2 + 1,
            role="assistant",
            kind="chat",
            text=assistant_text,
            audio_path=None,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(user_msg)
        await db.refresh(assistant_msg)

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
        await emit_text_chunks(self._send, assistant_text, rate=self._tts_rate)
        await self._send(
            {
                "type": "turn_saved",
                "turnId": assistant_msg.id,
                "userMessageId": user_msg.id,
                "hasUserAudio": bool(
                    user_msg.audio_path and str(user_msg.audio_path).strip()
                ),
                "indexInSession": self.turn_index,
            }
        )
        if tts_bytes:
            tts_path.write_bytes(tts_bytes)
            assistant_msg.audio_path = str(tts_path)
            await db.commit()
        self.turn_index += 1
        return True

    async def _score_pending_turns_and_send_summary(self, db: AsyncSession) -> None:
        """After conversation ends: score turns missing scores, notify client, roadmap auto-complete."""
        if not self.session_id or not self.topic:
            return

        out = await finalize_session_scoring(
            db, self.session_id, self._user_id, self._scorer
        )
        if not out:
            return

        if out.get("averages"):
            await self._send(
                {
                    "type": "session_scores",
                    "turns": out["turns"],
                    "averages": out["averages"],
                    "session_feedback": out.get("session_feedback") or "",
                }
            )
        elif (out.get("session_feedback") or "").strip():
            await self._send(
                {
                    "type": "session_scores",
                    "turns": out.get("turns") or [],
                    "session_feedback": out["session_feedback"],
                }
            )

        if out.get("roadmap_unit_completed") and out.get("topic_unit_id") is not None:
            await self._send(
                {
                    "type": "status",
                    "message": "roadmap_unit_completed",
                    "topicUnitId": out["topic_unit_id"],
                    "sessionId": self.session_id,
                }
            )

    async def handle_rework(self, db: AsyncSession, data: dict) -> bool:
        """Remove this turn and all following turns; client continues from before this slot."""
        if not self.session_id or not self.topic:
            await self._send({"type": "error", "message": "Send 'start' first"})
            return False
        try:
            turn_index = int(data.get("turnIndex", -1))
        except (TypeError, ValueError):
            turn_index = -1
        if turn_index < 0 or turn_index >= self.turn_index:
            await self._send({"type": "error", "message": "Invalid rework"})
            return False

        sid = self.session_id
        old_ti = self.turn_index
        user_dir = AUDIO_DIR / str(self._user_id) / str(sid)
        await db.execute(
            delete(SessionMessage).where(
                SessionMessage.session_id == sid,
                SessionMessage.index_in_session >= turn_index * 2,
            )
        )
        await db.commit()

        for i in range(turn_index, old_ti):
            for name in (f"turn_{i}_user.webm", f"turn_{i}_ai.mp3"):
                p = user_dir / name
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    logger.warning("Could not delete %s", p)

        self.turn_index = turn_index

        r_msg = await db.execute(
            select(SessionMessage)
            .where(
                SessionMessage.session_id == sid,
                SessionMessage.kind != "score_feedback",
            )
            .order_by(SessionMessage.index_in_session, SessionMessage.id)
        )
        messages = list(r_msg.scalars().all())
        self._rebuild_lm_history_from_messages(messages)
        await self._send(
            {
                "type": "history",
                "messages": self._client_history_messages_from_messages(messages),
            }
        )

        status_payload: dict[str, Any] = {
            "type": "status",
            "message": "rework_applied",
            "sessionId": sid,
            "topicId": self.topic.id,
            "topicLevel": self.topic.level,
        }
        await self._attach_topic_unit_ws_meta(db, status_payload)
        await self._send(status_payload)
        return True

    async def handle_stop(self, db: AsyncSession) -> None:
        """Score any pending turns, then mark session ended and send session_stopped."""
        sid = self.session_id
        if sid and self.topic:
            await self._score_pending_turns_and_send_summary(db)
        elif sid:
            sess_q = await db.execute(select(Session).where(Session.id == sid))
            sess = sess_q.scalar_one_or_none()
            if sess is not None:
                sess.ended_at = datetime.now(timezone.utc)
                await db.commit()
        await self._send({"type": "status", "message": "session_stopped"})
