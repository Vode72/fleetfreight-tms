"""Constraints of the 2B-3b place tables (D92), checked against the migrated PostgreSQL schema."""

import uuid
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from domain.locations import (
    LEVELS_BY_SCHEME,
    BorderCrossingStatus,
    ParkingCertificationScheme,
    ParkingService,
)

pytestmark = pytest.mark.usefixtures("clean_registers")

SOURCE = {"source_url": "https://example.com", "checked_on": "2026-11-22"}


def _exec(engine: Engine, sql: str, **values: Any) -> Any:
    with engine.begin() as conn:
        return conn.execute(text(sql), values).scalar()


def _insert(engine: Engine, table: str, returning: str = "id", **values: Any) -> Any:
    columns = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    return _exec(
        engine, f"INSERT INTO {table} ({columns}) VALUES ({params}) RETURNING {returning}", **values
    )


def _location(engine: Engine, location_type: str, name: str, country: str = "FI") -> uuid.UUID:
    return uuid.UUID(
        str(
            _insert(
                engine,
                "locations",
                type=location_type,
                name=name,
                country=country,
                timezone="Europe/Helsinki",
            )
        )
    )


def _parking(engine: Engine, name: str = "Demo Parking", **kw: Any) -> uuid.UUID:
    location_id = _location(engine, "parking", name)
    _insert(engine, "parking_details", returning="location_id", location_id=location_id, **kw)
    return location_id


def _crossing(engine: Engine, name: str = "Demo Crossing", **kw: Any) -> uuid.UUID:
    location_id = _location(engine, "border_crossing", name)
    values = {"location_id": location_id, "other_country": "SE", **kw}
    _insert(engine, "border_crossing_details", returning="location_id", **values)
    return location_id


def _rejected(fn: Any, *args: Any, **kw: Any) -> None:
    with pytest.raises(IntegrityError):
        fn(*args, **kw)


# --- parking


def test_parking_details_defaults(test_engine: Engine) -> None:
    location_id = _parking(test_engine)
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT location_type, booking_possible, services, adr_vehicles_allowed"
                " FROM parking_details WHERE location_id = :id"
            ),
            {"id": location_id},
        ).one()
    assert tuple(row) == ("parking", False, [], None)


def test_parking_details_only_for_parking_locations(test_engine: Engine) -> None:
    depot = _location(test_engine, "depot", "Demo Depot")
    _rejected(_insert, test_engine, "parking_details", returning="location_id", location_id=depot)
    # the type column is fixed: a depot cannot pass as a parking area
    _rejected(
        _insert,
        test_engine,
        "parking_details",
        returning="location_id",
        location_id=depot,
        location_type="depot",
    )


def test_parking_location_type_cannot_change_while_details_exist(test_engine: Engine) -> None:
    location_id = _parking(test_engine)
    _rejected(
        _exec, test_engine, "UPDATE locations SET type = 'depot' WHERE id = :id", id=location_id
    )


def test_parking_details_values(test_engine: Engine) -> None:
    services = [s.value for s in ParkingService]
    _parking(
        test_engine,
        spaces=10,
        night_price_cents=2500,
        price_currency="EUR",
        reefer_plug_count=0,
        services=services,
    )
    bad: list[dict[str, Any]] = [
        {"spaces": 0},
        {"night_price_cents": 100},  # price without currency
        {"price_currency": "EUR"},  # currency without price
        {"night_price_cents": -1, "price_currency": "EUR"},
        {"night_price_cents": 100, "price_currency": "eur"},
        {"reefer_plug_count": -1},
        {"services": ["sauna"]},
    ]
    for number, values in enumerate(bad):
        _rejected(_parking, test_engine, f"Demo Bad {number}", **values)


@pytest.mark.parametrize(
    ("scheme", "level"),
    [(s.value, lv.value) for s, levels in LEVELS_BY_SCHEME.items() for lv in levels],
)
def test_certification_levels_accepted(test_engine: Engine, scheme: str, level: str) -> None:
    location_id = _parking(test_engine)
    _insert(
        test_engine,
        "parking_certifications",
        location_id=location_id,
        scheme=scheme,
        level=level,
        valid_from="2026-01-01",
    )


