import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.main import create_app
from db.models import User
from db.session import get_session, make_engine
from domain.passwords import PasswordService
from domain.roles import Role

DEFAULT_TEST_URL = "postgresql+psycopg://fleetfreight:change-me@localhost:5432/fleetfreight_test"


def _test_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    name = make_url(url).database or ""
    # Safety guard: tests must never run against a development database.
    if not name.endswith("_test"):
        raise RuntimeError(f"TEST_DATABASE_URL database name must end with '_test', got {name!r}")
    if url == os.environ.get("DATABASE_URL"):
        raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL")
    return url


def _ensure_database(url: str) -> None:
    """Create the dedicated test database if it does not exist yet."""
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": parsed.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    admin.dispose()


def _migrate(engine: Engine) -> None:
    backend = Path(__file__).parent.parent
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    cfg.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%")
    )
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    url = _test_url()
    _ensure_database(url)
    engine = make_engine(url)
    _migrate(engine)
    yield engine
    engine.dispose()


CSRF_HEADERS = {"X-Requested-With": "fleetfreight"}
PASSWORD = "correct horse battery staple"


def cheap_passwords() -> PasswordService:
    """Argon2id with minimal cost so tests stay fast (production uses the library defaults)."""
    return PasswordService(PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "development",
        "session_cookie_secure": False,  # TestClient talks plain HTTP
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture
def make_app(test_engine: Engine) -> Iterator[Callable[..., FastAPI]]:
    """Factory for isolated app instances bound to the test database."""
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE users CASCADE"))

    def build(**settings: object) -> FastAPI:
        application = create_app(make_settings(**settings))
        application.state.password_service = cheap_passwords()
        application.dependency_overrides[get_session] = override
        return application

    yield build


@pytest.fixture
def app(make_app: Callable[..., FastAPI]) -> FastAPI:
    return make_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Client that sends the CSRF header by default."""
    with TestClient(app, headers=CSRF_HEADERS) as c:
        yield c


@pytest.fixture
def add_user(test_engine: Engine) -> Callable[..., User]:
    def add(
        email: str = "planner@demo.example.com",
        password: str = PASSWORD,
        role: Role = Role.PLANNER,
        is_active: bool = True,
    ) -> User:
        with sessionmaker(bind=test_engine, expire_on_commit=False)() as session:
            user = User(
                email=email,
                password_hash=cheap_passwords().hash(password),
                role=role.value,
                is_active=is_active,
            )
            session.add(user)
            session.commit()
            return user

    return add
