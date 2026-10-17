"""Apply the database migrations (app/migrations/NNN_name.sql) to the DATABASE_URL database.

    python -m scripts.migrate           # apply every pending migration
    python -m scripts.migrate status    # list each migration as applied (with date) or pending

The server does the same at startup; this is for running them by hand first. See docs/dev-environment.md.
"""

from __future__ import annotations

import argparse

from app.services import db


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply pending database migrations to the DATABASE_URL database.")
    ap.add_argument("command", nargs="?", choices=["status"], help="'status' lists migrations instead of applying them")
    args = ap.parse_args()
    if not db.enabled():
        raise SystemExit("DATABASE_URL is empty: set it in .env (see .env.example).")

    if args.command == "status":
        for name, applied_at in db.migration_status():
            print(f"{name:<40}{'applied ' + applied_at if applied_at else 'pending'}")
        return
    applied = db.migrate()
    print("\n".join(f"Applied {name}" for name in applied) if applied else "Nothing to apply: the database is up to date.")


if __name__ == "__main__":
    main()
