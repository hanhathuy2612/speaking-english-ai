"""Practice history in a local SQLite file, so progress can be tracked across sessions.

One row per session and one row per turn (typed, spoken or unclear). Aggregates are computed
on read, so undoing a turn only needs to delete its row. Disabled when HISTORY_DB is empty
(agents run test servers that way so they do not pollute the user's history).
See docs/features/session-history.md.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime

from app.core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    unit_id TEXT NOT NULL,
    unit_title TEXT NOT NULL,
    phrase_total INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source TEXT NOT NULL,              -- 'voice' | 'text'
    unclear INTEGER NOT NULL DEFAULT 0,
    words INTEGER,
    wpm INTEGER,
    wpm_speaking INTEGER,
    long_pauses INTEGER,
    avg_logprob REAL,
    no_speech REAL,
    used_phrases TEXT NOT NULL DEFAULT '[]',  -- JSON list of phrase indices used in this turn
    note TEXT,
    retry INTEGER,
    stt_ms INTEGER,
    first_audio_ms INTEGER
);
CREATE INDEX IF NOT EXISTS turns_session ON turns(session_id);
"""


def enabled() -> bool:
    return bool(config.HISTORY_DB)


def _connect() -> sqlite3.Connection:
    path = config.ROOT_DIR / config.HISTORY_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    if not enabled():
        return
    with closing(_connect()) as conn, conn:
        conn.executescript(SCHEMA)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def start_session(unit: dict) -> int | None:
    if not enabled():
        return None
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO sessions (unit_id, unit_title, phrase_total, started_at) VALUES (?, ?, ?, ?)",
            (unit["id"], unit["title"], len(unit["phrases"]), _now()),
        )
        return cur.lastrowid


def add_turn(session_id: int | None, turn: dict) -> int | None:
    """turn keys match the `turns` columns (except id, session_id, created_at); missing ones are NULL."""
    if session_id is None:
        return None
    row = {**turn, "used_phrases": json.dumps(turn.get("used_phrases", []))}
    cols = ["session_id", "created_at", *row]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO turns ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (session_id, _now(), *row.values()),
        )
        return cur.lastrowid


def delete_turn(turn_id: int | None) -> None:
    if turn_id is None or not enabled():
        return
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM turns WHERE id = ?", (turn_id,))


def set_completed(session_id: int | None, completed: bool) -> None:
    if session_id is None:
        return
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE sessions SET completed = ? WHERE id = ?",
            (int(completed), session_id),
        )


def delete_session(session_id: int) -> bool:
    if not enabled():
        return False
    with closing(_connect()) as conn, conn:
        return (
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,)).rowcount
            > 0
        )


def _summarize(session: sqlite3.Row, turns: list[sqlite3.Row]) -> dict:
    """Aggregate one session. Speed and pause rate only use spoken, clear turns long enough to time,
    so a session with one two-word answer does not report 0 pauses per 100 words."""
    answered = [t for t in turns if not t["unclear"]]
    spoken = [t for t in answered if t["source"] == "voice" and t["words"]]
    timed = [t for t in spoken if t["wpm"] is not None]
    words = sum(t["words"] for t in spoken)
    timed_words = sum(t["words"] for t in timed)
    timed_pauses = sum(t["long_pauses"] or 0 for t in timed)
    used: set[int] = set()
    for t in answered:
        used |= set(json.loads(t["used_phrases"]))
    avg = lambda k: (
        round(sum(t[k] for t in timed) / len(timed)) if timed else None
    )  # noqa: E731
    return {
        "id": session["id"],
        "unit_id": session["unit_id"],
        "unit_title": session["unit_title"],
        "started_at": session["started_at"],
        "completed": bool(session["completed"]),
        "turns": len(answered),
        "spoken_turns": len(spoken),
        "unclear_turns": len(turns) - len(answered),
        "words": words,
        "wpm": avg("wpm"),
        "wpm_speaking": avg("wpm_speaking"),
        "long_pauses": sum(t["long_pauses"] or 0 for t in spoken),
        "pauses_per_100_words": (
            round(timed_pauses / timed_words * 100, 1) if timed_words else None
        ),
        "phrases_used": len(used),
        "phrase_total": session["phrase_total"],
    }


def list_sessions() -> list[dict]:
    """Sessions with at least one answered turn, oldest first."""
    if not enabled():
        return []
    with closing(_connect()) as conn:
        sessions = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at, id"
        ).fetchall()
        turns = conn.execute("SELECT * FROM turns ORDER BY id").fetchall()
    by_session: dict[int, list[sqlite3.Row]] = {}
    for t in turns:
        by_session.setdefault(t["session_id"], []).append(t)
    out = [_summarize(s, by_session.get(s["id"], [])) for s in sessions]
    return [s for s in out if s["turns"]]


def session_turns(session_id: int) -> list[dict]:
    if not enabled():
        return []
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
    return [{**dict(r), "used_phrases": json.loads(r["used_phrases"])} for r in rows]
