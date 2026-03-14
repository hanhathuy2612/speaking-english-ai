import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings

# Default system prompt: natural, conversational tone (length can vary)
_DEFAULT_SYSTEM = (
    "You are a friendly English conversation partner. "
    "Sound natural and relaxed, like talking to a friend—not like a textbook or a formal teacher. "
    "Use everyday language, contractions (I'm, that's), and a warm tone. "
    "It's fine to reply in 2–4 sentences when it fits the flow. Avoid lists, bullet points, or stiff phrases. "
    "If the user makes a small mistake, you can gently correct in a natural way. "
    "Stay on the topic."
)


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

    def build_messages(
        self,
        history: list[dict[str, str]],
        topic_context: str | None = None,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        settings = get_settings()
        system = system_prompt or _DEFAULT_SYSTEM
        if topic_context:
            system += f"\n\nCurrent conversation topic: {topic_context}"
        if settings.lm_system_prompt_extra:
            system += f"\n\n{settings.lm_system_prompt_extra.strip()}"
        return [{"role": "system", "content": system}, *history]

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> AsyncIterator[str]:
        """Call LM Studio in streaming mode and yield text chunks."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
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
                        yield delta

    async def generate_text(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        """Non-streaming version - returns full text (used for scoring)."""
        full = ""
        async for chunk in self.generate_stream(messages, temperature, max_tokens):
            full += chunk
        return full
