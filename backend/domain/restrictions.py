"""Countries, public holidays and road restrictions (phase 2B-3a, D84). Pure domain module.

Holds the allowed values and the structure rules shared by the database CHECK constraints and the
reference data loader. It holds NO legal values: limits, bans and holidays are reference data
with a source link and a check date per row (D84), and Plan Check evaluates them in phase 5.

Road restrictions
- A limit (weights, bridge, height, length, seasonal weight) has a value and its unit: kilograms
  for weights, millimetres for heights and lengths.
- A driving ban, an HCT route and an environmental zone have no value; an ADR tunnel restriction
  has a tunnel category B-E instead.
- Who it applies to: vehicles over a permissible gross weight (e.g. over 7.5 t), compared with the
  single vehicle or the whole combination; optionally any truck towing a trailer whatever its
  weight (Germany); ADR only; loaded or empty vehicles; and listed exemptions (e.g. perishable
  goods). Country-specific conditions of an exemption (lists of goods, distances) are in the note
  and are evaluated in phase 5.

Driving ban windows (local time of the country or region)
- A window applies on given weekdays, on public holidays, on the day before a public holiday, or
  on one calendar date (for countries that publish a yearly list of ban days).
- Optionally only within a yearly season (e.g. Saturdays in July and August), given as month and
  day; a season may run over the new year.
- A window stays within one day: start < end, or no end = until midnight. A ban from Saturday
  22:00 to Sunday 22:00 is two windows.
"""

from dataclasses import dataclass
from datetime import date, time
from enum import StrEnum


class TollSystem(StrEnum):
    NONE = "none"
    TIME_BASED = "time_based"  # vignette
    DISTANCE_BASED = "distance_based"


class RestrictionType(StrEnum):
    DRIVING_BAN = "driving_ban"
    AXLE_WEIGHT = "axle_weight"
    BOGIE_WEIGHT = "bogie_weight"
    GROSS_WEIGHT = "gross_weight"
    SEASONAL_WEIGHT = "seasonal_weight"  # e.g. spring thaw (kelirikko)
    BRIDGE = "bridge"
    HEIGHT = "height"
    LENGTH = "length"
    HCT_ROUTE = "hct_route"
    ADR_TUNNEL = "adr_tunnel"
    ENVIRONMENTAL_ZONE = "environmental_zone"


class LimitUnit(StrEnum):
    KG = "kg"
    MM = "mm"


class LoadState(StrEnum):
    ANY = "any"
    LOADED = "loaded"
    EMPTY = "empty"


class WeightBasis(StrEnum):
    """Which permissible gross weight a weight scope is compared with."""

    VEHICLE = "vehicle"  # the single vehicle (e.g. Germany: a truck over 7.5 t)
    COMBINATION = "combination"  # the vehicle or the whole combination (e.g. Poland over 12 t)


class SoloTractor(StrEnum):
    """Whether a tractor unit driving without a trailer falls under a driving ban (D85)."""

    EXEMPT = "exempt"  # e.g. Germany: a tractor without a semi-trailer is not a truck under the ban
    CONDITIONAL = "conditional"  # e.g. Italy: on the return trip or when collecting a trailer
    NOT_EXEMPT = "not_exempt"  # e.g. Poland: the tractor's own permissible weight counts


class Exemption(StrEnum):
    PERISHABLE_GOODS = "perishable_goods"
    LIVE_ANIMALS = "live_animals"
    COMBINED_TRANSPORT = "combined_transport"  # road leg to or from a rail terminal or port
    EMPTY_RUN = "empty_run"  # an empty run linked to an exempted transport
    OTHER = "other"  # explained in the note


class WindowKind(StrEnum):
    WEEKDAYS = "weekdays"
    PUBLIC_HOLIDAY = "public_holiday"
    DAY_BEFORE_HOLIDAY = "day_before_holiday"
    DATE = "date"  # one calendar day, for bans published as a yearly list of dates


ADR_TUNNEL_CATEGORIES = ("B", "C", "D", "E")

UNIT_BY_TYPE: dict[RestrictionType, LimitUnit] = {
    RestrictionType.AXLE_WEIGHT: LimitUnit.KG,
    RestrictionType.BOGIE_WEIGHT: LimitUnit.KG,
    RestrictionType.GROSS_WEIGHT: LimitUnit.KG,
    RestrictionType.SEASONAL_WEIGHT: LimitUnit.KG,
    RestrictionType.BRIDGE: LimitUnit.KG,
    RestrictionType.HEIGHT: LimitUnit.MM,
    RestrictionType.LENGTH: LimitUnit.MM,
}


def validate_restriction(
    restriction_type: RestrictionType,
    limit_value: int | None,
    limit_unit: LimitUnit | None,
    tunnel_category: str | None,
) -> None:
    """Raise ValueError unless the value fields fit the restriction type."""
    unit = UNIT_BY_TYPE.get(restriction_type)
    if unit is not None:
        if limit_value is None or limit_value <= 0:
            raise ValueError(f"{restriction_type} needs a positive limit value")
        if limit_unit is not unit:
            raise ValueError(f"{restriction_type} is given in {unit}")
    elif limit_value is not None or limit_unit is not None:
        raise ValueError(f"{restriction_type} has no limit value")
    if restriction_type is RestrictionType.ADR_TUNNEL:
        if tunnel_category not in ADR_TUNNEL_CATEGORIES:
            raise ValueError("ADR tunnel category must be B, C, D or E")
    elif tunnel_category is not None:
        raise ValueError("only an ADR tunnel restriction has a tunnel category")


def validate_period(valid_from: date, valid_until: date | None) -> None:
    if valid_until is not None and valid_until < valid_from:
        raise ValueError("valid_until must not be before valid_from")


def month_day(value: int) -> tuple[int, int]:
    """Split an MMDD season bound (e.g. 701 = 1 July) and check it is a real day."""
    month, day = divmod(value, 100)
    try:
        date(2028, month, day)  # a leap year, so 29 February is allowed
    except ValueError:
        raise ValueError(f"{value} is not a month and day (MMDD)") from None
    return month, day


@dataclass(frozen=True)
class BanWindow:
    kind: WindowKind
    start: time
    end: time | None = None  # None = until midnight
    weekdays: tuple[int, ...] = ()  # ISO weekdays 1 = Monday ... 7 = Sunday
    season_start: int | None = None  # MMDD
    season_end: int | None = None  # MMDD
    on_date: date | None = None  # kind DATE only

    def __post_init__(self) -> None:
        if (self.kind is WindowKind.DATE) != (self.on_date is not None):
            raise ValueError("a date window has exactly one date, and only it has one")
        if self.kind is WindowKind.DATE and self.season_start is not None:
            raise ValueError("a date window has no season")
        if self.end is not None and self.end <= self.start:
            raise ValueError("a window stays within one day: end after start, or no end")
        if self.kind is WindowKind.WEEKDAYS:
            if not self.weekdays:
                raise ValueError("a weekday window needs weekdays")
            if any(d < 1 or d > 7 for d in self.weekdays) or len(set(self.weekdays)) != len(
                self.weekdays
            ):
                raise ValueError("weekdays are distinct ISO numbers 1-7")
        elif self.weekdays:
            raise ValueError(f"a {self.kind} window has no weekdays")
        if (self.season_start is None) != (self.season_end is None):
            raise ValueError("a season needs both a start and an end")
        if self.season_start is not None and self.season_end is not None:
            month_day(self.season_start)
            month_day(self.season_end)