def test_certification_level_must_match_scheme_and_period_run_forward(test_engine: Engine) -> None:
    location_id = _parking(test_engine)
    for scheme, level, start, end in (
        ("eu_sspa", "level_1", "2026-01-01", None),
        ("tapa_psr", "gold", "2026-01-01", None),
        ("none", "gold", "2026-01-01", None),
        ("eu_sspa", "gold", "2026-02-01", "2026-01-31"),
    ):
        _rejected(
            _insert,
            test_engine,
            "parking_certifications",
            location_id=location_id,
            scheme=scheme,
            level=level,
            valid_from=start,
            valid_until=end,
        )


def test_certification_periods_of_one_scheme_do_not_overlap(test_engine: Engine) -> None:
    location_id = _parking(test_engine)

    def cert(scheme: str, level: str, start: str, end: str | None) -> Any:
        return _insert(
            test_engine,
            "parking_certifications",
            location_id=location_id,
            scheme=scheme,
            level=level,
            valid_from=start,
            valid_until=end,
        )

    cert("tapa_psr", "level_3", "2024-01-01", "2026-06-30")
    cert("tapa_psr", "level_2", "2026-07-01", None)  # renewal: history kept
    cert("eu_sspa", "gold", "2025-01-01", None)  # both schemes at once
    _rejected(cert, "tapa_psr", "level_1", "2026-06-30", "2026-12-31")


def test_parking_with_certificates_cannot_lose_its_details(test_engine: Engine) -> None:
    location_id = _parking(test_engine)
    _insert(
        test_engine,
        "parking_certifications",
        location_id=location_id,
        scheme=ParkingCertificationScheme.EU_SSPA.value,
        level="bronze",
        valid_from="2026-01-01",
    )
    _rejected(
        _exec, test_engine, "DELETE FROM parking_details WHERE location_id = :id", id=location_id
    )
    _rejected(_exec, test_engine, "DELETE FROM locations WHERE id = :id", id=location_id)


# --- border crossings


def test_border_crossing_details_only_for_border_crossings(test_engine: Engine) -> None:
    _crossing(test_engine)
    parking = _location(test_engine, "parking", "Demo Parking")
    _rejected(
        _insert,
        test_engine,
        "border_crossing_details",
        returning="location_id",
        location_id=parking,
        other_country="SE",
    )


def test_customs_offices_must_be_customs_offices(test_engine: Engine) -> None:
    office = _location(test_engine, "customs_office", "Demo Office FI")
    other = _location(test_engine, "customs_office", "Demo Office SE", country="SE")
    depot = _location(test_engine, "depot", "Demo Depot")
    _crossing(
        test_engine,
        customs_office_id=office,
        customs_office_type="customs_office",
        other_customs_office_id=other,
        other_customs_office_type="customs_office",
    )
    _rejected(
        _crossing,
        test_engine,
        "Demo Crossing 2",
        customs_office_id=depot,
        customs_office_type="customs_office",
    )
    _rejected(
        _crossing,
        test_engine,
        "Demo Crossing 3",
        customs_office_id=depot,
        customs_office_type="depot",
    )
    # the two sides need two different offices
    _rejected(
        _crossing,
        test_engine,
        "Demo Crossing 5",
        customs_office_id=office,
        customs_office_type="customs_office",
        other_customs_office_id=office,
        other_customs_office_type="customs_office",
    )
    # id and type come as a pair
    _rejected(_crossing, test_engine, "Demo Crossing 4", customs_office_id=office)
    # an office in use cannot be deleted
    _rejected(_exec, test_engine, "DELETE FROM locations WHERE id = :id", id=office)


