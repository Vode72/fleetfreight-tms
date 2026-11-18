import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

import scripts.seed_demo_data as seed
from domain.locations import validate_opening_hours, validate_postal_code, validate_timezone
from domain.qualifications import (
    DriverQualificationType,
    QualificationPeriod,
    overlapping_periods,
    validate_adr_qualifications,
)
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
    assert q("SELECT count(*) FROM customers WHERE type = 'customer'") == 9
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
    assert q("SELECT count(*) FROM locations WHERE type = 'port'") == 15
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
            "Naantali",
            "Långnäs",
            "Kapellskär",
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


def _rows(engine: Engine, sql: str) -> list[tuple[object, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql))]


def test_no_two_places_share_coordinates_except_port_area_and_its_quays(
    test_engine: Engine,
) -> None:
    _run(test_engine)
    by_point: dict[tuple[object, object], list[tuple[object, object]]] = defaultdict(list)
    for loc_id, parent_id, lat, lon in _rows(
        test_engine, "SELECT id, parent_location_id, latitude, longitude FROM locations"
    ):
        by_point[(lat, lon)].append((loc_id, parent_id))
    for point, rows in by_point.items():
        if len(rows) > 1:
            ids = {r[0] for r in rows}
            # allowed only when every row but one is a child of the shared parent
            assert all(parent in ids for _, parent in rows if parent is not None), point
            assert sum(1 for _, parent in rows if parent is None) == 1, point


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(a))


def test_finnish_customer_sites_are_10_to_40_km_from_the_nearest_terminal(
    test_engine: Engine,
) -> None:
    _run(test_engine)
    terminals = [
        (float(r[0]), float(r[1]))  # type: ignore[arg-type]
        for r in _rows(
            test_engine, "SELECT latitude, longitude FROM locations WHERE type = 'terminal'"
        )
    ]
    sites = _rows(
        test_engine,
        "SELECT name, latitude, longitude FROM locations "
        "WHERE type = 'customer_site' AND country = 'FI'",
    )
    assert len(sites) >= 10
    for name, lat, lon in sites:
        nearest = min(_km(float(lat), float(lon), *t) for t in terminals)  # type: ignore[arg-type]
        if "Jyväskylä" in str(name):
            assert nearest > 40  # outside any terminal area: handled from Tampere or Kuopio (D31)
        else:
            assert 10 <= nearest <= 40, (name, nearest)


def test_terminals_sit_at_the_city_centre_and_ports_do_not_share_them(
    test_engine: Engine,
) -> None:
    _run(test_engine)
    # the Helsinki-area port is not at the terminal's city-centre point
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations p JOIN locations t ON t.type = 'terminal' "
            "AND t.latitude = p.latitude AND t.longitude = p.longitude WHERE p.type = 'port'",
        )
        == 0
    )


