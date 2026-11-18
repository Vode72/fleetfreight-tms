"""Locations (D13, D31-D33, D48). Pure domain module.

The allowed values are stored in the database (see the CHECK constraints in db/models.py and the
migration); tests/test_domain_locations.py keeps both in step.
"""

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Any
from zoneinfo import available_timezones


class LocationType(StrEnum):
    CUSTOMER_SITE = "customer_site"
    TERMINAL = "terminal"
    PORT = "port"
    DEPOT = "depot"
    WORKSHOP = "workshop"
    WASH = "wash"
    INSPECTION = "inspection"
    PARKING = "parking"
    # Intermodal rail terminal (terminal fields of type "terminal" do not apply).
    RAIL_TERMINAL = "rail_terminal"
    FUEL = "fuel"
    CUSTOMS_OFFICE = "customs_office"


WEEKDAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_FI_POSTAL_RE = re.compile(r"[0-9]{5}")
_TIME_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d|24:00")


def validate_timezone(value: str) -> str:
    """The name must be an IANA time zone key known to the zoneinfo database."""
    if value not in available_timezones():
        raise ValueError(f"unknown IANA time zone: {value!r}")
    return value


def validate_postal_code(country: str, value: str) -> str:
    """Postal codes are checked per country; only Finland (five digits) has a rule so far.

    Other countries take free text (trimmed, not empty, at most 20 characters). Note that Aland
    (AX) uses the free-text rule: its codes look Finnish but the country differs.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("postal code must not be empty")
    if len(stripped) > 20:
        raise ValueError("postal code must be at most 20 characters")
    if country == "FI" and not _FI_POSTAL_RE.fullmatch(stripped):
        raise ValueError("a Finnish postal code is five digits")
    return stripped


def validate_latitude(value: Decimal) -> Decimal:
    if not Decimal(-90) <= value <= Decimal(90):
        raise ValueError("latitude must be between -90 and 90")
    return value


def validate_longitude(value: Decimal) -> Decimal:
    if not Decimal(-180) <= value <= Decimal(180):
        raise ValueError("longitude must be between -180 and 180")
    return value


def _minutes(value: object) -> int:
    if not isinstance(value, str) or not _TIME_RE.fullmatch(value):
        raise ValueError(f"opening time must be 'HH:MM' (00:00-24:00), got {value!r}")
    return int(value[:2]) * 60 + int(value[3:])


def validate_opening_hours(value: Mapping[str, Any]) -> dict[str, list[list[str]]]:
    """Weekly opening hours in the location's local time.

    Shape: {"mon": [["08:00", "16:00"], ...], ...}. Keys are mon..sun; a missing day or an empty
    list means closed. Each interval is [open, close) with open < close ("24:00" allowed as the
    close); intervals of a day must be sorted and must not overlap. An overnight opening is
    written as two intervals on two days. An empty mapping is valid but means "closed all week";
    unknown opening hours are NULL in the database instead.
    """
    result: dict[str, list[list[str]]] = {}
    for day, intervals in value.items():
        if day not in WEEKDAYS:
            raise ValueError(f"unknown weekday {day!r}; use {', '.join(WEEKDAYS)}")
        if not isinstance(intervals, Sequence) or isinstance(intervals, str):
            raise ValueError(f"{day}: intervals must be a list")
        previous_close = -1
        cleaned: list[list[str]] = []
        for interval in intervals:
            if not isinstance(interval, Sequence) or isinstance(interval, str):
                raise ValueError(f"{day}: each interval must be [open, close]")
            if len(interval) != 2:
                raise ValueError(f"{day}: each interval must be [open, close]")
            opens, closes = _minutes(interval[0]), _minutes(interval[1])
            if opens >= closes:
                raise ValueError(f"{day}: opening time must be before closing time")
            if opens < previous_close:
                raise ValueError(f"{day}: intervals must be sorted and must not overlap")
            previous_close = closes
            cleaned.append([str(interval[0]), str(interval[1])])
        result[day] = cleaned
    return result


def validate_terminal_fields(
    location_type: LocationType,
    *,
    loading_docks: int | None,
    cold_storage: bool | None,
    temperature_min: Decimal | None,
    temperature_max: Decimal | None,
    reefer_plug_count: int | None,
) -> None:
    """Terminal fields apply to terminals only; mirrors ck_locations_terminal_fields.

    A terminal has at least one loading dock (D32) and states whether it has cold storage (D33).
    The temperature range is allowed only with cold storage. Reefer plugs are independent of the
    cold room (a trailer can be plugged in without one).
    """
    if location_type is not LocationType.TERMINAL:
        if any(
            v is not None
            for v in (
                loading_docks,
                cold_storage,
                temperature_min,
                temperature_max,
                reefer_plug_count,
            )
        ):
            raise ValueError("terminal fields are allowed only for locations of type 'terminal'")
        return
    if loading_docks is None or loading_docks < 1:
        raise ValueError("a terminal needs at least one loading dock")
    if cold_storage is None:
        raise ValueError("a terminal must state whether it has cold storage")
    if reefer_plug_count is not None and reefer_plug_count < 0:
        raise ValueError("reefer_plug_count must not be negative")
    if not cold_storage and (temperature_min is not None or temperature_max is not None):
        raise ValueError("a temperature range requires cold storage")
    if (
        temperature_min is not None
        and temperature_max is not None
        and temperature_min > temperature_max
    ):
        raise ValueError("temperature_min must not exceed temperature_max")
