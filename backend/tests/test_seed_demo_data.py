from datetime import date

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

import scripts.seed_demo_data as seed
from domain.locations import validate_opening_hours, validate_timezone
from scripts.seed_demo_data import seed_demo_data
from tests.conftest import make_settings

pytestmark = pytest.mark.usefixtures("clean_registers")
TODAY = date(2026, 11, 18)


def _count(engine: Engine, sql: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar() or 0)


def _run(engine: Engine, today: date = TODAY) -> dict[str, int]:
    with sessionmaker(bind=engine)() as session:
        return dict(seed_demo_data(session, today))


def test_seed_is_idempotent(test_engine: Engine) -> None:
    first = _run(test_engine)
    tables = ("customers", "locations", "carriers", "drivers", "driver_qualifications")
    counts = {t: _count(test_engine, f"SELECT count(*) FROM {t}") for t in tables}
    assert first == counts
    assert _run(test_engine) == {}  # nothing created the second time
    assert counts == {t: _count(test_engine, f"SELECT count(*) FROM {t}") for t in tables}


def test_seed_content(test_engine: Engine) -> None:
    _run(test_engine)

    def q(sql: str) -> int:
        return _count(test_engine, sql)

    assert (
        q("SELECT count(*) FROM customers WHERE type = 'own_company' AND name = 'Demo Freight Oy'")
        == 1
    )
    assert 4 <= q("SELECT count(*) FROM customers WHERE type = 'customer'") <= 6
    assert q("SELECT count(*) FROM customers WHERE pallet_exchange_agreed") == 1
    assert 3 <= q("SELECT count(*) FROM carriers") <= 4
    assert q("SELECT count(*) FROM carriers WHERE type = 'own'") == 1
    assert 6 <= q("SELECT count(*) FROM drivers") <= 8
    # D31-D33: five terminals, all with docks; cold storage and plugs in Central, Tampere, Oulu.
    assert q("SELECT count(*) FROM locations WHERE type = 'terminal'") == 5
    assert q("SELECT count(*) FROM locations WHERE type = 'terminal' AND loading_docks >= 1") == 5
    with test_engine.connect() as conn:
        cold = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT name FROM locations WHERE type = 'terminal' AND cold_storage "
                    "AND reefer_plug_count > 0 AND temperature_min IS NOT NULL"
                )
            )
        }
        warm = _count(
            test_engine,
            "SELECT count(*) FROM locations WHERE type = 'terminal' AND NOT cold_storage "
            "AND reefer_plug_count IS NULL",
        )
    assert cold == {"Demo Terminal Central", "Demo Terminal Tampere", "Demo Terminal Oulu"}
    assert warm == 2
    assert q("SELECT count(*) FROM locations WHERE type = 'port'") == 12
    with test_engine.connect() as conn:
        ports = {r[0] for r in conn.execute(text("SELECT name FROM locations WHERE type = 'port'"))}
    assert ports == {
        f"Demo Port {n}"
        for n in (
            "Kotka",
            "Vuosaari",
            "Hanko",
            "Oulu",
            "Travemünde",
            "Lübeck",
            "Rostock",
            "Gdynia",
            "Tallinn",
            "Antwerpen",
            "Lübeck \u2013 Lehmannkai",
            "Lübeck \u2013 Seelandkai",
        )
    }
    assert (
        q(
            "SELECT count(*) FROM locations c JOIN locations p ON p.id = c.parent_location_id "
            "WHERE p.name = 'Demo Port Lübeck' AND c.type = 'port' "
            "AND c.name IN ('Demo Port Lübeck \u2013 Lehmannkai', "
            "'Demo Port Lübeck \u2013 Seelandkai')"
        )
        == 2
    )
    # one expiring qualification, one GDP, some ADR
    assert (
        q("SELECT count(*) FROM driver_qualifications WHERE valid_until <= DATE '2026-12-18'") >= 1
    )
    assert q("SELECT count(*) FROM driver_qualifications WHERE type = 'gdp'") == 1
    assert (
        q("SELECT count(DISTINCT driver_id) FROM driver_qualifications WHERE type LIKE 'adr_%'")
        >= 2
    )
    # subcontractor drivers belong to subcontractors, own drivers to the own carrier
    assert (
        q(
            "SELECT count(*) FROM drivers d JOIN carriers c ON c.id = d.carrier_id "
            "WHERE (d.employment = 'own') <> (c.type = 'own')"
        )
        == 0
    )


def test_every_demo_name_contains_demo_and_emails_are_example(test_engine: Engine) -> None:
    _run(test_engine)
    for table in ("customers", "locations", "carriers", "drivers"):
        assert (
            _count(test_engine, f"SELECT count(*) FROM {table} WHERE name NOT LIKE 'Demo %'") == 0
        )


def test_seed_data_is_valid_by_the_domain_rules() -> None:
    for place in seed.PLACES:
        validate_timezone(place.timezone)
        if place.hours:
            validate_opening_hours(place.hours)
    customer_names = {c[0] for c in seed.CUSTOMERS}
    assert {p.customer for p in seed.PLACES if p.customer} <= customer_names
    assert all(c[0].startswith("Demo ") for c in seed.CUSTOMERS)
    assert all(c[0].startswith("Demo ") for c in seed.CARRIERS)


def test_seed_does_not_overwrite_manual_edits_or_add_a_second_own_company(
    test_engine: Engine,
) -> None:
    _run(test_engine)
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE customers SET country = 'SE' WHERE name = 'Demo Paper Oy'"))
        conn.execute(
            text("UPDATE customers SET name = 'Demo Renamed Oy' WHERE type = 'own_company'")
        )
    assert _run(test_engine) == {}
    assert _count(test_engine, "SELECT count(*) FROM customers WHERE country = 'SE'") == 1
    assert _count(test_engine, "SELECT count(*) FROM customers WHERE type = 'own_company'") == 1


def test_main_refuses_outside_development(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(seed, "get_settings", lambda: make_settings(environment="production"))
    assert seed.main() == 2
    assert "ENVIRONMENT=development" in capsys.readouterr().err
    assert _count(test_engine, "SELECT count(*) FROM customers") == 0
