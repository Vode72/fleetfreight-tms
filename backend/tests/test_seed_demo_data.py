import math
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

import scripts.seed_demo_data as seed
from domain.combinations import (
    DollyPart,
    TrailerPart,
    TruckPart,
    combination_totals,
    validate_combination_structure,
)
from domain.equipment import CouplingType, EquipmentQualificationType, TruckType
from domain.lines import vessel_overlaps
from domain.locations import validate_opening_hours, validate_postal_code, validate_timezone
from domain.qualifications import (
    DriverQualificationType,
    QualificationPeriod,
    overlapping_periods,
    validate_adr_qualifications,
)
from scripts.seed_demo_data import seed_demo_data
from tests.conftest import REGISTER_TABLES, make_settings

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
        "reefer_units",
        "reefer_evaporators",
        "compartments",
        "equipment_qualifications",
        "parking_details",
        "parking_certifications",
        "border_crossing_details",
        "border_crossing_status_periods",
        "trailer_storage_rules",
        "wash_details",
        "line_operators",
        "vessels",
        "vessel_adr_classes",
        "line_routes",
        "line_route_stops",
        "line_schedules",
        "line_schedule_calls",
        "line_departures",
        "line_departure_calls",
        "cargo_crime_reports",
        "cargo_crime_counts",
        "risk_areas",
        "border_wait_observations",
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
        ("Demo Customs Office Svinesund SE", "SE"),
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
        conn.execute(text(f"TRUNCATE {REGISTER_TABLES} CASCADE"))
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
        == 8
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
    assert q(f"SELECT count(*) FROM trucks WHERE carrier_id = {own} AND type = 'rigid_truck'") == 3
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
        == 3
    )
    assert q("SELECT count(*) FROM load_units WHERE type = 'fixed_body' AND tail_lift") == 1
    assert (
        q("SELECT count(*) FROM load_units WHERE type = 'fixed_body' AND body_type = 'reefer'") == 1
    )
    # 8-13 trailers with the D36 variety
    assert 8 <= q("SELECT count(*) FROM load_units WHERE type = 'trailer'") <= 13
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
    from domain.equipment import (
        BodyType,
        EvaporatorPosition,
        ModelCode,
        validate_compartment_set,
        validate_evaporators,
        validate_reefer_units,
        validate_zones,
    )

    _run(test_engine)
    with test_engine.connect() as conn:
        thermos = {
            r.registration: (r.id, r.model_code)
            for r in conn.execute(
                text(
                    "SELECT id, registration, model_code FROM load_units WHERE body_type = 'reefer'"
                )
            )
        }
        # 4 thermo load units: 3 trailers (FD, FD, FS) and one fixed body (FB)
        assert {k: v[1] for k, v in thermos.items()} == {
            "DEMO-TRL-007": "FD",
            "DEMO-TRL-012": "FD",
            "DEMO-TRL-013": "FS",
            "DEMO-BOD-002": "FB",
        }
        for registration, (unit_id, code) in thermos.items():
            comps = conn.execute(
                text(
                    "SELECT number, independently_controlled FROM compartments"
                    " WHERE load_unit_id = :i ORDER BY number"
                ),
                {"i": unit_id},
            ).all()
            validate_compartment_set(BodyType.REEFER, [c.number for c in comps])
            validate_zones(len(comps), [c.independently_controlled for c in comps], ModelCode(code))
            assert comps, registration
            machines = conn.execute(
                text("SELECT count(*) FROM reefer_units WHERE load_unit_id = :i"), {"i": unit_id}
            ).scalar()
            validate_reefer_units(BodyType.REEFER, machines or 0, ModelCode(code))
            positions = [
                EvaporatorPosition(r[0])
                for r in conn.execute(
                    text("SELECT position FROM reefer_evaporators WHERE load_unit_id = :i"),
                    {"i": unit_id},
                )
            ]
            validate_evaporators(positions, ModelCode(code))
        # one machine each; evaporators: FD front and rear, FB and FS one
        counts = {
            r.registration: (r.machines, r.evaporators)
            for r in conn.execute(
                text(
                    "SELECT l.registration, count(DISTINCT r.id) AS machines,"
                    " count(e.id) AS evaporators FROM reefer_units r"
                    " JOIN load_units l ON l.id = r.load_unit_id"
                    " JOIN reefer_evaporators e ON e.reefer_unit_id = r.id GROUP BY l.registration"
                )
            )
        }
        assert counts == {
            "DEMO-TRL-007": (1, 2),
            "DEMO-TRL-012": (1, 2),
            "DEMO-TRL-013": (1, 1),
            "DEMO-BOD-002": (1, 1),
        }
        # the two-zone FD: freezer and chilled, both independently controlled, one evaporator each
        rows = conn.execute(
            text(
                "SELECT c.number, c.temperature_min, c.temperature_max, c.independently_controlled,"
                " e.position FROM compartments c JOIN load_units l ON l.id = c.load_unit_id"
                " JOIN reefer_evaporators e ON e.id = c.evaporator_id"
                " WHERE l.registration = 'DEMO-TRL-007' ORDER BY c.number"
            )
        ).all()
        assert [(r.number, r.independently_controlled, r.position) for r in rows] == [
            (1, True, "front"),
            (2, True, "rear"),
        ]
        assert rows[0].temperature_max < 0 < rows[1].temperature_min
        # the other FD: two zones too (D76), one evaporator each
        other = conn.execute(
            text(
                "SELECT c.number, c.pallet_places, e.position FROM compartments c"
                " JOIN load_units l ON l.id = c.load_unit_id"
                " JOIN reefer_evaporators e ON e.id = c.evaporator_id"
                " WHERE l.registration = 'DEMO-TRL-012' ORDER BY c.number"
            )
        ).all()
        assert [(o.number, o.pallet_places, o.position) for o in other] == [
            (1, None, "front"),
            (2, None, "rear"),
        ]
        # no compartments or reefer units on any other body type
        for table in ("compartments", "reefer_units", "reefer_evaporators"):
            assert (
                conn.execute(
                    text(
                        f"SELECT count(*) FROM {table} t JOIN load_units l ON l.id = t.load_unit_id"
                        " WHERE l.body_type <> 'reefer'"
                    )
                ).scalar()
                == 0
            )
        powers = {r[0] for r in conn.execute(text("SELECT power_source FROM reefer_units"))}
    assert powers == {"diesel", "hybrid", "electric"}


