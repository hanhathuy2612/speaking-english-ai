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
    first_audio_ms INTEGER,
    audio TEXT                         -- recording file name in SAVE_AUDIO_DIR (services/recordings.py)
);
CREATE INDEX IF NOT EXISTS turns_session ON turns(session_id);
CREATE TABLE IF NOT EXISTS shadows (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    target TEXT NOT NULL,
    heard TEXT NOT NULL,
    correct INTEGER NOT NULL,          -- reference tokens heard correctly
    total INTEGER NOT NULL,            -- reference tokens
    words INTEGER,
    wpm_speaking INTEGER,
    long_pauses INTEGER,
    avg_logprob REAL
);
CREATE TABLE IF NOT EXISTS retells (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    words INTEGER,
    original_words INTEGER,            -- words of the first answer to the same question
    steps_done INTEGER,
    steps_total INTEGER,
    wpm_speaking INTEGER,
    long_pauses INTEGER
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    prompt_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    text TEXT NOT NULL,
    words INTEGER NOT NULL,
    duration_s REAL NOT NULL,
    wpm INTEGER,
    wpm_speaking INTEGER,
    hesitations INTEGER NOT NULL,      -- pauses > 0.7 s inside a sentence
    hesitations_per_100 REAL,
    not_english INTEGER NOT NULL,
    avg_logprob REAL,
    passed INTEGER NOT NULL,           -- targets met (docs/features/speaking-check.md)
    total INTEGER NOT NULL             -- number of targets
);
CREATE TABLE IF NOT EXISTS drills (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    set_id TEXT NOT NULL,              -- docs/features/pronunciation-drills.md
    target TEXT NOT NULL,
    heard TEXT NOT NULL,
    correct INTEGER NOT NULL,          -- reference tokens heard correctly
    total INTEGER NOT NULL,
    focus_correct INTEGER NOT NULL,    -- focus words heard correctly
    focus_total INTEGER NOT NULL,
    avg_logprob REAL
);
CREATE TABLE IF NOT EXISTS fluency (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    run TEXT NOT NULL,                 -- one 4/3/2 exercise (docs/features/fluency-432.md)
    round INTEGER NOT NULL,            -- 1, 2, 3
    limit_s INTEGER NOT NULL,
    prompt_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    text TEXT NOT NULL,
    words INTEGER NOT NULL,
    duration_s REAL NOT NULL,
    wpm_speaking INTEGER,              -- NULL when not measurable, like checks
    hesitations INTEGER NOT NULL,
    hesitations_per_100 REAL,
    not_english INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,                -- 'note' | 'phrase' (docs/features/review.md)
    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    turn_id INTEGER UNIQUE REFERENCES turns(id) ON DELETE CASCADE,  -- note cards: undo removes them
    unit_id TEXT NOT NULL,
    phrase_index INTEGER,              -- phrase cards
    question TEXT NOT NULL,
    said TEXT,                         -- note cards: the learner's original answer
    target TEXT NOT NULL,              -- the NOTE, or the phrase to use
    box INTEGER NOT NULL DEFAULT 0,    -- Leitner box: 0 = new or forgotten
    due TEXT NOT NULL,                 -- YYYY-MM-DD
    reviews INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    suspended INTEGER NOT NULL DEFAULT 0,
    UNIQUE (unit_id, phrase_index)
);
CREATE TABLE IF NOT EXISTS card_reviews (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    heard TEXT,                        -- NULL when the answer was revealed without speaking
    correct INTEGER,
    total INTEGER,
    result TEXT NOT NULL               -- 'good' | 'again' (the learner's own grade)
);
"""

MIGRATIONS = [("turns", "audio", "TEXT")]  # (table, column, type) added to older databases


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
        # Columns added after a table existed: CREATE TABLE IF NOT EXISTS does not add them.
        for table, column, kind in MIGRATIONS:
            if column not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


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


def add_retell(session_id: int | None, attempt: dict) -> int | None:
    """One "Trả lời lại dài hơn" attempt; kept apart from turns like shadowing attempts."""
    if session_id is None:
        return None
    cols = ["session_id", "created_at", *attempt]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO retells ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (session_id, _now(), *attempt.values()),
        )
        return cur.lastrowid


def add_shadow(session_id: int | None, attempt: dict) -> int | None:
    """One shadowing attempt (reading a NOTE aloud). Kept apart from turns so it never skews
    the interview metrics."""
    if session_id is None:
        return None
    cols = ["session_id", "created_at", *attempt]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO shadows ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (session_id, _now(), *attempt.values()),
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


def _summarize(
    session: sqlite3.Row, turns: list[sqlite3.Row], shadows: list[sqlite3.Row] = ()
) -> dict:
    """Aggregate one session. Speed and pause rate only use spoken, clear turns long enough to time,
    so a session with one two-word answer does not report 0 pauses per 100 words.
    Shadowing accuracy pools all attempts: correct reference words / reference words."""
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
        "shadow_attempts": len(shadows),
        "shadow_accuracy": (
            round(sum(a["correct"] for a in shadows) / shadow_words * 100)
            if (shadow_words := sum(a["total"] for a in shadows))
            else None
        ),
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
        shadows = conn.execute("SELECT * FROM shadows ORDER BY id").fetchall()
    by_session: dict[int, list[sqlite3.Row]] = {}
    for t in turns:
        by_session.setdefault(t["session_id"], []).append(t)
    shadows_by: dict[int, list[sqlite3.Row]] = {}
    for a in shadows:
        shadows_by.setdefault(a["session_id"], []).append(a)
    out = [_summarize(s, by_session.get(s["id"], []), shadows_by.get(s["id"], [])) for s in sessions]
    return [s for s in out if s["turns"]]


def session_turns(session_id: int) -> list[dict]:
    if not enabled():
        return []
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
    return [{**dict(r), "used_phrases": json.loads(r["used_phrases"])} for r in rows]


def set_turn_audio(audio: dict[int, str]) -> None:
    """Store the recording file names of turns saved before `turns.audio` existed."""
    if not audio or not enabled():
        return
    with closing(_connect()) as conn, conn:
        conn.executemany("UPDATE turns SET audio = ? WHERE id = ?", [(n, i) for i, n in audio.items()])


def turn_audio_names() -> set[str]:
    """Recording names already linked to a turn."""
    return {r["audio"] for r in _rows("SELECT audio FROM turns WHERE audio IS NOT NULL")}


def unit_stats() -> dict[str, dict]:
    """Per unit: sessions with at least one answer, completed sessions, latest start time."""
    stats: dict[str, dict] = {}
    for s in list_sessions():
        st = stats.setdefault(s["unit_id"], {"sessions": 0, "completed": 0, "last_at": None})
        st["sessions"] += 1
        st["completed"] += s["completed"]
        st["last_at"] = max(st["last_at"] or "", s["started_at"])
    return stats


def add_check(check: dict) -> int | None:
    """One speaking check (docs/features/speaking-check.md); keys match the `checks` columns."""
    if not enabled():
        return None
    cols = ["created_at", *check]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO checks ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (_now(), *check.values()),
        )
        return cur.lastrowid


def list_checks() -> list[dict]:
    """All speaking checks, oldest first."""
    if not enabled():
        return []
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM checks ORDER BY created_at, id").fetchall()
    return [{**dict(r), "not_english": bool(r["not_english"])} for r in rows]


def _insert(table: str, row: dict) -> int | None:
    if not enabled():
        return None
    cols = ["created_at", *row]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (_now(), *row.values()),
        )
        return cur.lastrowid


def _rows(sql: str) -> list[dict]:
    if not enabled():
        return []
    with closing(_connect()) as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def add_drill(attempt: dict) -> int | None:
    """One pronunciation drill reading; keys match the `drills` columns."""
    return _insert("drills", attempt)


def list_drills() -> list[dict]:
    """All drill readings, oldest first."""
    return _rows("SELECT * FROM drills ORDER BY created_at, id")


def list_readings() -> list[dict]:
    """Every sentence read aloud against a reference (shadowing and drills), oldest first."""
    rows = _rows(
        "SELECT created_at, 0 AS src, id, target, heard, correct, total FROM shadows "
        "UNION ALL SELECT created_at, 1 AS src, id, target, heard, correct, total FROM drills "
        "ORDER BY created_at, src, id"  # timestamps have one-second resolution
    )
    return [{k: r[k] for k in ("created_at", "target", "heard", "correct", "total")} for r in rows]


def add_fluency_round(row: dict) -> int | None:
    """One round of a 4/3/2 exercise; keys match the `fluency` columns."""
    return _insert("fluency", row)


def list_fluency_rounds() -> list[dict]:
    """All 4/3/2 rounds, oldest first."""
    rows = _rows("SELECT * FROM fluency ORDER BY created_at, id")
    return [{**r, "not_english": bool(r["not_english"])} for r in rows]


# ----- Review cards (docs/features/review.md) -----


def note_turns_without_card() -> list[dict]:
    """Clear answers that got a NOTE and have no review card yet, oldest first."""
    return _rows(
        "SELECT t.id AS turn_id, t.session_id, s.unit_id, t.question, t.answer, t.note, t.created_at "
        "FROM turns t JOIN sessions s ON s.id = t.session_id "
        "LEFT JOIN cards c ON c.turn_id = t.id "
        "WHERE c.id IS NULL AND t.unclear = 0 AND t.note IS NOT NULL AND t.note != '' ORDER BY t.id"
    )


def completed_sessions_used_phrases() -> list[dict]:
    """Completed sessions with the phrase indices used in any answer: [{session_id, unit_id, used}]."""
    out: dict[int, dict] = {}
    for r in _rows(
        "SELECT s.id, s.unit_id, t.used_phrases FROM sessions s JOIN turns t ON t.session_id = s.id "
        "WHERE s.completed = 1 AND t.unclear = 0 ORDER BY s.id"
    ):
        row = out.setdefault(r["id"], {"session_id": r["id"], "unit_id": r["unit_id"], "used": set()})
        row["used"] |= set(json.loads(r["used_phrases"]))
    return list(out.values())


def add_card(card: dict) -> int | None:
    """Insert a card unless one already exists for the same turn or (unit, phrase)."""
    if not enabled():
        return None
    cols = ["created_at", *card]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT OR IGNORE INTO cards ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (_now(), *card.values()),
        )
        return cur.lastrowid if cur.rowcount else None


def list_cards(due_by: str | None = None, session_id: int | None = None) -> list[dict]:
    """Active cards, oldest due first: due on or before `due_by`, or all cards of one session."""
    if not enabled():
        return []
    where, args = ["suspended = 0"], []
    if due_by is not None:
        where.append("due <= ?")
        args.append(due_by)
    if session_id is not None:
        where.append("session_id = ?")
        args.append(session_id)
    with closing(_connect()) as conn:
        rows = conn.execute(
            f"SELECT * FROM cards WHERE {' AND '.join(where)} ORDER BY due, id", args
        ).fetchall()
    return [dict(r) for r in rows]


def get_card(card_id: int) -> dict | None:
    if not enabled():
        return None
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return dict(row) if row else None


def grade_card(card_id: int, box: int, due: str, result: str, attempt: dict) -> None:
    """Store the learner's grade and the new schedule. `attempt`: heard, correct, total (or empty)."""
    if not enabled():
        return
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE cards SET box = ?, due = ?, reviews = reviews + 1, lapses = lapses + ? WHERE id = ?",
            (box, due, int(result == "again"), card_id),
        )
        conn.execute(
            "INSERT INTO card_reviews (card_id, created_at, heard, correct, total, result) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (card_id, _now(), attempt.get("heard"), attempt.get("correct"), attempt.get("total"), result),
        )


def suspend_card(card_id: int) -> bool:
    if not enabled():
        return False
    with closing(_connect()) as conn, conn:
        return conn.execute("UPDATE cards SET suspended = 1 WHERE id = ?", (card_id,)).rowcount > 0


def card_stats(today: str, since: str, learned_box: int = 4) -> dict:
    """Counts for the review page: due today, active, learned (box >= learned_box), reviews since `since`."""
    if not enabled():
        return {"due": 0, "active": 0, "learned": 0, "reviews": 0, "good": 0}
    with closing(_connect()) as conn:
        c = conn.execute(
            "SELECT SUM(due <= ?), COUNT(*), SUM(box >= ?) FROM cards WHERE suspended = 0", (today, learned_box)
        ).fetchone()
        r = conn.execute(
            "SELECT COUNT(*), SUM(result = 'good') FROM card_reviews WHERE created_at >= ?", (since,)
        ).fetchone()
    return {"due": c[0] or 0, "active": c[1] or 0, "learned": c[2] or 0, "reviews": r[0] or 0, "good": r[1] or 0}
