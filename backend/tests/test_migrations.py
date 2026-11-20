from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError


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


# --- e0f14a4663b6: one reefer unit with evaporators (D76)


def _old_fd(engine: Engine) -> dict[str, object]:
    """An FD trailer in the d3ad319be9a8 shape: two machines (front diesel, rear hybrid), each
    serving one compartment, with a service period each."""
    from tests.test_fleet_db import _equipment, _trailer
    from tests.test_registers_db import _carrier, _insert

    carrier = _carrier(engine, "Demo Reefer Migration Oy")
    unit = _trailer(engine, carrier, body_type="reefer", model_code="FD", partition=True)
    front = _insert(
        engine,
        "reefer_units",
        load_unit_id=unit,
        position="front",
        unit_name="Demo Chill F",
        power_source="diesel",
    )
    rear = _insert(
        engine,
        "reefer_units",
        load_unit_id=unit,
        position="rear",
        unit_name="Demo Chill R",
        power_source="hybrid",
    )
    for number, machine in ((1, front), (2, rear)):
        _insert(
            engine,
            "compartments",
            load_unit_id=unit,
            reefer_unit_id=machine,
            number=number,
            temperature_min="-25.0",
            temperature_max="8.0",
        )
    _equipment(
        engine,
        type="reefer_service",
        reefer_unit_id=front,
        valid_from="2026-01-01",
        valid_until="2026-06-30",
    )
    return {"unit": unit, "front": front, "rear": rear}


def _at_fleet_tables(engine: Engine) -> Config:
    cfg = _config(engine)
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE equipment_qualifications, trucks, carriers CASCADE"))
    command.downgrade(cfg, "d3ad319be9a8")
    return cfg


def test_evaporator_migration_moves_machines_compartments_and_service(
    test_engine: Engine,
) -> None:
    from tests.test_fleet_db import _equipment

    cfg = _at_fleet_tables(test_engine)
    try:
        old = _old_fd(test_engine)
        _equipment(
            test_engine,
            type="reefer_service",
            reefer_unit_id=old["rear"],
            valid_from="2026-07-01",
            valid_until="2027-06-30",
        )
        command.upgrade(cfg, "e0f14a4663b6")
        with test_engine.connect() as conn:
            machines = conn.execute(
                text("SELECT id, unit_name, power_source FROM reefer_units")
            ).all()
            # the front machine is kept, with its own values
            assert [(m.id, m.unit_name, m.power_source) for m in machines] == [
                (old["front"], "Demo Chill F", "diesel")
            ]
            comps = conn.execute(
                text(
                    "SELECT c.number, e.position, e.reefer_unit_id FROM compartments c"
                    " JOIN reefer_evaporators e ON e.id = c.evaporator_id ORDER BY c.number"
                )
            ).all()
            assert [tuple(c) for c in comps] == [
                (1, "front", old["front"]),
                (2, "rear", old["front"]),
            ]
            # both service periods are now on the kept machine
            services = conn.execute(
                text(
                    "SELECT reefer_unit_id FROM equipment_qualifications"
                    " WHERE type = 'reefer_service'"
                )
            ).all()
            assert [s[0] for s in services] == [old["front"], old["front"]]

        command.downgrade(cfg, "d3ad319be9a8")
        with test_engine.connect() as conn:
            restored = conn.execute(
                text(
                    "SELECT r.position, c.number FROM compartments c"
                    " JOIN reefer_units r ON r.id = c.reefer_unit_id ORDER BY c.number"
                )
            ).all()
        assert [tuple(r) for r in restored] == [("front", 1), ("rear", 2)]
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("TRUNCATE equipment_qualifications, carriers CASCADE"))
        command.upgrade(cfg, "head")