def test_model_codes_of_the_demo_fleet(test_engine: Engine) -> None:
    from domain.equipment import BodyType, ModelCode, validate_model_code

    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT registration, body_type, model_code, side_doors, coil_well FROM load_units"
            )
        ).all()
    codes = {r.registration: r.model_code for r in rows}
    assert codes["DEMO-TRL-001"] == "CS"
    assert codes["DEMO-TRL-002"] == "MEGA"
    assert codes["DEMO-TRL-004"] == "COIL"
    assert codes["DEMO-TRL-003"] is None  # side-opening has no code
    assert codes["DEMO-BOD-001"] is None  # a box body has no code
    assert {c for c in codes.values() if c} == {"FB", "FD", "FS", "CS", "MEGA", "COIL"}
    for r in rows:
        validate_model_code(
            ModelCode(r.model_code) if r.model_code else None, BodyType(r.body_type), r.side_doors
        )
    # features stay separate columns: a COIL trailer has the coil well, the plain CS ones do not
    assert next(r for r in rows if r.registration == "DEMO-TRL-004").coil_well
    assert not next(r for r in rows if r.registration == "DEMO-TRL-001").coil_well
    # the Thermo Side trailer has side doors; the other thermos do not
    assert {r.registration for r in rows if r.side_doors} == {"DEMO-TRL-013"}


@pytest.mark.parametrize("registration", ["DEMO-TRL-007", "DEMO-TRL-012"])
def test_fd_partition_moves_one_eur_row_at_a_time(test_engine: Engine, registration: str) -> None:
    """D76: the FD has no fixed compartment places; the partition position is chosen for the
    load, from 4 + 28 to 28 + 4 EUR pallets in steps of one row."""
    from domain.equipment import PartitionSpec, partition_positions

    _run(test_engine)
    with test_engine.connect() as conn:
        unit = conn.execute(
            text("SELECT * FROM load_units WHERE registration = :r"), {"r": registration}
        ).one()
        places = [
            r[0]
            for r in conn.execute(
                text("SELECT pallet_places FROM compartments WHERE load_unit_id = :i"),
                {"i": unit.id},
            )
        ]
        with_partition = conn.execute(
            text("SELECT registration FROM load_units WHERE partition ORDER BY registration")
        ).all()
    # only FD has a partition, and every FD has one (D76)
    assert [r.registration for r in with_partition] == ["DEMO-TRL-007", "DEMO-TRL-012"]
    assert places == [None, None]
    spec = PartitionSpec(
        unit.internal_length_m,
        partition=unit.partition,
        thickness_mm=unit.partition_thickness_mm,
        step_pallet_rows=unit.partition_step_pallet_rows,
        min_pallets_front=unit.min_pallets_front,
        min_pallets_rear=unit.min_pallets_rear,
    )
    positions = partition_positions(spec, unit.pallet_places)
    assert [(p.front_pallets, p.rear_pallets) for p in positions] == [
        (front, 32 - front) for front in range(4, 29, 2)
    ]


