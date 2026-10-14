"""Accounts: password hashing, login tokens (JWT), email tokens, and the API guards (temporary SQLite file)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core import config
from app.services import accounts, history, tokens


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


def refreshed(refresh_token: str) -> dict | None:
    """What /api/auth/refresh checks, without HTTP: a valid token for an active user, same password."""
    claims = tokens.refresh_claims(refresh_token)
    state = accounts.login_state(claims[0]) if claims else None
    return state[0] if state and state[1] == claims[1] else None


def test_access_tokens_need_no_database_and_refresh_checks_the_account(db):
    user = accounts.create_user("me@example.com", "Me", "password1")
    t = tokens.issue(user, accounts.login_state(user["id"])[1])
    assert tokens.access_user(t["access_token"]) == {"id": user["id"], "email": "me@example.com", "name": "Me", "role": "user"}
    assert tokens.access_user(t["refresh_token"]) is None  # a refresh token is not an access token
    assert tokens.refresh_claims(t["access_token"]) is None
    assert tokens.access_user("forged") is None and tokens.access_user(None) is None
    assert refreshed(t["refresh_token"])["id"] == user["id"]

    accounts.set_password(user["id"], "password2")
    assert tokens.access_user(t["access_token"])  # lives out its 15 minutes
    assert refreshed(t["refresh_token"]) is None  # but cannot be renewed with the old password

    t = tokens.issue(user, accounts.login_state(user["id"])[1])
    accounts.update_user(user["id"], disabled=True)
    assert refreshed(t["refresh_token"]) is None
    accounts.update_user(user["id"], disabled=False)
    assert refreshed(t["refresh_token"])["id"] == user["id"]


def test_expired_tokens_and_unverified_users_are_refused(db, monkeypatch):
    uid = accounts.create_user("me@example.com", "Me", "password1", verified=False)["id"]
    assert accounts.login_state(uid) is None  # email not confirmed yet
    accounts.mark_verified(uid)
    user, stamp = accounts.login_state(uid)
    monkeypatch.setattr(tokens, "ACCESS_SECONDS", -1)  # issued already expired
    t = tokens.issue(user, stamp)
    assert tokens.access_user(t["access_token"]) is None
    assert refreshed(t["refresh_token"])["id"] == uid  # 30 days


def test_tokens_signed_with_another_key_are_refused(db, monkeypatch):
    user = accounts.create_user("me@example.com", "Me", "password1")
    t = tokens.issue(user, accounts.login_state(user["id"])[1])
    monkeypatch.setattr(config, "JWT_SECRET", "another key")
    assert tokens.access_user(t["access_token"]) is None


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
    use(client, r.json())
    return r.json()["user"]


def use(client, answer: dict) -> None:
    """Send the access token of a login answer on later requests, as the page does."""
    client.headers["Authorization"] = f"Bearer {answer['access_token']}"


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
    del client.headers["Authorization"]  # logging out: the page forgets its tokens
    assert client.get("/api/units").status_code == 401
    client.headers["Authorization"] = "Bearer forged"
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
    old = client.post("/api/auth/login", json={"email": "me@example.com", "password": "password1"}).json()
    r = client.post("/api/auth/password", json={"current": "password1", "password": "password2"})
    assert r.status_code == 200
    use(client, r.json())  # fresh tokens for this login
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": r.json()["refresh_token"]}).status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": old["refresh_token"]}).status_code == 401
    assert accounts.authenticate("me@example.com", "password2")


def test_websocket_needs_an_access_token_first(client):
    accounts.create_user("me@example.com", "Me", "password1")
    for first in ({"type": "start", "unit": "x"}, {"type": "auth", "token": "forged"}):
        with client.websocket_connect("/ws") as ws, pytest.raises(WebSocketDisconnect) as closed:
            ws.send_json(first)
            ws.receive_json()
        assert closed.value.code == 4401
    access = client.post("/api/auth/login", json={"email": "me@example.com", "password": "password1"}).json()
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": access["access_token"]})
        ws.send_json({"type": "undo"})  # nothing to undo: the connection stays open and quiet
        ws.close()


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
    assert r.status_code == 200 and r.json()["user"]["verified"] and r.json()["user"]["role"] == "user"
    use(client, r.json())
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
    old = client.post("/api/auth/login", json={"email": "me@example.com", "password": "password1"}).json()
    client.post("/api/auth/forgot", json={"email": "me@example.com"}, headers={"host": "evil.example"})
    [(_to, _subject, body)] = outbox
    assert "evil.example" not in body  # links use APP_URL, never the request's Host
    token = token_in(body, "reset")
    assert client.post("/api/auth/reset", json={"token": token, "password": "short"}).status_code == 400
    r = client.post("/api/auth/reset", json={"token": token, "password": "password2"})
    assert r.status_code == 200
    assert accounts.authenticate("me@example.com", "password2")
    assert client.post("/api/auth/refresh", json={"refresh_token": old["refresh_token"]}).status_code == 401
    use(client, r.json())
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
