from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

_DEFAULT_SYSTEM = """You are a friendly English conversation partner.

Sound natural and relaxed, like talking to a friend—not like a textbook or a formal teacher.
Use everyday language, contractions (I'm, that's), and a warm tone.

Keep your replies short and natural (usually 2–4 sentences). Avoid lists, bullet points, or over-explaining.

Always stay focused on the current topic and respond directly to what the user just said.
Use the conversation history so your replies feel connected and not random.

Keep the conversation going by asking a simple follow-up question when it feels natural.

If the user makes a mistake, gently correct only the important part in a natural way, without interrupting the flow.

If the user switches topics suddenly, briefly respond and then guide the conversation back.

If the user uses Vietnamese (or mixes Vietnamese and English), understand it but always reply in English.
Encourage them to try saying it in English in a simple way."""

_LEVEL_INSTRUCTIONS: dict[str, str] = {
    "a1": (
        "Level A1: Reply in ONE very short sentence only (about 5–12 words). "
        "Use only simple, common words. No long explanations."
    ),
    "a2": (
        "Level A2: Reply in 1–2 short sentences (about 10–20 words total). "
        "Use simple vocabulary and clear grammar."
    ),
    "b1": (
        "Level B1: Reply in 2–3 short sentences. Use everyday vocabulary. "
        "Keep it clear and not too long."
    ),
    "b2": (
        "Level B2: Reply in 2–4 sentences. Natural and clear. "
        "Avoid being long-winded."
    ),
    "c1": (
        "Level C1: You may reply in 2–4 sentences with natural, varied language. "
        "Still keep replies concise."
    ),
}


class LMStudioClient:
    """Wrapper around LM Studio's OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = (
            str(settings.lmstudio_base_url).rstrip("/")
            if settings.lmstudio_base_url
            else "http://localhost:1234"
        )
        self._api_key = settings.lmstudio_api_key
        self._model = settings.lmstudio_model
        self._extra_system = settings.lm_system_prompt_extra
        self._timeout = float(settings.request_timeout_seconds)
        self._http = httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        """Close the underlying HTTP client. Safe to call multiple times."""
        await self._http.aclose()

    async def __aenter__(self) -> LMStudioClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def build_messages(
        self,
        history: list[dict[str, str]],
        topic_context: str | None = None,
        topic_level: str | None = None,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        system = system_prompt or _DEFAULT_SYSTEM
        if topic_context:
            system += (
                f"\n\nCurrent conversation topic: {topic_context}. "
                "Keep your replies closely related to this topic and to the user's last message. "
                "Ask short follow-up questions about what the user just said, instead of changing the subject."
            )
        level_key = (topic_level or "").strip().lower()
        if level_key in _LEVEL_INSTRUCTIONS:
            system += f"\n\n{_LEVEL_INSTRUCTIONS[level_key]}"
        if self._extra_system:
            system += f"\n\n{self._extra_system.strip()}"
        return [{"role": "system", "content": system}, *history]

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> AsyncIterator[str]:
        """Call LM Studio in streaming mode and yield text chunks."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        t0 = time.monotonic()
        token_count = 0
        try:
            async with self._http.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (
                        chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                    )
                    if delta:
                        token_count += 1
                        yield delta
        except httpx.HTTPStatusError:
            log.exception(
                "LM Studio returned error (elapsed=%.1fs)",
                time.monotonic() - t0,
            )
            raise
        except httpx.RequestError:
            log.exception(
                "LM Studio request failed (elapsed=%.1fs)",
                time.monotonic() - t0,
            )
            raise
        else:
            elapsed = time.monotonic() - t0
            log.debug(
                "LM stream done: %d chunks in %.1fs (%.0f chunks/s)",
                token_count,
                elapsed,
                token_count / elapsed if elapsed > 0 else 0,
            )

    async def generate_text(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        """Non-streaming version — returns full text (used for scoring)."""
        chunks: list[str] = []
        async for chunk in self.generate_stream(messages, temperature, max_tokens):
            chunks.append(chunk)
        return "".join(chunks)
