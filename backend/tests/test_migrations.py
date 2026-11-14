from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect


def test_alembic_upgrade_head_runs_without_tables(test_engine: Engine) -> None:
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    cfg.set_main_option(
        "sqlalchemy.url", test_engine.url.render_as_string(hide_password=False).replace("%", "%%")
    )
    command.upgrade(cfg, "head")
    assert inspect(test_engine).get_table_names() in ([], ["alembic_version"])
