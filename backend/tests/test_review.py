"""Review cards: schedule, creation from history, grading (temporary SQLite file)."""

from datetime import date

import pytest

from app.core import config
from app.interview import review
from app.interview.units import units_by_id
from app.services import history

TODAY = date(2026, 10, 11)
UNIT = units_by_id["weekend"]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(config, "HISTORY_DB", "history.db")
    history.init()


def answer(sid, text, note, used=(), unclear=0):
    return history.add_turn(sid, {"question": "How was your weekend?", "answer": text, "source": "voice",
                                  "note": note, "used_phrases": list(used), "unclear": unclear})  # fmt: skip


def test_schedule_grows_the_gap_and_starts_over_when_forgotten():
    box, due = 0, TODAY
    gaps = []
    for _ in range(7):
        box, due2 = review.schedule(box, "good", due)
        gaps.append((due2 - due).days)
        due = due2
    assert gaps == [1, 3, 7, 14, 30, 60, 60]
    assert review.schedule(5, "again", TODAY) == (0, date(2026, 10, 12))


def test_notes_become_cards_except_repeats_and_unclear_answers(db):
    sid = history.start_session(UNIT)
    answer(sid, "I go to beach on Saturday.", "On Saturday, I went to the beach.")
    answer(sid, "On Saturday, I went to the beach.", "On Saturday, I went to the beach.")  # nothing to learn
    answer(sid, "mumble", "Something.", unclear=1)
    answer(sid, "Long story.", " ".join(["word"] * 31))  # too long to recall
    assert review.sync(TODAY) == 1
    assert review.sync(TODAY) == 0  # idempotent
    [card] = history.list_cards(due_by=TODAY.isoformat())
    assert card["kind"] == "note" and card["said"] == "I go to beach on Saturday." and card["box"] == 0


def test_undoing_a_turn_removes_its_card(db):
    sid = history.start_session(UNIT)
    tid = answer(sid, "I go to beach.", "I went to the beach.")
    review.sync(TODAY)
    history.delete_turn(tid)
    assert history.list_cards(due_by=TODAY.isoformat()) == []


def test_skipped_phrases_of_completed_sessions_become_cards(db):
    sid = history.start_session(UNIT)
    answer(sid, "On Saturday I went to the beach.", "On Saturday, I went to the beach.", used=[0])
    review.sync(TODAY)
    assert not [c for c in history.list_cards(session_id=sid) if c["kind"] == "phrase"]  # not completed
    history.set_completed(sid, True)
    review.sync(TODAY)
    phrases = [c for c in history.list_cards(session_id=sid) if c["kind"] == "phrase"]
    assert sorted(c["phrase_index"] for c in phrases) == list(range(1, len(UNIT["phrases"])))
    second = history.start_session(UNIT)
    answer(second, "Fine.", "It was fine, thanks.")
    history.set_completed(second, True)
    review.sync(TODAY)  # phrase 0, skipped this time, gets a card; the others are not duplicated
    indices = [c["phrase_index"] for c in history.list_cards() if c["kind"] == "phrase"]
    assert sorted(indices) == list(range(len(UNIT["phrases"])))


def test_grading_moves_the_card_and_suspending_hides_it(db):
    sid = history.start_session(UNIT)
    answer(sid, "I go to beach.", "I went to the beach.")
    review.sync(TODAY)
    [card] = history.list_cards()
    box, due = review.schedule(card["box"], "good", TODAY)
    history.grade_card(card["id"], box, due.isoformat(), "good", {"heard": "I went to the beach", "correct": 5, "total": 5})
    assert history.list_cards(due_by=TODAY.isoformat()) == []
    assert history.card_stats(TODAY.isoformat(), "2000-01-01") == {"due": 0, "active": 1, "learned": 0, "reviews": 1, "good": 1}
    history.suspend_card(card["id"])
    assert history.list_cards() == []


def test_attempt_checks_suggest_a_grade():
    note = {"kind": "note", "target": "On Saturday, I went to the beach."}
    assert review.check_attempt(note, "On Saturday I went to the beach")["suggest"] == "good"
    assert review.check_attempt(note, "I go beach")["suggest"] == "again"
    phrase = {"kind": "phrase", "unit_id": "weekend", "phrase_index": 1, "target": "The best part was ..."}
    assert review.check_attempt(phrase, "The best part was the food.")["phrase_used"] is True
    assert review.check_attempt(phrase, "It was good.")["suggest"] == "again"
