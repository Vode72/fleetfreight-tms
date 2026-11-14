from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env is looked up in the repository root and in backend/, independent of the working directory.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """Application settings, read from environment variables (and an optional .env file)."""

    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://fleetfreight:change-me@localhost:5432/fleetfreight",
        description="SQLAlchemy URL (psycopg 3 driver).",
    )
    app_name: str = "FleetFreight TMS"


@lru_cache
def get_settings() -> Settings:
    return Settings()
