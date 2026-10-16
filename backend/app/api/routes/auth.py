"""Login, sign-up with email confirmation, password reset, and the current user
(docs/features/accounts.md). Only /me and /password need a login. Logging in (password, email link,
refresh) answers with JWTs the page sends as `Authorization: Bearer`; there is no logout on the
server, the page forgets its tokens.

Sign-up, resend and forgot answer the same whether or not the email has an account, and send their
email from a background task, so neither the answer nor its timing tells which addresses exist.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import current_user
from app.core import config
from app.services import accounts, mailer, tokens

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Attempts kept in memory: enough for one local server, reset on restart.
WINDOW_S = 15 * 60
MAX_FAILS = {"email": 5, "ip": 20}  # wrong passwords
MAX_EMAILS = {"email": 3, "ip": 10}  # emails sent (sign-up, resend, forgot)
_fails: dict[str, deque[float]] = defaultdict(deque)
_sends: dict[str, deque[float]] = defaultdict(deque)
# Routes are plain `def`, so they run in threadpool threads: one lock guards both stores.
_lock = threading.RLock()

APP = "Phòng tập nói"


def _recent(store: dict[str, deque[float]], key: str) -> deque[float]:
    q = store[key]
    while q and q[0] < time.monotonic() - WINDOW_S:
        q.popleft()
    return q


def _over(store: dict[str, deque[float]], limits: dict[str, int], email: str, ip: str) -> bool:
    with _lock:
        return (
            len(_recent(store, f"email:{email}")) >= limits["email"] or len(_recent(store, f"ip:{ip}")) >= limits["ip"]
        )


def _count(store: dict[str, deque[float]], email: str, ip: str) -> float:
    """Records an attempt and returns its timestamp."""
    now = time.monotonic()
    with _lock:
        _recent(store, f"email:{email}").append(now)
        _recent(store, f"ip:{ip}").append(now)
    return now


def _check_and_count(store: dict[str, deque[float]], limits: dict[str, int], email: str, ip: str) -> float | None:
    """_over + _count in one step, so parallel requests cannot all pass the check before any is counted.
    Returns the attempt's timestamp, or None when over the limit."""
    with _lock:
        return None if _over(store, limits, email, ip) else _count(store, email, ip)


def _forget(store: dict[str, deque[float]], email: str, ip: str, stamp: float, *, all_for_email: bool = False) -> None:
    """Takes back one attempt (by its timestamp) from the email and ip lists; with all_for_email,
    also every other attempt for that email."""
    with _lock:
        if all_for_email:
            store.pop(f"email:{email}", None)
        for key in (f"email:{email}", f"ip:{ip}"):
            q = store.get(key)  # not store[key]: a defaultdict would recreate an empty deque
            if q and stamp in q:
                q.remove(stamp)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def logged_in(uid: int) -> dict:
    """{user, access_token, refresh_token, expires_in} for an active, verified user."""
    state = accounts.login_state(uid)
    if not state:
        raise HTTPException(401, "Phiên đăng nhập đã hết. Hãy đăng nhập lại.")
    user, stamp = state
    return {"user": user, **tokens.issue(user, stamp)}


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
    if _check_and_count(_sends, MAX_EMAILS, email, _ip(request)) is None:
        raise HTTPException(429, "Đã gửi nhiều email quá. Thử lại sau 15 phút.")


class Login(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: Login, request: Request) -> dict:
    email, ip = accounts.normalize_email(body.email), _ip(request)
    # The attempt is counted before the slow password check (scrypt), so a burst of parallel
    # guesses is limited too; a right password takes it back.
    stamp = _check_and_count(_fails, MAX_FAILS, email, ip)
    if stamp is None:
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần. Thử lại sau 15 phút.")
    user = accounts.authenticate(email, body.password)
    if not user:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    if user["disabled"] or not user["verified"]:  # right password: not a failed guess
        _forget(_fails, email, ip, stamp)
        if user["disabled"]:
            raise HTTPException(403, "Tài khoản đã bị khóa. Liên hệ quản trị viên.")
        raise HTTPException(403, detail={"code": "unverified", "msg": "Email chưa được xác nhận."})
    _forget(_fails, email, ip, stamp, all_for_email=True)
    return logged_in(user["id"])


class Refresh(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh(body: Refresh) -> dict:
    """New tokens for a refresh token, while the account is active and its password unchanged."""
    claims = tokens.refresh_claims(body.refresh_token)
    state = accounts.login_state(claims[0]) if claims else None
    if not state or state[1] != claims[1]:
        raise HTTPException(401, "Phiên đăng nhập đã hết. Hãy đăng nhập lại.")
    return logged_in(state[0]["id"])


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    """The full user row (verified, created_at...), not only what the access token carries."""
    found = accounts.get_user(user["id"])
    if not found:
        raise HTTPException(401, "Bạn cần đăng nhập.")
    return found


class NewPassword(BaseModel):
    current: str
    password: str


@router.post("/password")
def change_password(body: NewPassword, user: dict = Depends(current_user)) -> dict:
    if not accounts.authenticate(user["email"], body.current):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")
    if problem := accounts.password_problem(body.password):
        raise HTTPException(400, problem)
    accounts.set_password(user["id"], body.password)  # ends the other logins at their next refresh
    return logged_in(user["id"])  # new tokens for this one


# ----- Sign-up and email links -----


class Signup(BaseModel):
    email: str
    password: str
    name: str = ""


@router.post("/signup")
def signup(body: Signup, request: Request, tasks: BackgroundTasks) -> dict:
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
def resend(body: Email, request: Request, tasks: BackgroundTasks) -> dict:
    email = accounts.normalize_email(body.email)
    _email_limit(email, request)
    user = accounts.user_by_email(email)
    if user and not user["verified"] and not user["disabled"]:
        _send_verify(tasks, request, user)
    return {"ok": True}


class Token(BaseModel):
    token: str


@router.post("/verify")
def verify(body: Token) -> dict:
    """Confirms the email and logs the user in (they just proved they own the inbox)."""
    uid = accounts.use_token(body.token, "verify")
    user = accounts.get_user(uid) if uid else None
    if not user:
        raise HTTPException(400, "Link xác nhận không đúng hoặc đã hết hạn. Gửi lại email xác nhận ở dưới.")
    if user["disabled"]:
        raise HTTPException(403, "Tài khoản đã bị khóa. Liên hệ quản trị viên.")
    accounts.mark_verified(user["id"])
    return logged_in(user["id"])


@router.post("/forgot")
def forgot(body: Email, request: Request, tasks: BackgroundTasks) -> dict:
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
def reset(body: Reset) -> dict:
    if problem := accounts.password_problem(body.password):
        raise HTTPException(400, problem)
    uid = accounts.use_token(body.token, "reset")
    user = accounts.get_user(uid) if uid else None
    if not user:
        raise HTTPException(400, "Link đặt lại mật khẩu không đúng hoặc đã hết hạn. Hãy gửi link mới.")
    if user["disabled"]:
        raise HTTPException(403, "Tài khoản đã bị khóa. Liên hệ quản trị viên.")
    accounts.set_password(user["id"], body.password)  # ends the other logins at their next refresh
    accounts.mark_verified(user["id"])  # the reset link proved the inbox too
    return logged_in(user["id"])
