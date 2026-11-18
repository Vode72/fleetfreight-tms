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
    tables = (
        "customers",
        "locations",
        "carriers",
        "drivers",
        "driver_qualifications",
        "trucks",
        "dollies",
        "load_units",
        "compartments",
        "reefer_units",
        "equipment_qualifications",
    )
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
    for table in ("customers", "locations", "drivers"):
        assert (
            _count(test_engine, f"SELECT count(*) FROM {table} WHERE name NOT LIKE 'Demo %'") == 0
        )
    # carriers: a subcontractor has its own name; the own carrier's name is its customer's (D73)
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM carriers ca LEFT JOIN customers cu ON cu.id = ca.customer_id"
            " WHERE coalesce(ca.name, cu.name) NOT LIKE 'Demo %'",
        )
        == 0
    )
    # fleet: invented registrations and names only
    for table in ("trucks", "dollies", "load_units"):
        assert (
            _count(
                test_engine,
                f"SELECT count(*) FROM {table}"
                f" WHERE registration !~ '^DEMO-[A-Z]{{3}}-[0-9]{{3}}$'",
            )
            == 0
        )
    assert (
        _count(test_engine, "SELECT count(*) FROM reefer_units WHERE unit_name NOT LIKE 'Demo %'")
        == 0
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


# --- 2B-2: carriers' link to the own company (D73) and the fleet


def test_own_carrier_links_to_the_own_company_and_has_no_name_of_its_own(
    test_engine: Engine,
) -> None:
    from domain.parties import CarrierType, CustomerType, validate_carrier_customer_link

    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT ca.type AS carrier_type, ca.name, ca.country, ca.business_id,"
                " cu.type AS customer_type, cu.name AS customer_name FROM carriers ca"
                " LEFT JOIN customers cu ON cu.id = ca.customer_id"
            )
        ).all()
    assert len(rows) == 3
    for row in rows:
        validate_carrier_customer_link(
            CarrierType(row.carrier_type),
            CustomerType(row.customer_type) if row.customer_type else None,
        )
    own = next(r for r in rows if r.carrier_type == "own")
    assert (own.name, own.country, own.business_id) == (None, None, None)
    assert own.customer_name == "Demo Freight Oy"
    assert all(r.name and r.country for r in rows if r.carrier_type != "own")


def test_seed_reuses_an_existing_own_carrier_and_company(test_engine: Engine) -> None:
    """E.g. a database migrated from 2B-1: the own carrier is already linked (revision A)."""
    with test_engine.begin() as conn:
        customer = conn.execute(
            text(
                "INSERT INTO customers (name, type, country) VALUES"
                " ('Demo Existing Oy', 'own_company', 'FI') RETURNING id"
            )
        ).scalar()
        conn.execute(
            text("INSERT INTO carriers (type, customer_id) VALUES ('own', :c)"), {"c": customer}
        )
    created = _run(test_engine)
    assert "carriers" in created  # only the two subcontractors
    assert created["carriers"] == 2
    assert _count(test_engine, "SELECT count(*) FROM customers WHERE type = 'own_company'") == 1
    assert _count(test_engine, "SELECT count(*) FROM carriers WHERE type = 'own'") == 1
    # the fleet hangs on that carrier
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM trucks t JOIN carriers c ON c.id = t.carrier_id"
            " JOIN customers cu ON cu.id = c.customer_id WHERE cu.name = 'Demo Existing Oy'",
        )
        == 7
    )
    assert _run(test_engine) == {}


def _fleet_counts(engine: Engine) -> dict[str, int]:
    return {
        t: _count(engine, f"SELECT count(*) FROM {t}")
        for t in ("trucks", "dollies", "load_units", "compartments", "reefer_units")
    }


