"""The orphan check of scripts/migrate_sqlite.py (MySQL test database)."""

from __future__ import annotations

from app.services import accounts, db, history
from scripts import migrate_sqlite


def test_orphan_check_finds_rows_without_a_parent(mysql):
    with db.connect() as conn:
        assert all(n == 0 for *_, n in migrate_sqlite.orphans(conn))
        conn.execute("SET FOREIGN_KEY_CHECKS = 0")
        conn.execute("INSERT INTO email_tokens (token_hash, user_id, kind, expires_at) VALUES ('h', 999, 'reset', 'x')")
        conn.execute("SET FOREIGN_KEY_CHECKS = 1")
        found = {(t, c): n for t, c, _, n in migrate_sqlite.orphans(conn)}
    assert found[("email_tokens", "user_id")] == 1
