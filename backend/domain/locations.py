"""Locations (D13, D31-D33, D48, D92). Pure domain module.

The allowed values are stored in the database (see the CHECK constraints in db/models.py and the
migration); tests/test_domain_locations.py keeps both in step.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
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
    # Road border crossing between two countries (D92); its details are in border_crossing_details.
    BORDER_CROSSING = "border_crossing"


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


# --- Secure truck parking (D92) ---------------------------------------------------------------


class ParkingCertificationScheme(StrEnum):
    """Certification schemes of truck parking areas (general industry standards)."""

    # EU standard for safe and secure parking areas, Delegated Regulation (EU) 2022/1012.
    EU_SSPA = "eu_sspa"
    # TAPA EMEA Parking Security Requirements.
    TAPA_PSR = "tapa_psr"


class ParkingCertificationLevel(StrEnum):
    # (EU) 2022/1012, Annex I B: four security levels.
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    # TAPA PSR: level 1 is the highest, level 3 the baseline.
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"


_L = ParkingCertificationLevel
LEVELS_BY_SCHEME: dict[ParkingCertificationScheme, frozenset[ParkingCertificationLevel]] = {
    ParkingCertificationScheme.EU_SSPA: frozenset({_L.BRONZE, _L.SILVER, _L.GOLD, _L.PLATINUM}),
    ParkingCertificationScheme.TAPA_PSR: frozenset({_L.LEVEL_1, _L.LEVEL_2, _L.LEVEL_3}),
}


class ParkingService(StrEnum):
    SHOWER = "shower"
    TOILET = "toilet"
    RESTAURANT = "restaurant"
    FUEL = "fuel"
    # Rooms for the driver: the regular weekly rest may not be taken in the cab (EU 561/2006).
    ACCOMMODATION = "accommodation"
    # Security staff on site (the certification tells the full security level).
    SECURITY_STAFF = "security_staff"


def validate_parking_certification(
    scheme: ParkingCertificationScheme,
    level: ParkingCertificationLevel,
    valid_from: date,
    valid_until: date | None,
) -> None:
    """A certificate has a level of its own scheme and a validity period (D67)."""
    allowed = LEVELS_BY_SCHEME[scheme]
    if level not in allowed:
        names = ", ".join(sorted(v.value for v in allowed))
        raise ValueError(f"certification level of {scheme.value} must be one of: {names}")
    if valid_until is not None and valid_until < valid_from:
        raise ValueError("valid_until must not be before valid_from")


def validate_parking_details(
    *,
    spaces: int | None,
    night_price_cents: int | None,
    price_currency: str | None,
    reefer_plug_count: int | None,
    booking_possible: bool,
    booking_required: bool,
    services: Sequence[str],
) -> list[str]:
    """Checks a parking area and returns its services de-duplicated and sorted.

    booking_required is the location's own field; a required booking must also be possible.
    """
    if spaces is not None and spaces < 1:
        raise ValueError("spaces must be at least 1")
    if night_price_cents is not None and night_price_cents < 0:
        raise ValueError("night price must not be negative")
    if (night_price_cents is None) != (price_currency is None):
        raise ValueError("a night price needs its currency, and a currency needs a price")
    if price_currency is not None and not _CURRENCY_RE.fullmatch(price_currency):
        raise ValueError("currency must be an ISO 4217 code")
    if reefer_plug_count is not None and reefer_plug_count < 0:
        raise ValueError("reefer_plug_count must not be negative")
    if booking_required and not booking_possible:
        raise ValueError("a parking area that requires booking must allow booking")
    known = {s.value for s in ParkingService}
    unknown = sorted(set(services) - known)
    if unknown:
        raise ValueError(f"unknown parking services: {', '.join(unknown)}")
    return sorted(set(services))


# --- Border crossings (D92) -------------------------------------------------------------------


class BorderCrossingStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    # Open with limits, e.g. goods traffic only or limited hours; the limit is in the note.
    RESTRICTED = "restricted"


_COUNTRY_RE = re.compile(r"[A-Z]{2}")
_CURRENCY_RE = re.compile(r"[A-Z]{3}")


def validate_border_crossing(
    country: str,
    other_country: str,
    *,
    typical_wait_minutes: int | None,
    customs_office_country: str | None = None,
    other_customs_office_country: str | None = None,
) -> None:
    """The crossing lies in `country` (the location's country) and leads to `other_country`.

    The customs office of each side lies in that side's country (D48).
    """
    if not _COUNTRY_RE.fullmatch(other_country):
        raise ValueError("other_country must be an ISO 3166-1 alpha-2 code")
    if other_country == country:
        raise ValueError("a border crossing leads to another country")
    if typical_wait_minutes is not None and typical_wait_minutes < 0:
        raise ValueError("typical wait must not be negative")
    if customs_office_country is not None and customs_office_country != country:
        raise ValueError("the customs office of this side must lie in the crossing's country")
    if other_customs_office_country is not None and other_customs_office_country != other_country:
        raise ValueError("the other side's customs office must lie in the other country")


def validate_customs_office_pair(
    customs_office_id: object | None, other_customs_office_id: object | None
) -> None:
    """The two sides need two different offices (mirrors ck_border_crossing_details_...)."""
    if customs_office_id is not None and customs_office_id == other_customs_office_id:
        raise ValueError("the customs offices of the two sides must differ")


def validate_status_periods(
    periods: Sequence[tuple[BorderCrossingStatus, datetime, datetime | None]],
) -> None:
    """Periods [starts_at, ends_at) must have a time zone, run forward and not overlap.

    Mirrors the exclusion constraint; ends_at None = until further notice.
    """
    for _, starts_at, ends_at in periods:
        if starts_at.tzinfo is None or (ends_at is not None and ends_at.tzinfo is None):
            raise ValueError("status period times need a time zone")
    ordered = sorted(periods, key=lambda p: p[1])
    previous_end: datetime | None = None
    for index, (_, starts_at, ends_at) in enumerate(ordered):
        if ends_at is not None and ends_at <= starts_at:
            raise ValueError("a status period must end after it starts")
        if index and (previous_end is None or starts_at < previous_end):
            raise ValueError("status periods must not overlap")
        previous_end = ends_at


def status_at(
    periods: Sequence[tuple[BorderCrossingStatus, datetime, datetime | None]], moment: datetime
) -> BorderCrossingStatus | None:
    """The status at a moment; None = not recorded (Plan Check shows it as unknown, not OK)."""
    for status, starts_at, ends_at in periods:
        if starts_at <= moment and (ends_at is None or moment < ends_at):
            return status
    return None


# --- Loading sites, port storage and wash places (2B-3b part b, D93) --------------------------


def validate_site_features(
    location_type: LocationType,
    *,
    forklift_available: bool | None,
    tail_lift_required: bool | None,
) -> None:
    """Forklift and tail lift needs are recorded for customer sites only (like has_loading_dock).

    Terminals always have docks and forklifts (D32); None = not known.
    """
    if location_type is not LocationType.CUSTOMER_SITE and (
        forklift_available is not None or tail_lift_required is not None
    ):
        raise ValueError("forklift and tail lift fields are for customer sites only")


# Location types whose trailer storage terms are recorded (D63, D83, D93).
STORAGE_LOCATION_TYPES: tuple[LocationType, ...] = (LocationType.PORT, LocationType.RAIL_TERMINAL)


def validate_trailer_storage_rule(
    location_type: str,
    *,
    free_days: int,
    daily_fee_cents: int,
    currency: str,
    reefer_plug_available: bool,
    reefer_plug_daily_fee_cents: int | None,
    valid_from: date,
    valid_until: date | None,
) -> None:
    """D83: free days (the arrival day counts as the first) and a fee for each further day.

    Recorded for ports and rail terminals (D63, D93).
    """
    if location_type not in {t.value for t in STORAGE_LOCATION_TYPES}:
        raise ValueError("storage terms are recorded for ports and rail terminals only")
    if free_days < 0:
        raise ValueError("free_days must not be negative")
    if daily_fee_cents < 0:
        raise ValueError("daily fee must not be negative")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ValueError("currency must be an ISO 4217 code")
    if reefer_plug_daily_fee_cents is not None:
        if not reefer_plug_available:
            raise ValueError("a reefer plug fee needs reefer plugs")
        if reefer_plug_daily_fee_cents < 0:
            raise ValueError("reefer plug fee must not be negative")
    if valid_until is not None and valid_until < valid_from:
        raise ValueError("valid_until must not be before valid_from")


def storage_rule_for(
    day: date,
    own_rules: Sequence[tuple[date, date | None]],
    parent_rules: Sequence[tuple[date, date | None]],
) -> tuple[str, int] | None:
    """Which storage rule applies on a day: ("own" | "parent", index) or None = not recorded.

    A quay uses its own rule on the days it has one, otherwise the rule of its port area (D93).
    Rules of one place never overlap (exclusion constraint), so at most one matches.
    """
    for source, rules in (("own", own_rules), ("parent", parent_rules)):
        for index, (valid_from, valid_until) in enumerate(rules):
            if valid_from <= day and (valid_until is None or day <= valid_until):
                return source, index
    return None


class WashScope(StrEnum):
    """What is washed."""

    INTERIOR = "interior"
    EXTERIOR = "exterior"


class WashGrade(StrEnum):
    """Cleaning level of an interior wash (D56: e.g. after dangerous goods before food)."""

    GENERAL = "general"
    FOOD_GRADE = "food_grade"
    CHEMICAL = "chemical"
    TANK = "tank"


def validate_wash_details(
    scopes: Sequence[str],
    grades: Sequence[str],
    *,
    issues_cleaning_document: bool,
    issues_ecd: bool,
) -> tuple[list[str], list[str]]:
    """Returns scopes and grades de-duplicated and sorted.

    Grades describe interior cleaning, so they need the interior scope. A cleaning document is
    issued after an interior wash; the European Cleaning Document (ECD) is used for tank and bulk
    cleaning, so it needs the tank grade and is a cleaning document itself.
    """
    for values, enum, label in ((scopes, WashScope, "scopes"), (grades, WashGrade, "grades")):
        unknown = sorted(set(values) - {v.value for v in enum})
        if unknown:
            raise ValueError(f"unknown wash {label}: {', '.join(unknown)}")
    if not scopes:
        raise ValueError("a wash place washes the interior, the exterior or both")
    interior = WashScope.INTERIOR.value in scopes
    if grades and not interior:
        raise ValueError("wash grades need an interior wash")
    if interior and not grades:
        raise ValueError("an interior wash needs at least one grade")
    if issues_cleaning_document and not interior:
        raise ValueError("a cleaning document needs an interior wash")
    if issues_ecd and (not issues_cleaning_document or WashGrade.TANK.value not in grades):
        raise ValueError("an ECD needs the tank grade and is a cleaning document")
    return sorted(set(scopes)), sorted(set(grades))
