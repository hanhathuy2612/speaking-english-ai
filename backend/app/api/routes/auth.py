"""Login, sign-up with email confirmation, password reset, and the current user
(docs/features/accounts.md). Only /me and /password need a login.

Sign-up, resend and forgot answer the same whether or not the email has an account, and send their
email from a background task, so neither the answer nor its timing tells which addresses exist.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import COOKIE, current_user
from app.core import config
from app.services import accounts, mailer

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Attempts kept in memory: enough for one local server, reset on restart.
WINDOW_S = 15 * 60
MAX_FAILS = {"email": 5, "ip": 20}  # wrong passwords
MAX_EMAILS = {"email": 3, "ip": 10}  # emails sent (sign-up, resend, forgot)
_fails: dict[str, deque[float]] = defaultdict(deque)
_sends: dict[str, deque[float]] = defaultdict(deque)

APP = "Phòng tập nói"


def _recent(store: dict[str, deque[float]], key: str) -> deque[float]:
    q = store[key]
    while q and q[0] < time.monotonic() - WINDOW_S:
        q.popleft()
    return q


def _over(store: dict[str, deque[float]], limits: dict[str, int], email: str, ip: str) -> bool:
    return len(_recent(store, f"email:{email}")) >= limits["email"] or len(_recent(store, f"ip:{ip}")) >= limits["ip"]


def _count(store: dict[str, deque[float]], email: str, ip: str) -> None:
    _recent(store, f"email:{email}").append(time.monotonic())
    _recent(store, f"ip:{ip}").append(time.monotonic())


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def set_login_cookie(request: Request, response: Response, uid: int) -> None:
    response.set_cookie(
        COOKIE,
        accounts.new_session(uid),
        max_age=accounts.SESSION_DAYS * 86400,
        httponly=True,  # page scripts never see it
        samesite="lax",  # not sent on another site's POST or WebSocket
        secure=request.url.scheme == "https",
        path="/",
    )


def _link(request: Request, page: str, token: str) -> str:
    """Link for an email. APP_URL when set; the request's own address only while emails go to the
    console, because a forged Host header would otherwise send someone's reset link elsewhere."""
    if config.APP_URL:
        base = config.APP_URL
    elif mailer.configured():
        raise HTTPException(500, "Máy chủ chưa cấu hình APP_URL nên chưa gửi được email.")
    else:
        base = str(request.base_url).rstrip("/")
    return f"{base}/{page}?token={token}"


def _send_verify(tasks: BackgroundTasks, request: Request, user: dict) -> None:
    link = _link(request, "verify", accounts.new_token(user["id"], "verify"))
    body = (
        f"Chào {user['name']},\n\n"
        f"Bấm link sau để kích hoạt tài khoản {APP} (hết hạn sau {accounts.TOKEN_HOURS['verify']} giờ):\n{link}\n\n"
        "Nếu bạn không đăng ký, hãy bỏ qua email này."
    )
    tasks.add_task(mailer.send, user["email"], f"Xác nhận email · {APP}", body)


def _send_reset(tasks: BackgroundTasks, request: Request, user: dict) -> None:
    link = _link(request, "reset", accounts.new_token(user["id"], "reset"))
    body = (
        f"Chào {user['name']},\n\n"
        f"Bấm link sau để đặt mật khẩu mới (hết hạn sau {accounts.TOKEN_HOURS['reset']} giờ):\n{link}\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này: mật khẩu cũ vẫn dùng được."
    )
    tasks.add_task(mailer.send, user["email"], f"Đặt lại mật khẩu · {APP}", body)


def _email_limit(email: str, request: Request) -> None:
    if _over(_sends, MAX_EMAILS, email, _ip(request)):
        raise HTTPException(429, "Đã gửi nhiều email quá. Thử lại sau 15 phút.")
    _count(_sends, email, _ip(request))


