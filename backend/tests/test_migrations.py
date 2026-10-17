"""Schema migrations (db.migrate) against scratch MySQL databases named like TEST_DATABASE_URL's, plus `_<n>`."""

from __future__ import annotations

import pymysql
import pytest

from app.core import config
from app.services import db

EXPECTED_TABLES = {
    "users", "email_tokens", "sessions", "turns", "shadows", "retells", "checks", "talk_practice", "drills",
    "fluency", "cards", "card_reviews", "lesson_reads", "lessons", "content_topics", "content_units",
}  # fmt: skip


@pytest.fixture
def scratch(_test_database, monkeypatch):
    """An empty database next to the test one (its name ends in `_test`, so it is never the real one)."""
    params = config.parse_database_url(_test_database)
    name = params.pop("database").removesuffix("_test") + "_migrations_test"
    admin = pymysql.connect(charset="utf8mb4", autocommit=True, **params)
    admin.cursor().execute(f"DROP DATABASE IF EXISTS `{name}`")
    admin.cursor().execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
    monkeypatch.setattr(config, "DATABASE_URL", _test_database.rsplit("/", 1)[0] + "/" + name)
    yield
    admin.cursor().execute(f"DROP DATABASE IF EXISTS `{name}`")
    admin.close()


def _columns(table):
    with db.connect() as conn:
        return {r["COLUMN_NAME"] for r in conn.execute(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            (table,))}


def test_fresh_database_gets_the_initial_schema_once(scratch):
    assert db.migrate() == ["001_initial.sql"]
    with db.connect() as conn:
        tables = {next(iter(r.values())) for r in conn.execute("SHOW TABLES")}
        collations = {r["TABLE_COLLATION"] for r in conn.execute(
            "SELECT TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")}
    assert tables == EXPECTED_TABLES | {"schema_migrations"}
    assert collations == {"utf8mb4_bin"}
    assert db.migrate() == []
    assert [(n, bool(at)) for n, at in db.migration_status()] == [("001_initial.sql", True)]


def test_a_database_made_before_migrations_just_records_001(scratch):
    db.migrate()
    with db.connect() as conn:
        conn.execute("DROP TABLE schema_migrations")
    assert db.migrate() == ["001_initial.sql"]  # IF NOT EXISTS: tables are kept, 001 is recorded


def test_only_new_files_are_applied(scratch, tmp_path):
    (tmp_path / "001_initial.sql").write_text("CREATE TABLE a (id INT PRIMARY KEY);\n", encoding="utf-8")
    assert db.migrate(tmp_path) == ["001_initial.sql"]
    (tmp_path / "002_x.sql").write_text(
        "-- add a column; the comment has a semicolon\nALTER TABLE a ADD COLUMN note VARCHAR(10); -- trailing\n",
        encoding="utf-8",
    )
    assert db.migration_status(tmp_path)[1][1] is None
    assert db.migrate(tmp_path) == ["002_x.sql"]
    assert _columns("a") == {"id", "note"}


def test_a_failing_migration_names_the_file_and_is_not_recorded(scratch, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE a (id INT);\n", encoding="utf-8")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE b (id INT);\nALTER TABLE nope ADD COLUMN x INT;\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match=r"002_bad\.sql.*ALTER TABLE nope"):
        db.migrate(tmp_path)
    assert [(n, bool(at)) for n, at in db.migration_status(tmp_path)] == [("001_ok.sql", True), ("002_bad.sql", False)]


@pytest.mark.parametrize("name", ["1_x.sql", "0001_x.sql", "init.sql"])
def test_a_misnamed_file_raises(scratch, tmp_path, name):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE a (id INT);\n", encoding="utf-8")
    (tmp_path / name).write_text("CREATE TABLE b (id INT);\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match=name.replace(".", r"\.") + ".*NNN_name.sql"):
        db.migrate(tmp_path)


def test_a_percent_sign_in_a_migration_works(scratch, tmp_path):
    (tmp_path / "001_p.sql").write_text(
        "CREATE TABLE a (v VARCHAR(10));\nINSERT INTO a VALUES ('ab'), ('c');\nDELETE FROM a WHERE v LIKE 'a%';\n",
        encoding="utf-8",
    )
    assert db.migrate(tmp_path) == ["001_p.sql"]
    with db.connect() as conn:
        assert conn.execute("SELECT v FROM a").fetchall() == [{"v": "c"}]
