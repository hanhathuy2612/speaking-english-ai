"""Practice history in MySQL, so progress can be tracked across sessions.

One row per session and one row per turn (typed, spoken or unclear). Aggregates are computed
on read, so undoing a turn only needs to delete its row. Every learner's rows carry their
`user_id` (sessions, checks, drills, fluency rounds, cards, lesson reads); turns, shadowing and
retell attempts belong to a session, card reviews to a card. Functions that read take the user id
first, so one learner never sees another's history. Disabled when DATABASE_URL is empty (tests).
See docs/features/session-history.md and docs/features/accounts.md.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.services import db


OWNED = ("sessions", "checks", "drills", "fluency", "cards", "lesson_reads", "lessons", "talk_practice")  # with user_id

enabled = db.enabled
_connect = db.connect


def claim_unowned(uid: int) -> int:
    """Give the rows saved before accounts existed (user_id NULL) to this user; returns how many."""
    if not enabled():
        return 0
    with _connect() as conn:
        return sum(conn.execute(f"UPDATE {t} SET user_id = %s WHERE user_id IS NULL", (uid,)).rowcount for t in OWNED)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def start_session(uid: int, unit: dict) -> int | None:
    if not enabled():
        return None
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (unit_id, unit_title, phrase_total, started_at, user_id) VALUES (%s, %s, %s, %s, %s)",
            (unit["id"], unit["title"], len(unit["phrases"]), _now(), uid),
        )
        return cur.lastrowid


def add_turn(session_id: int | None, turn: dict) -> int | None:
    """turn keys match the `turns` columns (except id, session_id, created_at); missing ones are NULL."""
    if session_id is None:
        return None
    row = {**turn, "used_phrases": json.dumps(turn.get("used_phrases", []))}
    cols = ["session_id", "created_at", *row]
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO turns ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            (session_id, _now(), *row.values()),
        )
        return cur.lastrowid


def add_retell(session_id: int | None, attempt: dict) -> int | None:
    """One "Trả lời lại dài hơn" attempt; kept apart from turns like shadowing attempts."""
    if session_id is None:
        return None
    cols = ["session_id", "created_at", *attempt]
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO retells ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            (session_id, _now(), *attempt.values()),
        )
        return cur.lastrowid


def add_shadow(session_id: int | None, attempt: dict) -> int | None:
    """One shadowing attempt (reading a NOTE aloud). Kept apart from turns so it never skews
    the interview metrics."""
    if session_id is None:
        return None
    cols = ["session_id", "created_at", *attempt]
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO shadows ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            (session_id, _now(), *attempt.values()),
        )
        return cur.lastrowid


def delete_turn(turn_id: int | None) -> None:
    if turn_id is None or not enabled():
        return
    with _connect() as conn:
        conn.execute("DELETE FROM turns WHERE id = %s", (turn_id,))


def set_completed(session_id: int | None, completed: bool) -> None:
    if session_id is None:
        return
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET completed = %s WHERE id = %s",
            (int(completed), session_id),
        )


def delete_session(uid: int, session_id: int) -> bool:
    if not enabled():
        return False
    with _connect() as conn:
        return conn.execute("DELETE FROM sessions WHERE id = %s AND user_id = %s", (session_id, uid)).rowcount > 0


def _summarize(
    session: dict, turns: list[dict], shadows: list[dict] = ()
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
    mine = "session_id IN (SELECT id FROM sessions WHERE user_id = %s)"
    with _connect() as conn:
        sessions = conn.execute(
            "SELECT * FROM sessions WHERE user_id = %s ORDER BY started_at, id", (uid,)
        ).fetchall()
        turns = conn.execute(f"SELECT * FROM turns WHERE {mine} ORDER BY id", (uid,)).fetchall()
        shadows = conn.execute(f"SELECT * FROM shadows WHERE {mine} ORDER BY id", (uid,)).fetchall()
    by_session: dict[int, list[dict]] = {}
    for t in turns:
        by_session.setdefault(t["session_id"], []).append(t)
    shadows_by: dict[int, list[dict]] = {}
    for a in shadows:
        shadows_by.setdefault(a["session_id"], []).append(a)
    out = [_summarize(s, by_session.get(s["id"], []), shadows_by.get(s["id"], [])) for s in sessions]
    return [s for s in out if s["turns"]]


def session_turns(uid: int, session_id: int) -> list[dict]:
    rows = _rows(
        "SELECT t.* FROM turns t JOIN sessions s ON s.id = t.session_id "
        "WHERE t.session_id = %s AND s.user_id = %s ORDER BY t.id",
        (session_id, uid),
    )
    return [{**r, "used_phrases": json.loads(r["used_phrases"])} for r in rows]


def set_turn_audio(audio: dict[int, str]) -> None:
    """Store the recording file names of turns saved before `turns.audio` existed."""
    if not audio or not enabled():
        return
    with _connect() as conn:
        conn.executemany("UPDATE turns SET audio = %s WHERE id = %s", [(n, i) for i, n in audio.items()])


def turn_audio_names() -> set[str]:
    """Recording names already linked to a turn, of any user (so no file is linked twice)."""
    return {r["audio"] for r in _rows("SELECT audio FROM turns WHERE audio IS NOT NULL")}


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
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            (_now(), *row.values()),
        )
        return cur.lastrowid


def _rows(sql: str, args: tuple = ()) -> list[dict]:
    if not enabled():
        return []
    with _connect() as conn:
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
    rows = _rows("SELECT * FROM checks WHERE user_id = %s ORDER BY created_at, id", (uid,))
    return [_check_row(r) for r in rows]


def get_check(uid: int, check_id: int) -> dict | None:
    rows = _rows("SELECT * FROM checks WHERE id = %s AND user_id = %s", (check_id, uid))
    return _check_row(rows[0]) if rows else None


def set_check_review(check_id: int, review: dict) -> None:
    if not enabled():
        return
    with _connect() as conn:
        conn.execute("UPDATE checks SET review = %s WHERE id = %s", (json.dumps(review, ensure_ascii=False), check_id))


def add_talk_practice(uid: int, row: dict) -> int | None:
    """One practice talk (after a talk lesson, or a retry after a check); never counted as a check."""
    return _insert("talk_practice", {**row, "user_id": uid})


def list_talk_practice(uid: int, source: str | None = None, ref: str | None = None) -> list[dict]:
    where, args = ["user_id = %s"], [uid]
    if source is not None:
        where.append("source = %s")
        args.append(source)
    if ref is not None:
        where.append("ref = %s")
        args.append(ref)
    return _rows(f"SELECT * FROM talk_practice WHERE {' AND '.join(where)} ORDER BY created_at, id", tuple(args))


def studied_check_prompts(uid: int) -> set[str]:
    """Check prompts the user prepared after a check: asked for the review or retried the talk."""
    rows = _rows(
        "SELECT prompt_id FROM checks WHERE user_id = %s AND review IS NOT NULL "
        "UNION SELECT prompt_id FROM talk_practice WHERE user_id = %s AND source = 'check'",
        (uid, uid),
    )
    return {r["prompt_id"] for r in rows}


def add_drill(uid: int, attempt: dict) -> int | None:
    """One pronunciation drill reading; keys match the `drills` columns."""
    return _insert("drills", {**attempt, "user_id": uid})


def list_drills(uid: int) -> list[dict]:
    """The user's drill readings, oldest first."""
    return _rows("SELECT * FROM drills WHERE user_id = %s ORDER BY created_at, id", (uid,))


