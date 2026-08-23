from collections.abc import AsyncIterator
from dataclasses import dataclass

import edge_tts

from app.core.config import get_settings

# Microsoft TTS metadata uses 100-nanosecond ticks.
_TTS_TICKS_PER_SEC = 10_000_000.0


@dataclass(frozen=True, slots=True)
class TtsWordTiming:
    """One spoken word and its start time in the synthesized audio."""

    text: str
    offset_sec: float
    duration_sec: float


def _ticks_to_sec(value: object) -> float:
    try:
        return max(0.0, float(value) / _TTS_TICKS_PER_SEC)
    except (TypeError, ValueError):
        return 0.0


class TTSService:
    """
    Wrapper around edge-tts for text-to-speech streaming.
    Voice and rate come from config (env: TTS_VOICE, TTS_RATE).
    """

    def __init__(
        self,
        voice: str | None = None,
        rate: str | None = None,
    ) -> None:
        settings = get_settings()
        self._voice = voice or settings.tts_voice
        self._rate = rate if rate is not None else settings.tts_rate

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        rate: str | None = None,
        word_timings: list[TtsWordTiming] | None = None,
    ) -> AsyncIterator[bytes]:
        v = voice or self._voice
        r = rate or self._rate
        communicate = _make_communicate(text, v, r)
        async for chunk in communicate.stream():
            kind = chunk.get("type")
            if kind == "audio":
                data = chunk.get("data")
                if isinstance(data, (bytes, bytearray)):
                    yield bytes(data)
                continue
            if word_timings is None or kind != "WordBoundary":
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
