from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from db.session import get_session, make_engine
from tests.conftest import make_settings


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_database_down() -> None:
    # Port 1 refuses connections, simulating an unreachable database.
    dead = make_engine(
        make_url("postgresql+psycopg://x:x@127.0.0.1:1/x").render_as_string(hide_password=False)
    )
    factory = sessionmaker(bind=dead)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    application = create_app(make_settings())
    application.dependency_overrides[get_session] = override
    try:
        response = TestClient(application).get("/health")
    finally:
        dead.dispose()
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error"}