def set_drill_audio(audio: dict[int, str]) -> None:
    """Store the recording file names of drill readings saved before `drills.audio` existed."""
    if not audio or not enabled():
        return
    with _connect() as conn:
        conn.executemany("UPDATE drills SET audio = %s WHERE id = %s", [(n, i) for i, n in audio.items()])


def recording_names() -> set[str]:
    """Recording names already linked to a turn or a drill reading, of any user."""
    rows = _rows(
        "SELECT audio FROM turns WHERE audio IS NOT NULL "
        "UNION SELECT audio FROM drills WHERE audio IS NOT NULL"
    )
    return {r["audio"] for r in rows}


def owns_recording(uid: int, name: str) -> bool:
    """Whether a kept recording is one of this user's answers or drill readings."""
    return bool(
        _rows(
            "SELECT 1 FROM turns t JOIN sessions s ON s.id = t.session_id WHERE t.audio = %s AND s.user_id = %s "
            "UNION SELECT 1 FROM drills WHERE audio = %s AND user_id = %s",
            (name, uid, name, uid),
        )
    )


def list_readings(uid: int) -> list[dict]:
    """Every sentence the user read aloud against a reference (shadowing, drills, lessons), oldest first."""
    rows = _rows(
        "SELECT a.created_at, 0 AS src, a.id, a.target, a.heard, a.correct, a.total FROM shadows a "
        "JOIN sessions s ON s.id = a.session_id WHERE s.user_id = %s "
        "UNION ALL SELECT created_at, 1 AS src, id, target, heard, correct, total FROM drills WHERE user_id = %s "
        "UNION ALL SELECT created_at, 2 AS src, id, target, heard, correct, total FROM lesson_reads WHERE user_id = %s "
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
    rows = _rows("SELECT unit_id, COUNT(*) AS n FROM lessons WHERE user_id = %s GROUP BY unit_id", (uid,))
    return {r["unit_id"]: r["n"] for r in rows}


def add_fluency_round(uid: int, row: dict) -> int | None:
    """One round of a 4/3/2 exercise; keys match the `fluency` columns."""
    return _insert("fluency", {**row, "user_id": uid})


def list_fluency_rounds(uid: int) -> list[dict]:
    """The user's 4/3/2 rounds, oldest first."""
    rows = _rows("SELECT * FROM fluency WHERE user_id = %s ORDER BY created_at, id", (uid,))
    return [{**r, "not_english": bool(r["not_english"])} for r in rows]


# ----- Review cards (docs/features/review.md) -----


def note_turns_without_card(uid: int) -> list[dict]:
    """The user's clear answers that got a NOTE and have no review card yet, oldest first."""
    return _rows(
        "SELECT t.id AS turn_id, t.session_id, s.unit_id, t.question, t.answer, t.note, t.created_at "
        "FROM turns t JOIN sessions s ON s.id = t.session_id "
        "LEFT JOIN cards c ON c.turn_id = t.id "
        "WHERE s.user_id = %s AND c.id IS NULL AND t.unclear = 0 AND t.note IS NOT NULL AND t.note != '' "
        "ORDER BY t.id",
        (uid,),
    )


def completed_sessions_used_phrases(uid: int) -> list[dict]:
    """The user's completed sessions with the phrase indices used in any answer: [{session_id, unit_id, used}]."""
    out: dict[int, dict] = {}
    for r in _rows(
        "SELECT s.id, s.unit_id, t.used_phrases FROM sessions s JOIN turns t ON t.session_id = s.id "
        "WHERE s.user_id = %s AND s.completed = 1 AND t.unclear = 0 ORDER BY s.id",
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
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO cards ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) ON DUPLICATE KEY UPDATE id = id",
            (_now(), *row.values()),
        )
        return cur.lastrowid if cur.rowcount else None


