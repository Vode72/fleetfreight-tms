"""Driver qualifications (R6). Pure domain module.

Vehicle and equipment eligibility (ADR approval, GDP temperature mapping, tail lift) comes in
its own table in phase 2B-2, with its own foreign keys.
"""

from collections.abc import Mapping
from datetime import date, timedelta
from enum import StrEnum


class DriverQualificationType(StrEnum):
    ADR_BASIC = "adr_basic"
    ADR_TANK = "adr_tank"
    ADR_CLASS1 = "adr_class1"
    ADR_CLASS7 = "adr_class7"
    DRIVING_LICENCE_C = "driving_licence_c"
    DRIVING_LICENCE_CE = "driving_licence_ce"
    PROFESSIONAL_COMPETENCE = "professional_competence"
    TACHOGRAPH_CARD = "tachograph_card"
    GDP = "gdp"


def is_valid_on(valid_until: date, day: date) -> bool:
    """Valid through the whole of `valid_until` (the last day of validity is inclusive)."""
    return day <= valid_until


def expires_within(valid_until: date, today: date, days: int) -> bool:
    """True when still valid today but the last valid day is at most `days` days away."""
    return today <= valid_until <= today + timedelta(days=days)


# A driver's qualifications as {type: valid_until} (one record per type, as in the table).
Qualifications = Mapping[DriverQualificationType, date]

ADR_SPECIAL_SCOPES: tuple[DriverQualificationType, ...] = (
    DriverQualificationType.ADR_TANK,
    DriverQualificationType.ADR_CLASS1,
    DriverQualificationType.ADR_CLASS7,
)


def holds_valid(quals: Qualifications, qtype: DriverQualificationType, day: date) -> bool:
    valid_until = quals.get(qtype)
    return valid_until is not None and is_valid_on(valid_until, day)


def holds_licence_c(quals: Qualifications, day: date) -> bool:
    """Category CE covers category C (a CE licence entitles the holder to drive C vehicles)."""
    return holds_valid(quals, DriverQualificationType.DRIVING_LICENCE_C, day) or holds_valid(
        quals, DriverQualificationType.DRIVING_LICENCE_CE, day
    )


def adr_special_scopes_without_valid_basic(
    quals: Qualifications, day: date
) -> list[DriverQualificationType]:
    """Special scopes (tank, class 1, class 7) that are valid on `day` while adr_basic is not.

    A special-scope training builds on the basic ADR certificate, so it counts only together
    with a valid adr_basic.
    """
    if holds_valid(quals, DriverQualificationType.ADR_BASIC, day):
        return []
    return [t for t in ADR_SPECIAL_SCOPES if holds_valid(quals, t, day)]


def adr_special_scopes_outlasting_basic(quals: Qualifications) -> list[DriverQualificationType]:
    """Special scopes whose validity ends after the adr_basic validity (or without adr_basic).

    The special-scope validity cannot be longer than the basic certificate's.
    """
    basic = quals.get(DriverQualificationType.ADR_BASIC)
    return [t for t in ADR_SPECIAL_SCOPES if t in quals and (basic is None or quals[t] > basic)]


def validate_adr_qualifications(quals: Qualifications, day: date) -> None:
    """Raise ValueError when the ADR records of a driver break the two rules above.

    Reservation: the exact rules (validity periods, renewal, what a special scope requires) are to
    be checked against ADR section 8.2.2.8 before phase 5 (Plan Check); this is the modelled
    simplification until then.
    """
    problems = [
        f"{t.value} needs a valid adr_basic"
        for t in adr_special_scopes_without_valid_basic(quals, day)
    ] + [
        f"{t.value} must not outlast adr_basic" for t in adr_special_scopes_outlasting_basic(quals)
    ]
    if problems:
        raise ValueError("; ".join(problems))
