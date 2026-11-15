from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.sessions import SessionPolicy

# .env is looked up in the repository root and in backend/, independent of the working directory.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """Application settings, read from environment variables (and an optional .env file)."""

    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://fleetfreight:change-me@localhost:5432/fleetfreight",
        description="SQLAlchemy URL (psycopg 3 driver).",
    )
    app_name: str = "FleetFreight TMS"

    # Safe default: anything but "development" is treated as production (no /docs, Secure cookie).
    environment: Literal["development", "production"] = "production"

    # Session cookie and server-side session lifetime.
    session_cookie_name: str = "fleetfreight_session"
    # Send the cookie over HTTPS only. Turn off for plain-HTTP local development.
    session_cookie_secure: bool = True
    session_idle_timeout_minutes: int = Field(default=480, ge=1)
    session_absolute_timeout_days: int = Field(default=7, ge=1)
    # The client IP is personal data; store it with the session only when explicitly enabled.
    session_store_ip: bool = False

    # Login throttling (in memory, per process).
    login_max_failures: int = Field(default=5, ge=1)
    login_window_minutes: int = Field(default=15, ge=1)

    @property
    def docs_enabled(self) -> bool:
        return self.environment == "development"

    @property
    def session_policy(self) -> SessionPolicy:
        return SessionPolicy(
            idle_timeout=timedelta(minutes=self.session_idle_timeout_minutes),
            absolute_timeout=timedelta(days=self.session_absolute_timeout_days),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