def test_reefer_service_periods(test_engine: Engine) -> None:
    from domain.qualifications import expires_within

    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT l.registration, q.valid_until FROM equipment_qualifications q"
                " JOIN reefer_units r ON r.id = q.reefer_unit_id"
                " JOIN load_units l ON l.id = r.load_unit_id WHERE q.type = 'reefer_service'"
            )
        ).all()
        machines = conn.execute(text("SELECT count(*) FROM reefer_units")).scalar()
    assert len(rows) == machines == 4  # one service period for every machine
    assert all(r.valid_until >= TODAY for r in rows)
    assert [r.registration for r in rows if expires_within(r.valid_until, TODAY, 30)] == [
        "DEMO-TRL-007"
    ]


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


def _truck_part(engine: Engine, registration: str) -> tuple[TruckPart, TruckType, bool]:
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT * FROM trucks WHERE registration = :r"), {"r": registration}
        ).one()
    part = TruckPart(r.length_m, r.kerb_weight_kg, r.axles, r.fifth_wheel_from_front_m)
    return part, TruckType(r.type), r.drawbar_hitch


def _trailer_part(engine: Engine, registration: str) -> TrailerPart:
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT * FROM load_units WHERE registration = :r"), {"r": registration}
        ).one()
    return TrailerPart(
        r.external_length_m,
        r.kerb_weight_kg,
        r.axles,
        CouplingType(r.coupling_type),
        r.kingpin_from_front_m,
    )


def test_combinations_can_be_formed_from_the_seed_fleet(test_engine: Engine) -> None:
    """Tractor + semi + dolly + semi (HCT), rigid + dolly + semi (HCT) and rigid + full trailer."""
    _run(test_engine)
    with test_engine.connect() as conn:
        d = conn.execute(text("SELECT * FROM dollies WHERE registration = 'DEMO-DOL-001'")).one()
    dolly = DollyPart(d.length_m, d.kerb_weight_kg, d.axles)
    gap = Decimal("0.50")
    semi_1, semi_2 = (_trailer_part(test_engine, f"DEMO-TRL-00{n}") for n in (1, 5))
    semi_length = semi_1.length_m - semi_1.kingpin_from_front_m  # type: ignore[operator]

    tractor, tractor_type, hitch = _truck_part(test_engine, "DEMO-TRK-001")
    validate_combination_structure(tractor_type, semi_trailers=2, dollies=1, drawbar_hitch=hitch)
    assert tractor.fifth_wheel_from_front_m is not None
    hct = combination_totals(tractor, chain=[semi_1, dolly, semi_2], drawbar_gap_m=gap)
    assert hct.part_count == 4
    # tractor front to fifth wheel, two semi-trailers from kingpin to rear, dolly and one gap
    assert hct.length_m == tractor.fifth_wheel_from_front_m + 2 * semi_length + dolly.length_m + gap
    assert hct.length_m < sum(  # shorter than the parts laid end to end
        (p.length_m for p in (tractor, semi_1, dolly, semi_2)), Decimal(0)
    )

    # combination truck: hitch, full trailer (D55) or dolly + semi-trailer
    truck, truck_type, hitch = _truck_part(test_engine, "DEMO-TRK-011")
    assert truck_type is TruckType.RIGID_TRUCK and hitch
    full = _trailer_part(test_engine, "DEMO-TRL-011")
    assert full.coupling is CouplingType.FULL_TRAILER
    validate_combination_structure(truck_type, full_trailers=1, drawbar_hitch=hitch)
    assert combination_totals(truck, chain=[full], drawbar_gap_m=gap).length_m == (
        truck.length_m + gap + full.length_m
    )
    validate_combination_structure(truck_type, semi_trailers=1, dollies=1, drawbar_hitch=hitch)
    rigid_hct = combination_totals(truck, chain=[dolly, semi_1], drawbar_gap_m=gap)
    assert rigid_hct.length_m == truck.length_m + gap + dolly.length_m + semi_length

    # a rigid truck without a hitch cannot pull
    _, plain_type, plain_hitch = _truck_part(test_engine, "DEMO-TRK-006")
    assert not plain_hitch and plain_type is TruckType.RIGID_TRUCK
    with pytest.raises(ValueError, match="hitch"):
        validate_combination_structure(plain_type, full_trailers=1, drawbar_hitch=plain_hitch)


