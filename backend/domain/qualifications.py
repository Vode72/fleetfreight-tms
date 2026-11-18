"""Driver qualifications (R6). Pure domain module.

Vehicle and equipment eligibility (ADR approval, GDP temperature mapping, tail lift) comes in
its own table in phase 2B-2, with its own foreign keys.
"""

from datetime import date, timedelta
from enum import StrEnum


class DriverQualificationType(StrEnum):
    ADR_BASIC = "adr_basic"
    ADR_TANK = "adr_tank"
    ADR_CLASS1 = "adr_class1"
    ADR_CLASS7 = "adr_class7"
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
