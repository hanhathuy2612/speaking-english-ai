"""User management for admins (docs/features/accounts.md). Mounted behind require_admin in main.py."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_admin
from app.services import accounts

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


@router.get("")
def list_users() -> list[dict]:
    return accounts.list_users()


class NewUser(BaseModel):
    email: str
    name: str = ""
    password: str
    role: Literal["user", "admin"] = "user"


@router.post("")
def create_user(body: NewUser) -> dict:
    """An account made by an admin needs no email confirmation."""
    if not accounts.valid_email(accounts.normalize_email(body.email)):
        raise HTTPException(400, "Email không hợp lệ.")
    if problem := accounts.password_problem(body.password):
        raise HTTPException(400, problem)
    try:
        return accounts.create_user(body.email, body.name, body.password, body.role, verified=True)
    except ValueError:
        raise HTTPException(409, "Email này đã có tài khoản.") from None


class UserChange(BaseModel):
    name: str | None = None
    role: Literal["user", "admin"] | None = None
    disabled: bool | None = None
    password: str | None = None
    verified: bool | None = None  # True confirms the email on the user's behalf


@router.patch("/{uid}")
def update_user(uid: int, body: UserChange, me: dict = Depends(require_admin)) -> dict:
    user = accounts.get_user(uid)
    if not user:
        raise HTTPException(404)
    losing_admin = user["role"] == "admin" and not user["disabled"] and (body.role == "user" or body.disabled)
    if losing_admin and accounts.count_admins() <= 1:
        raise HTTPException(400, "Phải còn ít nhất một quản trị viên.")
    if uid == me["id"] and (body.disabled or body.role == "user"):
        raise HTTPException(400, "Không thể tự khóa hay tự bỏ quyền quản trị của mình.")
    if body.password is not None:
        if problem := accounts.password_problem(body.password):
            raise HTTPException(400, problem)
        accounts.set_password(uid, body.password)
    if body.verified:
        accounts.mark_verified(uid)
    accounts.update_user(uid, name=body.name, role=body.role, disabled=body.disabled)
    return accounts.get_user(uid) or {}