def test_tractor_features_in_the_seed(test_engine: Engine) -> None:
    _run(test_engine)
    own = "carrier_id = (SELECT id FROM carriers WHERE type = 'own')"

    def q(sql: str) -> int:
        return _count(test_engine, sql)

    # every tractor has its fifth wheel position; one low fifth wheel for the mega trailers
    assert (
        q("SELECT count(*) FROM trucks WHERE type = 'tractor' AND fifth_wheel_from_front_m IS NULL")
        == 0
    )
    assert q("SELECT count(*) FROM trucks WHERE low_fifth_wheel") >= 1
    assert q("SELECT count(*) FROM trucks WHERE low_fifth_wheel AND type = 'tractor'") == q(
        "SELECT count(*) FROM trucks WHERE low_fifth_wheel"
    )
    assert (
        q(f"SELECT count(*) FROM trucks WHERE {own} AND max_combination_weight_kg IS NOT NULL") >= 4
    )
    # own trucks have a base location (a terminal); subcontractor trucks have none recorded
    assert q(
        f"SELECT count(*) FROM trucks t JOIN locations l ON l.id = t.home_location_id"
        f" WHERE t.{own} AND l.type = 'terminal'"
    ) == q(f"SELECT count(*) FROM trucks WHERE {own}")
    assert q(f"SELECT count(*) FROM trucks WHERE NOT ({own}) AND home_location_id IS NOT NULL") == 0
    # exactly one combination truck: rigid, longest rigid, with a drawbar hitch
    assert q("SELECT count(*) FROM trucks WHERE drawbar_hitch") == 1
    assert (
        q(
            "SELECT count(*) FROM trucks WHERE drawbar_hitch AND type = 'rigid_truck'"
            " AND length_m ="
            " (SELECT max(length_m) FROM trucks WHERE type = 'rigid_truck')"
        )
        == 1
    )


def test_mega_trailers_can_be_pulled_by_a_low_fifth_wheel_tractor(test_engine: Engine) -> None:
    _run(test_engine)
    assert _count(test_engine, "SELECT count(*) FROM load_units WHERE body_type = 'mega'") >= 1
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM trucks t JOIN carriers c ON c.id = t.carrier_id"
            " WHERE t.low_fifth_wheel AND c.type = 'own'",
        )
        >= 1
    )


def test_coupling_dimensions_and_trailer_lengths(test_engine: Engine) -> None:
    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM load_units")).all()
    for r in rows:
        if r.type == "fixed_body":
            assert r.coupling_type is None and r.kingpin_from_front_m is None
            assert not r.rail_craneable
        else:
            assert r.coupling_type is not None
        if r.coupling_type == "semi_trailer":
            assert 0 < r.kingpin_from_front_m < r.external_length_m
            assert not r.tail_lift  # D25
        assert r.external_height_m and r.external_width_m  # demo values for every load unit
    couplings = {r.coupling_type for r in rows if r.type == "trailer"}
    assert couplings == {"semi_trailer", "full_trailer"}
    # side-loading semi-trailers: internal 13.60 m and 13.6 LDM, external a little longer
    for r in rows:
        if (
            r.body_type in ("curtainsider", "mega", "side_opening")
            and r.coupling_type == "semi_trailer"
        ):
            assert (r.internal_length_m, r.ldm) == (Decimal("13.60"), Decimal("13.60"))
            assert Decimal("13.60") < r.external_length_m < Decimal("14.00")


