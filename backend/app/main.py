from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from db.session import get_session

app = FastAPI(title=get_settings().app_name)


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "error"]


# INTENTIONALLY PUBLIC: /health needs no authentication so that container healthchecks and
# monitoring can call it. In phase 1D every other endpoint is protected by default and this
# one is listed as an explicit exception. It exposes no data beyond ok/error.
@app.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Database unreachable"}},
)
def health(response: Response, session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Reported as 503 to the caller; not swallowed silently.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="error", database="error")
    return HealthResponse(status="ok", database="ok")