def test_fleet_content(test_engine: Engine) -> None:
    _run(test_engine)

    def q(sql: str) -> int:
        return _count(test_engine, sql)

    own = "(SELECT id FROM carriers WHERE type = 'own')"
    # own carrier: 5 drivers, 4-5 tractors, 1-2 rigid trucks with a fixed body, 1 dolly
    assert q(f"SELECT count(*) FROM drivers WHERE carrier_id = {own}") == 5
    assert 4 <= q(f"SELECT count(*) FROM trucks WHERE carrier_id = {own} AND type = 'tractor'") <= 5
    assert q(f"SELECT count(*) FROM trucks WHERE carrier_id = {own} AND type = 'rigid_truck'") == 2
    assert q(f"SELECT count(*) FROM dollies WHERE carrier_id = {own}") == 1
    # subcontractors: one or two tractors each
    for name in ("Demo Trans GmbH", "Demo Kuljetus Oy"):
        n = q(
            "SELECT count(*) FROM trucks t JOIN carriers c ON c.id = t.carrier_id"
            f" WHERE c.name = '{name}' AND t.type = 'tractor'"
        )
        assert 1 <= n <= 2
    # fixed bodies: one per rigid truck, one with a tail lift, one thermo
    assert (
        q(
            "SELECT count(*) FROM load_units l JOIN trucks t ON t.id = l.truck_id"
            " WHERE l.type = 'fixed_body' AND t.type = 'rigid_truck'"
            " AND t.carrier_id = l.carrier_id"
        )
        == 2
    )
    assert q("SELECT count(*) FROM load_units WHERE type = 'fixed_body' AND tail_lift") == 1
    assert (
        q("SELECT count(*) FROM load_units WHERE type = 'fixed_body' AND body_type = 'reefer'") == 1
    )
    # 8-10 trailers with the D36 variety
    assert 8 <= q("SELECT count(*) FROM load_units WHERE type = 'trailer'") <= 10
    for body in ("curtainsider", "mega", "side_opening", "reefer"):
        assert q(f"SELECT count(*) FROM load_units WHERE type = 'trailer' AND body_type = '{body}'")
    for flag in ("xl_certified", "coil_well", "tir_cable", "top_loading"):
        assert q(f"SELECT count(*) FROM load_units WHERE {flag}") >= 1
    assert q("SELECT count(*) FROM load_units WHERE xl_certified AND coil_well") >= 1
    # D63: some, but not all, load units are rail-craneable
    craneable = q("SELECT count(*) FROM load_units WHERE rail_craneable")
    assert 2 <= craneable < q("SELECT count(*) FROM load_units")
    # one leased, one rented, one partner's trailer (carrier of a subcontractor)
    for ownership in ("leased", "rented"):
        assert q(f"SELECT count(*) FROM load_units WHERE ownership = '{ownership}'") == 1
    assert (
        q(
            "SELECT count(*) FROM load_units l JOIN carriers c ON c.id = l.carrier_id"
            " WHERE l.ownership = 'partner' AND c.type = 'subcontractor'"
        )
        == 1
    )


def test_thermo_load_units_have_compartments_and_reefer_units(test_engine: Engine) -> None:
    from domain.equipment import BodyType, validate_compartment_set

    _run(test_engine)
    with test_engine.connect() as conn:
        thermos = {
            r.registration: r.id
            for r in conn.execute(
                text("SELECT id, registration FROM load_units WHERE body_type = 'reefer'")
            )
        }
        assert len(thermos) == 2
        for registration, unit_id in thermos.items():
            numbers = [
                r[0]
                for r in conn.execute(
                    text("SELECT number FROM compartments WHERE load_unit_id = :i"), {"i": unit_id}
                )
            ]
            validate_compartment_set(BodyType.REEFER, numbers)
            assert numbers, registration
            assert (
                conn.execute(
                    text("SELECT count(*) FROM reefer_units WHERE load_unit_id = :i"),
                    {"i": unit_id},
                ).scalar()
                == 1
            )
        # the two-compartment thermo: freezer and chilled
        rows = conn.execute(
            text(
                "SELECT c.number, c.temperature_min, c.temperature_max FROM compartments c"
                " JOIN load_units l ON l.id = c.load_unit_id"
                " WHERE l.type = 'trailer' AND l.body_type = 'reefer' ORDER BY c.number"
            )
        ).all()
        assert [r.number for r in rows] == [1, 2]
        assert rows[0].temperature_max < 0 < rows[1].temperature_min
        # no compartments or reefer units on any other body type
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM compartments c JOIN load_units l ON l.id = c.load_unit_id"
                    " WHERE l.body_type <> 'reefer'"
                )
            ).scalar()
            == 0
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM reefer_units r JOIN load_units l ON l.id = r.load_unit_id"
                    " WHERE l.body_type <> 'reefer'"
                )
            ).scalar()
            == 0
        )
        powers = {r[0] for r in conn.execute(text("SELECT power_source FROM reefer_units"))}
    assert len(powers) == 2


