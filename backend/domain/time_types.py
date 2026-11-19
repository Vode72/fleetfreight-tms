"""Order time types FIX, Termin, ETA and to be agreed (D80). Pure domain module.

An order carries a time type and a time separately for loading and for unloading. Plan Check
(D77, phase 5) compares a Node's planned arrival with that time through `evaluate`.

- FIX: one exact time; the customer has paid for an exact delivery. Arriving late blocks the
  plan; arriving within the margin before the time is a risk.
- TERMIN: an agreed time or time window (start, optional end). Arriving after the end (or after
  the single time) blocks the plan; arriving within the margin before it is a risk.
- ETA: an estimated delivery date given to the customer. Not binding, so a later planned date is
  only a risk. Date only: the planned arrival is compared on the location's local date.
- TO_BE_AGREED: no time yet. A non-mandatory OPEN result: the trip can be planned and confirmed,
  and the time is filled in later.

Arriving before a FIX time or a TERMIN window is OK (the vehicle waits); the result says how
early, so a view can show the waiting time (Toni 19.11.2026).

Priority, most binding first, used for conflicts, ordering and optimisation: FIX, TERMIN, ETA,
TO_BE_AGREED.

The margin is a setting (default 30 minutes, D80); the caller passes it in.

All comparisons and differences are made in UTC: Python compares two datetimes that share one
tzinfo by wall clock, which is off by an hour across a daylight saving change.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
    EARLY = "early"  # arrives before the time or window; the vehicle waits
    WITHIN_MARGIN = "within_margin"
    LATE = "late"
    AFTER_ETA = "after_eta"
    TIME_TO_BE_AGREED = "time_to_be_agreed"


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


@dataclass(frozen=True)
class OrderTime:
    """The time of one loading or unloading on an order. Build it with the class methods.

    FIX: `start` = `end`. TERMIN: `start`, and `end` >= `start` or None for a single time.
    ETA: `eta_date` only. TO_BE_AGREED: nothing.
    """

    time_type: TimeType
    start: datetime | None = None
    end: datetime | None = None
    eta_date: date | None = None

    def __post_init__(self) -> None:
        for name in ("start", "end"):
            value = getattr(self, name)
            if value is not None:
                _require_aware(value, name)
        t = self.time_type
        if t is TimeType.FIX:
            if self.start is None or self.end is None or _utc(self.start) != _utc(self.end):
                raise ValueError("FIX needs one time: start and end equal")
        elif t is TimeType.TERMIN:
            if self.start is None:
                raise ValueError("TERMIN needs a start")
            if self.end is not None and _utc(self.end) < _utc(self.start):
                raise ValueError("TERMIN end must not be before its start")
        elif t is TimeType.ETA and self.eta_date is None:
            raise ValueError("ETA needs a date")
        if t is not TimeType.ETA and self.eta_date is not None:
            raise ValueError("only ETA has a date")
        if t in (TimeType.ETA, TimeType.TO_BE_AGREED) and (
            self.start is not None or self.end is not None
        ):
            raise ValueError(f"{t} has no start or end time")

    @classmethod
    def fix(cls, at: datetime) -> OrderTime:
        return cls(TimeType.FIX, start=at, end=at)

    @classmethod
    def termin(cls, start: datetime, end: datetime | None = None) -> OrderTime:
        return cls(TimeType.TERMIN, start=start, end=end)

    @classmethod
    def eta(cls, day: date) -> OrderTime:
        return cls(TimeType.ETA, eta_date=day)

    @classmethod
    def to_be_agreed(cls) -> OrderTime:
        return cls(TimeType.TO_BE_AGREED)

    @property
    def latest(self) -> datetime | None:
        """Last acceptable arrival for FIX and TERMIN."""
        return self.end if self.end is not None else self.start


@dataclass(frozen=True)
class TimeCheckResult:
    level: CheckLevel
    reason: TimeCheckReason
    # Whether the check is mandatory (D77): a missing or failing mandatory check affects the
    # overall status; a non-mandatory OPEN is shown as a note.
    mandatory: bool
    # FIX and TERMIN: latest acceptable arrival minus planned arrival (negative when late).
    slack: timedelta | None = None
    # FIX and TERMIN: how long the vehicle waits before the time or window opens.
    early_by: timedelta | None = None


def evaluate(
    order_time: OrderTime,
    planned_arrival: datetime,
    location_tz: ZoneInfo,
    margin: timedelta = DEFAULT_MARGIN,
) -> TimeCheckResult:
    """Compare a Node's planned arrival with the order's time (D80)."""
    _require_aware(planned_arrival, "planned_arrival")
    if margin < timedelta(0):
        raise ValueError("margin must not be negative")
    t = order_time.time_type

    if t is TimeType.TO_BE_AGREED:
        return TimeCheckResult(CheckLevel.OPEN, TimeCheckReason.TIME_TO_BE_AGREED, mandatory=False)

    if t is TimeType.ETA:
        if order_time.eta_date is None:  # guaranteed by OrderTime; narrows the type
            raise ValueError("ETA needs a date")
        planned_day = planned_arrival.astimezone(location_tz).date()
        if planned_day > order_time.eta_date:
            return TimeCheckResult(CheckLevel.RISK, TimeCheckReason.AFTER_ETA, mandatory=False)
        return TimeCheckResult(CheckLevel.OK, TimeCheckReason.ON_TIME, mandatory=False)

    # FIX and TERMIN
    if order_time.start is None or order_time.latest is None:  # guaranteed by OrderTime
        raise ValueError(f"{t} needs a time")
    planned = _utc(planned_arrival)
    start = _utc(order_time.start)
    slack = _utc(order_time.latest) - planned
    if slack < timedelta(0):
        return TimeCheckResult(
            CheckLevel.BLOCKED, TimeCheckReason.LATE, mandatory=True, slack=slack
        )
    early_by = start - planned if planned < start else None
    if slack < margin:
        return TimeCheckResult(
            CheckLevel.RISK,
            TimeCheckReason.WITHIN_MARGIN,
            mandatory=True,
            slack=slack,
            early_by=early_by,
        )
    reason = TimeCheckReason.EARLY if early_by is not None else TimeCheckReason.ON_TIME
    return TimeCheckResult(CheckLevel.OK, reason, mandatory=True, slack=slack, early_by=early_by)
