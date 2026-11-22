"""Ferry and rail lines, vessels, weekly schedules and departures (2B-3c, D62, D63, D94).

Pure domain module. A route is a sequence of stops (ports or rail terminals); a schedule is a
weekly pattern of one route with the local time at every stop; a departure is one dated trip of
the route, generated from a schedule or entered by hand. Generating never edits or deletes an
existing departure: a booked or hand-changed departure stays as it is (rules 8 and 9).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


class LineMode(StrEnum):
    FERRY = "ferry"
    RAIL = "rail"


class VesselType(StrEnum):
    # Freight ro-ro: few or no driver places.
    RORO = "roro"
    # Ro-pax: freight and passengers, cabins for drivers.
    ROPAX = "ropax"


class AdrAcceptance(StrEnum):
    ALLOWED = "allowed"
    FORBIDDEN = "forbidden"
    # Accepted only after the operator's approval for the departure.
    PRE_APPROVAL = "pre_approval"


class DepartureStatus(StrEnum):
    PLANNED = "planned"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


# ADR (and IMDG) dangerous goods classes; a vessel lists how it accepts each.
ADR_CLASSES: tuple[str, ...] = (
    "1",
    "2",
    "3",
    "4.1",
    "4.2",
    "4.3",
    "5.1",
    "5.2",
    "6.1",
    "6.2",
    "7",
    "8",
    "9",
)


def validate_route(
    mode: LineMode,
    *,
    accompanied: bool,
    unaccompanied: bool,
    checkin_minutes: int | None,
    cutoff_minutes: int | None,
    dg_declaration_hours: int | None,
) -> None:
    """A route carries accompanied units, unaccompanied units or both.

    Rail carries load units only (D63). Check-in applies to accompanied units (the driver), the
    cut-off to unaccompanied ones; both are defaults that a stop or a departure may override.
    """
    if not (accompanied or unaccompanied):
        raise ValueError("a route carries accompanied or unaccompanied units")
    if mode is LineMode.RAIL and accompanied:
        raise ValueError("rail carries load units without a tractor (D63)")
    if checkin_minutes is not None and (not accompanied or checkin_minutes < 0):
        raise ValueError("check-in is for accompanied units and must not be negative")
    if cutoff_minutes is not None and (not unaccompanied or cutoff_minutes < 0):
        raise ValueError("cut-off is for unaccompanied units and must not be negative")
    if dg_declaration_hours is not None and dg_declaration_hours < 0:
        raise ValueError("dangerous goods declaration deadline must not be negative")


@dataclass(frozen=True)
class Stop:
    sequence: int
    loading: bool
    unloading: bool


def validate_stops(stops: Sequence[Stop]) -> None:
    """At least two stops numbered 1..n; the first only loads, the last only unloads."""
    if len(stops) < 2:
        raise ValueError("a route has at least two stops")
    if [s.sequence for s in stops] != list(range(1, len(stops) + 1)):
        raise ValueError("stops are numbered 1..n in order")
    first, last = stops[0], stops[-1]
    if not first.loading or first.unloading:
        raise ValueError("the first stop only loads")
    if last.loading or not last.unloading:
        raise ValueError("the last stop only unloads")
    if any(not (s.loading or s.unloading) for s in stops[1:-1]):
        raise ValueError("an intermediate stop loads, unloads or both")


@dataclass(frozen=True)
class Call:
    """Local times at one stop of a weekly schedule, as day offsets from the first departure."""

    sequence: int
    arrival_day: int | None
    arrival_time: time | None
    departure_day: int | None
    departure_time: time | None


def validate_calls(calls: Sequence[Call]) -> None:
    """The first call departs on day 0 and has no arrival; the last arrives and does not depart.

    Every pair (day, time) is set or unset together. Order in time is checked by
    departure_times, which knows the stops' time zones.
    """
    if len(calls) < 2:
        raise ValueError("a schedule calls at least two stops")
    if [c.sequence for c in calls] != list(range(1, len(calls) + 1)):
        raise ValueError("calls are numbered 1..n in order")
    for call in calls:
        if (call.arrival_day is None) != (call.arrival_time is None) or (
            call.departure_day is None
        ) != (call.departure_time is None):
            raise ValueError("a call's day and time are given together")
        for day in (call.arrival_day, call.departure_day):
            if day is not None and not 0 <= day <= 14:
                raise ValueError("day offsets are 0..14")
    first, last = calls[0], calls[-1]
    if first.arrival_day is not None or first.departure_day != 0:
        raise ValueError("the first call departs on day 0 and has no arrival")
    if last.departure_day is not None or last.arrival_day is None:
        raise ValueError("the last call arrives and does not depart")
    for call in calls[1:-1]:
        if call.arrival_day is None or call.departure_day is None:
            raise ValueError("an intermediate call has an arrival and a departure")


@dataclass(frozen=True)
class CallTimes:
    sequence: int
    arrives_at: datetime | None
    departs_at: datetime | None


def _local(day: date, offset: int, at: time, zone: ZoneInfo) -> datetime:
    """A local wall-clock time; a time that does not exist (spring forward) moves an hour on."""
    local = datetime.combine(day + timedelta(days=offset), at, tzinfo=zone)
    # Round trip through UTC detects a non-existent local time (fold rules of PEP 495).
    if local.astimezone(ZoneInfo("UTC")).astimezone(zone).replace(tzinfo=None) != (
        local.replace(tzinfo=None)
    ):
        local = local + timedelta(hours=1)
    return local


def departure_times(
    service_date: date, calls: Sequence[Call], zones: Sequence[str]
) -> list[CallTimes]:
    """The times of one departure: every call's local time in its own stop's time zone.

    `service_date` is the local date of the first departure; `zones` the stops' IANA zones in
    call order. Times must run forward (arrival before departure, each stop after the one
    before).
    """
    validate_calls(calls)
    if len(zones) != len(calls):
        raise ValueError("one time zone per call")
    result: list[CallTimes] = []
    previous: datetime | None = None
    for call, zone_name in zip(calls, zones, strict=True):
        zone = ZoneInfo(zone_name)
        arrives = (
            _local(service_date, call.arrival_day, call.arrival_time, zone)
            if call.arrival_day is not None and call.arrival_time is not None
            else None
        )
        departs = (
            _local(service_date, call.departure_day, call.departure_time, zone)
            if call.departure_day is not None and call.departure_time is not None
            else None
        )
        for moment in (arrives, departs):
            if moment is None:
                continue
            if previous is not None and moment <= previous:
                raise ValueError(f"call {call.sequence}: times must run forward")
            previous = moment
        result.append(CallTimes(call.sequence, arrives, departs))
    return result


def service_dates(
    weekday: int, valid_from: date, valid_until: date | None, start: date, end: date
) -> list[date]:
    """Dates in [start, end] that fall on an ISO weekday (1 = Monday) within the schedule's
    validity (both ends inclusive)."""
    if not 1 <= weekday <= 7:
        raise ValueError("weekday is 1 (Monday) .. 7 (Sunday)")
    first = max(start, valid_from)
    last = end if valid_until is None else min(end, valid_until)
    day = first + timedelta(days=(weekday - first.isoweekday()) % 7)
    dates: list[date] = []
    while day <= last:
        dates.append(day)
        day += timedelta(days=7)
    return dates


def dates_to_generate(planned: Iterable[date], existing: Iterable[date]) -> list[date]:
    """Only the missing departures are created; existing ones are never touched or removed."""
    have = set(existing)
    return sorted(d for d in set(planned) if d not in have)


def validate_vessel(
    *,
    lane_metres: int | None,
    deck_height_mm: int | None,
    reefer_plug_count: int | None,
    accompanied: bool,
    unaccompanied: bool,
    driver_cabins: bool,
) -> None:
    for value, name in (
        (lane_metres, "lane metres"),
        (deck_height_mm, "deck height"),
    ):
        if value is not None and value <= 0:
            raise ValueError(f"{name} must be positive")
    if reefer_plug_count is not None and reefer_plug_count < 0:
        raise ValueError("reefer plug count must not be negative")
    if not (accompanied or unaccompanied):
        raise ValueError("a vessel carries accompanied or unaccompanied units")
    if accompanied and not driver_cabins:
        raise ValueError("a vessel that carries accompanied units has driver cabins (D23)")
