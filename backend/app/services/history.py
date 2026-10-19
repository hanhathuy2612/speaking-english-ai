"""Practice history in a local SQLite file, so progress can be tracked across sessions.

One row per session and one row per turn (typed, spoken or unclear). Aggregates are computed
on read, so undoing a turn only needs to delete its row. Every learner's rows carry their
`user_id` (sessions, checks, drills, fluency rounds, cards, lesson reads); turns, shadowing and
retell attempts belong to a session, card reviews to a card. Functions that read take the user id
first, so one learner never sees another's history. Disabled when HISTORY_DB is empty (tests).
See docs/features/session-history.md and docs/features/accounts.md.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime

from app.core import config
from app.services import db

USER = "user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"  # NULL: saved before accounts existed

CARDS = f"""
CREATE TABLE IF NOT EXISTS {{name}} (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,                -- 'note' | 'phrase' | 'talk' (docs/features/review.md)
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
    {USER},
    UNIQUE (user_id, unit_id, phrase_index)
);
"""

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    unit_id TEXT NOT NULL,
    unit_title TEXT NOT NULL,
    phrase_total INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    {USER}
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
    total INTEGER NOT NULL,            -- number of targets
    {USER},
    stuck TEXT,                        -- JSON: hesitations with the words around them (check.stuck_points)
    review TEXT                        -- JSON: the AI review asked for after the check (docs/features/talk-lessons.md)
);
CREATE TABLE IF NOT EXISTS talk_practice (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,              -- 'talk' (practice after a talk lesson) | 'check' (retry after a check)
    ref TEXT NOT NULL,                 -- the talk id, or the check id
    prompt_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    text TEXT NOT NULL,
    words INTEGER NOT NULL,
    duration_s REAL NOT NULL,
    wpm_speaking INTEGER,              -- NULL when not measurable, like checks
    hesitations INTEGER NOT NULL,
    hesitations_per_100 REAL,
    steps_done INTEGER,                -- frame steps said (talk practice)
    steps_total INTEGER,
    {USER}
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
    avg_logprob REAL,
    audio TEXT,                        -- recording file name in SAVE_AUDIO_DIR, for "Nghe lại"
    {USER}
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
    not_english INTEGER NOT NULL,
    {USER}
);
{CARDS.format(name="cards")}
CREATE TABLE IF NOT EXISTS card_reviews (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    heard TEXT,                        -- NULL when the answer was revealed without speaking
    correct INTEGER,
    total INTEGER,
    result TEXT NOT NULL               -- 'good' | 'again' (the learner's own grade)
);
CREATE TABLE IF NOT EXISTS lesson_reads (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    unit_id TEXT NOT NULL,             -- docs/features/lesson.md
    sentence INTEGER NOT NULL,         -- index in the unit's lesson.sentences
    target TEXT NOT NULL,
    heard TEXT NOT NULL,
    correct INTEGER NOT NULL,          -- reference tokens heard correctly
    total INTEGER NOT NULL,
    avg_logprob REAL,
    {USER}
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,          -- when the learner reached the end of the lesson part
    unit_id TEXT NOT NULL,
    {USER}
);
"""

OWNED = ("sessions", "checks", "drills", "fluency", "cards", "lesson_reads", "lessons", "talk_practice")  # with user_id
# (table, column, type) added to older databases
MIGRATIONS = [
    ("turns", "audio", "TEXT"),
    ("drills", "audio", "TEXT"),
    *((t, "user_id", USER) for t in OWNED),
    ("checks", "stuck", "TEXT"),
    ("checks", "review", "TEXT"),
]
INDEXES = [f"CREATE INDEX IF NOT EXISTS {t}_user ON {t}(user_id)" for t in OWNED]

enabled = db.enabled
_connect = db.connect


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _backup_before_accounts() -> None:
    """Copy a database written before accounts existed, once, before it is migrated."""
    path = config.ROOT_DIR / config.HISTORY_DB
    if not path.is_file():
        return
    with closing(sqlite3.connect(path)) as conn:
        old = "sessions" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master")} and (
            "user_id" not in _columns(conn, "sessions")
        )
    backup = path.with_name(path.name + ".before-accounts")
    if old and not backup.exists():
        shutil.copy2(path, backup)
        print(f"Backed up the history database to {backup} before adding accounts.")


