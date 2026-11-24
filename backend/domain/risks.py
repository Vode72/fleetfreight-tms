"""Cargo crime risk and border waiting times (2B-3e, D95). Pure domain module.

Risk is planning information, not a verdict: the system shows it and Plan Check (phase 5) warns,
the traffic planner decides (rule 8). Missing risk data is "unknown", never "low".

The allowed values are stored in the database as CHECK constraints (db/models.py and the
migration); tests/test_domain_risks.py keeps both in step.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from statistics import median
from zoneinfo import ZoneInfo

RISK_LEVELS: tuple[int, ...] = (1, 2, 3, 4, 5)
_COUNTRY_RE = re.compile(r"[A-Z]{2}")
_REGION_RE = re.compile(r"[A-Z]{2}-[A-Z0-9]{1,3}")
DEMO_WAIT_NOTE = "Invented demo value, not a measurement."


class RiskSourceType(StrEnum):
    # Classified from published data; the row links to it.
    DATA = "data"
    # A planner's or expert's judgement; the row states its basis.
    EXPERT_ESTIMATE = "expert_estimate"


class WaitSourceType(StrEnum):
    MANUAL = "manual"  # a planner or driver reported it
    OFFICIAL_FEED = "official_feed"  # an authority's published waiting time
    HISTORICAL_AVG = "historical_avg"  # an average published for a weekday and hour
    DEMO = "demo"  # invented for the demo, never mixed with real values


class WaitDirection(StrEnum):
    # Relative to the crossing's own country (D92: the location lies in its own country).
    ENTRY = "entry"
    EXIT = "exit"


@dataclass(frozen=True)
class RiskLevelSettings:
    """How a country's level is computed from reported incidents per month.

    `thresholds` are the lowest monthly averages of levels 2, 3, 4 and 5. The defaults are demo
    settings, not an industry standard: every company tunes them (D95).
    """

    window_months: int = 12
    min_months: int = 3
    thresholds: tuple[int, int, int, int] = (10, 40, 100, 200)

    def __post_init__(self) -> None:
        if not 1 <= self.min_months <= self.window_months:
            raise ValueError("min_months must be between 1 and window_months")
        if any(t <= 0 for t in self.thresholds) or list(self.thresholds) != sorted(
            set(self.thresholds)
        ):
            raise ValueError("thresholds must be positive and strictly increasing")


@dataclass(frozen=True)
class CountryRisk:
    country: str
    # None = unknown: too few months in which the country was reported.
    level: int | None
    months_used: int
    monthly_average: Decimal | None


def month_start(value: date) -> date:
    return value.replace(day=1)


def _months_back(month: date, count: int) -> date:
    index = month.year * 12 + month.month - 1 - count
    return date(index // 12, index % 12 + 1, 1)


def validate_report_month(value: date) -> date:
    """A monthly report is stored by the first day of its month."""
    if value.day != 1:
        raise ValueError("a report month is stored as the first day of the month")
    return value


def validate_incident_count(value: int) -> int:
    if value < 0:
        raise ValueError("an incident count must not be negative")
    return value


def level_for_average(average: Decimal, settings: RiskLevelSettings) -> int:
    return 1 + sum(1 for threshold in settings.thresholds if average >= threshold)


def country_risk(
    country: str,
    reports: Mapping[date, Mapping[str, int]],
    as_of: date,
    settings: RiskLevelSettings | None = None,
) -> CountryRisk:
    """A country's level from the monthly reports that were read, keyed by report month.

    Only completed months before `as_of` inside the window count. A month whose report was read
    but does not name the country is skipped, not counted as zero: the published reports list
    the highest countries only, so a missing country is unknown for that month (D95). The counts
    are reported incidents, which also follow market size and reporting habits, not risk per km.
    """
    settings = settings or RiskLevelSettings()
    current = month_start(as_of)
    first = _months_back(current, settings.window_months)
    counts = [
        report[country]
        for month, report in reports.items()
        if first <= validate_report_month(month) < current and country in report
    ]
    if len(counts) < settings.min_months:
        return CountryRisk(country, None, len(counts), None)
    average = (Decimal(sum(counts)) / len(counts)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return CountryRisk(country, level_for_average(average, settings), len(counts), average)


def validate_risk_area(
    *,
    country: str,
    region: str | None,
    road_ref: str | None,
    level: int,
    source_type: RiskSourceType,
    basis: str,
    source_url: str | None,
    valid_from: date,
    valid_until: date | None,
) -> None:
    """Mirrors the CHECK constraints of risk_areas."""
    if not _COUNTRY_RE.fullmatch(country):
        raise ValueError("country must be an ISO 3166-1 alpha-2 code")
    if region is not None and (not _REGION_RE.fullmatch(region) or region[:2] != country):
        raise ValueError("region must be an ISO 3166-2 code of the same country")
    if road_ref is not None and not road_ref.strip():
        raise ValueError("road_ref must not be blank")
    if level not in RISK_LEVELS:
        raise ValueError("risk level must be 1-5")
    if not basis.strip():
        raise ValueError("every risk area states how its level was classified")
    if source_url is not None and not source_url.startswith("https://"):
        raise ValueError("source_url must be an https link")
    if source_type is RiskSourceType.DATA and source_url is None:
        raise ValueError("a data-based risk area needs its source link")
    if valid_until is not None and valid_until < valid_from:
        raise ValueError("valid_until must not be before valid_from")


@dataclass(frozen=True)
class RiskArea:
    country: str
    region: str | None
    road_ref: str | None
    level: int
    valid_from: date
    valid_until: date | None

    def applies(self, country: str, region: str | None, road_ref: str | None, day: date) -> bool:
        """A country-wide row covers every region and road; a region row every road in it."""
        if self.country != country or day < self.valid_from:
            return False
        if self.valid_until is not None and day > self.valid_until:
            return False
        if self.region is not None and self.region != region:
            return False
        return self.road_ref is None or self.road_ref == road_ref


def effective_risk_level(
    country_level: int | None,
    areas: Iterable[RiskArea],
    *,
    country: str,
    region: str | None,
    road_ref: str | None,
    day: date,
) -> int | None:
    """The highest level of the country and every matching area (D95: the higher level wins).

    A low area never lowers a high country. None = nothing known, which Plan Check shows as
    unknown, not as low risk.
    """
    levels = [a.level for a in areas if a.applies(country, region, road_ref, day)]
    if country_level is not None:
        levels.append(country_level)
    return max(levels) if levels else None


# --- Border waiting times -------------------------------------------------------------------


def validate_wait_observation(
    *,
    observed_at: datetime,
    wait_minutes: int,
    source_type: WaitSourceType,
    source_url: str | None,
    note: str | None,
) -> None:
    """Mirrors the CHECK constraints of border_wait_observations."""
    if observed_at.tzinfo is None:
        raise ValueError("observed_at needs a time zone")
    if wait_minutes < 0:
        raise ValueError("a waiting time must not be negative")
    if source_url is not None and not source_url.startswith("https://"):
        raise ValueError("source_url must be an https link")
    if (
        source_type in (WaitSourceType.OFFICIAL_FEED, WaitSourceType.HISTORICAL_AVG)
        and source_url is None
    ):
        raise ValueError("a published waiting time needs its source link")
    if source_type is WaitSourceType.DEMO and note != DEMO_WAIT_NOTE:
        raise ValueError(f"a demo observation carries the note {DEMO_WAIT_NOTE!r}")


@dataclass(frozen=True)
class WaitObservation:
    observed_at: datetime
    direction: WaitDirection
    wait_minutes: int
    source_type: WaitSourceType


@dataclass(frozen=True)
class WaitEstimate:
    minutes: int
    sample_size: int
    # True = only invented demo values were available; the UI labels it "Invented demo value".
    is_demo: bool


def expected_wait(
    observations: Sequence[WaitObservation],
    *,
    direction: WaitDirection,
    at: datetime,
    time_zone: str,
) -> WaitEstimate | None:
    """Expected heavy-traffic wait at a moment: the median of the observations made on the same
    weekday and in the same local hour at the crossing. None = no observation for that slot.

    Demo values are never mixed with real ones: if any real observation matches, the demo ones
    are ignored.
    """
    if at.tzinfo is None:
        raise ValueError("the moment needs a time zone")
    zone = ZoneInfo(time_zone)
    local = at.astimezone(zone)
    slot = [
        o
        for o in observations
        if o.direction is direction
        and (seen := o.observed_at.astimezone(zone)).weekday() == local.weekday()
        and seen.hour == local.hour
    ]
    real = [o for o in slot if o.source_type is not WaitSourceType.DEMO]
    chosen = real or slot
    if not chosen:
        return None
    middle = Decimal(str(median(o.wait_minutes for o in chosen)))
    return WaitEstimate(
        int(middle.quantize(Decimal(1), ROUND_HALF_UP)), len(chosen), is_demo=not real
    )
