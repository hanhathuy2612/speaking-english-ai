"""Who is calling: the login cookie resolved to a user, and the role checks (docs/features/accounts.md).

Routers are mounted with `Depends(current_user)` (or `require_admin`) in main.py, so no API route is
reachable without logging in; a route that needs the user id declares the same dependency again,
which FastAPI resolves once per request.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, WebSocket

from app.services import accounts

COOKIE = "sid"


def current_user(request: Request) -> dict:
    user = accounts.session_user(request.cookies.get(COOKIE))
    if not user:
        raise HTTPException(401, "Bạn cần đăng nhập.")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được dùng chức năng này.")
    return user


def same_origin(origin: str | None, host: str | None) -> bool:
    """A browser sends Origin on WebSocket handshakes; another site's page must not reuse our cookie."""
    return origin is None or urlsplit(origin).netloc == host


def ws_user(ws: WebSocket) -> dict | None:
    if not same_origin(ws.headers.get("origin"), ws.headers.get("host")):
        return None
    return accounts.session_user(ws.cookies.get(COOKIE))