def _rebuild_cards(conn: sqlite3.Connection) -> None:
    """Phrase cards were unique per (unit, phrase); with accounts they are unique per learner.
    SQLite cannot change a UNIQUE constraint in place, so the table is copied (sqlite.org/lang_altertable.html)."""
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'cards'").fetchone()[0]
    if "UNIQUE (user_id, unit_id, phrase_index)" in sql:
        return
    cols = ", ".join(sorted(_columns(conn, "cards")))
    conn.execute("PRAGMA foreign_keys = OFF")  # dropping cards must not cascade to card_reviews
    try:
        with conn:
            conn.execute(CARDS.format(name="cards_new"))
            conn.execute(f"INSERT INTO cards_new ({cols}) SELECT {cols} FROM cards")
            conn.execute("DROP TABLE cards")
            conn.execute("ALTER TABLE cards_new RENAME TO cards")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def init() -> None:
    if not enabled():
        return
    _backup_before_accounts()
    with closing(_connect()) as conn:
        with conn:
            conn.executescript(SCHEMA)
            # Columns added after a table existed: CREATE TABLE IF NOT EXISTS does not add them.
            for table, column, kind in MIGRATIONS:
                if column not in _columns(conn, table):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
        _rebuild_cards(conn)
        with conn:
            for sql in INDEXES:
                conn.execute(sql)


def claim_unowned(uid: int) -> int:
    """Give the rows saved before accounts existed (user_id NULL) to this user; returns how many."""
    if not enabled():
        return 0
    with closing(_connect()) as conn, conn:
        return sum(conn.execute(f"UPDATE {t} SET user_id = ? WHERE user_id IS NULL", (uid,)).rowcount for t in OWNED)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def start_session(uid: int, unit: dict) -> int | None:
    if not enabled():
        return None
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO sessions (unit_id, unit_title, phrase_total, started_at, user_id) VALUES (?, ?, ?, ?, ?)",
            (unit["id"], unit["title"], len(unit["phrases"]), _now(), uid),
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


def delete_session(uid: int, session_id: int) -> bool:
    if not enabled():
        return False
    with closing(_connect()) as conn, conn:
        return conn.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, uid)).rowcount > 0


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


def list_sessions(uid: int) -> list[dict]:
    """The user's sessions with at least one answered turn, oldest first."""
    if not enabled():
        return []
    mine = "session_id IN (SELECT id FROM sessions WHERE user_id = ?)"
    with closing(_connect()) as conn:
        sessions = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY started_at, id", (uid,)
        ).fetchall()
        turns = conn.execute(f"SELECT * FROM turns WHERE {mine} ORDER BY id", (uid,)).fetchall()
        shadows = conn.execute(f"SELECT * FROM shadows WHERE {mine} ORDER BY id", (uid,)).fetchall()
    by_session: dict[int, list[sqlite3.Row]] = {}
    for t in turns:
        by_session.setdefault(t["session_id"], []).append(t)
    shadows_by: dict[int, list[sqlite3.Row]] = {}
    for a in shadows:
        shadows_by.setdefault(a["session_id"], []).append(a)
    out = [_summarize(s, by_session.get(s["id"], []), shadows_by.get(s["id"], [])) for s in sessions]
    return [s for s in out if s["turns"]]


def session_turns(uid: int, session_id: int) -> list[dict]:
    rows = _rows(
        "SELECT t.* FROM turns t JOIN sessions s ON s.id = t.session_id "
        "WHERE t.session_id = ? AND s.user_id = ? ORDER BY t.id",
        (session_id, uid),
    )
    return [{**r, "used_phrases": json.loads(r["used_phrases"])} for r in rows]


def unit_stats(uid: int) -> dict[str, dict]:
    """Per unit: sessions with at least one answer, completed sessions, latest start time."""
    stats: dict[str, dict] = {}
    for s in list_sessions(uid):
        st = stats.setdefault(s["unit_id"], {"sessions": 0, "completed": 0, "last_at": None})
        st["sessions"] += 1
        st["completed"] += s["completed"]
        st["last_at"] = max(st["last_at"] or "", s["started_at"])
    return stats


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


def _rows(sql: str, args: tuple = ()) -> list[dict]:
    if not enabled():
        return []
    with closing(_connect()) as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def add_check(uid: int, check: dict) -> int | None:
    """One speaking check (docs/features/speaking-check.md); keys match the `checks` columns."""
    return _insert("checks", {**check, "user_id": uid})


