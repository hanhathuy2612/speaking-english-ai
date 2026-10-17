"""Lesson content (topics and units) stored in the database so admins can edit it from the web.

data/units.json stays the shipped content: on startup every topic and unit of the file that is new
or still untouched by an admin is copied in (so content added in the repo still arrives), while
anything an admin saved (source 'admin') is left alone. Deleting only hides a unit (`deleted`), so
the file never brings it back and its practice history keeps a title. Rows hold the unit's JSON
as is; checking it is interview/units.py's job. See docs/features/content-admin.md.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.services import db

STEP = 10  # gap between positions, so a unit can be placed between two others


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dump(item: dict) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def _sync(conn: db.Conn, table: str, items: list[dict]) -> None:
    rows = {r["id"]: r for r in conn.execute(f"SELECT id, data, source FROM {table}")}
    end = (conn.execute(f"SELECT MAX(position) AS m FROM {table}").fetchone()["m"] or 0) + STEP
    for i, item in enumerate(items):
        row = rows.get(item["id"])
        if row is None:  # new in the file: after everything, in file order
            conn.execute(
                f"INSERT INTO {table} (id, position, data) VALUES (%s, %s, %s)",
                (item["id"], end + i * STEP if rows else i * STEP, _dump(item)),
            )
        elif row["source"] == "file" and row["data"] != _dump(item):
            conn.execute(f"UPDATE {table} SET data = %s WHERE id = %s", (_dump(item), item["id"]))


def init(file_topics: list[dict], file_units: list[dict]) -> None:
    """Bring in the shipped content (see the module docstring)."""
    if not db.enabled():
        return
    with db.connect() as conn:
        _sync(conn, "content_topics", file_topics)
        _sync(conn, "content_units", file_units)


def load(include_deleted: bool = False) -> tuple[list[dict], list[dict]]:
    """(topics, units) in roadmap order, as dicts like units.json."""
    with db.connect() as conn:
        topics = [json.loads(r["data"]) for r in conn.execute("SELECT data FROM content_topics ORDER BY position, id")]
        where = "" if include_deleted else "WHERE deleted = 0"
        units = [json.loads(r["data"]) for r in conn.execute(f"SELECT data FROM content_units {where} ORDER BY position, id")]
    return topics, units


def unit_rows() -> list[dict]:
    """Every unit with its admin metadata, deleted ones included, in roadmap order."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT c.*, u.name AS updated_by_name FROM content_units c LEFT JOIN users u ON u.id = c.updated_by "
            "ORDER BY c.position, c.id"
        ).fetchall()
    return [{**dict(r), "data": json.loads(r["data"]), "deleted": bool(r["deleted"])} for r in rows]


def get_unit(unit_id: str) -> dict | None:
    """A unit's row (deleted or not)."""
    return next((r for r in unit_rows() if r["id"] == unit_id), None)


def save_unit(unit: dict, uid: int) -> None:
    """Insert or replace a unit; a new one goes last in its topic (before the next topic's units)."""
    with db.connect() as conn:
        exists = conn.execute("SELECT 1 FROM content_units WHERE id = %s", (unit["id"],)).fetchone()
        if exists:
            conn.execute(
                "UPDATE content_units SET data = %s, source = 'admin', updated_at = %s, updated_by = %s WHERE id = %s",
                (_dump(unit), _now(), uid, unit["id"]),
            )
            return
        same_topic = [
            r["position"]
            for r in conn.execute("SELECT position, data FROM content_units ORDER BY position")
            if json.loads(r["data"])["topic"] == unit["topic"]
        ]
        last = conn.execute("SELECT MAX(position) AS m FROM content_units").fetchone()["m"] or 0
        position = max(same_topic) + 1 if same_topic else last + STEP
        conn.execute(
            "INSERT INTO content_units (id, position, data, source, updated_at, updated_by) VALUES (%s, %s, %s, 'admin', %s, %s)",
            (unit["id"], position, _dump(unit), _now(), uid),
        )


def set_deleted(unit_id: str, deleted: bool, uid: int) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE content_units SET deleted = %s, source = 'admin', updated_at = %s, updated_by = %s WHERE id = %s",
            (int(deleted), _now(), uid, unit_id),
        )


def set_order(unit_ids: list[str]) -> None:
    """New roadmap order: the given units first, in this order, then any others as they were."""
    with db.connect() as conn:
        rest = [r["id"] for r in conn.execute("SELECT id FROM content_units ORDER BY position, id") if r["id"] not in unit_ids]
        conn.executemany(
            "UPDATE content_units SET position = %s WHERE id = %s",
            [(i * STEP, uid) for i, uid in enumerate([*unit_ids, *rest])],
        )


def save_topic(topic: dict, uid: int) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE content_topics SET data = %s, source = 'admin', updated_at = %s, updated_by = %s WHERE id = %s",
            (_dump(topic), _now(), uid, topic["id"]),
        )
