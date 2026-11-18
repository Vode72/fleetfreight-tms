from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    # Default validity of a GDP training record, used to suggest valid_until (D69). A company
    # practice, not a regulation: the planner can always set another end date.
    gdp_training_default_validity_months: int = Field(default=12, ge=1, le=120)

    # Secret for the HMAC that pseudonymises e-mail addresses in logs. Empty: random per process.
    log_hmac_key: str = ""
    # Comma-separated reverse proxy addresses whose X-Forwarded-For is trusted. The container
    # entrypoint (start.sh) passes it to uvicorn. Empty (default): trust none.
    trusted_proxy_ips: str = ""

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> Settings:
        # Startup guard: a production deployment must never send the session cookie over HTTP.
        if self.environment == "production" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true when ENVIRONMENT=production")
        return self

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
