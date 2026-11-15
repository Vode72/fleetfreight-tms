"""Authentication, CSRF and role dependencies.

`guard` is installed as a global dependency of the application, so every route is authenticated
unless it is listed in `PUBLIC_ROUTES`. Endpoints get the user via `current_context`.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.public import PUBLIC_ROUTES
from app.config import Settings
from db.models import AuthSession, User
from db.session import get_session
from domain.passwords import PasswordService
from domain.rate_limit import AttemptLimiter
from domain.roles import Role
from domain.sessions import SessionStatus, evaluate_session, hash_token, should_touch

logger = logging.getLogger("fleetfreight.auth")

# CSRF defence: unsafe requests must carry this custom header. A cross-site page cannot add it
# without a CORS preflight, and this application sends no CORS headers, so browsers block it.
# This complements the SameSite=Lax cookie (which already withholds the cookie on cross-site POSTs).
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "fleetfreight"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_password_service(request: Request) -> PasswordService:
    service: PasswordService = request.app.state.password_service
    return service


def get_log_key(request: Request) -> bytes:
    key: bytes = request.app.state.log_hmac_key
    return key


def get_login_limiter(request: Request) -> AttemptLimiter:
    limiter: AttemptLimiter = request.app.state.login_limiter
    return limiter


def get_login_ip_limiter(request: Request) -> AttemptLimiter:
    limiter: AttemptLimiter = request.app.state.login_ip_limiter
    return limiter


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def guard(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AuthContext | None:
    """Global dependency: CSRF check for unsafe methods, then session authentication.

    Returns None only for routes listed in PUBLIC_ROUTES. A route whose path cannot be
    determined is treated as protected.
    """
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF check failed")

    route_path = getattr(request.scope.get("route"), "path", None)
    if (request.method, route_path) in PUBLIC_ROUTES:
        return None

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _unauthorized()

    row = session.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == hash_token(token))
    ).first()
    if row is None:
        raise _unauthorized()
    auth_session, user = row

    now = datetime.now(UTC)
    policy = settings.session_policy
    state = evaluate_session(
        expires_at=auth_session.expires_at,
        last_seen_at=auth_session.last_seen_at,
        revoked_at=auth_session.revoked_at,
        now=now,
        policy=policy,
    )
    if state is not SessionStatus.VALID or not user.is_active:
        raise _unauthorized()

    if should_touch(auth_session.last_seen_at, now, policy):
        session.execute(
            update(AuthSession).where(AuthSession.id == auth_session.id).values(last_seen_at=now)
        )
        session.commit()
    return AuthContext(user=user, session=auth_session)


def current_context(
    ctx: Annotated[AuthContext | None, Depends(guard)],
) -> AuthContext:
    """The authenticated user and session. `guard` is cached per request, so it runs once."""
    if ctx is None:  # a public route asked for a user: there is none
        raise _unauthorized()
    return ctx


def require_role(*roles: Role | str) -> Callable[[AuthContext], AuthContext]:
    """Dependency factory: `Depends(require_role("admin"))` -> 403 for other roles."""
    allowed = {Role(r) for r in roles}

    def dependency(ctx: Annotated[AuthContext, Depends(current_context)]) -> AuthContext:
        if Role(ctx.user.role) not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return ctx

    return dependency
