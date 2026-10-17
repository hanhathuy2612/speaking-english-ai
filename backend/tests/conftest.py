"""Test setup. Database tests run against TEST_DATABASE_URL (a MySQL database of their own).

The `mysql` fixture drops and recreates that database once per run, applies the migrations, and
empties its tables (not schema_migrations) before each test. Without TEST_DATABASE_URL those tests are skipped; DATABASE_URL (the real data) is never used.
"""

from __future__ import annotations

import os

import pymysql
import pytest

from app.core import config


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    """Tests that do not ask for `mysql` must not reach any database."""
    monkeypatch.setattr(config, "DATABASE_URL", "")


@pytest.fixture(scope="session")
def _test_database():
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set (see .env.example): MySQL tests need their own database")
    params = config.parse_database_url(url)
    name = params.pop("database")
    real_url = os.getenv("DATABASE_URL", "")
    real = config.parse_database_url(real_url)["database"].lower() if real_url else None
    # MySQL on Windows compares database names without case, so compare lower-cased; the test
    # database is dropped on every run, hence the "_test" suffix is required as well.
    if name.lower() in (real, "speaking") or not name.lower().endswith("_test"):
        pytest.exit(f"Refusing TEST_DATABASE_URL: database {name!r} must end with '_test' and differ from the real one "
                    "(it is dropped on every run).", returncode=2)
    conn = pymysql.connect(charset="utf8mb4", autocommit=True, **params)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
            cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
    finally:
        conn.close()
    from app.services import db

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "DATABASE_URL", url)
        db.migrate()
    return url


@pytest.fixture
def mysql(_test_database, tmp_path, monkeypatch):
    """Point the app at the test database (empty tables) and the project root at a temp directory."""
    monkeypatch.setattr(config, "DATABASE_URL", _test_database)
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    from app.services import db

    with db.connect() as conn:
        conn.execute("SET FOREIGN_KEY_CHECKS = 0")
        for row in conn.execute("SHOW TABLES").fetchall():
            table = next(iter(row.values()))
            if table != "schema_migrations" and conn.execute(f"SELECT 1 FROM `{table}` LIMIT 1").fetchone():  # TRUNCATE is slow, skip empty tables
                conn.execute(f"TRUNCATE TABLE `{table}`")
        conn.execute("SET FOREIGN_KEY_CHECKS = 1")
    return tmp_path
