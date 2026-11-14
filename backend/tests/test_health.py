from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from db.session import get_session, make_engine


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

    app.dependency_overrides[get_session] = override
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()
        dead.dispose()
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error"}
