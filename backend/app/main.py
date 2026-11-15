from datetime import timedelta
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.deps import guard
from app.auth.router import router as auth_router
from app.config import Settings, get_settings
from db.session import get_session
from domain.passwords import PasswordService
from domain.rate_limit import AttemptLimiter


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "error"]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    docs = settings.docs_enabled
    application = FastAPI(
        title=settings.app_name,
        # Secure by default: `guard` authenticates every route (and checks CSRF on unsafe
        # methods) unless the route is listed in app.auth.public.PUBLIC_ROUTES.
        dependencies=[Depends(guard)],
        # Interactive docs only in development. app.openapi() still works in every environment,
        # which scripts/export_openapi.py relies on.
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    window = timedelta(minutes=settings.login_window_minutes)
    application.state.settings = settings
    application.state.password_service = PasswordService()
    application.state.login_limiter = AttemptLimiter(settings.login_max_failures, window)
    # Coarser per-IP limit so rotating e-mail addresses from one address does not bypass the above.
    application.state.login_ip_limiter = AttemptLimiter(settings.login_max_failures * 4, window)

    application.include_router(auth_router)

    # PUBLIC (listed in app.auth.public.PUBLIC_ROUTES): /health needs no authentication so that
    # container healthchecks and monitoring can call it. It exposes no data beyond ok/error.
    @application.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Database unreachable"}},
    )
    def health(
        response: Response, session: Annotated[Session, Depends(get_session)]
    ) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            # Reported as 503 to the caller; not swallowed silently.
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return HealthResponse(status="error", database="error")
        return HealthResponse(status="ok", database="ok")

    return application


app = create_app()
