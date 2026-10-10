"""Các hàm thuần (không cần model/mạng) để dễ test.

- split_sections: tách đầu ra của LLM theo nhãn RETRY / SAY / ASK / NOTE (kể cả khi mới stream được một nửa)
- ready_sentences: lấy các câu SAY đã hoàn chỉnh để đẩy sang TTS ngay
- speech_metrics: chỉ số khách quan từ mốc thời gian từng từ của Whisper
- used_phrase_indices: người học đã dùng mẫu câu mục tiêu nào
- wer: tỉ lệ từ sai, dùng để so cấu hình STT
"""

from __future__ import annotations

import re

_LABEL = re.compile(r"(?im)^[ \t*#]*(RETRY|SAY|ASK|NOTE)[ \t*]*:[ \t*]*")
_SENT_END = re.compile(r"(?<=[.!?…])\s+")

# Từ chức năng: Whisper thường cho xác suất thấp dù nghe đúng, nên không đưa vào "nghe chưa chắc".
FUNCTION_WORDS = set(
    """a an the and or but so to of in on at for with from by as is am are was were be been
    i i'm i've me my you your we our it it's that this there they he she his her them
    do did does have has had will would can could um uh like just also very""".split()
)
SHORT_ANSWER_WORDS = 10  # dưới mức này tốc độ nói quá nhiễu, không tính
LONG_PAUSE_S = 0.7


def split_sections(raw: str) -> dict[str, str]:
    """{'RETRY': 'no', 'SAY': '...', 'ASK': '...', 'NOTE': '...'} - chỉ gồm các nhãn đã xuất hiện."""
    matches = list(_LABEL.finditer(raw))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        out[m.group(1).upper()] = raw[m.end() : end].strip()
    return out


def ready_sentences(say: str, say_done: bool, emitted: int) -> tuple[list[str], int]:
    """Các câu hoàn chỉnh mới xuất hiện kể từ vị trí `emitted`.

    Một câu chỉ coi là xong khi đã thấy khoảng trắng sau dấu chấm câu,
    hoặc khi SAY kết thúc (say_done=True) thì lấy nốt phần đuôi.
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


def used_phrase_indices(text: str, phrases: list[dict]) -> list[int]:
    padded = f" {norm(text)} "
    return [
        i
        for i, p in enumerate(phrases)
        if any(f" {norm(m)} " in padded for m in p["match"])
    ]


def speech_metrics(words: list[dict]) -> dict:
    """words: [{'w','s','e','p'}] (từ, bắt đầu, kết thúc, xác suất nhận dạng).

    wpm: tính cả thời gian ngắt. wpm_speaking: bỏ các lần ngắt dài.
    Câu ngắn (dưới SHORT_ANSWER_WORDS từ) không tính tốc độ (None).
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


def word_errors(ref: str, hyp: str) -> tuple[int, int]:
    """(số lỗi thay/thêm/bớt, số từ tham chiếu) theo khoảng cách Levenshtein mức từ."""
    r, h = norm(ref).split(), norm(hyp).split()
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hw in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw))
        prev = cur
    return prev[-1], len(r)


def wer(ref: str, hyp: str) -> float:
    errors, n = word_errors(ref, hyp)
    return errors / max(n, 1)
