from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from domain.locations import (
    LEVELS_BY_SCHEME,
    BorderCrossingStatus,
    LocationType,
    ParkingCertificationLevel,
    status_at,
    validate_border_crossing,
    validate_customs_office_pair,
    validate_latitude,
    validate_longitude,
    validate_opening_hours,
    validate_parking_certification,
    validate_parking_details,
    validate_postal_code,
    validate_status_periods,
    validate_terminal_fields,
    validate_timezone,
)
from domain.locations import ParkingCertificationScheme as S

D = Decimal
L = ParkingCertificationLevel


@pytest.mark.parametrize(
    "tz",
    [
        "Europe/Helsinki",
        "Europe/Berlin",
        "Europe/Tallinn",
        "Europe/Mariehamn",
        "Europe/Stockholm",
        "Europe/Rome",
        "UTC",
    ],
)
def test_valid_timezone(tz: str) -> None:
    assert validate_timezone(tz) == tz


@pytest.mark.parametrize(
    "tz", ["", "Helsinki", "Europe/Helsinkii", "europe/helsinki", "EET+2", "../etc/passwd", "/UTC"]
)
def test_invalid_timezone(tz: str) -> None:
    with pytest.raises(ValueError):
        validate_timezone(tz)


def test_coordinates() -> None:
    assert validate_latitude(D("60.1699")) == D("60.1699")
    assert validate_longitude(D("-180")) == D("-180")
    for bad in (D("90.000001"), D("-91")):
        with pytest.raises(ValueError):
            validate_latitude(bad)
    for bad in (D("180.5"), D("-181")):
        with pytest.raises(ValueError):
            validate_longitude(bad)


def test_opening_hours_valid() -> None:
    hours = {
        "mon": [["06:00", "12:00"], ["13:00", "24:00"]],
        "sat": [],
        "sun": [["00:00", "01:00"]],
    }
    assert validate_opening_hours(hours) == hours
    assert validate_opening_hours({}) == {}


