"""Create an account from the command line: the first admin, or any user when the web is not handy.

    python -m scripts.create_user you@example.com --name "Huy" --admin

The password is asked for (not echoed), or read from NEW_USER_PASSWORD (scripts, test servers).
The first admin also takes over the practice history saved before accounts existed.
See docs/features/accounts.md.
"""

from __future__ import annotations

import argparse
import getpass
import os

from app.services import accounts, db, history


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a user account in the DATABASE_URL database.")
    ap.add_argument("email")
    ap.add_argument("--name", default="")
    ap.add_argument("--admin", action="store_true", help="give the admin role")
    args = ap.parse_args()
    if not db.enabled():
        raise SystemExit("DATABASE_URL is empty in .env: nowhere to store accounts.")
    if not accounts.valid_email(accounts.normalize_email(args.email)):
        raise SystemExit(f"Not a valid email address: {args.email}")
    db.migrate()
    password = os.getenv("NEW_USER_PASSWORD") or getpass.getpass("Password: ")
    if accounts.password_problem(password):
        raise SystemExit(f"Password refused: at least {accounts.MIN_PASSWORD} characters.")
    if not os.getenv("NEW_USER_PASSWORD") and getpass.getpass("Again: ") != password:
        raise SystemExit("Passwords differ.")
    try:
        user = accounts.create_user(args.email, args.name, password, "admin" if args.admin else "user")
    except ValueError:
        raise SystemExit(f"{args.email} already has an account.") from None
    print(f"Created {user['role']} {user['email']} (id {user['id']}).")
    if args.admin and (claimed := history.claim_unowned(user["id"])):
        print(f"Practice history saved before accounts ({claimed} rows) now belongs to {user['email']}.")


if __name__ == "__main__":
    main()