def test_fd_has_one_hybrid_machine_and_two_evaporators(test_engine: Engine) -> None:
    """D76: one machine at the front and two evaporators (front and rear of the partition);
    D27: TRL-007's machine is a hybrid that can run on electricity in a port."""
    _run(test_engine)
    with test_engine.connect() as conn:
        machines = conn.execute(
            text(
                "SELECT r.power_source FROM reefer_units r"
                " JOIN load_units l ON l.id = r.load_unit_id WHERE l.registration = 'DEMO-TRL-007'"
            )
        ).all()
        evaporators = conn.execute(
            text(
                "SELECT e.position FROM reefer_evaporators e"
                " JOIN load_units l ON l.id = e.load_unit_id WHERE l.registration = 'DEMO-TRL-007'"
                " ORDER BY e.position"
            )
        ).all()
        comps = conn.execute(
            text(
                "SELECT c.number, c.pallet_places FROM compartments c"
                " JOIN load_units l ON l.id = c.load_unit_id WHERE l.registration = 'DEMO-TRL-007'"
                " ORDER BY c.number"
            )
        ).all()
        total = conn.execute(
            text("SELECT pallet_places FROM load_units WHERE registration = 'DEMO-TRL-007'")
        ).scalar()
    assert [m.power_source for m in machines] == ["hybrid"]
    assert [e.position for e in evaporators] == ["front", "rear"]
    # no fixed places: the partition position is chosen for the load (D76)
    assert [tuple(c) for c in comps] == [(1, None), (2, None)]
    assert total == 32


def test_combination_truck_and_full_trailer_scenario(test_engine: Engine) -> None:
    _run(test_engine)
    with test_engine.connect() as conn:
        body = conn.execute(
            text(
                "SELECT l.body_type, l.tail_lift FROM load_units l"
                " JOIN trucks t ON t.id = l.truck_id"
                " WHERE t.registration = 'DEMO-TRK-011'"
            )
        ).one()
        full = conn.execute(
            text("SELECT * FROM load_units WHERE coupling_type = 'full_trailer'")
        ).all()
    assert body.body_type == "curtainsider"
    assert len(full) == 1 and full[0].kingpin_from_front_m is None


def test_expired_inspection_is_on_a_basic_trailer(test_engine: Engine) -> None:
    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT l.registration, l.top_loading, l.xl_certified, l.body_type FROM"
                " equipment_qualifications q JOIN load_units l ON l.id = q.load_unit_id"
                " WHERE q.type = 'inspection' AND q.valid_until < DATE '2026-11-18'"
            )
        ).all()
    assert [r.registration for r in rows] == ["DEMO-TRL-001"]
    assert not rows[0].top_loading and not rows[0].xl_certified  # a basic curtainsider
    # the only top-loading trailer (006) has a valid inspection
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM equipment_qualifications q"
            " JOIN load_units l ON l.id = q.load_unit_id"
            " WHERE l.top_loading AND q.type = 'inspection' AND q.valid_until >= DATE '2026-11-18'",
        )
        == 1
    )


def test_seed_qualifications_follow_the_subject_rules(test_engine: Engine) -> None:
    from domain.equipment import (
        BodyType,
        EquipmentQualificationType,
        EquipmentSubject,
        validate_equipment_qualification,
    )

    _run(test_engine)
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT q.type, l.body_type, l.tail_lift FROM equipment_qualifications q"
                " JOIN load_units l ON l.id = q.load_unit_id"
            )
        ).all()
    assert rows
    for r in rows:
        validate_equipment_qualification(
            EquipmentSubject("load_unit", BodyType(r.body_type), r.tail_lift),
            EquipmentQualificationType(r.type),
        )


