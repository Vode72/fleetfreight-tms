import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from db.session import get_session, make_engine

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


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    url = _test_url()
    _ensure_database(url)
    engine = make_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def client(test_engine: Engine) -> Iterator[TestClient]:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
