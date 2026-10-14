"""History store tests against a temporary SQLite file."""

import pytest

from app.core import config
from app.services import history

UNIT = {"id": "u1", "title": "Unit 1", "phrases": [{"say": "a"}, {"say": "b"}, {"say": "c"}]}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(config, "HISTORY_DB", "history.db")
    history.init()
    return tmp_path / "history.db"


def voice(words, wpm, wpm_speaking, pauses, used=()):
    return {
        "question": "Q?", "answer": "A", "source": "voice", "words": words, "wpm": wpm,
        "wpm_speaking": wpm_speaking, "long_pauses": pauses, "used_phrases": list(used),
    }


def test_aggregates_use_only_clear_spoken_turns(db):
    sid = history.start_session(UNIT)
    history.add_turn(sid, voice(20, 100, 120, 2, used=[0]))
    history.add_turn(sid, voice(30, 80, 100, 1, used=[1]))
    history.add_turn(sid, voice(5, None, None, 0))  # short answer: counted in words, not in speed
    history.add_turn(sid, {"question": "Q?", "answer": "typed", "source": "text", "used_phrases": [0]})
    history.add_turn(sid, {**voice(4, None, None, 0), "unclear": 1})

    [s] = history.list_sessions()
    assert s["turns"] == 4 and s["spoken_turns"] == 3 and s["unclear_turns"] == 1
    assert s["words"] == 55
    assert s["wpm"] == 90 and s["wpm_speaking"] == 110
    # pause rate only over the two timed turns (50 words), like speed
    assert s["long_pauses"] == 3 and s["pauses_per_100_words"] == 6.0
    assert s["phrases_used"] == 2 and s["phrase_total"] == 3
    assert s["completed"] is False


def test_session_with_only_short_answers_has_no_rates(db):
    sid = history.start_session(UNIT)
    history.add_turn(sid, voice(2, None, None, 0))
    [s] = history.list_sessions()
    assert s["words"] == 2 and s["wpm_speaking"] is None and s["pauses_per_100_words"] is None


def test_undo_deletes_the_turn_and_resets_completion(db):
    sid = history.start_session(UNIT)
    history.add_turn(sid, voice(20, 100, 120, 1))
    last = history.add_turn(sid, voice(20, 60, 80, 5))
    history.set_completed(sid, True)
    history.delete_turn(last)
    history.set_completed(sid, False)

    [s] = history.list_sessions()
    assert s["turns"] == 1 and s["wpm"] == 100 and s["completed"] is False


def test_sessions_without_answers_are_hidden_and_delete_cascades(db):
    empty = history.start_session(UNIT)
    sid = history.start_session(UNIT)
    history.add_turn(sid, voice(10, 90, 90, 0))
    assert [s["id"] for s in history.list_sessions()] == [sid]
    assert len(history.session_turns(sid)) == 1

    assert history.delete_session(sid) and not history.delete_session(999)
    assert history.list_sessions() == [] and history.session_turns(sid) == []
    assert empty is not None


def test_disabled_when_history_db_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(config, "HISTORY_DB", "")
    history.init()
    assert history.start_session(UNIT) is None
    assert history.add_turn(None, voice(10, 90, 90, 0)) is None
    assert history.list_sessions() == []
    assert list(tmp_path.iterdir()) == []


def test_shadow_attempts_are_stored_apart_and_deleted_with_the_session(db):
    import sqlite3

    sid = history.start_session(UNIT)
    history.add_turn(sid, voice(20, 100, 120, 1))
    history.add_shadow(sid, {"target": "I'm responsible for ...", "heard": "I responsible for",
                             "correct": 3, "total": 4, "words": 3})
    [s] = history.list_sessions()
    assert s["turns"] == 1  # shadowing never counts as an interview turn
    count = lambda: sqlite3.connect(db).execute("SELECT COUNT(*) FROM shadows").fetchone()[0]  # noqa: E731
    assert count() == 1
    history.delete_session(sid)
    assert count() == 0
    assert history.add_shadow(None, {"target": "x", "heard": "x", "correct": 1, "total": 1}) is None


