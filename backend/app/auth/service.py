"""Database-backed auth operations shared by endpoints and scripts."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from db.models import AuthSession


def revoke_all_sessions(session: Session, user_id: UUID, *, now: datetime | None = None) -> int:
    """Revoke every still-active session of a user and return how many were revoked.

    Every code path that deactivates a user or changes a password MUST call this, so existing
    cookies stop working immediately. (Today only scripts.seed_demo_users does either; future
    deactivation and password-change endpoints must call it too.) Does not commit.
    """
    result = session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now or datetime.now(UTC))
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