class Login(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: Login, request: Request, response: Response) -> dict:
    email, ip = accounts.normalize_email(body.email), _ip(request)
    if _over(_fails, MAX_FAILS, email, ip):
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần. Thử lại sau 15 phút.")
    user = accounts.authenticate(email, body.password)
    if not user:
        _count(_fails, email, ip)
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    if user["disabled"]:
        raise HTTPException(403, "Tài khoản đã bị khóa. Liên hệ quản trị viên.")
    if not user["verified"]:
        raise HTTPException(403, detail={"code": "unverified", "msg": "Email chưa được xác nhận."})
    _fails.pop(f"email:{email}", None)
    set_login_cookie(request, response, user["id"])
    return user


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    accounts.end_session(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(current_user)) -> dict:
    return user


class NewPassword(BaseModel):
    current: str
    password: str


@router.post("/password")
async def change_password(body: NewPassword, request: Request, response: Response,
                          user: dict = Depends(current_user)) -> dict:  # fmt: skip
    if not accounts.authenticate(user["email"], body.current):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")
    if problem := accounts.password_problem(body.password):
        raise HTTPException(400, problem)
    accounts.set_password(user["id"], body.password)  # ends every session, this one included
    set_login_cookie(request, response, user["id"])
    return {"ok": True}


# ----- Sign-up and email links -----


class Signup(BaseModel):
    email: str
    password: str
    name: str = ""


@router.post("/signup")
async def signup(body: Signup, request: Request, tasks: BackgroundTasks) -> dict:
    if not config.SIGNUP_ENABLED:
        raise HTTPException(403, "Đăng ký đang tắt. Nhờ quản trị viên tạo tài khoản cho bạn.")
    email = accounts.normalize_email(body.email)
    if not accounts.valid_email(email):
        raise HTTPException(400, "Email không hợp lệ.")
    if problem := accounts.password_problem(body.password):
        raise HTTPException(400, problem)
    _email_limit(email, request)
    existing = accounts.user_by_email(email)
    if existing is None:
        _send_verify(tasks, request, accounts.create_user(email, body.name, body.password, verified=False))
    elif not existing["verified"] and not existing["disabled"]:
        _send_verify(tasks, request, existing)  # signed up before and lost the email: send it again
    return {"ok": True}


class Email(BaseModel):
    email: str


@router.post("/resend")
async def resend(body: Email, request: Request, tasks: BackgroundTasks) -> dict:
    email = accounts.normalize_email(body.email)
    _email_limit(email, request)
    user = accounts.user_by_email(email)
    if user and not user["verified"] and not user["disabled"]:
        _send_verify(tasks, request, user)
    return {"ok": True}


class Token(BaseModel):
    token: str


@router.post("/verify")
async def verify(body: Token, request: Request, response: Response) -> dict:
    """Confirms the email and logs the user in (they just proved they own the inbox)."""
    uid = accounts.use_token(body.token, "verify")
    user = accounts.get_user(uid) if uid else None
    if not user:
        raise HTTPException(400, "Link xác nhận không đúng hoặc đã hết hạn. Gửi lại email xác nhận ở dưới.")
    if user["disabled"]:
        raise HTTPException(403, "Tài khoản đã bị khóa. Liên hệ quản trị viên.")
    accounts.mark_verified(user["id"])
    set_login_cookie(request, response, user["id"])
    return accounts.get_user(user["id"]) or {}


@router.post("/forgot")
async def forgot(body: Email, request: Request, tasks: BackgroundTasks) -> dict:
    email = accounts.normalize_email(body.email)
    _email_limit(email, request)
    user = accounts.user_by_email(email)
    if user and not user["disabled"]:
        _send_reset(tasks, request, user)
    return {"ok": True}


class Reset(BaseModel):
    token: str
    password: str


@router.post("/reset")
async def reset(body: Reset, request: Request, response: Response) -> dict:
    if problem := accounts.password_problem(body.password):
        raise HTTPException(400, problem)
    uid = accounts.use_token(body.token, "reset")
    user = accounts.get_user(uid) if uid else None
    if not user:
        raise HTTPException(400, "Link đặt lại mật khẩu không đúng hoặc đã hết hạn. Hãy gửi link mới.")
    if user["disabled"]:
        raise HTTPException(403, "Tài khoản đã bị khóa. Liên hệ quản trị viên.")
    accounts.set_password(user["id"], body.password)  # ends every other session
    accounts.mark_verified(user["id"])  # the reset link proved the inbox too
    set_login_cookie(request, response, user["id"])
    return accounts.get_user(user["id"]) or {}
