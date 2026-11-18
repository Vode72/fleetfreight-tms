from decimal import Decimal
from typing import Any

import pytest

from domain.locations import (
    LocationType,
    validate_latitude,
    validate_longitude,
    validate_opening_hours,
    validate_terminal_fields,
    validate_timezone,
)

D = Decimal


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