def test_evaporator_migration_stops_on_overlapping_service_periods(
    test_engine: Engine,
) -> None:
    from tests.test_fleet_db import _equipment

    cfg = _at_fleet_tables(test_engine)
    try:
        old = _old_fd(test_engine)
        _equipment(  # overlaps the front machine's period
            test_engine,
            type="reefer_service",
            reefer_unit_id=old["rear"],
            valid_from="2026-03-01",
            valid_until="2026-12-31",
        )
        with pytest.raises(IntegrityError):
            command.upgrade(cfg, "e0f14a4663b6")
        # the upgrade is one transaction: nothing changed
        with test_engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM reefer_units")).scalar() == 2
            assert "reefer_evaporators" not in inspect(test_engine).get_table_names()
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("TRUNCATE equipment_qualifications, carriers CASCADE"))
        command.upgrade(cfg, "head")


def test_evaporator_migration_stops_when_one_machine_serves_two_compartments(
    test_engine: Engine,
) -> None:
    from tests.test_registers_db import _insert

    cfg = _at_fleet_tables(test_engine)
    try:
        old = _old_fd(test_engine)
        _insert(
            test_engine,
            "compartments",
            load_unit_id=old["unit"],
            reefer_unit_id=old["front"],
            number=3,
            temperature_min="2.0",
            temperature_max="8.0",
        )
        with pytest.raises(RuntimeError, match="several compartments"):
            command.upgrade(cfg, "e0f14a4663b6")
        assert "reefer_evaporators" not in inspect(test_engine).get_table_names()
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("TRUNCATE equipment_qualifications, carriers CASCADE"))
        command.upgrade(cfg, "head")


def test_evaporator_migration_follows_the_model_code(test_engine: Engine) -> None:
    """FB with only a rear machine gets its evaporator at the front; an FD with one machine gets
    the missing evaporator; a compartment without a machine stays without an evaporator."""
    from tests.test_fleet_db import _trailer
    from tests.test_registers_db import _carrier, _insert

    cfg = _at_fleet_tables(test_engine)
    try:
        carrier = _carrier(test_engine, "Demo Reefer Codes Oy")
        fb = _trailer(test_engine, carrier, body_type="reefer", model_code="FB")
        fd = _trailer(test_engine, carrier, body_type="reefer", model_code="FD", partition=True)
        fb_rear = _insert(
            test_engine,
            "reefer_units",
            load_unit_id=fb,
            position="rear",
            unit_name="Demo Mono",
            power_source="electric",
        )
        _insert(
            test_engine,
            "reefer_units",
            load_unit_id=fd,
            position="front",
            unit_name="Demo Duo",
            power_source="diesel",
        )
        comp = {"temperature_min": "-25.0", "temperature_max": "8.0"}
        _insert(
            test_engine, "compartments", load_unit_id=fb, reefer_unit_id=fb_rear, number=1, **comp
        )
        _insert(test_engine, "compartments", load_unit_id=fd, number=1, **comp)  # no machine
        command.upgrade(cfg, "e0f14a4663b6")
        with test_engine.connect() as conn:
            evaporators = {
                (r.load_unit_id, r.position)
                for r in conn.execute(text("SELECT load_unit_id, position FROM reefer_evaporators"))
            }
            assert evaporators == {(fb, "front"), (fd, "front"), (fd, "rear")}
            comps = {
                r.load_unit_id: r.position
                for r in conn.execute(
                    text(
                        "SELECT c.load_unit_id, e.position FROM compartments c"
                        " LEFT JOIN reefer_evaporators e ON e.id = c.evaporator_id"
                    )
                )
            }
            assert comps == {fb: "front", fd: None}
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("TRUNCATE equipment_qualifications, carriers CASCADE"))
        command.upgrade(cfg, "head")


def test_evaporator_migration_stops_on_an_fs_with_two_machines(test_engine: Engine) -> None:
    from tests.test_fleet_db import _trailer
    from tests.test_registers_db import _carrier, _insert

    cfg = _at_fleet_tables(test_engine)
    try:
        carrier = _carrier(test_engine, "Demo Reefer Side Oy")
        fs = _trailer(test_engine, carrier, body_type="reefer", model_code="FS", side_doors=True)
        for position in ("front", "rear"):
            _insert(
                test_engine,
                "reefer_units",
                load_unit_id=fs,
                position=position,
                unit_name="Demo Side",
                power_source="diesel",
            )
        with pytest.raises(RuntimeError, match="FB / FS"):
            command.upgrade(cfg, "e0f14a4663b6")
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("TRUNCATE equipment_qualifications, carriers CASCADE"))
        command.upgrade(cfg, "head")


