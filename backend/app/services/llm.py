"""Streamed LLM calls to LM Studio (OpenAI-compatible API)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core import config

_client = AsyncOpenAI(base_url=config.LM_URL, api_key="lm-studio")


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
