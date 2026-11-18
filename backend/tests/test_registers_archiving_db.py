"""Revision f0c09cb23c9d: archiving (D72), RESTRICT foreign keys and the own carrier link (D73)."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from tests.test_registers_db import _carrier, _customer, _driver, _insert, _location, _own_carrier

pytestmark = pytest.mark.usefixtures("clean_registers")

ARCHIVABLE = ("customers", "locations", "carriers", "drivers", "trucks", "dollies", "load_units")


@pytest.mark.parametrize("table", ARCHIVABLE)
def test_archived_at_is_a_nullable_timestamptz(test_engine: Engine, table: str) -> None:
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns"
                " WHERE table_name = :t AND column_name = 'archived_at'"
            ),
            {"t": table},
        ).one()
    assert row.data_type == "timestamp with time zone"
    assert row.is_nullable == "YES"


def test_new_rows_are_active_and_archiving_keeps_the_row(test_engine: Engine) -> None:
    customer = _customer(test_engine)
    with test_engine.begin() as conn:
        assert conn.execute(text("SELECT archived_at FROM customers")).scalar() is None
        conn.execute(
            text("UPDATE customers SET archived_at = :t WHERE id = :i"),
            {"t": datetime(2026, 11, 18, 12, 0, tzinfo=UTC), "i": customer},
        )
    with test_engine.connect() as conn:
        archived = conn.execute(text("SELECT archived_at FROM customers")).scalar()
    assert archived == datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def test_every_register_foreign_key_is_restrict(test_engine: Engine) -> None:
    """D72: no register foreign key cascades or sets null (sessions -> users is not a register)."""
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT conrelid::regclass::text AS tbl, conname, confdeltype FROM pg_constraint"
                " WHERE contype = 'f' AND conrelid::regclass::text <> 'sessions'"
            )
        ).all()
    from db.session import Base

    modelled = {
        fk.name
        for table in Base.metadata.tables.values()
        if table.name != "sessions"
        for fk in table.foreign_key_constraints
    }
    assert {r.conname for r in rows} == modelled  # none missing from the model, none extra
    assert len(rows) >= 15
    assert {r.conname: r.confdeltype for r in rows if r.confdeltype != "r"} == {}


def test_referenced_rows_cannot_be_deleted(test_engine: Engine) -> None:
    customer = _customer(test_engine)
    parent = _location(test_engine, "Demo Parent")
    _location(test_engine, "Demo Child", parent_location_id=parent)
    _location(test_engine, "Demo Site", type="customer_site", customer_id=customer)
    for table, row_id in (("locations", parent), ("customers", customer)):
        with pytest.raises(IntegrityError), test_engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": row_id})


def test_unreferenced_rows_can_still_be_deleted(test_engine: Engine) -> None:
    carrier = _carrier(test_engine)
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM carriers WHERE id = :i"), {"i": carrier})


# --- D73: the own carrier links to the own company's customer row


def test_own_carrier_requires_a_customer_link(test_engine: Engine) -> None:
    with pytest.raises(IntegrityError):
        _insert(test_engine, "carriers", type="own")  # no link
    with pytest.raises(IntegrityError):
        _carrier(test_engine, "Demo Sub Oy", customer_id=_customer(test_engine))  # not own


def test_own_carrier_has_no_identity_of_its_own(test_engine: Engine) -> None:
    customer = _customer(test_engine, "Demo Own Oy", type="own_company")
    for column, value in (("name", "Demo Own Oy"), ("business_id", "DEMO-1"), ("country", "FI")):
        with pytest.raises(IntegrityError):
            _own_carrier(test_engine, customer, **{column: value})
    _own_carrier(test_engine, customer)


def test_subcontractor_needs_name_and_country(test_engine: Engine) -> None:
    for values in ({"name": None}, {"country": None}):
        with pytest.raises(IntegrityError):
            _insert(
                test_engine,
                "carriers",
                **{"type": "subcontractor", "name": "Demo X", "country": "DE"} | values,
            )


def test_carrier_link_must_point_to_an_existing_customer(test_engine: Engine) -> None:
    with pytest.raises(IntegrityError):
        _own_carrier(test_engine, uuid.uuid4())


def test_linked_customer_cannot_be_deleted(test_engine: Engine) -> None:
    customer = _customer(test_engine, "Demo Own Oy", type="own_company")
    _own_carrier(test_engine, customer)
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM customers WHERE id = :i"), {"i": customer})


def test_driver_of_the_own_carrier_is_stored_without_a_carrier_name(test_engine: Engine) -> None:
    own = _own_carrier(test_engine)
    _driver(test_engine, own)
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT coalesce(ca.name, cu.name) AS name FROM carriers ca"
                " LEFT JOIN customers cu ON cu.id = ca.customer_id"
            )
        ).one()
    assert row.name == "Demo Own Oy"


# --- migration with existing data


def _config(engine: Engine) -> Config:
    backend = Path(__file__).parent.parent
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    cfg.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%")
    )
    return cfg


def _rows(engine: Engine, sql: str) -> list[Any]:
    with engine.connect() as conn:
        return list(conn.execute(text(sql)).all())


def test_upgrade_links_an_existing_own_carrier_and_downgrade_restores_it(
    test_engine: Engine,
) -> None:
    cfg = _config(test_engine)
    command.downgrade(cfg, "c52d8e3f1a47")  # the 2B-1 schema
    try:
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO customers (name, type, country, business_id)"
                    " VALUES ('Demo Own Oy', 'own_company', 'FI', 'DEMO-FI-1')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO carriers (name, type, country, business_id)"
                    " VALUES ('Demo Own Oy', 'own', 'FI', 'DEMO-FI-1'),"
                    " ('Demo Sub Oy', 'subcontractor', 'DE', 'DEMO-DE-1')"
                )
            )
        command.upgrade(cfg, "f0c09cb23c9d")
        own = _rows(
            test_engine,
            "SELECT name, country, business_id, customer_id IS NOT NULL AS linked"
            " FROM carriers WHERE type = 'own'",
        )
        assert [tuple(r) for r in own] == [(None, None, None, True)]
        sub = _rows(test_engine, "SELECT name, country FROM carriers WHERE type = 'subcontractor'")
        assert [tuple(r) for r in sub] == [("Demo Sub Oy", "DE")]

        command.downgrade(cfg, "c52d8e3f1a47")
        own = _rows(test_engine, "SELECT name, country, business_id FROM carriers WHERE type='own'")
        assert [tuple(r) for r in own] == [("Demo Own Oy", "FI", "DEMO-FI-1")]
    finally:
        with test_engine.begin() as conn:
            conn.execute(
                text("TRUNCATE driver_qualifications, drivers, carriers, customers CASCADE")
            )
        command.upgrade(cfg, "head")  # leave the shared test database migrated


def test_upgrade_refuses_an_own_carrier_without_an_own_company(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.downgrade(cfg, "c52d8e3f1a47")
    try:
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO carriers (name, type, country) VALUES ('Demo Own Oy', 'own', 'FI')"
                )
            )
        with pytest.raises(RuntimeError, match="no own_company"):
            command.upgrade(cfg, "f0c09cb23c9d")
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("TRUNCATE carriers CASCADE"))
        command.upgrade(cfg, "head")


def test_downgrade_of_revision_a_restores_cascade_and_removes_columns(test_engine: Engine) -> None:
    cfg = _config(test_engine)
    command.downgrade(cfg, "c52d8e3f1a47")
    try:
        cols = {
            (r.table_name, r.column_name)
            for r in _rows(
                test_engine,
                "SELECT table_name, column_name FROM information_schema.columns"
                " WHERE column_name IN ('archived_at', 'customer_id')"
                " AND table_name IN ('customers', 'locations', 'carriers', 'drivers')",
            )
        }
        assert cols == {("locations", "customer_id")}
        rule = _rows(
            test_engine,
            "SELECT confdeltype FROM pg_constraint"
            " WHERE conname = 'fk_driver_qualifications_driver_id'",
        )
        assert [r.confdeltype for r in rule] == ["c"]
    finally:
        command.upgrade(cfg, "head")