def test_border_crossing_values(test_engine: Engine) -> None:
    _crossing(test_engine, typical_wait_minutes=0)
    bad: list[dict[str, Any]] = [
        {"other_country": "se"},
        {"other_country": "S1"},
        {"typical_wait_minutes": -1},
    ]
    for number, values in enumerate(bad):
        _rejected(_crossing, test_engine, f"Demo Bad {number}", **values)


@pytest.mark.parametrize("status", [s.value for s in BorderCrossingStatus])
def test_status_values(test_engine: Engine, status: str) -> None:
    location_id = _crossing(test_engine)
    _insert(
        test_engine,
        "border_crossing_status_periods",
        location_id=location_id,
        status=status,
        starts_at="2026-01-01T00:00+02:00",
        **SOURCE,
    )


def test_status_periods(test_engine: Engine) -> None:
    location_id = _crossing(test_engine)

    def period(status: str, starts: str, ends: str | None, **extra: Any) -> Any:
        return _insert(
            test_engine,
            "border_crossing_status_periods",
            location_id=location_id,
            status=status,
            starts_at=starts,
            ends_at=ends,
            **{**SOURCE, **extra},
        )

    # closed from 20.00: the day itself was open until then (half-open periods meet exactly)
    period("open", "2023-12-14T00:00+02:00", "2023-12-15T20:00+02:00")
    period("closed", "2023-12-15T20:00+02:00", None)
    _rejected(period, "restricted", "2024-01-01T00:00+02:00", None)  # overlaps the open end
    _rejected(period, "closed", "2023-12-01T00:00+02:00", "2023-12-01T00:00+02:00")  # empty
    _rejected(period, "unknown", "2020-01-01T00:00+02:00", "2020-02-01T00:00+02:00")
    _rejected(
        period, "open", "2020-01-01T00:00+02:00", "2020-02-01T00:00+02:00", source_url="http://x"
    )
    _rejected(
        period, "open", "2020-01-01T00:00+02:00", "2020-02-01T00:00+02:00", checked_on="2025-12-31"
    )
    with test_engine.connect() as conn:
        status = conn.execute(
            text(
                "SELECT status FROM border_crossing_status_periods WHERE location_id = :id"
                " AND tstzrange(starts_at, ends_at, '[)') @> CAST(:moment AS timestamptz)"
            ),
            {"id": location_id, "moment": "2023-12-15T19:59+02:00"},
        ).scalar()
    assert status == "open"


def test_crossing_with_status_history_cannot_be_deleted(test_engine: Engine) -> None:
    location_id = _crossing(test_engine)
    _insert(
        test_engine,
        "border_crossing_status_periods",
        location_id=location_id,
        status="open",
        starts_at="2026-01-01T00:00+02:00",
        **SOURCE,
    )
    _rejected(
        _exec,
        test_engine,
        "DELETE FROM border_crossing_details WHERE location_id = :id",
        id=location_id,
    )


# --- D93: site features, trailer storage, wash places


def _site(engine: Engine, name: str, **kw: Any) -> Any:
    customer = _insert(engine, "customers", name=f"{name} Oy", country="FI")
    values = {
        "type": "customer_site",
        "name": name,
        "country": "FI",
        "timezone": "Europe/Helsinki",
        "customer_id": customer,
        **kw,
    }
    return _insert(engine, "locations", **values)


def test_site_features_for_customer_sites_only(test_engine: Engine) -> None:
    _site(test_engine, "Demo Site A", forklift_available=False, tail_lift_required=True)
    _rejected(_site, test_engine, "Demo Site B", has_loading_dock=True, tail_lift_required=True)
    for column in ("forklift_available", "tail_lift_required"):
        _rejected(
            _insert,
            test_engine,
            "locations",
            type="depot",
            name=f"Demo Depot {column}",
            country="FI",
            timezone="Europe/Helsinki",
            **{column: True},
        )


def test_parking_trailer_drop(test_engine: Engine) -> None:
    _parking(test_engine, trailer_drop_allowed=True)


