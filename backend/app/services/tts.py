"""Text-to-speech with edge-tts (MP3). Swap point: changing TTS only touches tts_bytes().

If the new TTS returns WAV/PCM, change the Blob `type` in frontend/js/app.js (currently audio/mpeg).
"""

from __future__ import annotations

import edge_tts

from app.core import config

_cache: dict[str, bytes] = {}  # fixed lines (questions, greeting, closing): synthesized once


async def tts_bytes(text: str) -> bytes:
    out = bytearray()
    async for chunk in edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE).stream():
        if chunk["type"] == "audio":
            out.extend(chunk["data"])
    return bytes(out)


async def cached_tts(text: str) -> bytes:
    if text not in _cache:
        _cache[text] = await tts_bytes(text)
    return _cache[text]


async def prewarm(unit: dict) -> None:
    """Pre-synthesize a unit's fixed lines; runs in the background when a unit starts."""
    questions = unit["questions"]
    texts = [q["ask"] for q in questions[1:]] + [unit["closing"]] + [q["simple"] for q in questions]
    for text in texts:
        try:
            await cached_tts(text)
        except Exception:  # noqa: BLE001  (retried on real use)
            pass