RESTRICTION_TABLES = {
    "countries",
    "country_rules",
    "public_holidays",
    "road_restrictions",
    "road_restriction_windows",
}


def test_restrictions_migration_creates_and_removes_tables(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.upgrade(cfg, "2cb43f9f78c1")
    assert set(inspect(test_engine).get_table_names()) >= RESTRICTION_TABLES

    command.downgrade(cfg, "e0f14a4663b6")
    tables = set(inspect(test_engine).get_table_names())
    assert not RESTRICTION_TABLES & tables
    assert "load_units" in tables  # earlier revisions untouched

    command.upgrade(cfg, "head")
    assert set(inspect(test_engine).get_table_names()) >= RESTRICTION_TABLES


def test_solo_tractor_migration_adds_and_removes_the_column(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.upgrade(cfg, "9bb6eb8d032e")
    columns = {c["name"] for c in inspect(test_engine).get_columns("road_restrictions")}
    assert "solo_tractor" in columns
    command.downgrade(cfg, "2cb43f9f78c1")
    columns = {c["name"] for c in inspect(test_engine).get_columns("road_restrictions")}
    assert "solo_tractor" not in columns
    command.upgrade(cfg, "head")


def test_toll_system_migration_allows_an_unrecorded_value(test_engine: Engine) -> None:
    cfg = _config(test_engine)

    def nullable() -> bool:
        columns = inspect(test_engine).get_columns("country_rules")
        return next(c["nullable"] for c in columns if c["name"] == "toll_system")

    command.upgrade(cfg, "c3888037643f")
    assert nullable()
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO countries (code, name_en, name_fi, time_zone, currency, eu_member)"
                " VALUES ('FI', 'Finland', 'Suomi', 'Europe/Helsinki', 'EUR', true)"
                " ON CONFLICT DO NOTHING"
            )
        )
        for valid_from, valid_until, toll in (
            ("2026-01-01", "2026-12-31", None),
            ("2027-01-01", None, "none"),
        ):
            conn.execute(
                text(
                    "INSERT INTO country_rules (id, country, valid_from, valid_until,"
                    " toll_system, source_url, checked_on) VALUES (gen_random_uuid(), 'FI',"
                    " :valid_from, :valid_until, :toll, 'https://example.com', '2026-11-19')"
                ),
                {"valid_from": valid_from, "valid_until": valid_until, "toll": toll},
            )
    command.downgrade(cfg, "9bb6eb8d032e")
    assert not nullable()
    with test_engine.connect() as conn:
        # The row without a toll system is deleted; the recorded one stays.
        assert conn.execute(text("SELECT toll_system FROM country_rules")).scalars().all() == [
            "none"
        ]
        conn.execute(text("DELETE FROM country_rules"))
        conn.commit()
    command.upgrade(cfg, "head")


def test_speed_class_migration_clears_unclassified_speeds(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.downgrade(cfg, "c3888037643f")
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO countries (code, name_en, name_fi, time_zone, currency, eu_member)"
                " VALUES ('FI', 'Finland', 'Suomi', 'Europe/Helsinki', 'EUR', true)"
                " ON CONFLICT DO NOTHING"
            )
        )
        conn.execute(
            text(
                "INSERT INTO country_rules (id, country, valid_from, truck_speed_other_kmh,"
                " source_url, checked_on) VALUES (gen_random_uuid(), 'FI', '2026-01-01', 80,"
                " 'https://example.com', '2026-11-19')"
            )
        )
    command.upgrade(cfg, "47da3484520e")
    with test_engine.begin() as conn:
        # The class is unknown, so the speed becomes unrecorded for the loader to fill in.
        assert (
            conn.execute(text("SELECT truck_speed_other_kmh FROM country_rules")).scalar() is None
        )
        conn.execute(text("DELETE FROM country_rules"))
    command.downgrade(cfg, "c3888037643f")
    columns = {c["name"] for c in inspect(test_engine).get_columns("country_rules")}
    assert "speed_weight_basis" not in columns
    command.upgrade(cfg, "head")
