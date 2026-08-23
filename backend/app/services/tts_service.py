import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import edge_tts

from app.core.config import get_settings

# Microsoft TTS metadata uses 100-nanosecond ticks.
_TTS_TICKS_PER_SEC = 10_000_000.0
_TTS_MP3_BYTES_PER_SEC = 6000.0
_PAUSE_NOTE_SEC = 0.35
_VI_VOICE_FEMALE = "vi-VN-HoaiMyNeural"
_VI_VOICE_MALE = "vi-VN-NamMinhNeural"
_FEMALE_VOICE_HINTS = (
    "jenny",
    "aria",
    "ana",
    "emma",
    "jane",
    "sara",
    "michelle",
    "nancy",
    "sonia",
    "hoaimy",
    "female",
)
_VI_CHAR_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
_ABBREV_RE = re.compile(
    r"(?i)\b(?:e\.g|i\.e|mr|mrs|ms|dr|vs|etc|u\.s|u\.k)\.$"
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_CLAUSE_SPLIT_RE = re.compile(
    r"(?<=:)\s+(?=[\"“'A-ZÀÁẠẢÃĂẰẮẶẲẴÂẦẤẬẨẪÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ])"
)


@dataclass(frozen=True, slots=True)
class TtsWordTiming:
    """One spoken word and its start time in the synthesized audio."""

    text: str
    offset_sec: float
    duration_sec: float


@dataclass(frozen=True, slots=True)
class _TtsPart:
    text: str
    voice: str
    pause_before_sec: float
    track_words: bool


def _ticks_to_sec(value: object) -> float:
    try:
        return max(0.0, float(value) / _TTS_TICKS_PER_SEC)
    except (TypeError, ValueError):
        return 0.0


def looks_vietnamese(text: str) -> bool:
    """True when the text has Vietnamese diacritics (enough to need a vi voice)."""
    s = (text or "").strip()
    if not s:
        return False
    return bool(_VI_CHAR_RE.search(s))


def vi_voice_for(english_voice: str | None, configured: str | None = None) -> str:
    """Pick a Vietnamese neural voice that roughly matches the English voice gender."""
    if configured and str(configured).strip():
        return str(configured).strip()
    name = (english_voice or "").lower()
    if any(h in name for h in _FEMALE_VOICE_HINTS) or "female" in name:
        return _VI_VOICE_FEMALE
    if name and "neural" in name and not any(h in name for h in _FEMALE_VOICE_HINTS):
        # Many male IDs have no extra hint besides Guy/Andrew/Nam.
        if any(x in name for x in ("guy", "andrew", "christopher", "eric", "namminh", "male")):
            return _VI_VOICE_MALE
    return _VI_VOICE_FEMALE


def split_spoken_chunks(text: str) -> list[str]:
    """Split tutor speech into short clauses so TTS can pause between them."""
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return []
    pieces: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(raw):
        s = sentence.strip()
        if not s:
            continue
        if pieces and _ABBREV_RE.search(pieces[-1]):
            pieces[-1] = f"{pieces[-1]} {s}"
            continue
        clause_parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(s) if p.strip()]
        if len(clause_parts) <= 1:
            pieces.append(s)
            continue
        # Re-attach the colon to the lead-in: "A more natural way is" + ": I went…"
        lead = clause_parts[0]
        rest = s[len(lead) :].lstrip()
        if rest.startswith(":"):
            pieces.append(lead + ":")
            tail = rest[1:].strip()
            if tail:
                pieces.append(tail)
        else:
            pieces.extend(clause_parts)
    return pieces


def plan_tts_parts(
    text: str,
    *,
    voice: str,
    extra_text: str = "",
    extra_voice: str | None = None,
) -> list[_TtsPart]:
    """At most two Edge TTS calls: spoken line, then optional Vietnamese note."""
    parts: list[_TtsPart] = []
    spoken = (text or "").strip()
    note = (extra_text or "").strip()
    if spoken:
        use_vi = looks_vietnamese(spoken)
        parts.append(
            _TtsPart(
                text=spoken,
                voice=extra_voice if use_vi and extra_voice else voice,
                pause_before_sec=0.0,
                track_words=not use_vi,
            )
        )
    if note:
        parts.append(
            _TtsPart(
                text=note,
                voice=extra_voice or voice,
                pause_before_sec=_PAUSE_NOTE_SEC if parts else 0.0,
                track_words=False,
            )
        )
    return parts