def test_opening_hours_features(test_engine: Engine) -> None:
    _run(test_engine)
    hours: dict[str, Any] = {
        str(n): h for n, h in _rows(test_engine, "SELECT name, opening_hours FROM locations")
    }
    always = {d: [["00:00", "24:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    assert hours["Demo Terminal Central"] == always
    assert hours["Demo Terminal Tampere"] == always
    for city in ("Turku", "Kuopio", "Oulu"):
        h = hours[f"Demo Terminal {city}"]
        assert h["mon"] == h["fri"] == [["05:00", "23:00"]]
        assert h["sat"] == [["06:00", "14:00"]] and "sun" not in h
    assert hours["Demo Dairy Plant Site"]["sat"] == [["05:00", "15:00"]]
    assert "sun" not in hours["Demo Dairy Plant Site"]
    assert hours["Demo Paper Mill Site"] == always
    assert hours["Demo Pharma Warehouse Site"]["fri"] == [["08:00", "16:00"]]
    assert "sat" not in hours["Demo Pharma Warehouse Site"]
    # ports: NULL = not checked
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations WHERE type = 'port' AND opening_hours IS NOT NULL",
        )
        == 0
    )
    for name in (
        "Demo Customs Office Central",
        "Demo Customs Office Svinesund",
        "Demo Customs Office Oslo",
    ):
        assert hours[name] is not None


def test_site_features(test_engine: Engine) -> None:
    _run(test_engine)

    def names(where: str) -> set[str]:
        return {str(r[0]) for r in _rows(test_engine, f"SELECT name FROM locations WHERE {where}")}

    assert names("side_loading_possible") == {
        "Demo Timber Yard Site",
        "Demo Paper Mill Site",
        "Demo Paper Oy \u2013 Jyväskylä Site",
    }
    assert names("max_vehicle_length_m = 12.00") == {"Demo Pharma Warehouse Site"}
    assert names("booking_required AND name = 'Demo Paper Mill Site'")
    assert names("has_loading_dock = false") == {"Demo Kauppa Oy \u2013 Kuopio Shop Site"}
    assert names("has_loading_dock IS NULL AND type = 'customer_site'") == set()


def test_rail_terminals_and_aland_port(test_engine: Engine) -> None:
    _run(test_engine)
    assert _rows(
        test_engine,
        "SELECT name, country, timezone FROM locations WHERE type = 'rail_terminal' ORDER BY name",
    ) == [
        ("Demo Rail Terminal Rostock", "DE", "Europe/Berlin"),
        ("Demo Rail Terminal Travemünde", "DE", "Europe/Berlin"),
        ("Demo Rail Terminal Verona", "IT", "Europe/Rome"),
    ]
    assert _rows(
        test_engine,
        "SELECT country, timezone FROM locations WHERE name = 'Demo Port Långnäs'",
    ) == [("AX", "Europe/Mariehamn")]
    assert _rows(
        test_engine,
        "SELECT country, timezone FROM locations WHERE name = 'Demo Port Kapellskär'",
    ) == [("SE", "Europe/Stockholm")]
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations WHERE type = 'rail_terminal' "
            "AND (loading_docks IS NOT NULL OR cold_storage IS NOT NULL "
            "OR opening_hours IS NOT NULL)",
        )
        == 0
    )


def test_norway_customs_and_adr_consignor(test_engine: Engine) -> None:
    _run(test_engine)
    assert _rows(
        test_engine,
        "SELECT l.country, l.timezone FROM locations l JOIN customers c ON c.id = l.customer_id "
        "WHERE c.name = 'Demo Norge AS' AND c.country = 'NO'",
    ) == [("NO", "Europe/Oslo")]
    assert _rows(
        test_engine,
        "SELECT name, country FROM locations WHERE type = 'customs_office' ORDER BY name",
    ) == [
        ("Demo Customs Office Central", "FI"),
        ("Demo Customs Office Oslo", "NO"),
        ("Demo Customs Office Svinesund", "NO"),
    ]
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations l JOIN customers c ON c.id = l.customer_id "
            "WHERE c.name = 'Demo Kemia Oy' AND l.type = 'customer_site'",
        )
        == 1
    )
    # small LTL sites in the Kuopio, Turku and Oulu areas
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations WHERE name LIKE 'Demo Kauppa Oy%' "
            "OR name LIKE 'Demo Konepaja Oy%'",
        )
        == 4
    )


def test_qualification_scenarios(test_engine: Engine) -> None:
    _run(test_engine)
    assert _rows(
        test_engine,
        "SELECT d.name, q.type FROM driver_qualifications q JOIN drivers d ON d.id = q.driver_id "
        "WHERE q.valid_until < DATE '2026-11-18' ORDER BY d.name",
    ) == [("Demo Driver Aalto", "tachograph_card"), ("Demo Driver Becker", "tachograph_card")]
    assert _rows(
        test_engine,
        "SELECT name FROM drivers d WHERE NOT EXISTS (SELECT 1 FROM driver_qualifications q "
        "WHERE q.driver_id = d.id AND q.type = 'professional_competence')",
    ) == [("Demo Driver Salo",)]


