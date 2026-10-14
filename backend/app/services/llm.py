"""Streamed LLM calls to LM Studio (OpenAI-compatible API)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core import config

_client = AsyncOpenAI(base_url=config.LM_URL, api_key="lm-studio")


async def complete_json(messages: list[dict], schema: dict, max_tokens: int, temperature: float = 0.6) -> str:
    """One non-streamed reply forced to match a JSON schema (LM Studio's structured output)."""
    reply = await _client.chat.completions.create(
        model=config.LM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_schema", "json_schema": {"name": "draft", "strict": True, "schema": schema}},
        timeout=300,
    )
    return reply.choices[0].message.content or ""


async def stream_reply(messages: list[dict]) -> AsyncIterator[str]:
    extra = {"seed": int(config.LM_SEED)} if config.LM_SEED else {}
    stream = await _client.chat.completions.create(
        model=config.LM_MODEL,
        messages=messages,
        temperature=config.LM_TEMPERATURE,
        max_tokens=config.MAX_REPLY_TOKENS,
        stream=True,
        **extra,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
