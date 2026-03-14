"""
Create the PostgreSQL database if it does not exist.

Reads DATABASE_URL from .env (e.g. postgresql+asyncpg://user:pass@host:port/speaking_english),
connects to the default "postgres" database and runs CREATE DATABASE.

Usage (from backend/):
  poetry run poe create-db
  # or
  poetry run python scripts/create_pg_db.py
"""

from pathlib import Path
import os
import sys
from urllib.parse import urlparse, urlunparse

# Load .env from backend/
backend_dir = Path(__file__).resolve().parent.parent
env_file = backend_dir / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)

url = os.environ.get("DATABASE_URL", "")
if not url.startswith("postgresql"):
    print(
        "DATABASE_URL not set or not PostgreSQL. Set it in .env (e.g. postgresql+asyncpg://...).",
        file=sys.stderr,
    )
    sys.exit(1)

# Parse DATABASE_URL (handles special chars in password)
parse_url = url.replace("postgresql+asyncpg://", "postgresql://")
if "://" not in parse_url:
    parse_url = "postgresql://" + parse_url
u = urlparse(parse_url)
dbname = (u.path or "/").strip("/").split("?")[0] or "speaking_english"
# Connect to default "postgres" DB to run CREATE DATABASE
connect_url = urlunparse((u.scheme, u.netloc, "/postgres", u.params, u.query, u.fragment))

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Install psycopg2: poetry add --group dev psycopg2-binary", file=sys.stderr)
    sys.exit(1)

try:
    conn = psycopg2.connect(connect_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    if cur.fetchone():
        print(f"Database '{dbname}' already exists.")
    else:
        cur.execute(f'CREATE DATABASE "{dbname}"')
        print(f"Created database '{dbname}'.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Failed to create database: {e}", file=sys.stderr)
    sys.exit(1)