def _check_row(r: dict) -> dict:
    return {
        **r,
        "not_english": bool(r["not_english"]),
        "stuck": json.loads(r["stuck"]) if r.get("stuck") else [],
        "review": json.loads(r["review"]) if r.get("review") else None,
    }


def list_checks(uid: int) -> list[dict]:
    """The user's speaking checks, oldest first."""
    rows = _rows("SELECT * FROM checks WHERE user_id = ? ORDER BY created_at, id", (uid,))
    return [_check_row(r) for r in rows]


def get_check(uid: int, check_id: int) -> dict | None:
    rows = _rows("SELECT * FROM checks WHERE id = ? AND user_id = ?", (check_id, uid))
    return _check_row(rows[0]) if rows else None


def set_check_review(check_id: int, review: dict) -> None:
    if not enabled():
        return
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE checks SET review = ? WHERE id = ?", (json.dumps(review, ensure_ascii=False), check_id))


def add_talk_practice(uid: int, row: dict) -> int | None:
    """One practice talk (after a talk lesson, or a retry after a check); never counted as a check."""
    return _insert("talk_practice", {**row, "user_id": uid})


def list_talk_practice(uid: int, source: str | None = None, ref: str | None = None) -> list[dict]:
    where, args = ["user_id = ?"], [uid]
    if source is not None:
        where.append("source = ?")
        args.append(source)
    if ref is not None:
        where.append("ref = ?")
        args.append(ref)
    return _rows(f"SELECT * FROM talk_practice WHERE {' AND '.join(where)} ORDER BY created_at, id", tuple(args))


def studied_check_prompts(uid: int) -> set[str]:
    """Check prompts the user prepared after a check: asked for the review or retried the talk."""
    rows = _rows(
        "SELECT prompt_id FROM checks WHERE user_id = ? AND review IS NOT NULL "
        "UNION SELECT prompt_id FROM talk_practice WHERE user_id = ? AND source = 'check'",
        (uid, uid),
    )
    return {r["prompt_id"] for r in rows}


def add_drill(uid: int, attempt: dict) -> int | None:
    """One pronunciation drill reading; keys match the `drills` columns."""
    return _insert("drills", {**attempt, "user_id": uid})


def list_drills(uid: int) -> list[dict]:
    """The user's drill readings, oldest first."""
    return _rows("SELECT * FROM drills WHERE user_id = ? ORDER BY created_at, id", (uid,))


def owns_recording(uid: int, name: str) -> bool:
    """Whether a kept recording is one of this user's answers or drill readings."""
    return bool(
        _rows(
            "SELECT 1 FROM turns t JOIN sessions s ON s.id = t.session_id WHERE t.audio = ? AND s.user_id = ? "
            "UNION SELECT 1 FROM drills WHERE audio = ? AND user_id = ?",
            (name, uid, name, uid),
        )
    )


def list_readings(uid: int) -> list[dict]:
    """Every sentence the user read aloud against a reference (shadowing, drills, lessons), oldest first."""
    rows = _rows(
        "SELECT a.created_at, 0 AS src, a.id, a.target, a.heard, a.correct, a.total FROM shadows a "
        "JOIN sessions s ON s.id = a.session_id WHERE s.user_id = ? "
        "UNION ALL SELECT created_at, 1 AS src, id, target, heard, correct, total FROM drills WHERE user_id = ? "
        "UNION ALL SELECT created_at, 2 AS src, id, target, heard, correct, total FROM lesson_reads WHERE user_id = ? "
        "ORDER BY created_at, src, id",  # timestamps have one-second resolution
        (uid, uid, uid),
    )
    return [{k: r[k] for k in ("created_at", "target", "heard", "correct", "total")} for r in rows]


def add_lesson_read(uid: int, attempt: dict) -> int | None:
    """One lesson sentence read aloud; keys match the `lesson_reads` columns."""
    return _insert("lesson_reads", {**attempt, "user_id": uid})


def finish_lesson(uid: int, unit_id: str) -> int | None:
    """The learner reached the end of a unit's lesson part."""
    return _insert("lessons", {"unit_id": unit_id, "user_id": uid})


def lesson_counts(uid: int) -> dict[str, int]:
    """Per unit: how many times the user finished its lesson part."""
    rows = _rows("SELECT unit_id, COUNT(*) AS n FROM lessons WHERE user_id = ? GROUP BY unit_id", (uid,))
    return {r["unit_id"]: r["n"] for r in rows}


