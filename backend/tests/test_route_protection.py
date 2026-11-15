import re
from collections.abc import Callable, Iterator, Sequence

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute

from app.auth.public import PUBLIC_ROUTES
from tests.conftest import CSRF_HEADERS

DOC_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options"}


def _api_routes(app: FastAPI) -> list[tuple[str, str]]:
    """(METHOD, path) of every operation in the OpenAPI description (the public FastAPI API)."""
    return [
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method in HTTP_METHODS
    ]


def _leaf_routes(routes: Sequence[BaseRoute]) -> Iterator[BaseRoute]:
    """Flatten routers included with include_router (FastAPI keeps them as nested objects)."""
    for route in routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            yield from _leaf_routes(original.routes)
        else:
            yield route


def test_no_route_is_hidden_from_the_openapi_probe(app: FastAPI) -> None:
    """The probe below enumerates routes via OpenAPI; a route hidden from the schema would
    escape it, so hiding routes requires a deliberate change to this test."""
    api_routes = [r for r in _leaf_routes(app.routes) if isinstance(r, APIRoute)]
    assert api_routes
    assert all(r.include_in_schema for r in api_routes)


def test_every_non_public_route_requires_a_session(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    # A route added later, in any way, must be protected without doing anything special.
    late = APIRouter()
    late.add_api_route("/late-get", lambda: {}, methods=["GET"])
    late.add_api_route("/late-delete/{item_id}", lambda item_id: {}, methods=["DELETE"])
    app.include_router(late)
    app.add_api_route("/direct-post", lambda: {}, methods=["POST"])

    with TestClient(app, headers=CSRF_HEADERS) as c:
        routes = _api_routes(app)
        assert ("GET", "/late-get") in routes and ("POST", "/direct-post") in routes
        for method, path in routes:
            if (method, path) in PUBLIC_ROUTES:
                continue
            response = c.request(method, _concrete(path))
            assert response.status_code == 401, f"{method} {path} is reachable without a session"


def test_public_list_has_no_stale_entries(app: FastAPI) -> None:
    assert set(_api_routes(app)) >= PUBLIC_ROUTES


def test_public_routes_are_reachable_without_a_session(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    # Reaches validation (422) rather than being rejected as unauthenticated.
    assert client.post("/auth/login", json={}).status_code == 422


def test_docs_only_in_development(make_app: Callable[..., FastAPI]) -> None:
    dev = make_app(environment="development")
    prod = make_app(environment="production")
    with TestClient(dev) as c:
        assert c.get("/openapi.json").status_code == 200
        assert c.get("/docs").status_code == 200
    with TestClient(prod) as c:
        for path in DOC_PATHS:
            assert c.get(path).status_code == 404, path
    # Production app has no routes other than API routes.
    assert all(isinstance(r, APIRoute) for r in _leaf_routes(prod.routes))
    dev_extra = {
        r.path
        for r in _leaf_routes(dev.routes)
        if not isinstance(r, APIRoute) and hasattr(r, "path")
    }
    assert dev_extra == DOC_PATHS
    # The export script calls app.openapi() directly; it must work in production too.
    assert "/auth/login" in prod.openapi()["paths"]


def test_openapi_is_identical_in_every_environment(make_app: Callable[..., FastAPI]) -> None:
    assert (
        make_app(environment="development").openapi()
        == make_app(environment="production").openapi()
    )
