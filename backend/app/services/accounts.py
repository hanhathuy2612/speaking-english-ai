"""Accounts: users with a role and one-time email tokens, in the history database.

Passwords are hashed with scrypt (hashlib, no extra dependency). Logins are stateless JWTs
(services/tokens.py), nothing about them is stored here. Email tokens are random strings sent in a
link; only their SHA-256 is stored, so a copy of the database cannot be used to open them.
See docs/features/accounts.md.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from app.services import db

MAX_NAME = 255  # users.name VARCHAR(255)
ROLES = ("user", "admin")
MIN_PASSWORD = 8
TOKEN_HOURS = {"verify": 48, "reset": 1}
# scrypt cost: about 50 ms and 16 MB per hash, OWASP's minimum for scrypt.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
_DUMMY = None  # hash compared against when the email is unknown, so timing does not reveal accounts


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=64 << 20)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    got = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=64 << 20
    )
    return hmac.compare_digest(got.hex(), digest)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain and " " not in email and len(email) <= 254


def password_problem(password: str) -> str | None:
    """Why a new password is refused (Vietnamese, shown to the user), or None."""
    if len(password) < MIN_PASSWORD:
        return f"Mật khẩu cần ít nhất {MIN_PASSWORD} ký tự."
    if len(password) > 200:
        return "Mật khẩu quá dài."
    return None


def public(row: dict) -> dict:
    """A user as the API returns it: never the password hash."""
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "verified": row["verified_at"] is not None,
        "disabled": bool(row["disabled"]),
        "created_at": row["created_at"],
    }


def create_user(email: str, name: str, password: str, role: str = "user", verified: bool = True) -> dict:
    """Raises ValueError when the email is taken or the role is unknown."""
    assert role in ROLES, f"unknown role {role!r}"
    email = normalize_email(email)
    now = _now().isoformat()
    try:
        with db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, name, password, role, verified_at, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (email, name.strip() or email.split("@")[0], hash_password(password), role, now if verified else None, now),
            )
            uid = cur.lastrowid
    except db.IntegrityError as e:
        raise ValueError("email already registered") from e
    user = get_user(uid)
    assert user is not None
    return user


def seed_admin(email: str, password: str) -> dict | None:
    """First start only (no users at all): create this verified admin. None when users exist."""
    if _one("SELECT 1 AS x FROM users LIMIT 1", ()):
        return None
    return create_user(email, "", password, "admin")


def _one(sql: str, args: tuple) -> dict | None:
    with db.connect() as conn:
        return conn.execute(sql, args).fetchone()


def get_user(uid: int) -> dict | None:
    row = _one("SELECT * FROM users WHERE id = %s", (uid,))
    return public(row) if row else None


def user_by_email(email: str) -> dict | None:
    row = _one("SELECT * FROM users WHERE email = %s", (normalize_email(email),))
    return public(row) if row else None


def list_users() -> list[dict]:
    with db.connect() as conn:
        return [public(r) for r in conn.execute("SELECT * FROM users ORDER BY id")]


def count_admins() -> int:
    row = _one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND disabled = 0", ())
    return row["n"] if row else 0


def update_user(uid: int, *, name: str | None = None, role: str | None = None, disabled: bool | None = None) -> None:
    assert role is None or role in ROLES, f"unknown role {role!r}"
    fields = {"name": name, "role": role, "disabled": None if disabled is None else int(disabled)}
    sets = {k: v for k, v in fields.items() if v is not None}
    if not sets:
        return
    with db.connect() as conn:
        conn.execute(f"UPDATE users SET {', '.join(f'{k} = %s' for k in sets)} WHERE id = %s", (*sets.values(), uid))


def set_password(uid: int, password: str) -> None:
    """New password; refresh tokens issued before it stop working (login_state)."""
    with db.connect() as conn:
        conn.execute("UPDATE users SET password = %s WHERE id = %s", (hash_password(password), uid))


def mark_verified(uid: int) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE users SET verified_at = COALESCE(verified_at, %s) WHERE id = %s", (_now().isoformat(), uid))


def authenticate(email: str, password: str) -> dict | None:
    """The user whose email and password match (disabled or unverified users included: the caller
    tells them apart), or None."""
    global _DUMMY
    row = _one("SELECT * FROM users WHERE email = %s", (normalize_email(email),))
    if row is None:
        _DUMMY = _DUMMY or hash_password(secrets.token_hex(8))
        verify_password(password, _DUMMY)  # same work as a real check
        return None
    return public(row) if verify_password(password, row["password"]) else None


# ----- Login state (services/tokens.py signs the tokens) -----


def login_state(uid: int) -> tuple[dict, str] | None:
    """The active, verified user and a stamp of their password hash, or None. The stamp goes into the
    refresh token, so a new password ends the logins made with the old one."""
    if not db.enabled():
        return None
    row = _one("SELECT * FROM users WHERE id = %s AND disabled = 0 AND verified_at IS NOT NULL", (uid,))
    return (public(row), _sha(row["password"])[:16]) if row else None


# ----- One-time email tokens -----


def new_token(uid: int, kind: str) -> str:
    """A link token for `kind` ('verify' or 'reset'); earlier unused tokens of that kind stop working."""
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(hours=TOKEN_HOURS[kind])
    with db.connect() as conn:
        conn.execute("DELETE FROM email_tokens WHERE user_id = %s AND kind = %s", (uid, kind))
        conn.execute(
            "INSERT INTO email_tokens (token_hash, user_id, kind, expires_at) VALUES (%s, %s, %s, %s)",
            (_sha(token), uid, kind, expires.isoformat()),
        )
    return token


def use_token(token: str, kind: str) -> int | None:
    """The user id of a valid, unused token, which is then used up; None otherwise."""
    with db.connect() as conn:
        now = _now().isoformat()
        # One atomic UPDATE: of two concurrent requests with the same link, only one changes a row.
        cur = conn.execute(
            "UPDATE email_tokens SET used_at = %s WHERE token_hash = %s AND kind = %s AND used_at IS NULL AND expires_at > %s",
            (now, _sha(token), kind, now),
        )
        if cur.rowcount != 1:
            return None
        return conn.execute("SELECT user_id FROM email_tokens WHERE token_hash = %s", (_sha(token),)).fetchone()["user_id"]
