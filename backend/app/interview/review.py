"""Review cards: go back over the corrections of past sessions until they stick.

Each NOTE becomes a card: you see the question and what you said, say it better from memory, then
the NOTE is revealed. Each phrase skipped in a completed session becomes a card too: answer the
question using it. You grade yourself ("Nhớ được" / "Chưa nhớ"); the app only suggests a grade from
objective checks (word overlap with the NOTE, phrase detected), never from an LLM.
Scheduling is a Leitner system: remembered cards come back after longer and longer gaps.
See docs/features/review.md.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.interview.units import units_by_id
from app.services import history
from app.utils.compare import compare
from app.utils.parsing import used_phrase_indices

INTERVALS = [1, 3, 7, 14, 30, 60]  # days until the next review after box 1, 2, ... 6
LEARNED_BOX = 4  # passed the 14-day gap: counted as learned
GOOD_OVERLAP = 0.8  # share of NOTE words said that suggests "remembered"
MAX_NOTE_WORDS = 30  # a longer NOTE is a paragraph, too long to say back from memory


def schedule(box: int, result: str, today: date) -> tuple[int, date]:
    """New (box, due date) after a review. Forgotten cards start over and come back tomorrow."""
    if result == "again":
        return 0, today + timedelta(days=1)
    box = min(box + 1, len(INTERVALS))
    return box, today + timedelta(days=INTERVALS[box - 1])


def worth_a_card(said: str, note: str) -> bool:
    """A NOTE that repeats the answer word for word teaches nothing; a very long one cannot be
    recalled (stored NOTEs on 11/10/2026: 5 to 19 words, one of 38)."""
    return len(note.split()) <= MAX_NOTE_WORDS and compare(note, said)["accuracy"] < 1.0


def check_attempt(card: dict, heard: str) -> dict:
    """Objective checks of one spoken attempt, and the grade they suggest."""
    if card["kind"] == "phrase":
        unit = units_by_id.get(card["unit_id"])
        used = bool(unit) and card["phrase_index"] in used_phrase_indices(heard, unit["phrases"])
        return {"heard": heard, "phrase_used": used, "suggest": "good" if used else "again"}
    result = compare(card["target"], heard)
    return {
        "heard": heard,
        **result,
        "suggest": "good" if result["accuracy"] >= GOOD_OVERLAP else "again",
    }


def sync(uid: int, today: date) -> int:
    """Create the user's cards for NOTEs and skipped phrases that do not have one yet; returns how many."""
    added = 0
    for t in history.note_turns_without_card(uid):
        if worth_a_card(t["answer"], t["note"]):
            card = {
                "kind": "note", "session_id": t["session_id"], "turn_id": t["turn_id"],
                "unit_id": t["unit_id"], "question": t["question"], "said": t["answer"],
                "target": t["note"], "due": today.isoformat(),
            }  # fmt: skip
            added += history.add_card(uid, card) is not None
    for s in history.completed_sessions_used_phrases(uid):
        unit = units_by_id.get(s["unit_id"])
        if not unit:
            continue
        for i, p in enumerate(unit["phrases"]):
            if i in s["used"]:
                continue
            # Ask the main question that practises this phrase.
            q = next((q for q in unit["questions"] if i in q["phrases"]), unit["questions"][0])
            card = {
                "kind": "phrase", "session_id": s["session_id"], "unit_id": s["unit_id"],
                "phrase_index": i, "question": q["ask"], "target": p["say"], "due": today.isoformat(),
            }  # fmt: skip
            added += history.add_card(uid, card) is not None
    return added
