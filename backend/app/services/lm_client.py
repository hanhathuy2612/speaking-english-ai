from __future__ import annotations

import difflib
import json
import logging
import re
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

_TRANSCRIPT_NORMALIZE_SYSTEM = """You fix obvious speech-to-text (ASR) mistakes only.

Output exactly ONE line — the same utterance the speaker said. No quotes, labels, or explanation.

Rules (strict):
- Prefer returning the input byte-for-byte if it is understandable.
- Only fix clear typos / one obvious misheard word (same meaning, same sentence).
- Same words in the same order whenever possible. Do not reorder clauses.
- Do NOT add words, filler, or new sentences. Do NOT remove words except obvious ASR noise tokens.
- Do NOT “improve” grammar, style, or translate. Do NOT answer questions or finish the user’s idea.
- Do NOT invent scenarios, dialogs, or content not present in the raw line.
- If unsure, return the raw line unchanged.

If the input is empty or "(inaudible)", return it as given."""

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

    async def normalize_transcript(
        self,
        raw: str,
        *,
        topic_context: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Repair ASR text only; caller should fall back to `raw` on failure."""
        settings = get_settings()
        t = (
            temperature
            if temperature is not None
            else float(settings.lm_normalize_temperature)
        )
        mt = (
            max_tokens
            if max_tokens is not None
            else int(settings.lm_normalize_max_tokens)
        )
        raw_wc = len(raw.strip().split())
        # Tight cap: normalizer must not emit a long invented reply.
        mt = min(mt, max(24, raw_wc * 4 + 20))
        include_ctx = settings.lm_normalize_include_topic_context and (
            topic_context or ""
        ).strip()
        if include_ctx:
            ctx = (topic_context or "").strip()
            user = f"Topic context (homophone hints only; do not quote or expand):\n{ctx}\n\nRaw ASR transcript:\n{raw.strip()}"
        else:
            user = f"Raw ASR transcript:\n{raw.strip()}"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _TRANSCRIPT_NORMALIZE_SYSTEM},
            {"role": "user", "content": user},
        ]
        out = await self.generate_text(messages, temperature=t, max_tokens=mt)
        return _normalize_transcript_cleanup(out)


def _squish_for_compare(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return " ".join(s.split())


def transcript_normalization_plausible(
    raw: str,
    normalized: str,
    *,
    min_similarity: float = 0.65,
) -> bool:
    """
    Reject LLM output that is unrelated to the STT line (hallucinations).
    Keeps fixes like yea→yes when similarity stays high.
    """
    raw_s = raw.strip()
    norm_s = normalized.strip()
    if not raw_s or not norm_s:
        return False
    if raw_s.casefold() == norm_s.casefold():
        return True
    # Block huge length inflation (model wrote a different passage)
    if len(norm_s) > max(int(len(raw_s) * 1.35), len(raw_s) + 60):
        return False
    a = _squish_for_compare(raw_s)
    b = _squish_for_compare(norm_s)
    if not a:
        return True
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio < min_similarity:
        return False
    rw = len(a.split())
    nw = len(b.split())
    if rw <= 8 and nw > rw * 2 + 8:
        return False
    if rw <= 3 and nw > rw + 6:
        return False
    # Too many content words in output that never appeared in STT (hallucinated clause)
    aw = a.split()
    bw = b.split()
    if aw:
        raw_set = set(aw)
        novel = [w for w in bw if w not in raw_set and len(w) > 2]
        if len(novel) > max(2, min(6, rw // 2)):
            return False
    return True


def _normalize_transcript_cleanup(text: str) -> str:
    s = text.strip()
    if not s:
        return s
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        s = s[1:-1].strip()
    return s
