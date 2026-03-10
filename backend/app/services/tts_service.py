from collections.abc import AsyncIterator
from typing import Any

import edge_tts


class TTSService:
    """
    Wrapper around edge-tts for text-to-speech streaming.
    """

    def __init__(self, voice: str = "en-US-JennyNeural") -> None:
        self._voice = voice

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        communicate = edge_tts.Communicate(text, self._voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]  # type: ignore[misc]

