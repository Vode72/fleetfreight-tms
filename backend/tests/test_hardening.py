import logging
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.auth.service import revoke_all_sessions
from db.models import User
from domain.users import email_log_id
from tests.conftest import CSRF_HEADERS, PASSWORD, cheap_passwords, make_settings

EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cache-control": "no-store",
}


def _assert_headers(response: Any) -> None:
    headers = response.headers
    for name, value in EXPECTED_HEADERS.items():
        assert headers[name] == value, name


def test_security_headers_on_success_and_error_responses(client: TestClient) -> None:
    _assert_headers(client.get("/health"))
    _assert_headers(client.get("/auth/me"))  # 401
    _assert_headers(client.post("/auth/login", json={"email": "a@b.co", "password": "x"}))  # 401
    _assert_headers(client.post("/auth/login", json={}))  # 422


def test_unauthenticated_404_and_405_leak_nothing_but_status(app: FastAPI) -> None:
    with TestClient(app) as anonymous:
        missing = anonymous.get("/no/such/route")
        wrong_method = anonymous.get("/auth/login")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Not Found"}
    assert wrong_method.status_code == 405
    assert wrong_method.json() == {"detail": "Method Not Allowed"}
    for response in (missing, wrong_method):
        _assert_headers(response)
        assert "set-cookie" not in response.headers


def test_production_refuses_insecure_cookie() -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        make_settings(environment="production", session_cookie_secure=False)
    make_settings(environment="production", session_cookie_secure=True)
    make_settings(environment="development", session_cookie_secure=False)


def test_default_settings_are_production_safe() -> None:
    from app.config import Settings

    settings = Settings(_env_file=None)
    assert settings.environment == "production"
    assert settings.session_cookie_secure is True
    assert settings.trusted_proxy_ips == ""


def test_dummy_hash_is_computed_up_front_with_current_parameters() -> None:
    service = cheap_passwords()
    assert service._dummy_hash.startswith("$argon2id$")
    assert service._hasher.check_needs_rehash(service._dummy_hash) is False


def test_email_log_id_is_keyed_and_normalised() -> None:
    a = email_log_id("Planner@Demo.example.com", b"key-one")
    assert a == email_log_id(" planner@demo.example.com", b"key-one")
    assert a != email_log_id("planner@demo.example.com", b"key-two")
    assert "planner" not in a


def test_log_uses_hmac_identifier_not_plain_hash(
    make_app: Callable[..., FastAPI], caplog: pytest.LogCaptureFixture
) -> None:
    app = make_app(log_hmac_key="test-secret")
    with (
        caplog.at_level(logging.INFO, logger="fleetfreight.auth"),
        TestClient(app, headers=CSRF_HEADERS) as c,
    ):
        c.post("/auth/login", json={"email": "x@demo.example.com", "password": "bad"})
    expected = email_log_id("x@demo.example.com", b"test-secret")
    assert expected in caplog.text
    assert "x@demo.example.com" not in caplog.text


def test_revoke_all_sessions_revokes_only_that_users_active_sessions(
    make_app: Callable[..., FastAPI], add_user: Callable[..., User], test_engine: Engine
) -> None:
    app = make_app()
    first = add_user("planner@demo.example.com")
    add_user("viewer@demo.example.com")
    for email in (
        "planner@demo.example.com",
        "planner@demo.example.com",
        "viewer@demo.example.com",
    ):
        with TestClient(app, headers=CSRF_HEADERS) as c:
            assert (
                c.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code
                == 204
            )
    with sessionmaker(bind=test_engine)() as session:
        assert revoke_all_sessions(session, first.id) == 2
        session.commit()
    with sessionmaker(bind=test_engine)() as session:
        assert revoke_all_sessions(session, first.id) == 0  # already revoked
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT u.email, count(*) FILTER (WHERE s.revoked_at IS NULL) "
                "FROM sessions s JOIN users u ON u.id = s.user_id GROUP BY u.email ORDER BY u.email"
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("planner@demo.example.com", 0),
        ("viewer@demo.example.com", 1),
    ]


def test_revoked_cookie_stops_working(
    app: FastAPI, client: TestClient, add_user: Callable[..., User], test_engine: Engine
) -> None:
    user = add_user()
    client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
    assert client.get("/auth/me").status_code == 200
    with sessionmaker(bind=test_engine)() as session:
        revoke_all_sessions(session, user.id)
        session.commit()
    assert client.get("/auth/me").status_code == 401


def test_warns_about_missing_proxy_config_in_production(
    make_app: Callable[..., FastAPI], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="fleetfreight.app"):
        make_app(environment="production")
    assert "TRUSTED_PROXY_IPS is empty" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="fleetfreight.app"):
        make_app(environment="production", trusted_proxy_ips="10.0.0.5", log_hmac_key="k")
    assert caplog.text == ""