def test_retell_attempts_are_stored_apart_and_deleted_with_the_session(db):
    import sqlite3

    sid = history.start_session(UNIT)
    history.add_turn(sid, voice(6, None, None, 0))
    history.add_retell(sid, {"question": "Q?", "answer": "A longer answer", "words": 25,
                             "original_words": 6, "steps_done": 2, "steps_total": 3})
    [s] = history.list_sessions()
    assert s["turns"] == 1 and s["words"] == 6  # a retell never counts as an interview turn
    count = lambda: sqlite3.connect(db).execute("SELECT COUNT(*) FROM retells").fetchone()[0]  # noqa: E731
    assert count() == 1
    history.delete_session(sid)
    assert count() == 0
    assert history.add_retell(None, {"question": "Q?", "answer": "A"}) is None


def test_shadow_accuracy_pools_attempts(db):
    sid = history.start_session(UNIT)
    history.add_turn(sid, voice(20, 100, 120, 1))
    [s] = history.list_sessions()
    assert s["shadow_attempts"] == 0 and s["shadow_accuracy"] is None
    history.add_shadow(sid, {"target": "t", "heard": "h", "correct": 9, "total": 10})
    history.add_shadow(sid, {"target": "t", "heard": "h", "correct": 3, "total": 10})
    [s] = history.list_sessions()
    assert s["shadow_attempts"] == 2 and s["shadow_accuracy"] == 60


def test_unit_stats_counts_answered_sessions(db):
    a = history.start_session(UNIT)
    history.add_turn(a, voice(20, 100, 120, 1))
    history.set_completed(a, True)
    b = history.start_session(UNIT)
    history.add_turn(b, voice(20, 100, 120, 1))
    history.start_session(UNIT)  # no answers: not counted
    st = history.unit_stats()["u1"]
    assert st["sessions"] == 2 and st["completed"] == 1 and st["last_at"]


def test_checks_are_stored_and_listed(db):
    history.add_check({
        "prompt_id": "p", "prompt": "Talk", "text": "hello", "words": 1, "duration_s": 0.5,
        "wpm": None, "wpm_speaking": None, "hesitations": 0, "hesitations_per_100": 0.0,
        "not_english": 1, "avg_logprob": -0.3, "passed": 0, "total": 4,
    })
    [c] = history.list_checks()
    assert c["prompt_id"] == "p" and c["not_english"] is True and c["total"] == 4


def test_drills_and_shadows_feed_the_readings_list(db):
    sid = history.start_session(UNIT)
    history.add_shadow(sid, {"target": "A cat.", "heard": "a cap", "correct": 1, "total": 2})
    history.add_drill({"set_id": "final-s", "target": "Two cats.", "heard": "two cat", "correct": 1,
                       "total": 2, "focus_correct": 0, "focus_total": 1})  # fmt: skip
    assert [r["target"] for r in history.list_readings()] == ["A cat.", "Two cats."]
    assert history.list_drills()[0]["focus_total"] == 1


def test_drill_recordings_are_stored_and_can_be_linked_later(db):
    row = {"set_id": "final-s", "target": "Two cats.", "heard": "two cats", "correct": 2, "total": 2,
           "focus_correct": 1, "focus_total": 1}  # fmt: skip
    history.add_drill({**row, "audio": "20261014-100000-000001.webm"})
    old = history.add_drill(row)  # saved before drills.audio existed
    history.set_drill_audio({old: "20261014-090000-000001.webm"})
    audio = [d["audio"] for d in history.list_drills()]
    assert audio == ["20261014-100000-000001.webm", "20261014-090000-000001.webm"]
    assert history.recording_names() >= {"20261014-100000-000001.webm", "20261014-090000-000001.webm"}


def test_fluency_rounds_round_trip(db):
    history.add_fluency_round({"run": "r1", "round": 1, "limit_s": 240, "prompt_id": "p", "prompt": "P",
                               "text": "t", "words": 300, "duration_s": 200.0, "wpm_speaking": 100,
                               "hesitations": 4, "hesitations_per_100": 1.3, "not_english": 0})  # fmt: skip
    [r] = history.list_fluency_rounds()
    assert r["run"] == "r1" and r["not_english"] is False


def test_lesson_reads_join_the_readings_and_lessons_are_counted(db):
    history.add_lesson_read(
        {"unit_id": "u1", "sentence": 0, "target": "I am here.", "heard": "I am hear.", "correct": 2, "total": 3}
    )
    assert [r["target"] for r in history.list_readings()] == ["I am here."]
    assert history.lesson_counts() == {}
    history.finish_lesson("u1")
    history.finish_lesson("u1")
    assert history.lesson_counts() == {"u1": 2}
