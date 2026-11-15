import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from domain.passwords import PasswordService
from scripts.seed_demo_users import DEMO_USERS, seed_demo_users
from tests.conftest import cheap_passwords

PASSWORD = "a-demo-password-123"


def _emails(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, role FROM users ORDER BY email"))
        return [(str(r[0]), str(r[1])) for r in rows]


def test_seed_creates_three_demo_users_idempotently(test_engine: Engine, app: object) -> None:
    service: PasswordService = cheap_passwords()
    factory = sessionmaker(bind=test_engine)
    with factory() as session:
        first = seed_demo_users(session, PASSWORD, service)
    with factory() as session:
        second = seed_demo_users(session, PASSWORD, service)
    assert all(line.endswith("created") for line in first)
    assert all(line.endswith("unchanged") for line in second)
    assert _emails(test_engine) == [
        ("admin@demo.example.com", "admin"),
        ("planner@demo.example.com", "planner"),
        ("viewer@demo.example.com", "viewer"),
    ]
    assert all(email.endswith("@demo.example.com") for email, _ in DEMO_USERS)


def test_seed_repairs_deactivated_user_and_updates_password(
    test_engine: Engine, app: object
) -> None:
    service = cheap_passwords()
    factory = sessionmaker(bind=test_engine)
    with factory() as session:
        seed_demo_users(session, PASSWORD, service)
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = false WHERE role = 'viewer'"))
    with factory() as session:
        report = seed_demo_users(session, "another-demo-password", service)
    assert all(line.endswith("updated") for line in report)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users WHERE is_active")).scalar() == 3


def test_seed_rejects_short_password(test_engine: Engine, app: object) -> None:
    with sessionmaker(bind=test_engine)() as session, pytest.raises(ValueError):
        seed_demo_users(session, "short", cheap_passwords())
