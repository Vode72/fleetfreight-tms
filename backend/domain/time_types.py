"""Order time windows and time types FIX, Termin, ETA and to be agreed (D80). Pure domain module.

An order carries, separately for pickup and for delivery, an Earliest and a Latest bound and a
time type. A bound is a date with an optional clock time, in the location's local time (as the
customer states it). These are the earliest/latest pickup and delivery dates common to transport
management systems. The time type says how binding the window is:

| Case                     | Earliest      | Latest        |
|--------------------------|---------------|---------------|
| FIX 20.11.               | 20.11.        | 20.11.        |
| Termin 20.11. 14-16      | 20.11. 14:00  | 20.11. 16:00  |
| Pickup "from 14:00"      | 20.11. 14:00  | -             |
| ETA 20.11.               | -             | 20.11.        |
| To be agreed             | -             | -             |

- FIX: one exact date; the customer has paid for delivery on that day. Strict both ways: no
  handling before the day (the receiver may have a full warehouse or cross-dock straight onto
  another trailer) and none after it. No margin; the clock time is checked against the
  location's opening hours separately.
- TERMIN: an agreed date and time or time window, or only one end of it ("from 14:00",
  "by 16:00"). Every given bound has a clock time.
- ETA: an estimated delivery date given to the customer (Latest only). Not binding.
- TO_BE_AGREED: no time yet. A non-mandatory OPEN result: the trip can be planned and confirmed,
  and the time is filled in later.

One rule for Plan Check (D77), through `evaluate`:
- Arriving before Earliest is OK: the vehicle waits and handling starts at Earliest; the result
  gives the waiting time (arrival to handling start).
- Handling planned before Earliest is BLOCKED (e.g. no early unloading of a FIX delivery).
- Handling after Latest is BLOCKED for FIX and TERMIN, only a RISK for ETA.
- Handling within the margin before a Latest clock time is a RISK.
A date-only Earliest starts at 00:00 local time; a date-only Latest lasts to the end of that day.
A clock time skipped by a daylight saving change is rejected; a repeated one means its first
occurrence.

Priority, most binding first, used for conflicts, ordering and optimisation: FIX, TERMIN, ETA,
TO_BE_AGREED.

The margin is a setting (default 30 minutes, D80); the caller passes it in.

Instants are compared in UTC: Python compares two datetimes that share one tzinfo by wall
clock, which is off by an hour across a daylight saving change.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


class TimeType(StrEnum):
    FIX = "FIX"
    TERMIN = "TERMIN"
    ETA = "ETA"
    TO_BE_AGREED = "TO_BE_AGREED"


# Most binding first (D80).
PRIORITY: tuple[TimeType, ...] = (
    TimeType.FIX,
    TimeType.TERMIN,
    TimeType.ETA,
    TimeType.TO_BE_AGREED,
)

DEFAULT_MARGIN = timedelta(minutes=30)


def priority(time_type: TimeType) -> int:
    """Rank of a time type: 0 is the most binding. Use as a sort key."""
    return PRIORITY.index(time_type)


class CheckLevel(StrEnum):
    """Plan Check levels (D77)."""

    OK = "OK"
    RISK = "RISK"
    OPEN = "OPEN"
    BLOCKED = "BLOCKED"


class TimeCheckReason(StrEnum):
    ON_TIME = "on_time"
    WAITS = "waits"  # arrives before Earliest; handling starts at Earliest
    BEFORE_EARLIEST = "before_earliest"  # handling planned before Earliest; not allowed
    WITHIN_MARGIN = "within_margin"
    LATE = "late"
    AFTER_ETA = "after_eta"
    TIME_TO_BE_AGREED = "time_to_be_agreed"


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _local_instant(day: date, at: time, tz: ZoneInfo) -> datetime:
    """A local wall-clock time at a location as an instant.

    A time skipped by a daylight saving change (e.g. 03:30 when clocks go 03:00 -> 04:00) does
    not exist and is rejected. A repeated time (clocks go back) means its first occurrence.
    """
    local = datetime.combine(day, at, tzinfo=tz)  # fold=0: first occurrence
    if _utc(local).astimezone(tz).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError(f"{day} {at} does not exist in {tz.key} (daylight saving change)")
    return local


@dataclass(frozen=True)
class TimeBound:
    """A date with an optional clock time, in the location's local time."""

    day: date
    at: time | None = None

    def __post_init__(self) -> None:
        if self.at is not None and self.at.tzinfo is not None:
            raise ValueError("a bound's clock time is local: give it without a time zone")

    def sort_key(self, end_of_day: bool) -> tuple[date, time]:
        if self.at is not None:
            return (self.day, self.at)
        return (self.day, time.max if end_of_day else time.min)

    def earliest_instant(self, tz: ZoneInfo) -> datetime:
        """First allowed instant when this bound is an Earliest."""
        return _local_instant(self.day, self.at or time.min, tz)

    def latest_instant(self, tz: ZoneInfo) -> datetime:
        """End of the allowed time when this bound is a Latest (exclusive for a date only)."""
        if self.at is not None:
            return _local_instant(self.day, self.at, tz)
        return _local_instant(self.day + timedelta(days=1), time.min, tz)


