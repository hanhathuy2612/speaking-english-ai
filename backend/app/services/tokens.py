"""Login tokens: stateless JWTs signed with HS256 (docs/features/accounts.md).

An access token (15 minutes) carries the user's id, email, name and role, so an API call is checked
without reading the database. A refresh token (30 days) only carries the id and a stamp of the
password hash; exchanging it reads the user row once, so a disabled account, a role change or a new
password takes effect within one access token lifetime. Nothing about a login is stored on the server.

The signing key is JWT_SECRET, or a random key kept next to the database file when that is empty.
"""

from __future__ import annotations

import secrets
import time
from pathlib import Path

import jwt

from app.core import config

ALGORITHM = "HS256"
ACCESS_SECONDS = 15 * 60
REFRESH_SECONDS = 30 * 86400
_keys: dict[Path, str] = {}


def _key() -> str:
    if config.JWT_SECRET:
        return config.JWT_SECRET
    path = config.ROOT_DIR / "data" / "jwt_secret"
    if path not in _keys:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        _keys[path] = path.read_text(encoding="utf-8").strip()
    return _keys[path]


def _sign(claims: dict, seconds: int) -> str:
    now = int(time.time())
    return jwt.encode({**claims, "iat": now, "exp": now + seconds}, _key(), algorithm=ALGORITHM)


def _read(token: str | None, typ: str) -> dict | None:
    if not token:
        return None
    try:
        claims = jwt.decode(token, _key(), algorithms=[ALGORITHM], options={"require": ["exp", "sub", "typ"]})
    except jwt.InvalidTokenError:
        return None
    return claims if claims["typ"] == typ else None


def issue(user: dict, stamp: str) -> dict:
    """The tokens a login, an email link or a refresh hands to the browser."""
    access = {"sub": str(user["id"]), "typ": "access", "email": user["email"], "name": user["name"], "role": user["role"]}
    return {
        "access_token": _sign(access, ACCESS_SECONDS),
        "refresh_token": _sign({"sub": str(user["id"]), "typ": "refresh", "pwd": stamp}, REFRESH_SECONDS),
        "expires_in": ACCESS_SECONDS,
    }


def access_user(token: str | None) -> dict | None:
    """The caller of an API request, from the access token alone: {id, email, name, role}."""
    c = _read(token, "access")
    if not c:
        return None
    return {"id": int(c["sub"]), "email": c["email"], "name": c["name"], "role": c["role"]}


def refresh_claims(token: str | None) -> tuple[int, str] | None:
    """(user id, password stamp) of a valid refresh token; the caller checks both against the database."""
    c = _read(token, "refresh")
    return (int(c["sub"]), c.get("pwd", "")) if c else None
