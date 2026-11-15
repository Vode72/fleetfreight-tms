import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pytest
from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.auth.deps import AuthContext, require_role
from db.models import User
from domain.passwords import PasswordService, VerifyResult
from domain.roles import Role
from domain.sessions import hash_token
from tests.conftest import CSRF_HEADERS, PASSWORD

COOKIE = "fleetfreight_session"
CREDENTIALS = {"email": "planner@demo.example.com", "password": PASSWORD}


def _login(client: TestClient, **overrides: str) -> int:
    return client.post("/auth/login", json={**CREDENTIALS, **overrides}).status_code


def _rows(engine: Engine, sql: str) -> list[tuple[object, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql))]


def test_login_success_sets_cookie_and_me_works(
    client: TestClient, add_user: Callable[..., User]
) -> None:
    user = add_user()
    response = client.post("/auth/login", json=CREDENTIALS)
    assert response.status_code == 204
    assert response.content == b""
    assert COOKIE in client.cookies

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json() == {"id": str(user.id), "email": "planner@demo.example.com", "role": "planner"}


def test_login_normalizes_email(client: TestClient, add_user: Callable[..., User]) -> None:
    add_user()
    assert _login(client, email="  Planner@DEMO.example.com ") == 204


def test_login_wrong_password_and_unknown_user_give_same_generic_401(
    client: TestClient, add_user: Callable[..., User]
) -> None:
    add_user()
    wrong = client.post("/auth/login", json={**CREDENTIALS, "password": "nope"})
    unknown = client.post("/auth/login", json={**CREDENTIALS, "email": "x@demo.example.com"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password"}
    assert COOKIE not in client.cookies


def test_unknown_email_still_performs_a_hash_comparison(app: FastAPI, client: TestClient) -> None:
    calls: list[str] = []
    service: PasswordService = app.state.password_service
    original = service.verify

    def spy(password: str, stored_hash: str) -> VerifyResult:
        calls.append("verify")
        return original(password, stored_hash)

    service.verify = spy  # type: ignore[method-assign]
    client.post("/auth/login", json={**CREDENTIALS, "email": "ghost@demo.example.com"})
    assert calls == ["verify"]  # verify_dummy delegates to verify


def test_cookie_attributes(client: TestClient, add_user: Callable[..., User]) -> None:
    add_user()
    header = client.post("/auth/login", json=CREDENTIALS).headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "path=/" in header
    assert "secure" not in header  # development setting
    assert "max-age" not in header  # browser-session cookie


def test_cookie_secure_flag_when_enabled(
    make_app: Callable[..., FastAPI], add_user: Callable[..., User]
) -> None:
    add_user()
    app = make_app(session_cookie_secure=True)
    with TestClient(app, headers=CSRF_HEADERS) as c:
        header = c.post("/auth/login", json=CREDENTIALS).headers["set-cookie"].lower()
    assert "secure" in header
    assert "httponly" in header


def test_only_token_hash_is_stored(
    client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    client.post("/auth/login", json=CREDENTIALS, headers={"User-Agent": "x" * 500})
    token = client.cookies[COOKIE]
    rows = _rows(test_engine, "SELECT token_hash, length(user_agent), ip FROM sessions")
    assert rows == [(hash_token(token), 200, None)]  # hashed, UA truncated, IP off by default
    assert token not in str(rows)


def test_ip_stored_only_when_enabled(
    make_app: Callable[..., FastAPI], add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    with TestClient(make_app(session_store_ip=True), headers=CSRF_HEADERS) as c:
        c.post("/auth/login", json=CREDENTIALS)
    assert _rows(test_engine, "SELECT ip FROM sessions")[0][0] is not None


def test_login_updates_last_login(
    client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    assert _rows(test_engine, "SELECT last_login_at FROM users") == [(None,)]
    _login(client)
    assert _rows(test_engine, "SELECT last_login_at FROM users")[0][0] is not None


def test_me_without_session_is_401(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_forged_cookie_is_401(client: TestClient) -> None:
    client.cookies.set(COOKIE, "not-a-real-token")
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_session_server_side(
    client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    _login(client)
    token = client.cookies[COOKIE]

    response = client.post("/auth/logout")
    assert response.status_code == 204
    assert _rows(test_engine, "SELECT revoked_at IS NOT NULL FROM sessions") == [(True,)]

    # Replaying the old cookie must fail even though the client still holds it.
    client.cookies.set(COOKIE, token)
    assert client.get("/auth/me").status_code == 401


def test_logout_requires_session(client: TestClient) -> None:
    assert client.post("/auth/logout").status_code == 401


def test_idle_timeout_expires_session_and_activity_slides_it(
    client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    _login(client)
    with test_engine.begin() as conn:  # 7 h ago: within the 8 h idle limit
        conn.execute(text("UPDATE sessions SET last_seen_at = now() - interval '7 hours'"))
    assert client.get("/auth/me").status_code == 200
    # The request above slid the window forward (last_seen_at refreshed).
    seen = _rows(test_engine, "SELECT last_seen_at FROM sessions")[0][0]
    assert isinstance(seen, datetime)
    assert datetime.now(UTC) - seen < timedelta(minutes=1)

    with test_engine.begin() as conn:  # 9 h ago: idle too long
        conn.execute(text("UPDATE sessions SET last_seen_at = now() - interval '9 hours'"))
    assert client.get("/auth/me").status_code == 401


def test_absolute_timeout_expires_session_despite_activity(
    client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    _login(client)
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE sessions SET expires_at = now() - interval '1 second'"))
    assert client.get("/auth/me").status_code == 401


def test_session_lifetimes_come_from_settings(
    make_app: Callable[..., FastAPI], add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    app = make_app(session_idle_timeout_minutes=5, session_absolute_timeout_days=1)
    with TestClient(app, headers=CSRF_HEADERS) as c:
        c.post("/auth/login", json=CREDENTIALS)
        span = _rows(test_engine, "SELECT expires_at - created_at FROM sessions")[0][0]
        assert span == timedelta(days=1)
        with test_engine.begin() as conn:
            conn.execute(text("UPDATE sessions SET last_seen_at = now() - interval '6 minutes'"))
        assert c.get("/auth/me").status_code == 401


def test_deactivated_user_cannot_login_or_use_existing_session(
    client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    _login(client)
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = false"))
    assert client.get("/auth/me").status_code == 401

    fresh = TestClient(client.app, headers=CSRF_HEADERS)
    response = fresh.post("/auth/login", json=CREDENTIALS)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_csrf_header_required_on_unsafe_methods(
    app: FastAPI, add_user: Callable[..., User]
) -> None:
    add_user()
    with TestClient(app) as bare:  # no X-Requested-With
        assert bare.post("/auth/login", json=CREDENTIALS).status_code == 403
        assert bare.post("/auth/logout").status_code == 403
        wrong = bare.post("/auth/login", json=CREDENTIALS, headers={"X-Requested-With": "other"})
        assert wrong.status_code == 403
        assert COOKIE not in bare.cookies
        # Safe methods do not need it.
        assert bare.get("/health").status_code == 200


def test_csrf_blocks_logout_even_with_valid_cookie(
    app: FastAPI, client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    _login(client)
    with TestClient(app) as attacker_like:
        attacker_like.cookies.set(COOKIE, client.cookies[COOKIE])
        assert attacker_like.post("/auth/logout").status_code == 403
    assert _rows(test_engine, "SELECT revoked_at FROM sessions") == [(None,)]


def test_rate_limit_after_repeated_failures_and_other_email_unaffected(
    make_app: Callable[..., FastAPI], add_user: Callable[..., User]
) -> None:
    add_user()
    app = make_app(login_max_failures=3)
    with TestClient(app, headers=CSRF_HEADERS) as c:
        for _ in range(3):
            assert _login(c, password="wrong") == 401
        blocked = c.post("/auth/login", json=CREDENTIALS)  # correct password, still blocked
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
        # A different e-mail from the same IP is tracked separately.
        assert _login(c, email="other@demo.example.com") == 401


def test_rate_limit_is_logged(
    make_app: Callable[..., FastAPI],
    add_user: Callable[..., User],
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_user()
    app = make_app(login_max_failures=1)
    with (
        caplog.at_level(logging.WARNING, logger="fleetfreight.auth"),
        TestClient(app, headers=CSRF_HEADERS) as c,
    ):
        _login(c, password="wrong")
        _login(c, password="wrong")
    assert any("rate limited" in r.message for r in caplog.records)
    assert "planner@demo.example.com" not in caplog.text


def test_successful_login_resets_failure_counter(
    make_app: Callable[..., FastAPI], add_user: Callable[..., User]
) -> None:
    add_user()
    app = make_app(login_max_failures=3)
    with TestClient(app, headers=CSRF_HEADERS) as c:
        assert _login(c, password="wrong") == 401
        assert _login(c, password="wrong") == 401
        assert _login(c) == 204
        assert _login(c, password="wrong") == 401
        assert _login(c, password="wrong") == 401  # would be blocked had the counter not reset


def test_password_hash_is_upgraded_on_login_when_parameters_change(
    client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    add_user()
    old = _rows(test_engine, "SELECT password_hash FROM users")[0][0]
    # Simulate a parameter bump: the service now expects a higher time cost than the stored hash.
    client.app.state.password_service._hasher = PasswordHasher(  # type: ignore[attr-defined]
        time_cost=2, memory_cost=8, parallelism=1
    )
    assert _login(client) == 204
    new = _rows(test_engine, "SELECT password_hash FROM users")[0][0]
    assert new != old
    assert "t=2" in str(new)
    assert _login(client) == 204  # new hash still verifies


def test_login_validation_errors(client: TestClient) -> None:
    assert client.post("/auth/login", json={"email": "a@b.co"}).status_code == 422
    assert (
        client.post("/auth/login", json={"email": "a@b.co", "password": "x" * 2000}).status_code
        == 422
    )


def test_email_must_be_lowercase_in_database(
    test_engine: Engine, add_user: Callable[..., User]
) -> None:
    add_user()

    def insert(email: str, role: str) -> str:
        return f"INSERT INTO users (email, password_hash, role) VALUES ('{email}', 'x', '{role}')"

    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text(insert("Mixed@Demo.example.com", "viewer")))
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text(insert("x@demo.example.com", "driver")))
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text(insert("planner@demo.example.com", "viewer")))


def test_role_dependency(make_app: Callable[..., FastAPI], add_user: Callable[..., User]) -> None:
    app = make_app()
    extra = APIRouter()

    @extra.get("/admin-only")
    def admin_only(_: Annotated[AuthContext, Depends(require_role("admin"))]) -> dict[str, str]:
        return {"ok": "admin"}

    @extra.get("/planning")
    def planning(
        _: Annotated[AuthContext, Depends(require_role(Role.ADMIN, Role.PLANNER))],
    ) -> dict[str, str]:
        return {"ok": "planning"}

    app.include_router(extra)
    add_user("admin@demo.example.com", role=Role.ADMIN)
    add_user("planner@demo.example.com", role=Role.PLANNER)
    add_user("viewer@demo.example.com", role=Role.VIEWER)

    expected = {
        "admin@demo.example.com": (200, 200),
        "planner@demo.example.com": (403, 200),
        "viewer@demo.example.com": (403, 403),
    }
    for email, (admin_status, planning_status) in expected.items():
        with TestClient(app, headers=CSRF_HEADERS) as c:
            c.post("/auth/login", json={"email": email, "password": PASSWORD})
            assert c.get("/admin-only").status_code == admin_status, email
            assert c.get("/planning").status_code == planning_status, email
    with TestClient(app, headers=CSRF_HEADERS) as anonymous:
        assert anonymous.get("/admin-only").status_code == 401
