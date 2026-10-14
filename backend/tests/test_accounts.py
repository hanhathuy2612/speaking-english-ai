"""Accounts: password hashing, login sessions, email tokens, and the API guards (temporary SQLite file)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core import config
from app.services import accounts, history


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(config, "HISTORY_DB", "history.db")
    accounts.init()
    history.init()
    return tmp_path / "history.db"


def test_passwords_are_salted_and_checked():
    a, b = accounts.hash_password("correct horse"), accounts.hash_password("correct horse")
    assert a != b and a.startswith("scrypt$")
    assert accounts.verify_password("correct horse", a)
    assert not accounts.verify_password("correct hors", a)
    assert not accounts.verify_password("x", "not-a-hash")


def test_authenticate_and_duplicate_emails(db):
    user = accounts.create_user(" Me@Example.com ", "Me", "password1")
    assert user["email"] == "me@example.com" and user["role"] == "user" and user["verified"]
    assert "password" not in user
    assert accounts.authenticate("ME@example.com", "password1")["id"] == user["id"]
    assert accounts.authenticate("me@example.com", "wrong-pass") is None
    assert accounts.authenticate("nobody@example.com", "password1") is None
    with pytest.raises(ValueError):
        accounts.create_user("me@example.com", "Again", "password2")


def test_sessions_end_on_logout_password_change_and_lock(db):
    uid = accounts.create_user("me@example.com", "Me", "password1")["id"]
    token = accounts.new_session(uid)
    assert accounts.session_user(token)["id"] == uid
    assert accounts.session_user("forged") is None and accounts.session_user(None) is None
    accounts.end_session(token)
    assert accounts.session_user(token) is None

    token = accounts.new_session(uid)
    accounts.set_password(uid, "password2")
    assert accounts.session_user(token) is None

    token = accounts.new_session(uid)
    accounts.update_user(uid, disabled=True)
    assert accounts.session_user(token) is None
    accounts.update_user(uid, disabled=False)
    assert accounts.session_user(accounts.new_session(uid))["id"] == uid


def test_expired_sessions_and_unverified_users_are_refused(db):
    uid = accounts.create_user("me@example.com", "Me", "password1", verified=False)["id"]
    token = accounts.new_session(uid)
    assert accounts.session_user(token) is None  # email not confirmed yet
    accounts.mark_verified(uid)
    assert accounts.session_user(token)["id"] == uid
    past = (datetime.now() - timedelta(minutes=1)).isoformat()
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE auth_sessions SET expires_at = ?", (past,))
    assert accounts.session_user(token) is None


def test_email_tokens_work_once_for_their_kind(db):
    uid = accounts.create_user("me@example.com", "Me", "password1")["id"]
    old = accounts.new_token(uid, "reset")
    token = accounts.new_token(uid, "reset")
    assert accounts.use_token(old, "reset") is None  # replaced by the newer link
    assert accounts.use_token(token, "verify") is None
    assert accounts.use_token(token, "reset") == uid
    assert accounts.use_token(token, "reset") is None


# ----- API -----


@pytest.fixture
def client(db):
    from app.main import app

    return TestClient(app)  # no `with`: the lifespan (Whisper) does not run


def login(client, email, password="password1"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_api_needs_login_and_admin_routes_need_the_admin_role(client):
    accounts.create_user("admin@example.com", "Admin", "password1", "admin")
    accounts.create_user("user@example.com", "User", "password1")
    assert client.get("/api/units").status_code == 401
    assert client.get("/api/history/sessions").status_code == 401
    login(client, "user@example.com")
    assert client.get("/api/auth/me").json()["email"] == "user@example.com"
    assert client.get("/api/units").status_code == 200
    assert client.get("/api/admin/users").status_code == 403
    assert client.get("/api/bench").status_code == 403
    client.post("/api/auth/logout")
    assert client.get("/api/units").status_code == 401
    login(client, "admin@example.com")
    assert [u["email"] for u in client.get("/api/admin/users").json()] == ["admin@example.com", "user@example.com"]


def test_login_errors_and_rate_limit(client, monkeypatch):
    from app.api.routes import auth

    monkeypatch.setattr(auth, "_fails", type(auth._fails)(auth._fails.default_factory))
    accounts.create_user("new@example.com", "New", "password1", verified=False)
    r = client.post("/api/auth/login", json={"email": "new@example.com", "password": "password1"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "unverified"
    for _ in range(auth.MAX_FAILS["email"]):
        assert client.post("/api/auth/login", json={"email": "x@example.com", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "x@example.com", "password": "bad"}).status_code == 429


def test_admins_cannot_remove_the_last_admin(client):
    me = accounts.create_user("admin@example.com", "Admin", "password1", "admin")
    login(client, "admin@example.com")
    r = client.post("/api/admin/users", json={"email": "u@example.com", "password": "password1"})
    assert r.status_code == 200 and r.json()["role"] == "user"
    assert client.post("/api/admin/users", json={"email": "u@example.com", "password": "password1"}).status_code == 409
    assert client.post("/api/admin/users", json={"email": "u2@example.com", "password": "short"}).status_code == 400
    assert client.patch(f"/api/admin/users/{me['id']}", json={"role": "user"}).status_code == 400
    assert client.patch(f"/api/admin/users/{me['id']}", json={"disabled": True}).status_code == 400
    uid = r.json()["id"]
    assert client.patch(f"/api/admin/users/{uid}", json={"role": "admin"}).json()["role"] == "admin"
    assert client.patch(f"/api/admin/users/{uid}", json={"disabled": True}).json()["disabled"] is True


def test_change_password_keeps_this_login(client):
    accounts.create_user("me@example.com", "Me", "password1")
    login(client, "me@example.com")
    bad = client.post("/api/auth/password", json={"current": "nope", "password": "password2"})
    assert bad.status_code == 400
    assert client.post("/api/auth/password", json={"current": "password1", "password": "password2"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200  # a fresh cookie replaced the ended session
    assert accounts.authenticate("me@example.com", "password2")


def test_websocket_refuses_anonymous_and_cross_site_connections(client):
    accounts.create_user("me@example.com", "Me", "password1")
    with client.websocket_connect("/ws") as ws, pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()
    assert closed.value.code == 4401
    login(client, "me@example.com")
    with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


@pytest.fixture
def outbox(monkeypatch):
    from app.api.routes import auth
    from app.services import mailer

    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, body: sent.append((to, subject, body)))
    monkeypatch.setattr(auth, "_sends", type(auth._sends)(auth._sends.default_factory))
    monkeypatch.setattr(config, "SIGNUP_ENABLED", True)
    monkeypatch.setattr(config, "APP_URL", "https://app.example")
    return sent


def token_in(body: str, page: str) -> str:
    import re

    return re.search(rf"https://app\.example/{page}\?token=(\S+)", body).group(1)


def test_signup_needs_the_emailed_link_before_login(client, outbox):
    r = client.post("/api/auth/signup", json={"email": "New@Example.com", "password": "password1", "name": "New"})
    assert r.status_code == 200
    [(to, _subject, body)] = outbox
    assert to == "new@example.com"
    r = client.post("/api/auth/login", json={"email": "new@example.com", "password": "password1"})
    assert r.status_code == 403
    assert client.post("/api/auth/verify", json={"token": "forged"}).status_code == 400
    r = client.post("/api/auth/verify", json={"token": token_in(body, "verify")})
    assert r.status_code == 200 and r.json()["verified"] and r.json()["role"] == "user"
    assert client.get("/api/auth/me").json()["email"] == "new@example.com"  # logged in by the link
    assert client.post("/api/auth/verify", json={"token": token_in(body, "verify")}).status_code == 400  # once


def test_signup_and_forgot_do_not_reveal_which_emails_exist(client, outbox):
    accounts.create_user("taken@example.com", "Taken", "password1")
    r = client.post("/api/auth/signup", json={"email": "taken@example.com", "password": "password2"})
    assert r.status_code == 200 and outbox == []  # same answer, nothing sent, password unchanged
    assert accounts.authenticate("taken@example.com", "password1")
    assert client.post("/api/auth/forgot", json={"email": "nobody@example.com"}).status_code == 200
    assert outbox == []
    assert client.post("/api/auth/signup", json={"email": "bad", "password": "password1"}).status_code == 400


def test_password_reset_by_email(client, outbox):
    accounts.create_user("me@example.com", "Me", "password1")
    old = accounts.new_session(accounts.user_by_email("me@example.com")["id"])
    client.post("/api/auth/forgot", json={"email": "me@example.com"}, headers={"host": "evil.example"})
    [(_to, _subject, body)] = outbox
    assert "evil.example" not in body  # links use APP_URL, never the request's Host
    token = token_in(body, "reset")
    assert client.post("/api/auth/reset", json={"token": token, "password": "short"}).status_code == 400
    assert client.post("/api/auth/reset", json={"token": token, "password": "password2"}).status_code == 200
    assert accounts.authenticate("me@example.com", "password2") and accounts.session_user(old) is None
    assert client.get("/api/auth/me").status_code == 200


def test_email_sending_is_rate_limited_and_signup_can_be_turned_off(client, outbox, monkeypatch):
    from app.api.routes import auth

    for _ in range(auth.MAX_EMAILS["email"]):
        assert client.post("/api/auth/forgot", json={"email": "x@example.com"}).status_code == 200
    assert client.post("/api/auth/forgot", json={"email": "x@example.com"}).status_code == 429
    monkeypatch.setattr(config, "SIGNUP_ENABLED", False)
    r = client.post("/api/auth/signup", json={"email": "y@example.com", "password": "password1"})
    assert r.status_code == 403


def test_links_need_app_url_once_smtp_is_configured(client, outbox, monkeypatch):
    accounts.create_user("me@example.com", "Me", "password1")
    monkeypatch.setattr(config, "APP_URL", "")
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example")
    assert client.post("/api/auth/forgot", json={"email": "me@example.com"}).status_code == 500
    assert outbox == []