def add_fluency_round(uid: int, row: dict) -> int | None:
    """One round of a 4/3/2 exercise; keys match the `fluency` columns."""
    return _insert("fluency", {**row, "user_id": uid})


def list_fluency_rounds(uid: int) -> list[dict]:
    """The user's 4/3/2 rounds, oldest first."""
    rows = _rows("SELECT * FROM fluency WHERE user_id = ? ORDER BY created_at, id", (uid,))
    return [{**r, "not_english": bool(r["not_english"])} for r in rows]


# ----- Review cards (docs/features/review.md) -----


def note_turns_without_card(uid: int) -> list[dict]:
    """The user's clear answers that got a NOTE and have no review card yet, oldest first."""
    return _rows(
        "SELECT t.id AS turn_id, t.session_id, s.unit_id, t.question, t.answer, t.note, t.created_at "
        "FROM turns t JOIN sessions s ON s.id = t.session_id "
        "LEFT JOIN cards c ON c.turn_id = t.id "
        "WHERE s.user_id = ? AND c.id IS NULL AND t.unclear = 0 AND t.note IS NOT NULL AND t.note != '' "
        "ORDER BY t.id",
        (uid,),
    )


def completed_sessions_used_phrases(uid: int) -> list[dict]:
    """The user's completed sessions with the phrase indices used in any answer: [{session_id, unit_id, used}]."""
    out: dict[int, dict] = {}
    for r in _rows(
        "SELECT s.id, s.unit_id, t.used_phrases FROM sessions s JOIN turns t ON t.session_id = s.id "
        "WHERE s.user_id = ? AND s.completed = 1 AND t.unclear = 0 ORDER BY s.id",
        (uid,),
    ):
        row = out.setdefault(r["id"], {"session_id": r["id"], "unit_id": r["unit_id"], "used": set()})
        row["used"] |= set(json.loads(r["used_phrases"]))
    return list(out.values())


def add_card(uid: int, card: dict) -> int | None:
    """Insert a card unless the user already has one for the same turn or (unit, phrase)."""
    if not enabled():
        return None
    row = {**card, "user_id": uid}
    cols = ["created_at", *row]
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT OR IGNORE INTO cards ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (_now(), *row.values()),
        )
        return cur.lastrowid if cur.rowcount else None


def list_cards(uid: int, due_by: str | None = None, session_id: int | None = None) -> list[dict]:
    """The user's active cards, oldest due first: due on or before `due_by`, or all cards of one session."""
    where, args = ["user_id = ?", "suspended = 0"], [uid]
    if due_by is not None:
        where.append("due <= ?")
        args.append(due_by)
    if session_id is not None:
        where.append("session_id = ?")
        args.append(session_id)
    return _rows(f"SELECT * FROM cards WHERE {' AND '.join(where)} ORDER BY due, id", tuple(args))


def get_card(uid: int, card_id: int) -> dict | None:
    rows = _rows("SELECT * FROM cards WHERE id = ? AND user_id = ?", (card_id, uid))
    return rows[0] if rows else None


def grade_card(card_id: int, box: int, due: str, result: str, attempt: dict) -> None:
    """Store the learner's grade and the new schedule. `attempt`: heard, correct, total (or empty).
    The caller checked the card is theirs (get_card)."""
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
    """The caller checked the card is theirs (get_card)."""
    if not enabled():
        return False
    with closing(_connect()) as conn, conn:
        return conn.execute("UPDATE cards SET suspended = 1 WHERE id = ?", (card_id,)).rowcount > 0


def card_stats(uid: int, today: str, since: str, learned_box: int = 4) -> dict:
    """The user's counts for the review page: due today, active, learned (box >= learned_box),
    reviews since `since`."""
    if not enabled():
        return {"due": 0, "active": 0, "learned": 0, "reviews": 0, "good": 0}
    with closing(_connect()) as conn:
        c = conn.execute(
            "SELECT SUM(due <= ?), COUNT(*), SUM(box >= ?) FROM cards WHERE user_id = ? AND suspended = 0",
            (today, learned_box, uid),
        ).fetchone()
        r = conn.execute(
            "SELECT COUNT(*), SUM(r.result = 'good') FROM card_reviews r JOIN cards c ON c.id = r.card_id "
            "WHERE c.user_id = ? AND r.created_at >= ?",
            (uid, since),
        ).fetchone()
    return {"due": c[0] or 0, "active": c[1] or 0, "learned": c[2] or 0, "reviews": r[0] or 0, "good": r[1] or 0}
