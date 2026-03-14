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
    "Stay on the topic. "
    "If the user speaks in Vietnamese or mixes Vietnamese with English, still understand what they mean and respond only in English; kindly encourage them to try saying it in English for practice (e.g. 'I get what you mean! Try saying that in English—even a simple sentence is great practice.')."
)

# Guidelines for different topic levels
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

    def build_messages(
        self,
        history: list[dict[str, str]],
        topic_context: str | None = None,
        topic_level: str | None = None,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        settings = get_settings()
        system = system_prompt or _DEFAULT_SYSTEM
        if topic_context:
            system += f"\n\nCurrent conversation topic: {topic_context}"
        level_key = (topic_level or "").strip().lower()
        if level_key in _LEVEL_INSTRUCTIONS:
            system += f"\n\n{_LEVEL_INSTRUCTIONS[level_key]}"
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
