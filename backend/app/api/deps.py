"""Who is calling: the access token resolved to a user, and the role checks (docs/features/accounts.md).

Routers are mounted with `Depends(current_user)` (or `require_admin`) in main.py, so no API route is
reachable without logging in; a route that needs the user id declares the same dependency again,
which FastAPI resolves once per request. The token is a stateless JWT (services/tokens.py): checking
it reads no database.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.services import tokens


def bearer(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else None


def current_user(request: Request) -> dict:
    user = tokens.access_user(bearer(request))
    if not user:
        raise HTTPException(401, "Bạn cần đăng nhập.")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được dùng chức năng này.")
    return user