def _ffmpeg_exe() -> str | None:
    settings = get_settings()
    if settings.ffmpeg_path and Path(settings.ffmpeg_path).exists():
        return str(Path(settings.ffmpeg_path).resolve())
    found = shutil.which("ffmpeg")
    return found


@lru_cache(maxsize=8)
def _silence_mp3(duration_ms: int) -> bytes:
    """CBR-ish silent MP3 so the player keeps a beat between clauses."""
    ms = max(80, min(int(duration_ms), 2000))
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return b""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "silence.mp3"
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{ms / 1000:.3f}",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "48k",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return b""
        data = out.read_bytes() if out.exists() else b""
    return data


def _pause_bytes(sec: float) -> bytes:
    if sec < 0.05:
        return b""
    return _silence_mp3(int(round(sec * 1000)))


class TTSService:
    """
    Wrapper around edge-tts for text-to-speech streaming.
    Splits clauses, inserts short pauses, and switches to a Vietnamese voice
    when the text (or an extra coaching note) needs it.
    """

    def __init__(
        self,
        voice: str | None = None,
        rate: str | None = None,
    ) -> None:
        settings = get_settings()
        self._voice = voice or settings.tts_voice
        self._rate = rate if rate is not None else settings.tts_rate
        self._vi_voice = vi_voice_for(self._voice, settings.tts_voice_vi)

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        rate: str | None = None,
        word_timings: list[TtsWordTiming] | None = None,
        extra_text: str = "",
        extra_voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        v = voice or self._voice
        r = rate or self._rate
        vi = extra_voice or vi_voice_for(v, self._vi_voice)
        parts = plan_tts_parts(text, voice=v, extra_text=extra_text, extra_voice=vi)
        if not parts:
            return
        extra_task: asyncio.Task[tuple[bytes, list[TtsWordTiming]]] | None = None
        if len(parts) > 1:
            extra = parts[1]
            extra_task = asyncio.create_task(
                _collect_one(extra.text, extra.voice, r)
            )
        first = parts[0]
        local: list[TtsWordTiming] = []
        try:
            async for chunk in _stream_one(
                first.text,
                first.voice,
                r,
                local,
            ):
                yield chunk
            if word_timings is not None and first.track_words:
                word_timings.extend(local)
            if extra_task is None:
                return
            extra_audio, _extra_words = await extra_task
            extra = parts[1]
            pause = _pause_bytes(extra.pause_before_sec)
            if pause:
                yield pause
            if extra_audio:
                yield extra_audio
        finally:
            if extra_task is not None and not extra_task.done():
                extra_task.cancel()


async def _collect_one(
    text: str, voice: str, rate: str
) -> tuple[bytes, list[TtsWordTiming]]:
    timings: list[TtsWordTiming] = []
    out = bytearray()
    async for chunk in _stream_one(text, voice, rate, timings):
        out.extend(chunk)
    return bytes(out), timings


async def _stream_one(
    text: str,
    voice: str,
    rate: str,
    word_timings: list[TtsWordTiming],
) -> AsyncIterator[bytes]:
    communicate = _make_communicate(text, voice, rate)
    async for chunk in communicate.stream():
        kind = chunk.get("type")
        if kind == "audio":
            data = chunk.get("data")
            if isinstance(data, (bytes, bytearray)):
                yield bytes(data)
            continue
        if kind != "WordBoundary":
            continue
        word = str(chunk.get("text") or "").strip()
        if not word:
            continue
        word_timings.append(
            TtsWordTiming(
                text=word,
                offset_sec=_ticks_to_sec(chunk.get("offset")),
                duration_sec=_ticks_to_sec(chunk.get("duration")),
            )
        )


def _make_communicate(text: str, voice: str, rate: str) -> edge_tts.Communicate:
    """Prefer word-level metadata; older edge-tts builds omit the boundary kwarg."""
    try:
        return edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:
        return edge_tts.Communicate(text, voice, rate=rate)