def test_lease_periods_are_valid_on_the_seed_day(test_engine: Engine) -> None:
    from domain.equipment import Ownership, lease_valid_on

    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT ownership, lease_valid_from, lease_valid_until FROM load_units"
                " WHERE ownership IN ('leased', 'rented')"
            )
        ).all()
    assert len(rows) == 2
    for row in rows:
        assert lease_valid_on(
            Ownership(row.ownership), row.lease_valid_from, row.lease_valid_until, TODAY
        )


def test_hct_combinations_can_be_formed_from_the_seed_fleet(test_engine: Engine) -> None:
    """Tractor + semi + dolly + semi, and rigid truck + dolly + semi (D61)."""
    from decimal import Decimal

    from domain.combinations import VehiclePart, combination_totals, validate_combination_structure
    from domain.equipment import TruckType

    _run(test_engine)

    def part(sql: str) -> VehiclePart:
        with test_engine.connect() as conn:
            r = conn.execute(text(sql)).one()
        return VehiclePart(r.length_m, r.kerb_weight_kg, r.axles)

    own = "carrier_id = (SELECT id FROM carriers WHERE type = 'own')"
    tractor = part(
        f"SELECT * FROM trucks WHERE {own} AND type = 'tractor' ORDER BY registration LIMIT 1"
    )
    rigid = part(
        f"SELECT * FROM trucks WHERE {own} AND type = 'rigid_truck' ORDER BY registration LIMIT 1"
    )
    dolly = part(f"SELECT * FROM dollies WHERE {own} ORDER BY registration LIMIT 1")
    with test_engine.connect() as conn:
        trailers = [
            VehiclePart(r.external_length_m, r.kerb_weight_kg, r.axles)
            for r in conn.execute(
                text(
                    "SELECT external_length_m, kerb_weight_kg, axles FROM load_units"
                    f" WHERE type = 'trailer' AND {own} AND body_type <> 'reefer'"
                    " AND ownership = 'own' ORDER BY registration LIMIT 2"
                )
            )
        ]
    assert len(trailers) == 2

    validate_combination_structure(TruckType.TRACTOR, has_dolly=True, trailer_count=2)
    hct = combination_totals(tractor, dolly=dolly, trailers=trailers)
    assert hct.part_count == 4
    assert hct.length_m == sum((p.length_m for p in (tractor, dolly, *trailers)), Decimal(0))

    validate_combination_structure(TruckType.RIGID_TRUCK, has_dolly=True, trailer_count=1)
    assert combination_totals(rigid, dolly=dolly, trailers=trailers[:1]).part_count == 3


def test_equipment_qualification_scenarios(test_engine: Engine) -> None:
    from domain.equipment import EquipmentQualificationType as E
    from domain.qualifications import QualificationPeriod, current, expires_within

    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT l.registration, l.body_type, q.type, q.class_code, q.valid_from,"
                " q.valid_until FROM equipment_qualifications q"
                " JOIN load_units l ON l.id = q.load_unit_id"
            )
        ).all()
    atp = [r for r in rows if r.type == "atp"]
    # ATP for both thermo load units, none for anything else
    assert {r.registration for r in atp} == {
        r.registration for r in rows if r.body_type == "reefer"
    }
    assert all(r.class_code for r in atp)
    # one thermo's ATP is expiring soon (valid today, ends within 30 days)
    expiring = {r.registration for r in atp if expires_within(r.valid_until, TODAY, 30)}
    assert len(expiring) == 1
    # the trailer's ATP has two consecutive periods (history), valid today through the renewal
    trailer_atp = [r for r in atp if r.registration == "DEMO-TRL-007"]
    assert len(trailer_atp) == 2
    periods = [QualificationPeriod(E.ATP, r.valid_from, r.valid_until) for r in trailer_atp]
    assert len(current(periods, TODAY)) == 1
    assert sorted(p.valid_until for p in periods)[0] < TODAY
    first, second = sorted(periods, key=lambda p: p.valid_from)
    assert (second.valid_from - first.valid_until).days == 1
    # a GDP temperature mapping for one thermo, a tail lift inspection for the tail-lift body
    assert [r.registration for r in rows if r.type == "gdp_temperature_mapping"] == ["DEMO-TRL-007"]
    tail = [r for r in rows if r.type == "tail_lift_inspection"]
    assert [r.registration for r in tail] == ["DEMO-BOD-001"]


