from __future__ import annotations

import difflib
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.core.config import get_settings
from app.core.ielts_levels import format_ielts_band, resolve_ielts_band

log = logging.getLogger(__name__)

_DEFAULT_SYSTEM = """You are a supportive **English speaking teacher** helping the learner practise IELTS Speaking (Parts 1–3).
You are not a silent exam examiner: you react, coach, and keep the chat going.

Every reply MUST use this exact format (no extra labels, no markdown):

SAY:
<spoken English only — this is read aloud>

NOTE:
<Vietnamese coaching note — never spoken aloud>

RETRY:
yes

or

RETRY:
no

Judge the learner's last line against YOUR last question (the one they should answer now).

Set RETRY: yes only when the reply is not a real answer yet:
- off-topic / does not address the question
- too thin to count (only yes/no, one word, "I don't know" with no try)
- mostly Vietnamese or not English
- empty, inaudible, or nonsense
- clearly misunderstood the question

Do NOT retry for grammar, tense, or wording mistakes if they did answer the question — recast and continue.

If RETRY is no:
- SAY: 2–4 short sentences: react, recast at most one issue, then one new follow-up.
- NOTE: 1–2 short Vietnamese sentences (fix or a useful tip). You may quote a short English phrase.

If RETRY is yes:
- SAY: do NOT ask a new question. Say the answer was not enough, repeat the SAME question, and give one short English model they can adapt.
- NOTE: 3–5 short Vietnamese sentences: (1) vì sao chưa ổn (2) cần nói những ý gì (3) khung câu / ví dụ tiếng Anh trong ngoặc kép. Cụ thể, đừng chung chung. Remind them to speak again now.

Stay on the topic. If they switch topics, treat that as RETRY: yes and guide back to the question.
If they speak Vietnamese, understand it but SAY stays English."""

OPENING_SYSTEM = """You start an IELTS speaking practice chat as a friendly teacher.
Reply with 1–2 short English sentences only: greet the learner and ask one question.
Do not use SAY/NOTE labels. No Vietnamese. No corrections yet."""

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

def _ielts_tutor_instruction(band: float) -> str:
    """How the AI should shape its turns for the learner's IELTS Speaking target band."""
    label = format_ielts_band(band)
    if band <= 5.0:
        return (
            f"IELTS Speaking target Band {label}. "
            "If RETRY is no: SAY one or two very short sentences (about 10–22 words). "
            "If RETRY is yes: SAY may be a bit longer so you can repeat the question and give a model. "
            "NOTE: Vietnamese, very simple; include a full example sentence in quotes."
        )
    if band <= 6.0:
        return (
            f"IELTS Speaking target Band {label}. "
            "SAY: 2–3 short sentences, everyday vocabulary, one follow-up. "
            "NOTE: one clear Vietnamese tip (grammar or a natural phrase)."
        )
    if band <= 7.0:
        return (
            f"IELTS Speaking target Band {label}. "
            "SAY: 2–4 sentences, natural linkers, a focused follow-up. "
            "NOTE: a precise Vietnamese tip (collocation, tense, or how to extend)."
        )
    return (
        f"IELTS Speaking target Band {label}. "
        "SAY: 2–4 fluent spoken sentences, not essay-like. "
        "NOTE: a short Vietnamese nuance tip (more natural wording or a stronger idea)."
    )


_SAY_NOTE_RE = re.compile(
    r"(?is)^\s*(?:SAY\s*:)?\s*(.*?)\s+(?:NOTE|LƯU Ý|LUU Y)\s*:\s*(.+)\s*$"
)
_RETRY_LINE_RE = re.compile(
    r"(?im)^\s*RETRY\s*:\s*(yes|no|true|false|1|0)\s*$"
)
_STORED_NOTE_RE = re.compile(
    r"\n\n> \*\*(?:Lưu ý|Thử lại):\*\* .+\s*\Z", re.DOTALL
)
_RETRY_YES = frozenset({"yes", "true", "1"})


def parse_tutor_retry(raw: str) -> bool:
    """True when the model marked this turn as a must-retry."""
    matches = list(_RETRY_LINE_RE.finditer(raw or ""))
    if not matches:
        return False
    return matches[-1].group(1).lower() in _RETRY_YES


def _strip_retry_lines(raw: str) -> str:
    return _RETRY_LINE_RE.sub("", raw or "").strip()


