"""From a one-sentence answer to a longer one: the NOTE stays a short corrected sentence, and the
question's "steps" (data/units.json) show what to add next, each with a Vietnamese hint and an
English starter ("Vì sao?" / "That's because ..."). See docs/features/answer-steps.md.

- trim_invented(): the 7B model keeps adding reasons the learner never gave ("The main reason is
  that it provides real practice", 3/3 replays). That teaches a made-up answer and hides the
  missing step, so a sentence after the first, or a "because ..." clause, whose content words are
  mostly new is cut. The reason then shows up as an open step instead.
- mark_steps(): a step counts as done when the text says its starter, or the same move in other
  words ("because" gives a reason, "for instance" an example). No LLM involved.
"""

from __future__ import annotations

import re

from app.utils.parsing import norm

NEW_SHARE = 0.6  # a part is invented when at least this share of its content words is new
MIN_NEW = 2  # ... and at least this many (one new word is usually just a better word choice)
MIN_LEAD_WORDS = 2  # a shorter starter ("I'll ...") is too common to prove the step was said

# Words of 4+ letters that carry no content; shorter words are ignored anyway.
_FILLER = set(
    "that this these those with they them their there then than what when which would could should "
    "about also just very really more most much many some because think thing things make makes "
    "made does doing done have been being into from your mine will".split()
)

# Starters that make the same move: an answer with "because" already gives a reason.
SAME_MOVE = [
    ("because", "the reason", "that's why", "that is why"),
    ("for example", "for instance"),
    ("as a result", "in the end"),
]


def steps_for(unit: dict, q_index: int) -> list[dict]:
    return unit["questions"][q_index].get("steps", [])


def _lead(say: str) -> str:
    return norm(say.split("...")[0])


def _done(say: str, text: str) -> bool:
    lead = _lead(say)
    if len(lead.split()) >= MIN_LEAD_WORDS and f" {lead} " in text:
        return True
    return any(
        any(f" {m} " in f" {lead} " for m in move) and any(f" {m} " in text for m in move) for move in SAME_MOVE
    )


def mark_steps(steps: list[dict], text: str) -> list[dict]:
    padded = f" {norm(text)} "
    return [{"hint": st["hint"], "say": st["say"], "done": _done(st["say"], padded)} for st in steps]


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _content(text: str) -> list[str]:
    return [_stem(w) for w in norm(text).split() if len(w) >= 4 and w not in _FILLER]


def _invented(part: str, known: set[str], given: set[str]) -> bool:
    words = [w for w in _content(part) if w not in given]
    new = [w for w in words if w not in known]
    return len(new) >= MIN_NEW and len(new) >= NEW_SHARE * len(words)


def trim_invented(note: str, said: str, given: str) -> str:
    """Cut what the learner did not say. `said`: their answers and the questions they answered;
    `given`: text the app supplied (target phrases), whose words never count as new. An empty
    "because ..." the model left is cut too: the reason step asks for it."""
    known, giv = set(_content(said)), set(_content(given))
    out: list[str] = []
    for i, sentence in enumerate(re.split(r"(?<=[.!?])\s+", note.strip())):
        head, sep, reason = sentence.partition(" because")
        if sep and (_invented(reason, known, giv) or not norm(reason)):
            sentence = head.rstrip(" ,") + "."
        if i > 0 and _invented(sentence, known, giv):
            continue
        out.append(sentence)
    return " ".join(out)