def test_inspections_cover_trucks_dollies_and_trailers_with_one_expired(
    test_engine: Engine,
) -> None:
    _run(test_engine)

    def q(sql: str) -> int:
        return _count(test_engine, sql)

    inspections = "type = 'inspection'"
    assert q(
        f"SELECT count(DISTINCT truck_id) FROM equipment_qualifications WHERE {inspections}"
    ) == q("SELECT count(*) FROM trucks")
    assert (
        q(f"SELECT count(DISTINCT dolly_id) FROM equipment_qualifications WHERE {inspections}") == 1
    )
    assert q(
        f"SELECT count(DISTINCT load_unit_id) FROM equipment_qualifications WHERE {inspections}"
    ) == q("SELECT count(*) FROM load_units WHERE type = 'trailer'")
    expired = q(
        f"SELECT count(*) FROM equipment_qualifications WHERE {inspections}"
        f" AND valid_until < DATE '{TODAY.isoformat()}'"
    )
    assert expired == 1
    # every other inspection is still valid on the seed day
    valid = q(
        f"SELECT count(*) FROM equipment_qualifications WHERE {inspections}"
        f" AND valid_from <= DATE '{TODAY.isoformat()}'"
        f" AND valid_until >= DATE '{TODAY.isoformat()}'"
    )
    assert valid == q(f"SELECT count(*) FROM equipment_qualifications WHERE {inspections}") - 1


def test_seed_does_not_overwrite_manual_fleet_edits_or_duplicate_rows(test_engine: Engine) -> None:
    _run(test_engine)
    before = _fleet_counts(test_engine)
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE trucks SET axles = 2 WHERE registration = 'DEMO-TRK-001'"))
        conn.execute(
            text("UPDATE load_units SET pallet_places = 1 WHERE registration = 'DEMO-TRL-001'")
        )
        conn.execute(text("UPDATE compartments SET temperature_min = -30"))
    assert _run(test_engine) == {}
    assert _fleet_counts(test_engine) == before
    assert _count(test_engine, "SELECT axles FROM trucks WHERE registration = 'DEMO-TRK-001'") == 2
    assert _count(test_engine, "SELECT count(*) FROM compartments WHERE temperature_min = -30") == 3


def test_seed_fleet_data_is_valid_by_the_domain_rules() -> None:
    from decimal import Decimal

    from domain.equipment import LoadUnitType, validate_vehicle

    assert len({t.registration for t in seed.TRUCKS}) == len(seed.TRUCKS)
    assert len({u.registration for u in seed.LOAD_UNITS}) == len(seed.LOAD_UNITS)
    carrier_names = {c[0] for c in seed.CARRIERS}
    assert {t.carrier for t in seed.TRUCKS} <= carrier_names
    assert {u.carrier for u in seed.LOAD_UNITS} <= carrier_names
    for t in seed.TRUCKS:
        validate_vehicle(
            length_m=Decimal(t.length_m),
            kerb_weight_kg=t.kerb_weight_kg,
            max_gross_weight_kg=t.max_gross_weight_kg,
            axles=t.axles,
        )
    trucks = {t.registration for t in seed.TRUCKS}
    assert all(u.truck in trucks for u in seed.LOAD_UNITS if u.type is LoadUnitType.FIXED_BODY)
    assert all(u.registration.startswith("DEMO-") for u in seed.LOAD_UNITS)
