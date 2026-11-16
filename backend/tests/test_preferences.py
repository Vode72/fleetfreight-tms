from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from db.models import User
from domain.roles import Role
from tests.conftest import CSRF_HEADERS, PASSWORD

URL = "/auth/me/preferences"


def _login(client: TestClient, email: str) -> None:
    assert (
        client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 204
    )


def test_me_contains_null_preferences_by_default(
    client: TestClient, add_user: Callable[..., User]
) -> None:
    add_user()
    _login(client, "planner@demo.example.com")
    body = client.get("/auth/me").json()
    assert body["theme"] is None and body["language"] is None


@pytest.mark.parametrize("role", list(Role))
def test_any_role_can_patch_own_preferences(
    client: TestClient, add_user: Callable[..., User], role: Role
) -> None:
    user = add_user(email=f"{role.value}@demo.example.com", role=role)
    _login(client, user.email)
    response = client.patch(URL, json={"theme": "control-dark", "language": "fi"})
    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "role": role.value,
        "theme": "control-dark",
        "language": "fi",
    }
    assert client.get("/auth/me").json() == response.json()


def test_partial_update_keeps_other_field_and_null_resets(
    client: TestClient, add_user: Callable[..., User]
) -> None:
    add_user()
    _login(client, "planner@demo.example.com")
    client.patch(URL, json={"theme": "control-dark", "language": "fi"})
    assert client.patch(URL, json={"language": "en"}).json()["theme"] == "control-dark"
    reset = client.patch(URL, json={"theme": None}).json()
    assert reset["theme"] is None and reset["language"] == "en"


def test_patch_without_session_is_401(client: TestClient) -> None:
    assert client.patch(URL, json={"theme": "control-dark"}).status_code == 401


def test_patch_without_csrf_header_is_403(app: FastAPI, add_user: Callable[..., User]) -> None:
    add_user()
    with TestClient(app, headers=CSRF_HEADERS) as c:
        _login(c, "planner@demo.example.com")
        c.headers.pop("X-Requested-With")
        assert c.patch(URL, json={"theme": "control-dark"}).status_code == 403
        c.headers.update(CSRF_HEADERS)
        assert c.get("/auth/me").json()["theme"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"theme": "neon"},
        {"language": "sv"},
        {"theme": 1},
        {},
        {"theme": "control-dark", "role": "admin"},
        {"email": "x@demo.example.com"},
    ],
)
def test_patch_invalid_body_is_422(
    client: TestClient, add_user: Callable[..., User], payload: dict[str, object]
) -> None:
    add_user()
    _login(client, "planner@demo.example.com")
    assert client.patch(URL, json=payload).status_code == 422
    body = client.get("/auth/me").json()
    assert body["theme"] is None and body["language"] is None and body["role"] == "planner"


def test_user_a_change_does_not_affect_user_b(app: FastAPI, add_user: Callable[..., User]) -> None:
    add_user(email="a@demo.example.com")
    add_user(email="b@demo.example.com", role=Role.VIEWER)
    with (
        TestClient(app, headers=CSRF_HEADERS) as a,
        TestClient(app, headers=CSRF_HEADERS) as b,
    ):
        _login(a, "a@demo.example.com")
        _login(b, "b@demo.example.com")
        a.patch(URL, json={"theme": "control-dark", "language": "fi"})
        body = b.get("/auth/me").json()
        assert body["theme"] is None and body["language"] is None


def test_database_rejects_invalid_values(
    test_engine: Engine, add_user: Callable[..., User]
) -> None:
    add_user()
    for column, value in (("theme", "neon"), ("language", "sv")):
        with pytest.raises(IntegrityError), test_engine.begin() as conn:
            conn.execute(text(f"UPDATE users SET {column} = :v"), {"v": value})