@dataclass(frozen=True)
class OrderTime:
    """Pickup or delivery time of an order (D80). Build it with the class methods."""

    time_type: TimeType
    earliest: TimeBound | None = None
    latest: TimeBound | None = None

    def __post_init__(self) -> None:
        t, first, last = self.time_type, self.earliest, self.latest
        if t is TimeType.FIX:
            if first is None or last is None or first.day != last.day:
                raise ValueError("FIX needs one date: Earliest and Latest on the same day")
            if first.at is not None or last.at is not None:
                raise ValueError("FIX is a date without a clock time")
        elif t is TimeType.TERMIN:
            if first is None and last is None:
                raise ValueError("TERMIN needs an Earliest, a Latest or both")
            if any(b is not None and b.at is None for b in (first, last)):
                raise ValueError("TERMIN bounds need a clock time")
        elif t is TimeType.ETA:
            if first is not None or last is None or last.at is not None:
                raise ValueError("ETA is a Latest date only")
        elif first is not None or last is not None:
            raise ValueError("TO_BE_AGREED has no Earliest or Latest")
        if (
            first is not None
            and last is not None
            and last.sort_key(end_of_day=True) < first.sort_key(end_of_day=False)
        ):
            raise ValueError("Latest must not be before Earliest")

    @classmethod
    def fix(cls, day: date) -> OrderTime:
        return cls(TimeType.FIX, TimeBound(day), TimeBound(day))

    @classmethod
    def termin(
        cls, earliest: TimeBound | None = None, latest: TimeBound | None = None
    ) -> OrderTime:
        return cls(TimeType.TERMIN, earliest, latest)

    @classmethod
    def eta(cls, day: date) -> OrderTime:
        return cls(TimeType.ETA, latest=TimeBound(day))

    @classmethod
    def to_be_agreed(cls) -> OrderTime:
        return cls(TimeType.TO_BE_AGREED)


@dataclass(frozen=True)
class TimeCheckResult:
    level: CheckLevel
    reason: TimeCheckReason
    # Whether the check is mandatory (D77): a missing or failing mandatory check affects the
    # overall status; a non-mandatory OPEN or RISK is shown as a note.
    mandatory: bool
    # When handling starts, in UTC (convert to the location's time zone for display): the given
    # planned handling, or arrival / Earliest, whichever is later.
    handling_start: datetime | None = None
    # How long the vehicle waits from arrival until handling starts.
    wait: timedelta | None = None
    # Latest clock time minus handling start (negative when late); only for a Latest with a time.
    slack: timedelta | None = None


def evaluate(
    order_time: OrderTime,
    arrival: datetime,
    location_tz: ZoneInfo,
    margin: timedelta = DEFAULT_MARGIN,
    planned_handling: datetime | None = None,
) -> TimeCheckResult:
    """Compare a Node's planned arrival (and planned handling, if set) with the order's time.

    Without `planned_handling` the vehicle is assumed to wait for Earliest.
    """
    _require_aware(arrival, "arrival")
    if planned_handling is not None:
        _require_aware(planned_handling, "planned_handling")
    if margin < timedelta(0):
        raise ValueError("margin must not be negative")
    t = order_time.time_type
    mandatory = t in (TimeType.FIX, TimeType.TERMIN)

    if t is TimeType.TO_BE_AGREED:
        return TimeCheckResult(CheckLevel.OPEN, TimeCheckReason.TIME_TO_BE_AGREED, mandatory=False)

    arrival_utc = _utc(arrival)
    earliest = (
        _utc(order_time.earliest.earliest_instant(location_tz))
        if order_time.earliest is not None
        else None
    )

    if planned_handling is not None:
        handling = _utc(planned_handling)
        if handling < arrival_utc:
            raise ValueError("planned_handling must not be before arrival")
    else:
        handling = max(arrival_utc, earliest) if earliest is not None else arrival_utc
    wait = handling - arrival_utc if handling > arrival_utc else None

    def result(
        level: CheckLevel, reason: TimeCheckReason, slack: timedelta | None = None
    ) -> TimeCheckResult:
        return TimeCheckResult(level, reason, mandatory, handling, wait, slack)

    if earliest is not None and handling < earliest:
        return result(CheckLevel.BLOCKED, TimeCheckReason.BEFORE_EARLIEST)

    last = order_time.latest
    slack: timedelta | None = None
    if last is not None:
        latest = _utc(last.latest_instant(location_tz))
        if last.at is not None:
            slack = latest - handling
        late = handling > latest if last.at is not None else handling >= latest
        if late:
            if t is TimeType.ETA:
                return result(CheckLevel.RISK, TimeCheckReason.AFTER_ETA)
            return result(CheckLevel.BLOCKED, TimeCheckReason.LATE, slack)
        if slack is not None and slack < margin:
            return result(CheckLevel.RISK, TimeCheckReason.WITHIN_MARGIN, slack)

    reason = TimeCheckReason.WAITS if wait is not None else TimeCheckReason.ON_TIME
    return result(CheckLevel.OK, reason, slack)
