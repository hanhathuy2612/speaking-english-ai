"""Compare what the learner said with a reference sentence, word by word.

Both sides are normalized first so that differences in *writing* are not counted as mistakes:
digits vs words ("5" / "five", "30%" / "thirty percent", "10,000" / "ten thousand"), contractions
("I've" / "I have"), case, punctuation and hyphens. What remains are differences in what was
actually heard, which for the learner mostly means pronunciation (dropped -s / -ed, "cache" -> "kit").

Used by shadowing (docs/features/shadowing.md) and by the STT benchmark's WER.
"""

from __future__ import annotations

import re

ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen"
).split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()

CONTRACTIONS = {
    "i'm": "i am", "i've": "i have", "i'll": "i will", "i'd": "i would",
    "you're": "you are", "you've": "you have", "we're": "we are", "we've": "we have",
    "they're": "they are", "they've": "they have", "he's": "he is", "she's": "she is",
    "it's": "it is", "that's": "that is", "what's": "what is", "there's": "there is",
    "let's": "let us", "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "can't": "can not", "cannot": "can not",
    "won't": "will not", "wouldn't": "would not", "couldn't": "could not", "shouldn't": "should not",
}  # fmt: skip


def number_words(n: int) -> list[str]:
    """English words for 0 <= n < 1,000,000 ("ten thousand", "one hundred twenty")."""
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10]] + (number_words(n % 10) if n % 10 else [])
    if n < 1000:
        return [ONES[n // 100], "hundred"] + (number_words(n % 100) if n % 100 else [])
    if n < 1_000_000:
        return number_words(n // 1000) + ["thousand"] + (number_words(n % 1000) if n % 1000 else [])
    return [str(n)]


def word_tokens(word: str) -> list[str]:
    """Normalize one written word into the tokens it is pronounced as."""
    w = word.lower().replace("’", "'").strip()
    percent = w.rstrip(".,!?;:").endswith("%")
    w = re.sub(r"(?<=\d),(?=\d{3})", "", w)  # 10,000 -> 10000
    out: list[str] = []
    for part in re.split(r"[-–—/]", w):
        part = re.sub(r"[^a-z0-9']", "", part).strip("'")
        if not part:
            continue
        if part.isdigit():
            out += number_words(int(part))
        else:
            out += CONTRACTIONS.get(part, part).split()
    if percent:
        out.append("percent")
    return out


def tokens(text: str) -> list[str]:
    return [t for w in text.split() for t in word_tokens(w)]


def _align(ref: list[str], hyp: list[str]) -> list[tuple[str, int | None, int | None]]:
    """Word-level Levenshtein alignment: [(op, ref_index, hyp_index)], op in ok/sub/del/ins."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    ops: list[tuple[str, int | None, int | None]] = []
    i, j = n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            ops.append(("ok" if ref[i - 1] == hyp[j - 1] else "sub", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            ops.append(("del", i - 1, None))
            i -= 1
        else:
            ops.append(("ins", None, j - 1))
            j -= 1
    return ops[::-1]


def compare(reference: str, heard: str) -> dict:
    """Per reference word: ok / wrong (with what was heard) / miss; extra words the learner added.

    Returns {"items": [{"kind": "word", "text", "status", "heard"} | {"kind": "extra", "text"}],
             "correct", "total", "accuracy"} where counts are over normalized tokens.
    """
    ref_words = reference.split()
    owner: list[int] = []  # normalized ref token -> index of the written word it came from
    ref: list[str] = []
    for k, w in enumerate(ref_words):
        for t in word_tokens(w):
            ref.append(t)
            owner.append(k)
    hyp = tokens(heard)

    per_word: list[list[tuple[str, str | None]]] = [[] for _ in ref_words]
    extras: dict[int, list[str]] = {}  # after written word index (-1 = before the first) -> words
    last = -1
    ops_all = _align(ref, hyp)
    for op, i, j in ops_all:
        if op == "ins":
            extras.setdefault(last, []).append(hyp[j])
            continue
        last = owner[i]
        per_word[last].append((op, hyp[j] if j is not None else None))

    items: list[dict] = []
    if -1 in extras:
        items.append({"kind": "extra", "text": " ".join(extras[-1])})
    for k, w in enumerate(ref_words):
        ops = per_word[k]
        if ops:  # words with no tokens (stray punctuation) are skipped
            if all(op == "ok" for op, _ in ops):
                status, said = "ok", None
            elif all(op == "del" for op, _ in ops):
                status, said = "miss", None
            else:
                status, said = "wrong", " ".join(h for _, h in ops if h)
            items.append({"kind": "word", "text": w, "status": status, "heard": said})
        if k in extras:
            items.append({"kind": "extra", "text": " ".join(extras[k])})

    correct = sum(1 for op, _, _ in ops_all if op == "ok")
    return {
        "items": items,
        "correct": correct,
        "total": len(ref),
        "accuracy": round(correct / len(ref), 3) if ref else 0.0,
    }


def word_errors(ref: str, hyp: str) -> tuple[int, int]:
    """(substitutions + insertions + deletions, reference token count) after normalization."""
    r, h = tokens(ref), tokens(hyp)
    return sum(op != "ok" for op, _, _ in _align(r, h)), len(r)


def wer(ref: str, hyp: str) -> float:
    errors, n = word_errors(ref, hyp)
    return errors / max(n, 1)


# Words that carry a checkable fact. "one" is left out: it is usually a pronoun ("the one", "no one").
# Time units catch "a few months ago" -> "a few years ago" (2/3 NOTEs in one replay); "day" is
# left out: "every day", "during the day" are ordinary rewording.
FACT_WORDS = (
    set(ONES[2:] + TENS[2:] + ["zero", "hundred", "thousand", "million", "percent"])
    | set("monday tuesday wednesday thursday friday saturday sunday".split())
    | set("january february march april may june july august september october november december".split())
    | set("today tomorrow yesterday tonight".split())
    | set("minute minutes hour hours week weeks month months year years".split())
)


def invented_facts(note: str, said: str) -> list[str]:
    """Numbers, days, months, time units and relative dates in `note` that never appear in `said`.

    Both sides are normalized like shadowing ("5" == "five", "30%" == "thirty percent").
    "may" counts only when it is not the modal verb, which cannot be told apart here, so it is ignored.
    """
    known = set(tokens(said))
    out: list[str] = []
    for t in tokens(note):
        if t in FACT_WORDS and t != "may" and t not in known and t not in out:
            out.append(t)
    return out