def split_tutor_reply(raw: str) -> tuple[str, str]:
    """Parse SAY/NOTE tutor output into (spoken English, Vietnamese coach note)."""
    text = _strip_retry_lines(raw)
    if not text:
        return "", ""
    m = _SAY_NOTE_RE.match(text)
    if not m:
        spoken = _LEADING_SAY_RE.sub("", text).strip()
        return spoken or text, ""
    spoken = _LEADING_SAY_RE.sub("", m.group(1).strip()).strip()
    note = m.group(2).strip()
    return spoken or text, note


def parse_tutor_reply(raw: str) -> tuple[str, str, bool]:
    """Return (spoken English, Vietnamese note, must_retry)."""
    return (*split_tutor_reply(raw), parse_tutor_retry(raw))


_PARTIAL_CUT_RE = re.compile(r"(?im)^\s*(?:NOTE|LƯU Ý|LUU Y|RETRY)\s*:")
_LEADING_SAY_RE = re.compile(r"(?is)^\s*SAY\s*:\s*")
_FIRST_SENT_RE = re.compile(r"^(.+?[.!?…])(\s+|$)", re.DOTALL)


def spoken_prefix_from_partial(raw: str) -> tuple[str, bool]:
    """Spoken English seen so far while the model is still streaming. done=NOTE/RETRY started."""
    text = raw or ""
    cut = _PARTIAL_CUT_RE.search(text)
    done = cut is not None
    body = text[: cut.start()] if cut else text
    body = _LEADING_SAY_RE.sub("", body).strip()
    return body, done


def first_flushable_sentence(spoken: str, *, section_done: bool) -> str | None:
    """First SAY sentence ready to TTS, or the whole SAY once that section finishes."""
    spoken_s = (spoken or "").strip()
    if not spoken_s:
        return None
    m = _FIRST_SENT_RE.match(spoken_s)
    if m:
        sentence = m.group(1).strip()
        words = sentence.split()
        has_more = bool(m.group(2)) and len(spoken_s) > len(sentence) + 2
        if section_done or has_more or len(words) >= 5 or len(sentence) >= 28:
            return sentence
        return None
    if section_done and len(spoken_s) >= 8:
        return spoken_s
    return None


def format_tutor_display(spoken: str, note: str, *, retry: bool = False) -> str:
    """Chat bubble text: spoken reply plus a markdown coach note."""
    spoken_s = (spoken or "").strip()
    note_s = (note or "").strip()
    if not note_s:
        return spoken_s
    label = "Thử lại" if retry else "Lưu ý"
    return f"{spoken_s}\n\n> **{label}:** {note_s}"


def spoken_from_stored_assistant(text: str) -> str:
    """Drop the displayed coach note so LM history stays spoken English only."""
    return _STORED_NOTE_RE.sub("", (text or "").strip()).strip()


class OpenAIClient:
    """Wrapper around OpenAI-compatible chat-completions endpoint."""

    def __init__(self) -> None:
        settings = get_settings()
        base_url = (
            str(settings.openai_base_url).strip() if settings.openai_base_url else ""
        )
        if base_url and not base_url.rstrip("/").endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        self._api_key = settings.openai_api_key or "lm-studio"
        self._model = settings.openai_model
        self._extra_system = settings.lm_system_prompt_extra
        self._timeout = float(settings.request_timeout_seconds)
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=base_url.rstrip("/") if base_url else None,
            timeout=self._timeout,
        )

    async def aclose(self) -> None:
        """Close the underlying SDK client. Safe to call multiple times."""
        await self._client.close()

    async def __aenter__(self) -> OpenAIClient:
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
        band = resolve_ielts_band(topic_level)
        if band is not None:
            system += f"\n\n{_ielts_tutor_instruction(band)}"
        if self._extra_system:
            system += f"\n\n{self._extra_system.strip()}"
        return [{"role": "system", "content": system}, *history]

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 256,
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Call OpenAI-compatible endpoint in streaming mode and yield text chunks."""
        req_model = (model.strip() if model else None) or self._model
        t0 = time.monotonic()
        token_count = 0
        try:
            stream = await self._client.chat.completions.create(
                model=req_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    token_count += 1
                    yield delta
        except OpenAIError:
            log.exception(
                "OpenAI endpoint returned error (elapsed=%.1fs)",
                time.monotonic() - t0,
            )
            raise
        except Exception:
            log.exception(
                "OpenAI request failed (elapsed=%.1fs)",
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
        *,
        model: str | None = None,
    ) -> str:
        """Non-streaming version — returns full text (used for scoring)."""
        req_model = (model.strip() if model else None) or self._model
        response = await self._client.chat.completions.create(
            model=req_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not response.choices:
            return ""
        content = response.choices[0].message.content
        return content if isinstance(content, str) else ""

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


# Backward compatibility for old imports.
LMStudioClient = OpenAIClient
