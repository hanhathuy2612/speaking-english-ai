"""Pure functions (no model or network), easy to test.

- split_sections: split LLM output by the RETRY / SAY / ASK / NOTE labels (works mid-stream)
- ready_sentences: complete SAY sentences that can go to TTS right away
- speech_metrics: objective metrics from Whisper word timestamps
- used_phrase_indices: which target phrases the learner used
- has_vietnamese: Whisper output that is Vietnamese text
- has_cjk: LLM output that drifted into Chinese (or Japanese/Korean)
"""

from __future__ import annotations

import re

_LABEL = re.compile(r"(?im)^[ \t*#]*(RETRY|SAY|ASK|NOTE)[ \t*]*:[ \t*]*")
_SENT_END = re.compile(r"(?<=[.!?…])\s+")

# Function words: Whisper gives them low probability even when correct, so they are excluded from low_conf.
FUNCTION_WORDS = set(
    """a an the and or but so to of in on at for with from by as is am are was were be been
    i i'm i've me my you your we our it it's that this there they he she his her them
    do did does have has had will would can could um uh like just also very""".split()
)
SHORT_ANSWER_WORDS = 10  # below this, speaking rate is too noisy to report
LONG_PAUSE_S = 0.7


def split_sections(raw: str) -> dict[str, str]:
    """{'RETRY': 'no', 'SAY': '...', 'ASK': '...', 'NOTE': '...'} - only labels seen so far."""
    matches = list(_LABEL.finditer(raw))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        out[m.group(1).upper()] = raw[m.end() : end].strip()
    return out


def ready_sentences(say: str, say_done: bool, emitted: int) -> tuple[list[str], int]:
    """New complete sentences since position `emitted`.

    A sentence counts as complete once whitespace follows its punctuation,
    or when SAY has ended (say_done=True), which flushes the tail.
    """
    rest = say[emitted:]
    sentences: list[str] = []
    pos = 0
    for m in _SENT_END.finditer(rest):
        s = rest[pos : m.start()].strip()
        if s:
            sentences.append(s)
        pos = m.end()
    emitted += pos
    if say_done:
        tail = rest[pos:].strip()
        if tail:
            sentences.append(tail)
        emitted = len(say)
    return sentences, emitted


def is_question(text: str) -> bool:
    t = text.strip()
    return t.endswith("?") and len(t.split()) >= 3 and t.upper() != "NEXT"


def norm(text: str) -> str:
    t = text.lower().replace("’", "'")
    return " ".join(re.sub(r"[^a-z0-9' ]+", " ", t).split())


# Letters that only Vietnamese uses (plain accented vowels like é also appear in English loanwords).
_VIETNAMESE = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.IGNORECASE)


# Qwen sometimes switches to Chinese mid-sentence; such text must never be shown or spoken.
_CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿가-힯＀-￯]")


def has_cjk(text: str) -> bool:
    """True when the LLM output contains Chinese, Japanese or Korean characters."""
    return bool(_CJK.search(text))


def has_vietnamese(text: str) -> bool:
    """True when Whisper wrote Vietnamese text even though it was told the audio is English."""
    return bool(_VIETNAMESE.search(text))


def used_phrase_indices(text: str, phrases: list[dict]) -> list[int]:
    padded = f" {norm(text)} "
    return [
        i
        for i, p in enumerate(phrases)
        if any(f" {norm(m)} " in padded for m in p["match"])
    ]


def hesitation_pauses(words: list[dict]) -> int:
    """Long pauses (> LONG_PAUSE_S) inside a sentence. A pause after ".", "?" or "!" is a natural
    sentence break: fluent speech has them too (edge-tts reading 217 words: 11 long pauses, 0 inside
    a sentence), so only the others count as hesitation."""
    return sum(
        1
        for a, b in zip(words, words[1:])
        if b["s"] - a["e"] > LONG_PAUSE_S and not a["w"].rstrip().endswith((".", "?", "!"))
    )


def speech_metrics(words: list[dict]) -> dict:
    """words: [{'w','s','e','p'}] (word, start, end, recognition probability).

    wpm: includes pauses. wpm_speaking: excludes long pauses.
    Short answers (under SHORT_ANSWER_WORDS words) get no rate (None).
    """
    if not words:
        return {"words": 0, "wpm": None, "wpm_speaking": None, "long_pauses": 0, "low_conf": []}
    duration = max(words[-1]["e"] - words[0]["s"], 0.1)
    gaps = [b["s"] - a["e"] for a, b in zip(words, words[1:])]
    long_gaps = [g for g in gaps if g > LONG_PAUSE_S]
    low_conf: list[str] = []
    for w in words:
        shown = w["w"].strip(" ,.?!")
        clean = norm(shown)
        if w["p"] < 0.5 and clean and clean not in FUNCTION_WORDS and shown not in low_conf:
            low_conf.append(shown)
    short = len(words) < SHORT_ANSWER_WORDS
    speaking = max(duration - sum(long_gaps), 0.1)
    return {
        "words": len(words),
        "wpm": None if short else round(len(words) / duration * 60),
        "wpm_speaking": None if short else round(len(words) / speaking * 60),
        "long_pauses": len(long_gaps),
        "low_conf": low_conf[:6],
    }