def test_seed_refuses_a_qualification_that_breaks_the_rules(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seed calls validate_equipment_qualification: an ATP on a curtainsider is not seeded."""
    bad = ("load_unit", "DEMO-TRL-001", EquipmentQualificationType.ATP, "FRC", -10, 100)
    monkeypatch.setattr(seed, "EQUIPMENT_QUALIFICATIONS", (*seed.EQUIPMENT_QUALIFICATIONS, bad))
    with pytest.raises(ValueError, match="reefer"):
        _run(test_engine)


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
    assert (
        _count(test_engine, "SELECT count(*) FROM compartments WHERE temperature_min = -30")
        == before["compartments"]
    )


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


def test_parking_areas_and_certificates(test_engine: Engine) -> None:
    _run(test_engine)
    assert _count(test_engine, "SELECT count(*) FROM locations WHERE type = 'parking'") == 4
    # every parking location has its details; prices abroad in the local currency
    assert _rows(
        test_engine,
        "SELECT l.name, d.price_currency FROM locations l"
        " JOIN parking_details d ON d.location_id = l.id ORDER BY l.name",
    ) == [
        ("Demo Truck Parking Gdańsk", "PLN"),
        ("Demo Truck Parking Jönköping", "SEK"),
        ("Demo Truck Parking Lübeck", "EUR"),
        ("Demo Truck Parking Rostock", None),
    ]
    # a required booking is always possible
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations l JOIN parking_details d ON d.location_id = l.id"
            " WHERE l.booking_required AND NOT d.booking_possible",
        )
        == 0
    )
    # Lübeck holds both schemes on the seed day; Gdańsk shows an expired period and its renewal
    valid_now = _rows(
        test_engine,
        "SELECT l.name, c.scheme FROM parking_certifications c"
        " JOIN locations l ON l.id = c.location_id"
        f" WHERE c.valid_from <= DATE '{TODAY}' AND (c.valid_until IS NULL"
        f" OR c.valid_until >= DATE '{TODAY}') ORDER BY 1, 2",
    )
    assert valid_now == [
        ("Demo Truck Parking Gdańsk", "tapa_psr"),
        ("Demo Truck Parking Jönköping", "eu_sspa"),
        ("Demo Truck Parking Lübeck", "eu_sspa"),
        ("Demo Truck Parking Lübeck", "tapa_psr"),
    ]
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM parking_certifications c JOIN locations l"
            " ON l.id = c.location_id WHERE l.name = 'Demo Truck Parking Gdańsk'"
            f" AND c.valid_until < DATE '{TODAY}'",
        )
        == 1
    )


def test_border_crossings_and_status_history(test_engine: Engine) -> None:
    _run(test_engine)
    assert _rows(
        test_engine,
        "SELECT l.name, l.country, d.other_country, d.typical_wait_minutes FROM locations l"
        " JOIN border_crossing_details d ON d.location_id = l.id ORDER BY l.name",
    ) == [
        ("Demo Border Crossing Svinesund", "SE", "NO", None),
        ("Demo Border Crossing Tornio\u2013Haaparanta", "FI", "SE", None),
        ("Demo Border Crossing Vaalimaa", "FI", "RU", None),
    ]
    # Svinesund: the customs office of each side lies in that side's country (D48)
    assert _rows(
        test_engine,
        "SELECT o.country, x.country FROM border_crossing_details d"
        " JOIN locations o ON o.id = d.customs_office_id"
        " JOIN locations x ON x.id = d.other_customs_office_id",
    ) == [("SE", "NO")]

    def status(moment: str) -> object:
        rows = _rows(
            test_engine,
            "SELECT p.status FROM border_crossing_status_periods p"
            " JOIN locations l ON l.id = p.location_id"
            " WHERE l.name = 'Demo Border Crossing Vaalimaa'"
            f" AND tstzrange(p.starts_at, p.ends_at, '[)') @> TIMESTAMPTZ '{moment}'",
        )
        return rows[0][0] if rows else None

    assert status("2023-11-17 12:00+02") is None  # before the recorded history
    assert status("2023-11-18 00:00+02") == "closed"
    assert status("2023-12-15 19:59+02") == "open"  # reopened for one day
    assert status("2023-12-15 20:00+02") == "closed"  # closed again from 20.00
    assert status("2026-11-22 12:00+02") == "closed"  # until further notice
    # official sources only
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM border_crossing_status_periods"
            " WHERE source_url !~ '^https://(tulli\\.fi|toll\\.no)/'",
        )
        == 0
    )


def test_seed_parking_and_border_data_is_valid_by_the_domain_rules() -> None:
    names = {p.name for p in seed.PLACES}
    assert set(seed.PARKING) <= names
    assert set(seed.BORDER_CROSSINGS) <= names
    assert {c[0] for c in seed.PARKING_CERTIFICATIONS} <= set(seed.PARKING)
    assert {s[0] for s in seed.BORDER_STATUS} <= set(seed.BORDER_CROSSINGS)


def test_site_features_storage_rules_and_washes(test_engine: Engine) -> None:
    _run(test_engine)
    # the shop without a dock needs a tail lift and has no forklift
    assert _rows(
        test_engine,
        "SELECT forklift_available, tail_lift_required, has_loading_dock FROM locations"
        " WHERE name = 'Demo Kauppa Oy \u2013 Kuopio Shop Site'",
    ) == [(False, True, False)]
    # every port area and rail terminal of the ferry and rail network has storage terms
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM locations l WHERE l.type IN ('port', 'rail_terminal')"
            " AND l.parent_location_id IS NULL AND NOT EXISTS (SELECT 1 FROM"
            " trailer_storage_rules r WHERE r.location_id = l.id)",
        )
        == 0
    )
    # a quay with its own terms and one using the port area's (D93)
    assert _rows(
        test_engine,
        "SELECT l.name, count(r.id) FROM locations l LEFT JOIN trailer_storage_rules r"
        " ON r.location_id = l.id WHERE l.parent_location_id IS NOT NULL"
        " GROUP BY l.name ORDER BY l.name",
    ) == [("Demo Port Lübeck \u2013 Lehmannkai", 1), ("Demo Port Lübeck \u2013 Seelandkai", 0)]
    assert _rows(
        test_engine,
        "SELECT DISTINCT currency FROM trailer_storage_rules ORDER BY 1",
    ) == [("EUR",), ("PLN",), ("SEK",)]
    # invented fees at real port names are marked as demo values
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM trailer_storage_rules"
            " WHERE note NOT LIKE 'Demo value, not a tariff.%'",
        )
        == 0
    )
    # washes: a food-grade wash and a tank cleaning that issues the ECD
    assert _rows(
        test_engine,
        "SELECT l.name, w.grades, w.issues_ecd FROM wash_details w"
        " JOIN locations l ON l.id = w.location_id ORDER BY l.name",
    ) == [
        ("Demo Tank Cleaning Kotka", ["chemical", "tank"], True),
        ("Demo Truck Wash Tampere", ["food_grade", "general"], False),
    ]
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM parking_details WHERE trailer_drop_allowed",
        )
        == 2
    )


def test_lines_routes_and_departures(test_engine: Engine) -> None:
    _run(test_engine)
    # D62: every connection both ways; D63: two rail connections both ways
    assert _count(test_engine, "SELECT count(*) FROM line_routes WHERE mode = 'ferry'") == 18
    assert _count(test_engine, "SELECT count(*) FROM line_routes WHERE mode = 'rail'") == 4
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM line_routes r WHERE NOT EXISTS (SELECT 1 FROM line_routes b"
            " JOIN line_route_stops bs ON bs.route_id = b.id AND bs.sequence = 1"
            " JOIN line_route_stops rl ON rl.route_id = r.id AND rl.sequence ="
            " (SELECT max(sequence) FROM line_route_stops WHERE route_id = r.id)"
            " WHERE bs.location_id = rl.location_id AND b.operator_id = r.operator_id)",
        )
        == 0
    )  # every route has a return route of the same operator from its last stop
    # weekly frequencies from D62
    freq: dict[object, object] = {
        row[0]: row[1]
        for row in _rows(
            test_engine,
            "SELECT r.name, count(*) FROM line_schedules s JOIN line_routes r"
            " ON r.id = s.route_id GROUP BY r.name",
        )
    }
    assert freq["Demo Vuosaari\u2013Travemünde"] == 7
    assert freq["Demo Vuosaari\u2013Tallinn"] == 14
    assert freq["Demo Hanko\u2013Gdynia"] == 6
    assert freq["Demo Hanko\u2013Rostock"] == 4
    assert freq["Demo Kotka\u2013Antwerpen"] == 1
    assert freq["Demo Oulu\u2013Travemünde\u2013Antwerpen"] == 1
    assert freq["Demo Naantali\u2013Långnäs\u2013Kapellskär"] == 14
    # departures for eight weeks from the seed day, each with a call per stop
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM line_departures WHERE service_date < DATE '2026-11-18'"
            " OR service_date > DATE '2026-11-18' + 55",
        )
        == 0
    )
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM line_departures d WHERE (SELECT count(*) FROM"
            " line_departure_calls c WHERE c.departure_id = d.id) <> (SELECT count(*) FROM"
            " line_route_stops s WHERE s.route_id = d.route_id)",
        )
        == 0
    )
    # Naantali 10:00 local -> Kapellskär 17:45 Swedish time: 8 h 45 min
    assert _rows(
        test_engine,
        "SELECT DISTINCT a.arrives_at - d.departs_at FROM line_departure_calls d"
        " JOIN line_departure_calls a ON a.departure_id = d.departure_id AND a.sequence = 3"
        " JOIN line_departures x ON x.id = d.departure_id JOIN line_routes r"
        " ON r.id = x.route_id WHERE d.sequence = 1"
        " AND r.name = 'Demo Naantali\u2013Långnäs\u2013Kapellskär'"
        " AND extract(hour FROM d.departs_at AT TIME ZONE 'Europe/Helsinki') = 10",
    ) == [(timedelta(hours=8, minutes=45),)]
    # cut-off only where units are loaded, and before the departure
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM line_departure_calls c JOIN line_route_stops s"
            " ON s.route_id = c.route_id AND s.sequence = c.sequence"
            " WHERE (c.cutoff_at IS NOT NULL) <> s.loading",
        )
        == 0
    )
    # no vessel on rail; a vessel never sails two departures at once
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM line_departures WHERE route_mode = 'rail'"
            " AND vessel_id IS NOT NULL",
        )
        == 0
    )
    voyages = _rows(
        test_engine,
        "SELECT d.vessel_id, d.id, min(c.departs_at), max(c.arrives_at) FROM line_departures d"
        " JOIN line_departure_calls c ON c.departure_id = d.id WHERE d.vessel_id IS NOT NULL"
        " GROUP BY d.vessel_id, d.id",
    )
    by_vessel: dict[object, list[tuple[str, Any, Any]]] = defaultdict(list)
    for vessel_id, dep_id, start, end in voyages:
        by_vessel[vessel_id].append((str(dep_id), start, end))
    assert len(by_vessel) >= 6
    for vessel_voyages in by_vessel.values():
        assert vessel_overlaps(vessel_voyages) == []
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM line_schedules WHERE note NOT LIKE 'Demo timetable%'",
        )
        == 0
    )


def test_seed_keeps_a_changed_departure(test_engine: Engine) -> None:
    _run(test_engine)
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE line_departures SET status = 'cancelled', note = 'Demo storm'"
                " WHERE id = (SELECT id FROM line_departures ORDER BY service_date LIMIT 1)"
            )
        )
    _run(test_engine)
    assert (
        _count(test_engine, "SELECT count(*) FROM line_departures WHERE status = 'cancelled'") == 1
    )
    # a later seed day adds the new week and keeps the old departures
    before = _count(test_engine, "SELECT count(*) FROM line_departures")
    created = _run(test_engine, TODAY + timedelta(days=7))
    assert created["line_departures"] > 0
    assert _count(test_engine, "SELECT count(*) FROM line_departures") == (
        before + created["line_departures"]
    )


def test_all_line_and_vessel_names_are_demo() -> None:
    assert all(name.startswith("Demo ") for name, _ in seed.LINE_OPERATORS)
    assert all(name.startswith("Demo ") for name in seed.VESSELS)
    assert all(name.startswith("Demo ") for name in seed.LINE_ROUTES)


def test_risk_data(test_engine: Engine) -> None:
    _run(test_engine)
    # a country an article does not name gets no row (unknown, not 0)
    assert (
        _count(test_engine, "SELECT count(*) FROM cargo_crime_counts WHERE incident_count = 0") == 0
    )
    assert _rows(
        test_engine,
        "SELECT c.incident_count FROM cargo_crime_counts c JOIN cargo_crime_reports r"
        " ON r.id = c.report_id WHERE c.country = 'DE' ORDER BY r.report_month",
    ) == [(115,), (223,), (1295,), (440,), (200,), (202,)]
    # data rows link to their source; expert estimates are marked as demo estimates
    assert (
        _count(
            test_engine,
            "SELECT count(*) FROM risk_areas WHERE source_type = 'data' AND source_url IS NULL",
        )
        == 0
    )
    assert _rows(
        test_engine,
        "SELECT country, region, road_ref FROM risk_areas WHERE source_type = 'expert_estimate'"
        " AND basis LIKE 'Demo estimate%' ORDER BY country",
    ) == [("ES", "ES-CT", "AP-7"), ("FR", "FR-ARA", None)]
    # every border wait is an invented demo value with its note
    assert _rows(
        test_engine,
        "SELECT DISTINCT source_type, note FROM border_wait_observations",
    ) == [("demo", "Invented demo value, not a measurement.")]


def test_seed_risk_reports_are_valid_by_the_domain_rules() -> None:
    from domain.risks import country_risk

    months = [m for m, _, _, _ in seed.CARGO_CRIME_REPORTS]
    assert len(months) == len(set(months))
    reports = {m: counts for m, _, _, counts in seed.CARGO_CRIME_REPORTS}
    # Germany: six named months in the year before the seed day
    assert country_risk("DE", reports, date(2026, 11, 24)).months_used == 6
    assert {w[0] for w in seed.BORDER_WAITS} <= set(seed.BORDER_CROSSINGS)
