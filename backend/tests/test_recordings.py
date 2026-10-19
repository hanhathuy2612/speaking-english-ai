"""Recordings for "Nghe lại" on the progress page: safe file names and the audio column migration."""

import sqlite3

from app.core import config
from app.services import history, recordings


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


def test_init_adds_the_audio_column_to_an_old_database(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(config, "HISTORY_DB", "old.db")
    old_schema = history.SCHEMA.replace(
        "    first_audio_ms INTEGER,\n    audio TEXT", "    first_audio_ms INTEGER\n   "
    )
    assert "audio TEXT" not in old_schema.split("CREATE TABLE IF NOT EXISTS shadows")[0]
    with sqlite3.connect(tmp_path / "old.db") as conn:
        conn.executescript(old_schema)
    history.init()
    history.init()  # idempotent
    with sqlite3.connect(tmp_path / "old.db") as conn:
        assert "audio" in {r[1] for r in conn.execute("PRAGMA table_info(turns)")}
