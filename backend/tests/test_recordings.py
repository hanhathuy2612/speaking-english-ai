"""Recordings for "Nghe lại" on the progress page: matching old turns, safe file names, migration."""

from app.core import config
from app.services import recordings


def turn(tid, created_at, answer, source="voice", audio=None):
    return {"id": tid, "created_at": created_at, "answer": answer, "source": source, "audio": audio}


def test_old_turns_match_the_recording_with_the_same_text_just_before():
    heard = {
        "20261011-100000-000001.webm": "I went to the beach.",
        "20261011-100500-000001.webm": "I went to the beach.",  # same words, later: the second answer
        "20261011-090000-000001.webm": "Too early.",
    }
    turns = [
        turn(1, "2026-10-11T10:00:12", "I went to the beach."),
        turn(2, "2026-10-11T10:05:09", "I went to the beach."),
        turn(3, "2026-10-11T10:30:00", "Too early."),  # 90 minutes after its only candidate
        turn(4, "2026-10-11T10:06:00", "Typed answer", source="text"),
    ]
    found = recordings.match_turns(turns, heard, taken=set())
    assert found == {1: "20261011-100000-000001.webm", 2: "20261011-100500-000001.webm"}


def test_a_recording_is_used_only_once():
    heard = {"20261011-100000-000001.webm": "Yes."}
    turns = [turn(1, "2026-10-11T10:00:05", "Yes."), turn(2, "2026-10-11T10:00:09", "Yes.")]
    assert len(recordings.match_turns(turns, heard, taken=set())) == 1
    assert recordings.match_turns(turns, heard, taken={"20261011-100000-000001.webm"}) == {}


def test_only_files_the_app_created_are_served(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(config, "SAVE_AUDIO_DIR", "recordings")
    (tmp_path / "recordings").mkdir()
    good = "20261011-100000-000001.webm"
    (tmp_path / "recordings" / good).write_bytes(b"x")
    (tmp_path / "secret.txt").write_text("no")
    assert recordings.path_for(good) == tmp_path / "recordings" / good
    for bad in ["../secret.txt", r"..\secret.txt", "secret.txt", "20261011-100000-000002.webm", None]:
        assert recordings.path_for(bad) is None
    monkeypatch.setattr(config, "SAVE_AUDIO_DIR", "")
    assert recordings.path_for(good) is None


def test_old_drill_readings_find_their_recording_by_time():
    names = ["20261014-100000-000001.webm", "20261014-100010-000001.webm", "20261014-090000-000001.webm"]
    rows = [
        {"id": 1, "created_at": "2026-10-14T10:00:02", "audio": None},  # 2 s after the first file
        {"id": 2, "created_at": "2026-10-14T10:00:12", "audio": None},
        {"id": 3, "created_at": "2026-10-14T10:00:13", "audio": "kept.webm"},  # already linked
        {"id": 4, "created_at": "2026-10-14T09:30:00", "audio": None},  # nothing within 15 s
    ]
    found = recordings.match_by_time(rows, names, taken=set())
    assert found == {1: "20261014-100000-000001.webm", 2: "20261014-100010-000001.webm"}
    assert recordings.match_by_time(rows[:1], names, taken={names[0]}) == {}