@pytest.mark.parametrize(
    "hours",
    [
        {"monday": [["08:00", "16:00"]]},  # unknown day key
        {"mon": "08:00-16:00"},  # not a list
        {"mon": [["08:00"]]},  # not a pair
        {"mon": [["16:00", "08:00"]]},  # closes before it opens
        {"mon": [["08:00", "08:00"]]},  # empty interval
        {"mon": [["08:00", "12:00"], ["11:00", "13:00"]]},  # overlap
        {"mon": [["13:00", "14:00"], ["08:00", "12:00"]]},  # unsorted
        {"mon": [["8:00", "16:00"]]},  # bad format
        {"mon": [["08:00", "25:00"]]},  # bad hour
        {"mon": [["24:00", "24:00"]]},
        {"mon": [[8, 16]]},  # not strings
    ],
)
def test_opening_hours_invalid(hours: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        validate_opening_hours(hours)


def _terminal(**kw: object) -> None:
    args: dict[str, Any] = {
        "loading_docks": 4,
        "cold_storage": False,
        "temperature_min": None,
        "temperature_max": None,
        "reefer_plug_count": None,
    }
    args.update(kw)
    validate_terminal_fields(LocationType.TERMINAL, **args)


def test_terminal_fields_valid() -> None:
    _terminal()
    _terminal(
        cold_storage=True, temperature_min=D("-25"), temperature_max=D("8"), reefer_plug_count=6
    )
    _terminal(reefer_plug_count=2)  # plugs without a cold room


@pytest.mark.parametrize(
    "overrides",
    [
        {"loading_docks": None},
        {"loading_docks": 0},
        {"cold_storage": None},
        {"reefer_plug_count": -1},
        {"temperature_min": D("2")},  # range without cold storage
        {"cold_storage": True, "temperature_min": D("9"), "temperature_max": D("8")},
    ],
)
def test_terminal_fields_invalid(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _terminal(**overrides)


@pytest.mark.parametrize(
    "location_type", [t for t in LocationType if t is not LocationType.TERMINAL]
)
def test_terminal_fields_forbidden_on_other_types(location_type: LocationType) -> None:
    none: dict[str, Any] = {
        "loading_docks": None,
        "cold_storage": None,
        "temperature_min": None,
        "temperature_max": None,
        "reefer_plug_count": None,
    }
    validate_terminal_fields(location_type, **none)
    for field, value in (("loading_docks", 2), ("cold_storage", False), ("reefer_plug_count", 1)):
        with pytest.raises(ValueError):
            validate_terminal_fields(location_type, **{**none, field: value})


@pytest.mark.parametrize("value", ["00100", "33100", "01510", " 70100 "])
def test_finnish_postal_code_valid(value: str) -> None:
    assert validate_postal_code("FI", value) == value.strip()


@pytest.mark.parametrize(
    "value", ["", "  ", "3310", "331000", "33 100", "ABCDE", "3310A", "FI-33100"]
)
def test_finnish_postal_code_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_postal_code("FI", value)


@pytest.mark.parametrize(
    ("country", "value"),
    [("SE", "760 40"), ("DE", "23552"), ("PL", "81-310"), ("NO", "0150"), ("AX", "22100")],
)
def test_other_countries_take_free_text(country: str, value: str) -> None:
    assert validate_postal_code(country, value) == value


def test_free_text_postal_code_is_still_bounded() -> None:
    with pytest.raises(ValueError):
        validate_postal_code("DE", " ")
    with pytest.raises(ValueError):
        validate_postal_code("DE", "1" * 21)


# --- D92: parking and border crossings


def test_certification_levels_by_scheme() -> None:
    validate_parking_certification(S.EU_SSPA, L.PLATINUM, date(2026, 1, 1), None)
    validate_parking_certification(S.TAPA_PSR, L.LEVEL_1, date(2026, 1, 1), date(2026, 1, 1))
    with pytest.raises(ValueError, match="level"):
        validate_parking_certification(S.EU_SSPA, L.LEVEL_1, date(2026, 1, 1), None)
    with pytest.raises(ValueError, match="level"):
        validate_parking_certification(S.TAPA_PSR, L.GOLD, date(2026, 1, 1), None)
    with pytest.raises(ValueError, match="before"):
        validate_parking_certification(S.EU_SSPA, L.GOLD, date(2026, 2, 1), date(2026, 1, 31))
    # every level belongs to exactly one scheme
    levels = [lv for group in LEVELS_BY_SCHEME.values() for lv in group]
    assert sorted(levels) == sorted(ParkingCertificationLevel)


def _parking_kw(**kw: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "spaces": 10,
        "night_price_cents": 2500,
        "price_currency": "EUR",
        "reefer_plug_count": 4,
        "booking_possible": True,
        "booking_required": False,
        "services": ["toilet", "shower", "toilet"],
    }
    return {**values, **kw}


def test_parking_details() -> None:
    assert validate_parking_details(**_parking_kw()) == ["shower", "toilet"]
    assert validate_parking_details(**_parking_kw(night_price_cents=None, price_currency=None))
    for bad in (
        {"spaces": 0},
        {"night_price_cents": -1},
        {"price_currency": None},
        {"night_price_cents": None},
        {"price_currency": "euro"},
        {"reefer_plug_count": -1},
        {"booking_possible": False, "booking_required": True},
        {"services": ["sauna"]},
    ):
        with pytest.raises(ValueError):
            validate_parking_details(**_parking_kw(**bad))


def test_border_crossing() -> None:
    validate_border_crossing("SE", "NO", typical_wait_minutes=0)
    validate_border_crossing(
        "SE",
        "NO",
        typical_wait_minutes=None,
        customs_office_country="SE",
        other_customs_office_country="NO",
    )
    cases: list[tuple[str, str, dict[str, Any]]] = [
        ("FI", "FI", {}),
        ("FI", "se", {}),
        ("FI", "SE", {"typical_wait_minutes": -1}),
        ("SE", "NO", {"customs_office_country": "NO"}),
        ("SE", "NO", {"other_customs_office_country": "SE"}),
    ]
    for country, other, kw in cases:
        with pytest.raises(ValueError):
            validate_border_crossing(country, other, **{"typical_wait_minutes": None, **kw})


HEL = ZoneInfo("Europe/Helsinki")
OPEN, CLOSED = BorderCrossingStatus.OPEN, BorderCrossingStatus.CLOSED


def test_status_periods_meet_but_do_not_overlap() -> None:
    evening = datetime(2023, 12, 15, 20, 0, tzinfo=HEL)
    periods = [
        (CLOSED, evening, None),
        (OPEN, datetime(2023, 12, 14, tzinfo=HEL), evening),
    ]
    validate_status_periods(periods)
    assert status_at(periods, datetime(2023, 12, 15, 19, 59, tzinfo=HEL)) is OPEN
    assert status_at(periods, evening) is CLOSED
    assert status_at(periods, datetime(2030, 1, 1, tzinfo=HEL)) is CLOSED
    # before the first row: not recorded (shown as unknown, not as OK)
    assert status_at(periods, datetime(2023, 1, 1, tzinfo=HEL)) is None


def test_status_periods_rejected() -> None:
    a = datetime(2024, 1, 1, tzinfo=HEL)
    b = datetime(2024, 2, 1, tzinfo=HEL)
    for periods in (
        [(OPEN, a, None), (CLOSED, b, None)],  # open-ended row overlaps the next
        [(OPEN, a, b), (CLOSED, datetime(2024, 1, 15, tzinfo=HEL), None)],
        [(OPEN, b, a)],
        [(OPEN, a, a)],
        [(OPEN, datetime(2024, 1, 1), None)],  # no time zone
        [(OPEN, a, None), (CLOSED, datetime(2024, 3, 1), None)],  # mixed: no TypeError
    ):
        with pytest.raises(ValueError):
            validate_status_periods(periods)


def test_customs_offices_of_the_two_sides_differ() -> None:
    validate_customs_office_pair(None, None)
    validate_customs_office_pair(1, None)
    validate_customs_office_pair(1, 2)
    with pytest.raises(ValueError):
        validate_customs_office_pair(1, 1)