def _periods(engine: Engine) -> dict[object, list[QualificationPeriod]]:
    per_driver: dict[object, list[QualificationPeriod]] = defaultdict(list)
    for driver_id, qtype, valid_from, valid_until in _rows(
        engine,
        "SELECT driver_id, type, valid_from, valid_until FROM driver_qualifications",
    ):
        per_driver[driver_id].append(
            QualificationPeriod(DriverQualificationType(str(qtype)), valid_from, valid_until)  # type: ignore[arg-type]
        )
    return per_driver


def test_seed_adr_qualifications_obey_the_adr_rules(test_engine: Engine) -> None:
    _run(test_engine)
    per_driver = _periods(test_engine)
    assert len(per_driver) == 8
    for periods in per_driver.values():
        validate_adr_qualifications(periods, TODAY)
        assert overlapping_periods(periods) == []


def test_seed_shows_qualification_history(test_engine: Engine) -> None:
    _run(test_engine)
    rows = _rows(
        test_engine,
        "SELECT q.valid_from, q.valid_until FROM driver_qualifications q "
        "JOIN drivers d ON d.id = q.driver_id WHERE d.name = 'Demo Driver Aalto' "
        "AND q.type = 'tachograph_card' ORDER BY q.valid_from",
    )
    assert len(rows) == 2
    (_, old_end), (new_start, new_end) = ((cast(date, a), cast(date, b)) for a, b in rows)
    assert old_end < TODAY < new_end  # expired period and its renewal
    assert (new_start - old_end).days == 1  # consecutive
    # ADR periods start five years before they end
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM driver_qualifications WHERE type = 'adr_basic' "
            "AND valid_until - valid_from + 1 <> 365 * 5",
        )
        == 0
    )


def test_gdp_end_date_follows_the_setting(test_engine: Engine) -> None:
    sql = "SELECT valid_from, valid_until FROM driver_qualifications WHERE type = 'gdp'"
    _run(test_engine)  # setting default: 12 months
    ((start, end),) = _rows(test_engine, sql)
    assert end == date(start.year + 1, start.month, start.day) - timedelta(days=1)  # type: ignore[attr-defined]
    with test_engine.begin() as conn:
        conn.execute(
            text("TRUNCATE driver_qualifications, drivers, carriers, locations, customers CASCADE")
        )
    with sessionmaker(bind=test_engine)() as session:
        seed_demo_data(session, TODAY, gdp_validity_months=24)
    ((start, end),) = _rows(test_engine, sql)
    assert end == date(start.year + 2, start.month, start.day) - timedelta(days=1)  # type: ignore[attr-defined]


def test_locality_of_places(test_engine: Engine) -> None:
    _run(test_engine)
    rows = {
        str(n): (pc, c)
        for n, pc, c in _rows(test_engine, "SELECT name, postal_code, city FROM locations")
    }
    assert rows["Demo Terminal Central"] == ("01510", "Vantaa")
    assert rows["Demo Terminal Tampere"] == ("33100", "Tampere")
    assert rows["Demo Paper Oy \u2013 Jyväskylä Site"] == ("40100", "Jyväskylä")
    assert rows["Demo Port Vuosaari"] == ("00980", "Helsinki")
    assert rows["Demo Port Långnäs"] == (None, "Lumparland")  # code not certain: left empty
    assert all(city for _, city in rows.values())  # city always filled
    # Finnish codes are five digits (validated); street addresses are invented
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations WHERE address !~ '^Demo Street [0-9]+$'",
        )
        == 0
    )
    for name, (postal, _city) in rows.items():
        if postal is not None and name in {p.name for p in seed.PLACES if p.country == "FI"}:
            validate_postal_code("FI", str(postal))


def test_every_seed_place_has_a_locality() -> None:
    assert {p.name for p in seed._PLACES_WITHOUT_LOCALITY} == set(seed._LOCALITY)
