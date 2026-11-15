"""Server-side session rules. Pure domain module (no framework or database imports).

The browser holds a random token; only its SHA-256 digest is stored. The token has 256 bits of
entropy, so a fast hash is sufficient (unlike passwords, it cannot be guessed or brute-forced).
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class SessionStatus(StrEnum):
    VALID = "valid"
    REVOKED = "revoked"
    EXPIRED = "expired"  # absolute maximum lifetime reached
    IDLE = "idle"  # sliding inactivity timeout reached


@dataclass(frozen=True)
class SessionPolicy:
    idle_timeout: timedelta
    absolute_timeout: timedelta
    # last_seen_at is written at most this often, to avoid a database write on every request.
    touch_interval: timedelta = timedelta(minutes=1)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expires_at(created_at: datetime, policy: SessionPolicy) -> datetime:
    return created_at + policy.absolute_timeout


def evaluate_session(
    *,
    expires_at: datetime,
    last_seen_at: datetime,
    revoked_at: datetime | None,
    now: datetime,
    policy: SessionPolicy,
) -> SessionStatus:
    if revoked_at is not None:
        return SessionStatus.REVOKED
    if now >= expires_at:
        return SessionStatus.EXPIRED
    if now - last_seen_at >= policy.idle_timeout:
        return SessionStatus.IDLE
    return SessionStatus.VALID


def should_touch(last_seen_at: datetime, now: datetime, policy: SessionPolicy) -> bool:
    return now - last_seen_at >= policy.touch_interval