def list_cards(uid: int, due_by: str | None = None, session_id: int | None = None) -> list[dict]:
    """The user's active cards, oldest due first: due on or before `due_by`, or all cards of one session."""
    where, args = ["user_id = %s", "suspended = 0"], [uid]
    if due_by is not None:
        where.append("due <= %s")
        args.append(due_by)
    if session_id is not None:
        where.append("session_id = %s")
        args.append(session_id)
    return _rows(f"SELECT * FROM cards WHERE {' AND '.join(where)} ORDER BY due, id", tuple(args))


def get_card(uid: int, card_id: int) -> dict | None:
    rows = _rows("SELECT * FROM cards WHERE id = %s AND user_id = %s", (card_id, uid))
    return rows[0] if rows else None


def grade_card(card_id: int, box: int, due: str, result: str, attempt: dict) -> None:
    """Store the learner's grade and the new schedule. `attempt`: heard, correct, total (or empty).
    The caller checked the card is theirs (get_card)."""
    if not enabled():
        return
    with _connect() as conn:
        conn.execute(
            "UPDATE cards SET box = %s, due = %s, reviews = reviews + 1, lapses = lapses + %s WHERE id = %s",
            (box, due, int(result == "again"), card_id),
        )
        conn.execute(
            "INSERT INTO card_reviews (card_id, created_at, heard, correct, total, result) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (card_id, _now(), attempt.get("heard"), attempt.get("correct"), attempt.get("total"), result),
        )


def suspend_card(card_id: int) -> bool:
    """The caller checked the card is theirs (get_card)."""
    if not enabled():
        return False
    with _connect() as conn:
        return conn.execute("UPDATE cards SET suspended = 1 WHERE id = %s", (card_id,)).rowcount > 0


def card_stats(uid: int, today: str, since: str, learned_box: int = 4) -> dict:
    """The user's counts for the review page: due today, active, learned (box >= learned_box),
    reviews since `since`."""
    if not enabled():
        return {"due": 0, "active": 0, "learned": 0, "reviews": 0, "good": 0}
    with _connect() as conn:
        c = conn.execute(
            "SELECT COALESCE(SUM(due <= %s), 0) AS due, COUNT(*) AS active, COALESCE(SUM(box >= %s), 0) AS learned "
            "FROM cards WHERE user_id = %s AND suspended = 0",
            (today, learned_box, uid),
        ).fetchone()
        r = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(r.result = 'good'), 0) AS good FROM card_reviews r JOIN cards c ON c.id = r.card_id "
            "WHERE c.user_id = %s AND r.created_at >= %s",
            (uid, since),
        ).fetchone()
    # SUM() is a Decimal in MySQL
    return {"due": int(c["due"]), "active": c["active"], "learned": int(c["learned"]), "reviews": r["n"], "good": int(r["good"])}
