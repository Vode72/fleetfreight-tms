"""Driver qualifications with validity history (R6, D67). Pure domain module.

A qualification is a *period*: type, valid_from and valid_until (both inclusive). A driver can
hold several periods of the same type one after another (an expired one and its renewal), but
never overlapping ones; the database enforces the same with an exclusion constraint.

Vehicle and equipment eligibility (ADR approval, GDP temperature mapping, tail lift) comes in
its own table in phase 2B-2, with its own foreign keys.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True)
class QualificationPeriod:
    type: DriverQualificationType
    valid_from: date
    valid_until: date

    def __post_init__(self) -> None:
        if self.valid_from > self.valid_until:
            raise ValueError("valid_from must not be after valid_until")

    def covers(self, day: date) -> bool:
        """Both ends are inclusive: valid through the whole of valid_until."""
        return self.valid_from <= day <= self.valid_until

    def overlaps(self, other: QualificationPeriod) -> bool:
        """Same type and a shared day (a period ending the day another starts overlaps)."""
        return (
            self.type is other.type
            and self.valid_from <= other.valid_until
            and other.valid_from <= self.valid_until
        )


def expires_within(valid_until: date, today: date, days: int) -> bool:
    """True when still valid today but the last valid day is at most `days` days away."""
    return today <= valid_until <= today + timedelta(days=days)


def add_months(day: date, months: int) -> date:
    """`day` plus whole months; the day of month is clamped to the length of the target month."""
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    # Last day of the target month: first day of the next month minus one day.
    next_first = date(year + (month == 12), month % 12 + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


def suggest_valid_until(valid_from: date, months: int) -> date:
    """Last valid day for a record that is valid for `months` months from `valid_from`.

    A suggestion only (the planner decides). One month from 15 Jan ends on 14 Feb.
    """
    if months < 1:
        raise ValueError("months must be at least 1")
    return add_months(valid_from, months) - timedelta(days=1)


def suggest_gdp_valid_until(valid_from: date, default_months: int) -> date:
    """valid_until suggestion for a GDP training record.

    `default_months` comes from the setting GDP_TRAINING_DEFAULT_VALIDITY_MONTHS (default 12).
    The default is the company's own practice, not a regulatory period.
    """
    return suggest_valid_until(valid_from, default_months)


def valid_on(qualifications: Iterable[QualificationPeriod], day: date) -> list[QualificationPeriod]:
    """The periods that are valid on `day`."""
    return [q for q in qualifications if q.covers(day)]


def current(
    qualifications: Iterable[QualificationPeriod], today: date
) -> dict[DriverQualificationType, QualificationPeriod]:
    """The valid period per type today; types with no valid period today are absent.

    Periods of one type do not overlap, so at most one period per type is valid on a day.
    """
    return {q.type: q for q in valid_on(qualifications, today)}


def holds_valid(
    qualifications: Iterable[QualificationPeriod], qtype: DriverQualificationType, day: date
) -> bool:
    return any(q.type is qtype for q in valid_on(qualifications, day))


def overlapping_periods(
    qualifications: Sequence[QualificationPeriod],
) -> list[tuple[QualificationPeriod, QualificationPeriod]]:
    """Pairs of same-type periods that share a day (mirrors the database exclusion)."""
    return [
        (a, b)
        for i, a in enumerate(qualifications)
        for b in qualifications[i + 1 :]
        if a.overlaps(b)
    ]


def holds_licence_c(qualifications: Iterable[QualificationPeriod], day: date) -> bool:
    """Category CE covers category C (a CE licence entitles the holder to drive C vehicles)."""
    periods = list(qualifications)
    return holds_valid(periods, DriverQualificationType.DRIVING_LICENCE_C, day) or holds_valid(
        periods, DriverQualificationType.DRIVING_LICENCE_CE, day
    )


ADR_SPECIAL_SCOPES: tuple[DriverQualificationType, ...] = (
    DriverQualificationType.ADR_TANK,
    DriverQualificationType.ADR_CLASS1,
    DriverQualificationType.ADR_CLASS7,
)


def adr_special_scopes_without_valid_basic(
    qualifications: Iterable[QualificationPeriod], day: date
) -> list[DriverQualificationType]:
    """Special scopes (tank, class 1, class 7) valid on `day` while adr_basic is not valid that day.

    A special scope builds on the basic ADR certificate, so it counts only on days when an
    adr_basic period is valid as well.
    """
    periods = list(qualifications)
    if holds_valid(periods, DriverQualificationType.ADR_BASIC, day):
        return []
    return [t for t in ADR_SPECIAL_SCOPES if holds_valid(periods, t, day)]


def adr_special_scopes_outlasting_basic(
    qualifications: Iterable[QualificationPeriod],
) -> list[QualificationPeriod]:
    """Special-scope periods that end after the adr_basic period valid on their first day.

    The special scope cannot be valid longer than the basic certificate it rests on. A special
    period starting when no adr_basic is valid is reported as well.
    """
    periods = list(qualifications)
    result: list[QualificationPeriod] = []
    for special in (p for p in periods if p.type in ADR_SPECIAL_SCOPES):
        basics = [
            p
            for p in valid_on(periods, special.valid_from)
            if p.type is DriverQualificationType.ADR_BASIC
        ]
        if not basics or special.valid_until > basics[0].valid_until:
            result.append(special)
    return result


def validate_adr_qualifications(qualifications: Iterable[QualificationPeriod], day: date) -> None:
    """Raise ValueError when the ADR periods of a driver break the two rules above.

    Reservation: the exact rules (validity periods, renewal, what a special scope requires) are to
    be checked against ADR section 8.2.2.8 before phase 5 (Plan Check); this is the modelled
    simplification until then.
    """
    periods = list(qualifications)
    problems = [
        f"{t.value} needs an adr_basic valid on the same day"
        for t in adr_special_scopes_without_valid_basic(periods, day)
    ] + [
        f"{p.type.value} ({p.valid_from}..{p.valid_until}) must not outlast adr_basic"
        for p in adr_special_scopes_outlasting_basic(periods)
    ]
    if problems:
        raise ValueError("; ".join(problems))
