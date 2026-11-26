"""Routing suggestions and LTL linehauls (2B-3c part 2, D64, D96).

Pure domain module. A routing preference suggests the gateway (the port or rail terminal on the
foreign side of the sea leg), optionally the line route, the onward mode and a border crossing for
a country pair. The system suggests; the dispatcher decides (rule 8).

An LTL linehaul is a scheduled trunk run between two terminals (chapter 3B) with a cut-off and a
delivery promise in working days. It is a template: it never creates trips by itself (rule 8).
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, time, timedelta
from enum import StrEnum
from itertools import pairwise

_COUNTRY_RE = re.compile(r"[A-Z]{2}")
# Start of a postal code without spaces (mirrors the CHECK constraint).
_POSTAL_PREFIX_RE = re.compile(r"[0-9A-Z]{1,10}")


class OnwardMode(StrEnum):
    """How the unit continues from the gateway."""

    ROAD = "road"
    # Onward by an unaccompanied rail route (D63), e.g. Rostock - Verona.
    RAIL = "rail"


# --- Routing preferences ----------------------------------------------------------------------


def validate_preference(
    *,
    origin_country: str | None,
    destination_country: str,
    postal_prefix: str | None,
    priority: int,
    has_gateway: bool,
    has_line_route: bool,
    onward_mode: OnwardMode,
    has_onward_route: bool,
    has_via: bool,
    valid_from: date,
    valid_until: date | None,
) -> None:
    """Mirrors the CHECK constraints of routing_preferences."""
    if not _COUNTRY_RE.fullmatch(destination_country) or (
        origin_country is not None and not _COUNTRY_RE.fullmatch(origin_country)
    ):
        raise ValueError("countries are ISO 3166-1 alpha-2 codes")
    if origin_country is not None and origin_country == destination_country:
        raise ValueError("origin and destination country must differ")
    if postal_prefix is not None and not _POSTAL_PREFIX_RE.fullmatch(postal_prefix):
        raise ValueError("postal prefix is 1-10 digits or upper-case letters")
    if priority < 1:
        raise ValueError("priority starts at 1")
    if not (has_gateway or has_via):
        raise ValueError("a preference names a gateway or a border crossing (road only)")
    if has_line_route and not has_gateway:
        raise ValueError("a line route needs the gateway it serves")
    if (onward_mode is OnwardMode.RAIL) != has_onward_route:
        raise ValueError("onward rail needs a rail route, and only rail has one")
    if has_onward_route and not has_gateway:
        raise ValueError("onward rail starts from a gateway")
    if valid_until is not None and valid_until < valid_from:
        raise ValueError("validity ends before it starts")


def validate_gateway_on_route(gateway_id: object, route_stop_ids: Sequence[object]) -> None:
    """The suggested line route must call at the gateway."""
    if gateway_id not in route_stop_ids:
        raise ValueError("the line route does not call at the gateway")


@dataclass(frozen=True)
class Preference[T]:
    """A routing preference row for matching; `value` is what the caller wants back."""

    origin_country: str | None
    destination_country: str
    postal_prefix: str | None
    priority: int
    valid_from: date
    valid_until: date | None
    value: T


def _valid_on(valid_from: date, valid_until: date | None, day: date) -> bool:
    return valid_from <= day and (valid_until is None or day <= valid_until)


def suggest[T](
    preferences: Iterable[Preference[T]],
    *,
    origin_country: str,
    destination_country: str,
    postal_code: str | None,
    on: date,
) -> list[T]:
    """Suggestions for one shipment, best first.

    A row matches when it is valid on the day, its destination country matches, its origin is
    the shipment's or open (any), and its postal prefix (if any) starts the destination postal
    code. Only the most specific matching rows are kept: a longer postal prefix replaces shorter
    ones and the country level, and a named origin replaces an open one ("tarkempi korvaa").
    Rows of equal priority are alternatives (e.g. Travemünde or Lübeck) and keep their order.
    """
    code = (postal_code or "").replace(" ", "").upper()
    matches = [
        p
        for p in preferences
        if p.destination_country == destination_country
        and p.origin_country in (None, origin_country)
        and (p.postal_prefix is None or code.startswith(p.postal_prefix))
        and _valid_on(p.valid_from, p.valid_until, on)
    ]
    if not matches:
        return []

    def specificity(p: Preference[T]) -> tuple[int, int]:
        return (len(p.postal_prefix or ""), int(p.origin_country is not None))

    best = max(specificity(p) for p in matches)
    kept = [p for p in matches if specificity(p) == best]
    return [p.value for p in sorted(kept, key=lambda p: p.priority)]


# --- LTL linehauls ----------------------------------------------------------------------------


def validate_linehaul(
    *,
    origin_id: object,
    destination_id: object,
    weekdays: Sequence[int],
    departure_time: time,
    cutoff_time: time,
    arrival_day: int,
    arrival_time: time,
    delivery_days: int,
    valid_from: date,
    valid_until: date | None,
) -> None:
    """Mirrors the CHECK constraints of ltl_linehauls.

    Times are local at each terminal. The cut-off is on the departure day, at or before the
    departure. Arrival is a day offset from the departure day (0-14) and a local time after
    the departure; a same-day arrival is compared in local clock time, which assumes both
    terminals share a time zone (true for the Finnish terminal network of v1). The delivery
    promise counts working days from the departure day.
    """
    if origin_id == destination_id:
        raise ValueError("a linehaul runs between two different terminals")
    if not weekdays or any(not 1 <= d <= 7 for d in weekdays) or len(set(weekdays)) < len(weekdays):
        raise ValueError("weekdays are distinct ISO weekdays 1-7, at least one")
    if cutoff_time > departure_time:
        raise ValueError("the cut-off is at or before the departure")
    if not 0 <= arrival_day <= 14 or (arrival_day == 0 and arrival_time <= departure_time):
        raise ValueError("arrival is after the departure, within 14 days")
    if delivery_days < 0:
        raise ValueError("the delivery promise is 0 or more working days")
    if valid_until is not None and valid_until < valid_from:
        raise ValueError("validity ends before it starts")


def runs_on(weekdays: Iterable[int], day: date) -> bool:
    return day.isoweekday() in set(weekdays)


def add_working_days(start: date, days: int, holidays: Iterable[date]) -> date:
    """`days` working days after `start` (Mon-Fri, skipping holidays). 0 = `start` itself."""
    off = set(holidays)
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.isoweekday() <= 5 and current not in off:
            remaining -= 1
    return current


def promised_delivery(departure_day: date, delivery_days: int, holidays: Iterable[date]) -> date:
    """Delivery promised to the customer (D+n in working days), e.g. Friday D+1 -> Monday.

    `holidays` are the public holidays of the destination terminal's country (public_holidays).
    """
    return add_working_days(departure_day, delivery_days, holidays)


def validate_linehaul_periods(periods: Sequence[tuple[date, date | None]]) -> None:
    """Rows of one linehaul (same terminals and departure time) must not overlap (D67)."""
    ordered = sorted(periods, key=lambda period: period[0])
    for (_, end), (start, _) in pairwise(ordered):
        if end is None or start <= end:
            raise ValueError("periods of one linehaul must not overlap in validity")


def validate_thermo_linehaul(
    temperature_controlled: bool, origin_cold: bool, destination_cold: bool
) -> None:
    """LTL thermo is consolidated only at cold terminals (D33)."""
    if temperature_controlled and not (origin_cold and destination_cold):
        raise ValueError("a thermo linehaul runs between cold terminals (D33)")
