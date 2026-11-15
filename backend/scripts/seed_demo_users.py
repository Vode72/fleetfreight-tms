"""Create the demo users (admin, planner, viewer). Not part of any migration.

Usage (from the backend directory):
    DEMO_PASSWORD=... uv run python -m scripts.seed_demo_users

The password comes from the DEMO_PASSWORD environment variable (or .env); there is no default.
The command is idempotent: existing demo users are kept (and re-activated, their role restored,
the password updated if it differs). Refuses to run when ENVIRONMENT is not "development".
"""

import sys

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import ENV_FILES, get_settings
from db.models import User
from db.session import get_engine
from domain.passwords import PasswordService
from domain.roles import Role
from domain.users import normalize_email

MIN_PASSWORD_LENGTH = 12

DEMO_USERS: tuple[tuple[str, Role], ...] = (
    ("admin@demo.example.com", Role.ADMIN),
    ("planner@demo.example.com", Role.PLANNER),
    ("viewer@demo.example.com", Role.VIEWER),
)


class _SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    demo_password: str | None = None


def seed_demo_users(session: Session, password: str, passwords: PasswordService) -> list[str]:
    """Create or update the demo users. Returns a list of 'email: created|updated|unchanged'."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"DEMO_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters")
    report: list[str] = []
    for raw_email, role in DEMO_USERS:
        email = normalize_email(raw_email)
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            session.add(
                User(
                    email=email,
                    password_hash=passwords.hash(password),
                    role=role.value,
                    is_active=True,
                )
            )
            report.append(f"{email}: created")
            continue
        changed = False
        if user.role != role.value or not user.is_active:
            user.role = role.value
            user.is_active = True
            changed = True
        result = passwords.verify(password, user.password_hash)
        if not result.ok:
            user.password_hash = passwords.hash(password)
            changed = True
        elif result.new_hash is not None:
            user.password_hash = result.new_hash
            changed = True
        report.append(f"{email}: {'updated' if changed else 'unchanged'}")
    session.commit()
    return report


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo users unless ENVIRONMENT=development.", file=sys.stderr)
        return 2
    password = _SeedSettings().demo_password
    if not password:
        print("DEMO_PASSWORD is required (no default).", file=sys.stderr)
        return 2
    try:
        with sessionmaker(bind=get_engine())() as session:
            for line in seed_demo_users(session, password, PasswordService()):
                print(line)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
