"""Session state and next-question logic. The app, not the LLM, drives the interview flow."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from app.core.config import FOLLOWUPS, MAX_RETRIES
from app.utils.parsing import is_question

STATE_FIELDS = ("q", "asked", "followups", "retries", "done", "history", "used", "speech")


@dataclass
class Session:
    unit: dict
    q: int = 0  # index of the current main question
    asked: str = ""  # question awaiting an answer (main, follow-up or re-ask)
    followups: int = 0
    retries: int = 0
    done: bool = False
    history: list[dict] = field(default_factory=list)  # [{"q", "a"}]
    used: set[int] = field(default_factory=set)
    speech: list[dict] = field(default_factory=list)  # speech metrics per spoken turn (for the summary)
    prev: dict | None = None  # state before the last turn, for the undo button
    history_id: int | None = None  # sessions row in the history DB (None when history is off)
    last_turn_id: int | None = None  # turns row of the last answered turn, deleted on undo
    shadow_target: str | None = None  # NOTE sentence the next recording is compared against
    last_speech: dict | None = None  # speech metrics of the last spoken answer, shown next to shadowing

    def snapshot(self) -> dict:
        return {k: copy.deepcopy(getattr(self, k)) for k in STATE_FIELDS}

    def restore(self, snap: dict) -> None:
        for k, v in snap.items():
            setattr(self, k, v)


def next_step(s: Session, secs: dict[str, str]) -> tuple[str, bool]:
    """Decide what the interviewer says next. Returns (text, use_tts_cache)."""
    retry = secs.get("RETRY", "").lower().startswith("yes")
    ask = secs.get("ASK", "").strip()
    main = s.unit["questions"][s.q]
    if retry and s.retries < MAX_RETRIES:
        # Re-ask with a prewritten question (the 7B model copies few-shot questions when it rephrases).
        s.retries += 1
        if s.asked in (main["ask"], main["simple"]):
            s.asked = main["simple"]
            return s.asked, True
        return s.asked, False  # on a follow-up: repeat it as is
    if not retry and is_question(ask) and s.followups < FOLLOWUPS:
        s.followups += 1
        s.asked = ask
        return ask, False
    s.q, s.followups, s.retries = s.q + 1, 0, 0
    questions = s.unit["questions"]
    if s.q < len(questions):
        s.asked = questions[s.q]["ask"]
        return s.asked, True
    s.q, s.done = len(questions) - 1, True
    return s.unit["closing"], True


def progress(s: Session) -> dict:
    n = len(s.unit["questions"])
    return {"type": "progress", "q": s.q + 1, "n": n, "done": s.done}


def summary(s: Session) -> dict:
    timed = [m for m in s.speech if m["wpm"]]
    avg = lambda k: round(sum(m[k] for m in timed) / len(timed)) if timed else None  # noqa: E731
    phrases = s.unit["phrases"]
    return {
        "type": "summary",
        "turns": len(s.history),
        "questions": len(s.unit["questions"]),
        "phrases_used": [p["say"] for i, p in enumerate(phrases) if i in s.used],
        "phrases_missed": [p["say"] for i, p in enumerate(phrases) if i not in s.used],
        "wpm": avg("wpm"),
        "wpm_speaking": avg("wpm_speaking"),
        "long_pauses": sum(m["long_pauses"] for m in s.speech),
        "spoken_turns": len(s.speech),
    }
