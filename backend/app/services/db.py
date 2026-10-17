"""The MySQL database shared by accounts (services/accounts.py), practice history (services/history.py)
and lesson content (services/content.py).

One connection per call: `with db.connect() as conn:` commits on success, rolls back on error and
always closes. Rows are dicts. Strings compare as binary (utf8mb4_bin) like SQLite did, so ids and
emails are case-sensitive.

The schema lives in app/migrations/NNN_name.sql, applied in name order by `migrate()` (at startup and
by `python -m scripts.migrate`). One small change per file; never edit a file once it has been applied,
add a new one. MySQL commits DDL at once, so a file that fails halfway is not undone and is not recorded;
it is rerun in full on the next start, so a non-idempotent file (e.g. ALTER ... ADD COLUMN) that failed
halfway needs manual cleanup. Hence one statement per file where possible.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pymysql
from pymysql.cursors import DictCursor

from app.core import config

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_LOCK = "speaking_migrate"
IntegrityError = pymysql.err.IntegrityError


def enabled() -> bool:
    return bool(config.DATABASE_URL)


class Conn:
    """A pymysql connection whose execute() returns a dict cursor, like sqlite3's."""

    def __init__(self, raw: pymysql.connections.Connection):
        self.raw = raw

    def execute(self, sql: str, args: tuple | list = ()) -> DictCursor:
        cur = self.raw.cursor()
        cur.execute(sql, args)
        return cur

    def executemany(self, sql: str, rows: list) -> DictCursor:
        cur = self.raw.cursor()
        cur.executemany(sql, rows)
        return cur


def raw_connect(**overrides) -> pymysql.connections.Connection:
    params = {**config.parse_database_url(config.DATABASE_URL), **overrides}
    return pymysql.connect(charset="utf8mb4", autocommit=False, cursorclass=DictCursor, **params)


@contextmanager
def connect() -> Iterator[Conn]:
    raw = raw_connect()
    try:
        yield Conn(raw)
        raw.commit()
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()


def _statements(sql: str) -> list[str]:
    """Split a migration file into statements: drop `--` comments, split on `;`, skip empties.

    Simple on purpose: a string literal containing `--` or `;` would be cut, so keep those out of migrations.
    """
    code = "\n".join(re.sub(r"--.*", "", line) for line in sql.splitlines())
    return [s.strip() for s in code.split(";") if s.strip()]


def _files(folder: Path) -> list[Path]:
    files = sorted(folder.glob("*.sql"))
    for p in files:
        if not re.fullmatch(r"\d{3}_\w+\.sql", p.name):
            raise RuntimeError(f"Bad migration file name {p.name!r}: it must be NNN_name.sql with a 3-digit number")
    return files


def _applied(conn: Conn) -> dict[str, str]:
    """version -> applied_at, creating the bookkeeping table if needed."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(255) PRIMARY KEY, applied_at VARCHAR(32) NOT NULL) "
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin"
    )
    return {r["version"]: r["applied_at"] for r in conn.execute("SELECT version, applied_at FROM schema_migrations")}


def migration_status(folder: Path = MIGRATIONS_DIR) -> list[tuple[str, str | None]]:
    """(file name, applied_at or None when pending) for every migration file, in order."""
    with connect() as conn:
        done = _applied(conn)
    return [(p.name, done.get(p.stem)) for p in _files(folder)]


def migrate(folder: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply the migration files not yet recorded in schema_migrations; returns the names applied."""
    applied: list[str] = []
    with connect() as conn:
        if not conn.execute("SELECT GET_LOCK(%s, 30) AS got", (_LOCK,)).fetchone()["got"]:
            raise RuntimeError("Could not get the migration lock: another migration is running")
        try:
            done = _applied(conn)
            for path in _files(folder):
                if path.stem in done:
                    continue
                for stmt in _statements(path.read_text(encoding="utf-8")):
                    try:
                        conn.execute(stmt, None)  # no args: a literal % (LIKE 'a%') must not be formatted
                    except Exception as e:
                        raise RuntimeError(f"Migration {path.name} failed at: {stmt[:200]!r}: {e}") from e
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
                    (path.stem, datetime.now().isoformat(timespec="seconds")),
                )
                conn.raw.commit()
                applied.append(path.name)
        finally:
            try:
                conn.execute("SELECT RELEASE_LOCK(%s)", (_LOCK,))
            except Exception:
                pass  # must not hide the real error; closing the connection frees the lock anyway
    return applied
