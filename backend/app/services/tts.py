"""Text-to-speech with edge-tts (MP3). Swap point: changing TTS only touches tts_bytes().

If the new TTS returns WAV/PCM, change the Blob `type` in frontend/src/hooks/useAudioQueue.ts (currently audio/mpeg).
"""

from __future__ import annotations

import edge_tts

from app.core import config

_cache: dict[tuple[str, str], bytes] = {}  # fixed lines (questions, drills...): synthesized once
SLOW_RATE = "-30%"  # pronunciation drills: "listen slowly"


async def tts_bytes(text: str, rate: str | None = None) -> bytes:
    out = bytearray()
    voice = edge_tts.Communicate(text, config.TTS_VOICE, rate=rate or config.TTS_RATE)
    async for chunk in voice.stream():
        if chunk["type"] == "audio":
            out.extend(chunk["data"])
    return bytes(out)


async def cached_tts(text: str, rate: str | None = None) -> bytes:
    key = (text, rate or config.TTS_RATE)
    if key not in _cache:
        _cache[key] = await tts_bytes(text, rate)
    return _cache[key]


async def prewarm(unit: dict) -> None:
    """Pre-synthesize a unit's fixed lines; runs in the background when a unit starts."""
    questions = unit["questions"]
    texts = [q["ask"] for q in questions[1:]] + [unit["closing"]] + [q["simple"] for q in questions]
    for text in texts:
        try:
            await cached_tts(text)
        except Exception:  # noqa: BLE001  (retried on real use)
            pass
