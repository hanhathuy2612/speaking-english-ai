"""Copy an existing SQLite history file (the old data/history.db) into the MySQL database.

    python -m scripts.migrate_sqlite ../data/history.db   (from backend/)

The target is the database of DATABASE_URL in .env. It is created if needed and must be empty:
the script refuses to run when a table already has rows, unless --force (which empties the tables
first). Ids are kept, so foreign keys stay valid. Files from older versions that lack newer
columns are fine: those columns get their default. The SQLite file is opened read-only and never
changed. Prints the row count of every table in the source and in MySQL, and exits with status 1
when they differ.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from app.services import db

# Parents before children.
TABLES = [
    "users", "email_tokens", "sessions", "turns", "shadows", "retells", "checks", "talk_practice",
    "drills", "fluency", "cards", "card_reviews", "lesson_reads", "lessons", "content_topics", "content_units",
]  # fmt: skip
BATCH = 500


def open_source(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"No such file: {path}")
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def source_columns(src: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in src.execute(f"PRAGMA table_info({table})")]


def target_columns(conn: db.Conn, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
        (table,),
    )
    return [r["c"] for r in rows]


def count(conn: db.Conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) AS n FROM `{table}`").fetchone()["n"]


def orphans(conn: db.Conn) -> list[tuple[str, str, str, int]]:
    """(table, column, parent table, rows whose parent is missing) for every foreign key."""
    fks = conn.execute(
        "SELECT TABLE_NAME AS t, COLUMN_NAME AS c, REFERENCED_TABLE_NAME AS p, REFERENCED_COLUMN_NAME AS pc "
        "FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY TABLE_NAME, COLUMN_NAME"
    ).fetchall()
    found = []
    for fk in fks:
        n = conn.execute(
            f"SELECT COUNT(*) AS n FROM `{fk['t']}` AS child LEFT JOIN `{fk['p']}` AS parent "
            f"ON child.`{fk['c']}` = parent.`{fk['pc']}` "
            f"WHERE child.`{fk['c']}` IS NOT NULL AND parent.`{fk['pc']}` IS NULL"
        ).fetchone()["n"]
        found.append((fk["t"], fk["c"], fk["p"], n))
    return found


def copy_table(src: sqlite3.Connection, conn: db.Conn, table: str) -> int:
    """Copy the columns both sides have; the rest keep their MySQL default. Returns rows copied."""
    if not source_columns(src, table):
        return 0  # the old file has no such table
    cols = [c for c in target_columns(conn, table) if c in source_columns(src, table)]
    names = ", ".join(f"`{c}`" for c in cols)
    sql = f"INSERT INTO `{table}` ({names}) VALUES ({', '.join(['%s'] * len(cols))})"
    cur = src.execute(f"SELECT {names.replace('`', '')} FROM {table} ORDER BY rowid")
    copied = 0
    while rows := cur.fetchmany(BATCH):
        conn.executemany(sql, rows)
        copied += len(rows)
    return copied


def main() -> None:
    ap = argparse.ArgumentParser(description="Copy an old SQLite history file into the MySQL database of DATABASE_URL.")
    ap.add_argument("sqlite_file", type=Path, help="the SQLite file, e.g. ../data/history.db from backend/ (opened read-only)")
    ap.add_argument("--force", action="store_true", help="empty the MySQL tables first if they already have rows")
    args = ap.parse_args()
    if not db.enabled():
        raise SystemExit("DATABASE_URL is empty: set it in .env (see .env.example).")

    src = open_source(args.sqlite_file)
    db.migrate()
    with db.connect() as conn:
        busy = {t: n for t in TABLES if (n := count(conn, t))}
        if busy and not args.force:
            found = ", ".join(f"{t} ({n} rows)" for t, n in busy.items())
            raise SystemExit(f"The target database is not empty: {found}. Use --force to empty it first.")
        if busy:
            print(f"WARNING: --force empties these tables first: {', '.join(busy)}", file=sys.stderr)
        conn.execute("SET FOREIGN_KEY_CHECKS = 0")
        for t in reversed(TABLES):
            conn.execute(f"TRUNCATE TABLE `{t}`")
        for t in TABLES:
            copy_table(src, conn, t)
        conn.execute("SET FOREIGN_KEY_CHECKS = 1")

    ok = True
    print(f"{'table':<16}{'sqlite':>8}{'mysql':>8}")
    with db.connect() as conn:
        for t in TABLES:
            before = src.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] if source_columns(src, t) else 0
            after = count(conn, t)
            ok &= before == after
            print(f"{t:<16}{before:>8}{after:>8}{'' if before == after else '  MISMATCH'}")
    src.close()
    # The copy ran with foreign key checks off, so check every foreign key afterwards.
    print(f"\n{'foreign key':<34}{'orphans':>8}")
    broken = False
    with db.connect() as conn:
        for table, column, parent, n in orphans(conn):
            broken |= n > 0
            print(f"{table + '.' + column + ' -> ' + parent:<34}{n:>8}{'  ORPHANS' if n else ''}")
    if not ok:
        print("Row counts differ: do not use this copy.", file=sys.stderr)
        raise SystemExit(1)
    if broken:
        if not args.force:
            print("Some rows point at a missing parent: do not use this copy (--force to accept).", file=sys.stderr)
            raise SystemExit(1)
        print("WARNING: some rows point at a missing parent (accepted because of --force).", file=sys.stderr)
    print("Done: every table has the same number of rows" + ("." if not broken else ", with orphan rows."))


if __name__ == "__main__":
    main()
