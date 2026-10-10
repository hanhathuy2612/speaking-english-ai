"""WebSocket wrapper with a lock so a sentence's JSON and its audio frame are always sent together."""

from __future__ import annotations

import asyncio

from fastapi import WebSocket


class Conn:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.lock = asyncio.Lock()

    async def json(self, data: dict) -> None:
        async with self.lock:
            await self.ws.send_json(data)

    async def audio(self, text: str, audio: bytes, role: str = "ai") -> None:
        async with self.lock:
            await self.ws.send_json({"type": "sentence", "text": text, "role": role})
            await self.ws.send_bytes(audio)
