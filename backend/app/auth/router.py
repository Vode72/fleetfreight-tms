import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.deps import (
    AuthContext,
    current_context,
    get_app_settings,
    get_log_key,
    get_login_ip_limiter,
    get_login_limiter,
    get_password_service,
)
from app.config import Settings
from db.models import AuthSession, User
from db.session import get_session
from domain.passwords import PasswordService, VerifyResult
from domain.rate_limit import AttemptLimiter
from domain.roles import Role
from domain.sessions import expires_at, generate_token, hash_token
from domain.users import email_log_id, normalize_email

logger = logging.getLogger("fleetfreight.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    # Upper bound protects the hasher from huge inputs.
    password: str = Field(min_length=1, max_length=1024)


class MeResponse(BaseModel):
    id: UUID
    email: str
    role: Role


def _client_ip(request: Request) -> str:
    # Behind a reverse proxy this is the proxy's address unless uvicorn is started with
    # --proxy-headers --forwarded-allow-ips=<proxy> (TRUSTED_PROXY_IPS, see backend/README.md).
    # Otherwise every client shares the proxy's IP and the per-IP rate limit hits them together.
    # NOTE: the IP address is personal data. It is written to the log on failed and throttled
    # logins (and to the database only with SESSION_STORE_IP); keep log retention short.
    return request.client.host if request.client else "unknown"


@router.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Invalid e-mail or password (deliberately not specific)"},
        403: {"description": "Missing CSRF header"},
        429: {"description": "Too many failed attempts; see Retry-After"},
    },
)
def login(
    body: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
    pair_limiter: Annotated[AttemptLimiter, Depends(get_login_limiter)],
    ip_limiter: Annotated[AttemptLimiter, Depends(get_login_ip_limiter)],
    log_key: Annotated[bytes, Depends(get_log_key)],
) -> Response:
    email = normalize_email(body.email)
    ip = _client_ip(request)
    pair_key = f"{ip}|{email}"

    retry_after = max(
        pair_limiter.retry_after_seconds(pair_key), ip_limiter.retry_after_seconds(ip)
    )
    if retry_after > 0:
        logger.warning(
            "Login rate limited: ip=%s email_digest=%s retry_after=%ss",
            ip,
            email_log_id(email, log_key),
            retry_after,
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        # Same amount of hashing work as for a real account (timing attack on user enumeration).
        passwords.verify_dummy(body.password)
        result = VerifyResult(ok=False)
    else:
        result = passwords.verify(body.password, user.password_hash)

    if user is None or not result.ok or not user.is_active:
        pair_limiter.record_failure(pair_key)
        ip_limiter.record_failure(ip)
        logger.info("Login failed: ip=%s email_digest=%s", ip, email_log_id(email, log_key))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    now = datetime.now(UTC)
    if result.new_hash is not None:
        user.password_hash = result.new_hash  # hashing parameters have been upgraded
    user.last_login_at = now

    token = generate_token()
    user_agent = request.headers.get("user-agent", "")[:200] or None
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=expires_at(now, settings.session_policy),
            last_seen_at=now,
            user_agent=user_agent,
            ip=ip if settings.session_store_ip else None,
        )
    )
    # Housekeeping: drop this user's sessions that can no longer be valid.
    session.execute(
        delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at < now)
    )
    session.commit()
    pair_limiter.reset(pair_key)

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )  # no max_age: a browser-session cookie; lifetime is enforced on the server
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    ctx: Annotated[AuthContext, Depends(current_context)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Response:
    """Revoke the current session on the server and clear the cookie."""
    ctx.session.revoked_at = datetime.now(UTC)
    session.add(ctx.session)
    session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me", response_model=MeResponse)
def me(ctx: Annotated[AuthContext, Depends(current_context)]) -> MeResponse:
    return MeResponse(id=ctx.user.id, email=ctx.user.email, role=Role(ctx.user.role))