def _storage(engine: Engine, location_id: Any, location_type: str = "port", **kw: Any) -> Any:
    values = {
        "location_id": location_id,
        "location_type": location_type,
        "valid_from": "2026-01-01",
        "daily_fee_cents": 3000,
        "currency": "EUR",
        **kw,
    }
    return _insert(engine, "trailer_storage_rules", **values)


@pytest.mark.parametrize("location_type", ["port", "rail_terminal"])
def test_storage_rules_for_ports_and_rail_terminals(
    test_engine: Engine, location_type: str
) -> None:
    place = _location(test_engine, location_type, "Demo Place")
    _storage(test_engine, place, location_type)
    with test_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT free_days FROM trailer_storage_rules")).scalar() == 3
        )  # D83 default


def test_storage_rules_rejected_elsewhere(test_engine: Engine) -> None:
    depot = _location(test_engine, "depot", "Demo Depot")
    _rejected(_storage, test_engine, depot, "depot")
    _rejected(_storage, test_engine, depot, "port")  # type must match the location


def test_storage_rule_values_and_periods(test_engine: Engine) -> None:
    port = _location(test_engine, "port", "Demo Port")
    _storage(
        test_engine,
        port,
        valid_until="2026-06-30",
        reefer_plug_available=True,
        reefer_plug_daily_fee_cents=0,
    )
    _storage(test_engine, port, valid_from="2026-07-01", free_days=0)  # history kept
    bad: list[dict[str, Any]] = [
        {"free_days": -1},
        {"daily_fee_cents": -1},
        {"currency": "eur"},
        {"reefer_plug_daily_fee_cents": 100},  # fee without plugs
        {"reefer_plug_available": True, "reefer_plug_daily_fee_cents": -1},
        {"valid_until": "2025-12-31"},
    ]
    for number, values in enumerate(bad):
        other = _location(test_engine, "port", f"Demo Port {number}")
        _rejected(_storage, test_engine, other, **values)
    _rejected(_storage, test_engine, port, valid_from="2026-12-01")  # overlaps the open period
    _rejected(_exec, test_engine, "DELETE FROM locations WHERE id = :id", id=port)


def _wash(engine: Engine, name: str = "Demo Wash", **kw: Any) -> Any:
    location_id = _location(engine, "wash", name)
    return _insert(engine, "wash_details", returning="location_id", location_id=location_id, **kw)


def test_wash_details(test_engine: Engine) -> None:
    _wash(test_engine, scopes=["exterior"])
    _wash(
        test_engine,
        "Demo Wash 2",
        scopes=["interior", "exterior"],
        grades=["general", "food_grade"],
        issues_cleaning_document=True,
    )
    _wash(
        test_engine,
        "Demo Wash 4",
        scopes=["interior"],
        grades=["bulk"],
        issues_cleaning_document=True,
        issues_ecd=True,
    )
    _wash(
        test_engine,
        "Demo Wash 3",
        scopes=["interior"],
        grades=["tank"],
        issues_cleaning_document=True,
        issues_ecd=True,
    )
    bad: list[dict[str, Any]] = [
        {"scopes": []},
        {"scopes": ["roof"]},
        {"scopes": ["exterior"], "grades": ["general"]},  # grade without interior
        {"scopes": ["interior"]},  # interior without a grade
        {"scopes": ["interior"], "grades": ["steam"]},
        {"scopes": ["exterior"], "issues_cleaning_document": True},
        {"scopes": ["interior"], "grades": ["chemical"], "issues_ecd": True},
        {
            "scopes": ["interior"],
            "grades": ["chemical"],
            "issues_cleaning_document": True,
            "issues_ecd": True,
        },  # ECD needs the tank grade
    ]
    for number, values in enumerate(bad):
        _rejected(_wash, test_engine, f"Demo Bad Wash {number}", **values)
    depot = _location(test_engine, "depot", "Demo Depot")
    _rejected(
        _insert,
        test_engine,
        "wash_details",
        returning="location_id",
        location_id=depot,
        scopes=["exterior"],
    )
