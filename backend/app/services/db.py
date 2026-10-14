"""The SQLite file shared by accounts (services/accounts.py) and practice history (services/history.py)."""

from __future__ import annotations

import sqlite3

from app.core import config


def enabled() -> bool:
    return bool(config.HISTORY_DB)


def connect() -> sqlite3.Connection:
    path = config.ROOT_DIR / config.HISTORY_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
