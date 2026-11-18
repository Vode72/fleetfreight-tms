from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text


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


REGISTER_TABLES = {"customers", "locations", "carriers", "drivers", "driver_qualifications"}


def test_registers_migration_creates_and_removes_tables(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.upgrade(cfg, "head")
    insp = inspect(test_engine)
    assert set(insp.get_table_names()) >= REGISTER_TABLES
    index_names = {i["name"] for i in insp.get_indexes("customers")}
    assert "uq_customers_one_own_company" in index_names

    command.downgrade(cfg, "a1c4e7d90b25")
    tables = set(inspect(test_engine).get_table_names())
    assert not REGISTER_TABLES & tables
    assert {"users", "sessions"} <= tables  # earlier revisions untouched

    # btree_gist is created by the upgrade and deliberately kept by the downgrade
    with test_engine.connect() as conn:
        assert conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'")
        ).scalar()

    command.upgrade(cfg, "head")  # leave the shared test database migrated
    assert set(inspect(test_engine).get_table_names()) >= REGISTER_TABLES


def test_model_metadata_matches_migrated_schema(test_engine: Engine) -> None:
    """Alembic autogenerate finds no difference between the models and the migrated database."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import db.models  # noqa: F401  (registers the models)
    from db.session import Base

    command.upgrade(_config(test_engine), "head")
    with test_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


FLEET_TABLES = {
    "trucks",
    "dollies",
    "load_units",
    "compartments",
    "reefer_units",
    "reefer_evaporators",
    "equipment_qualifications",
}


def test_fleet_migration_creates_and_removes_tables(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.upgrade(cfg, "head")
    insp = inspect(test_engine)
    assert set(insp.get_table_names()) >= FLEET_TABLES
    # every foreign key column of the fleet tables is covered by an index (or a unique constraint)
    for table in FLEET_TABLES:
        covered = {i["column_names"][0] for i in insp.get_indexes(table)} | {
            u["column_names"][0] for u in insp.get_unique_constraints(table)
        }
        for fk in insp.get_foreign_keys(table):
            assert fk["constrained_columns"][0] in covered, (table, fk["name"])

    command.downgrade(cfg, "f0c09cb23c9d")  # revision B only
    tables = set(inspect(test_engine).get_table_names())
    assert not FLEET_TABLES & tables
    assert tables >= REGISTER_TABLES  # revision A and 2B-1 untouched
    carrier_columns = {c["name"] for c in inspect(test_engine).get_columns("carriers")}
    assert {"customer_id", "archived_at"} <= carrier_columns

    command.downgrade(cfg, "c52d8e3f1a47")  # revision A as well
    carrier_columns = {c["name"] for c in inspect(test_engine).get_columns("carriers")}
    assert not {"customer_id", "archived_at"} & carrier_columns

    command.upgrade(cfg, "head")  # leave the shared test database migrated
    assert set(inspect(test_engine).get_table_names()) >= FLEET_TABLES


def test_fleet_downgrade_is_possible_with_data(test_engine: Engine) -> None:
    """Dropping the fleet tables in reverse order works with rows in every table."""
    from tests.test_fleet_db import (
        _body,
        _compartment,
        _equipment,
        _evaporator,
        _reefer,
        _trailer,
        _truck,
    )
    from tests.test_registers_db import _carrier

    cfg = _config(test_engine)
    command.upgrade(cfg, "head")
    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE equipment_qualifications, trucks, carriers CASCADE"))
    carrier = _carrier(test_engine, "Demo Migration Oy")
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _body(test_engine, carrier, truck)
    unit = _trailer(test_engine, carrier, body_type="reefer")
    machine = _reefer(test_engine, unit)
    _compartment(test_engine, unit, evaporator_id=_evaporator(test_engine, machine, unit))
    _equipment(test_engine, type="atp", load_unit_id=unit)
    try:
        command.downgrade(cfg, "f0c09cb23c9d")
        assert not FLEET_TABLES & set(inspect(test_engine).get_table_names())
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("TRUNCATE carriers CASCADE"))
        command.upgrade(cfg, "head")
