from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect


def _config(engine: Engine) -> Config:
    backend = Path(__file__).parent.parent
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    cfg.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%")
    )
    return cfg


def test_upgrade_creates_auth_tables_and_downgrade_removes_them(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.upgrade(cfg, "head")
    tables = set(inspect(test_engine).get_table_names())
    assert {"users", "sessions"} <= tables

    command.downgrade(cfg, "base")
    assert set(inspect(test_engine).get_table_names()) <= {"alembic_version"}

    command.upgrade(cfg, "head")  # leave the shared test database migrated
    assert {"users", "sessions"} <= set(inspect(test_engine).get_table_names())


def test_preferences_migration_adds_and_removes_columns(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.upgrade(cfg, "head")
    columns = {c["name"]: c for c in inspect(test_engine).get_columns("users")}
    assert columns["theme"]["nullable"] and columns["language"]["nullable"]

    command.downgrade(cfg, "f73b3971a12f")
    names = {c["name"] for c in inspect(test_engine).get_columns("users")}
    assert "theme" not in names and "language" not in names

    command.upgrade(cfg, "head")  # leave the shared test database migrated
    names = {c["name"] for c in inspect(test_engine).get_columns("users")}
    assert {"theme", "language"} <= names
