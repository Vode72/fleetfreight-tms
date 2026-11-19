"""Order time types FIX, Termin, ETA and to be agreed (D80). Pure domain module.

An order carries a time type and a time separately for loading and for unloading. Plan Check
(D77, phase 5) compares a Node's planned time (arrival, or the planned handling time when the
vehicle waits) with that time through `evaluate`.

- FIX: one exact date; the customer has paid for delivery on that day. Strict both ways: an
  earlier day blocks (the receiver may have a full warehouse or cross-dock straight onto another
  trailer) and a later day blocks. The clock time is checked against the location's opening
  hours separately, so no margin applies.
- TERMIN: an agreed date and time or time window, e.g. 20.11. 14:00-16:00 (start, optional
  end). Arriving after the end (or after the single time) blocks the plan; arriving within the
  margin before it is a risk; arriving before the start is OK, the vehicle waits and the result
  says how long (Toni 19.11.2026).
- ETA: an estimated delivery date given to the customer. Not binding, so a later day is only a
  risk.
- TO_BE_AGREED: no time yet. A non-mandatory OPEN result: the trip can be planned and confirmed,
  and the time is filled in later.

FIX and ETA are dates and are compared on the location's local date.

Priority, most binding first, used for conflicts, ordering and optimisation: FIX, TERMIN, ETA,
TO_BE_AGREED.

The margin is a setting (default 30 minutes, D80); the caller passes it in.

All clock-time comparisons and differences are made in UTC: Python compares two datetimes that
share one tzinfo by wall clock, which is off by an hour across a daylight saving change.
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

# Time types given as a date, and those given as a clock time.
DATE_TYPES = frozenset({TimeType.FIX, TimeType.ETA})
CLOCK_TYPES = frozenset({TimeType.TERMIN})

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
    EARLY = "early"  # TERMIN: arrives before the window; the vehicle waits
    BEFORE_FIX_DATE = "before_fix_date"  # FIX: earlier day than agreed; not allowed
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

    FIX and ETA: `day` only. TERMIN: `start`, and `end` >= `start` or None for a single time.
    TO_BE_AGREED: nothing.
    """

    time_type: TimeType
    day: date | None = None
    start: datetime | None = None
    end: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("start", "end"):
            value = getattr(self, name)
            if value is not None:
                _require_aware(value, name)
        t = self.time_type
        if t in DATE_TYPES:
            if self.day is None:
                raise ValueError(f"{t} needs a date")
        elif self.day is not None:
            raise ValueError("only FIX and ETA have a date")
        if t not in CLOCK_TYPES and (self.start is not None or self.end is not None):
            raise ValueError(f"{t} has no start or end time")
        if t is TimeType.TERMIN:
            if self.start is None:
                raise ValueError("TERMIN needs a start")
            if self.end is not None and _utc(self.end) < _utc(self.start):
                raise ValueError("TERMIN end must not be before its start")

    @classmethod
    def fix(cls, day: date) -> OrderTime:
        return cls(TimeType.FIX, day=day)

    @classmethod
    def termin(cls, start: datetime, end: datetime | None = None) -> OrderTime:
        return cls(TimeType.TERMIN, start=start, end=end)

    @classmethod
    def eta(cls, day: date) -> OrderTime:
        return cls(TimeType.ETA, day=day)

    @classmethod
    def to_be_agreed(cls) -> OrderTime:
        return cls(TimeType.TO_BE_AGREED)

    @property
    def latest(self) -> datetime | None:
        """TERMIN: last acceptable arrival."""
        return self.end if self.end is not None else self.start


@dataclass(frozen=True)
class TimeCheckResult:
    level: CheckLevel
    reason: TimeCheckReason
    # Whether the check is mandatory (D77): a missing or failing mandatory check affects the
    # overall status; a non-mandatory OPEN is shown as a note.
    mandatory: bool
    # TERMIN: latest acceptable arrival minus planned arrival (negative when late).
    slack: timedelta | None = None
    # TERMIN: how long the vehicle waits before the window opens.
    early_by: timedelta | None = None
    # FIX and ETA: planned local date minus the agreed date, in days (negative = earlier).
    days_off: int | None = None


def evaluate(
    order_time: OrderTime,
    planned: datetime,
    location_tz: ZoneInfo,
    margin: timedelta = DEFAULT_MARGIN,
) -> TimeCheckResult:
    """Compare a Node's planned time with the order's time (D80)."""
    _require_aware(planned, "planned")
    if margin < timedelta(0):
        raise ValueError("margin must not be negative")
    t = order_time.time_type

    if t is TimeType.TO_BE_AGREED:
        return TimeCheckResult(CheckLevel.OPEN, TimeCheckReason.TIME_TO_BE_AGREED, mandatory=False)

    if t in DATE_TYPES:
        if order_time.day is None:  # guaranteed by OrderTime; narrows the type
            raise ValueError(f"{t} needs a date")
        days_off = (planned.astimezone(location_tz).date() - order_time.day).days
        if t is TimeType.FIX:
            if days_off < 0:
                return TimeCheckResult(
                    CheckLevel.BLOCKED,
                    TimeCheckReason.BEFORE_FIX_DATE,
                    mandatory=True,
                    days_off=days_off,
                )
            if days_off > 0:
                return TimeCheckResult(
                    CheckLevel.BLOCKED, TimeCheckReason.LATE, mandatory=True, days_off=days_off
                )
            return TimeCheckResult(
                CheckLevel.OK, TimeCheckReason.ON_TIME, mandatory=True, days_off=0
            )
        # ETA
        if days_off > 0:
            return TimeCheckResult(
                CheckLevel.RISK, TimeCheckReason.AFTER_ETA, mandatory=False, days_off=days_off
            )
        return TimeCheckResult(
            CheckLevel.OK, TimeCheckReason.ON_TIME, mandatory=False, days_off=days_off
        )

    # TERMIN
    if order_time.start is None or order_time.latest is None:  # guaranteed by OrderTime
        raise ValueError("TERMIN needs a time")
    planned_utc = _utc(planned)
    start = _utc(order_time.start)
    slack = _utc(order_time.latest) - planned_utc
    if slack < timedelta(0):
        return TimeCheckResult(
            CheckLevel.BLOCKED, TimeCheckReason.LATE, mandatory=True, slack=slack
        )
    early_by = start - planned_utc if planned_utc < start else None
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
