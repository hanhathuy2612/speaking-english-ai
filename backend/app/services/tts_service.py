from collections.abc import AsyncIterator

import edge_tts

from app.core.config import get_settings


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
    ) -> AsyncIterator[bytes]:
        v = voice or self._voice
        r = rate or self._rate
        communicate = edge_tts.Communicate(text, v, rate=r)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]  # type: ignore[misc]

