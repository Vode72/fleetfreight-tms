from datetime import date

import pytest

from domain.qualifications import DriverQualificationType as Q
from domain.qualifications import (
    QualificationPeriod,
    add_months,
    adr_special_scopes_outlasting_basic,
    adr_special_scopes_without_valid_basic,
    current,
    expires_within,
    holds_licence_c,
    holds_valid,
    overlapping_periods,
    suggest_gdp_valid_until,
    suggest_valid_until,
    valid_on,
    validate_adr_qualifications,
)

TODAY = date(2026, 11, 18)


def P(qtype: Q, start: str, end: str) -> QualificationPeriod:
    return QualificationPeriod(qtype, date.fromisoformat(start), date.fromisoformat(end))


def test_period_rejects_reversed_dates_and_allows_single_day() -> None:
    with pytest.raises(ValueError):
        P(Q.GDP, "2026-02-02", "2026-02-01")
    assert P(Q.GDP, "2026-02-01", "2026-02-01").covers(date(2026, 2, 1))


def test_period_ends_are_inclusive() -> None:
    period = P(Q.GDP, "2026-01-01", "2026-12-31")
    assert period.covers(date(2026, 1, 1)) and period.covers(date(2026, 12, 31))
    assert not period.covers(date(2025, 12, 31)) and not period.covers(date(2027, 1, 1))


def test_expires_within() -> None:
    assert expires_within(date(2026, 12, 18), TODAY, 30)
    assert not expires_within(date(2026, 12, 19), TODAY, 30)
    assert expires_within(TODAY, TODAY, 0)
    assert not expires_within(date(2026, 11, 17), TODAY, 30)  # already expired


def test_valid_on_returns_periods_valid_that_day() -> None:
    old = P(Q.TACHOGRAPH_CARD, "2021-01-01", "2025-12-31")
    renewed = P(Q.TACHOGRAPH_CARD, "2026-01-01", "2030-12-31")
    gdp = P(Q.GDP, "2026-06-01", "2027-05-31")
    periods = [old, renewed, gdp]
    assert valid_on(periods, date(2025, 6, 1)) == [old]
    assert valid_on(periods, date(2025, 12, 31)) == [old]
    assert valid_on(periods, date(2026, 1, 1)) == [renewed]
    assert valid_on(periods, date(2026, 6, 1)) == [renewed, gdp]
    assert valid_on(periods, date(2031, 1, 1)) == []
    assert valid_on([], TODAY) == []


def test_current_is_the_valid_period_per_type_today() -> None:
    old = P(Q.TACHOGRAPH_CARD, "2021-01-01", "2025-12-31")
    renewed = P(Q.TACHOGRAPH_CARD, "2026-01-01", "2030-12-31")
    expired_only = P(Q.GDP, "2024-01-01", "2024-12-31")
    future = P(Q.ADR_BASIC, "2027-01-01", "2031-12-31")
    result = current([old, renewed, expired_only, future], TODAY)
    assert result == {Q.TACHOGRAPH_CARD: renewed}  # expired and future-only types are absent
    assert holds_valid([old, renewed], Q.TACHOGRAPH_CARD, TODAY)
    assert not holds_valid([old], Q.TACHOGRAPH_CARD, TODAY)


def test_overlapping_periods() -> None:
    a = P(Q.GDP, "2026-01-01", "2026-12-31")
    consecutive = P(Q.GDP, "2027-01-01", "2027-12-31")
    shares_a_day = P(Q.GDP, "2026-12-31", "2027-12-31")
    other_type = P(Q.ADR_BASIC, "2026-06-01", "2027-06-01")
    assert overlapping_periods([a, consecutive, other_type]) == []  # consecutive is fine
    assert overlapping_periods([a, shares_a_day]) == [(a, shares_a_day)]
    inside = P(Q.GDP, "2026-03-01", "2026-04-01")
    assert overlapping_periods([a, inside]) == [(a, inside)]


def test_ce_covers_c() -> None:
    c = P(Q.DRIVING_LICENCE_C, "2020-01-01", "2030-01-01")
    ce = P(Q.DRIVING_LICENCE_CE, "2020-01-01", "2030-01-01")
    assert holds_licence_c([c], TODAY)
    assert holds_licence_c([ce], TODAY)  # CE covers C
    assert not holds_licence_c([], TODAY)
    assert not holds_licence_c([P(Q.DRIVING_LICENCE_CE, "2010-01-01", "2026-11-17")], TODAY)
    assert not holds_licence_c([P(Q.ADR_BASIC, "2020-01-01", "2030-01-01")], TODAY)
    assert not holds_valid([c], Q.DRIVING_LICENCE_CE, TODAY)  # C does not cover CE


def test_special_scope_needs_a_basic_valid_the_same_day() -> None:
    basic = P(Q.ADR_BASIC, "2022-01-01", "2027-01-01")
    tank = P(Q.ADR_TANK, "2022-01-01", "2027-01-01")
    assert adr_special_scopes_without_valid_basic([basic, tank], TODAY) == []
    assert adr_special_scopes_without_valid_basic([tank], TODAY) == [Q.ADR_TANK]
    # basic expired, special scope still valid on the day
    old_basic = P(Q.ADR_BASIC, "2020-01-01", "2026-11-01")
    class1 = P(Q.ADR_CLASS1, "2022-01-01", "2027-01-01")
    assert adr_special_scopes_without_valid_basic([old_basic, class1], TODAY) == [Q.ADR_CLASS1]
    # ...but on a day when the basic was valid it is fine (history)
    assert adr_special_scopes_without_valid_basic([old_basic, class1], date(2025, 1, 1)) == []
    # a special period not valid on the day is not a violation
    assert (
        adr_special_scopes_without_valid_basic([P(Q.ADR_CLASS7, "2020-01-01", "2021-01-01")], TODAY)
        == []
    )
    assert adr_special_scopes_without_valid_basic([], TODAY) == []


def test_basic_renewal_keeps_the_special_scope_valid() -> None:
    first = P(Q.ADR_BASIC, "2021-01-01", "2025-12-31")
    renewed = P(Q.ADR_BASIC, "2026-01-01", "2030-12-31")
    tank = P(Q.ADR_TANK, "2026-01-01", "2030-12-31")
    assert adr_special_scopes_without_valid_basic([first, renewed, tank], TODAY) == []
    assert adr_special_scopes_outlasting_basic([first, renewed, tank]) == []


def test_special_scope_must_not_outlast_basic() -> None:
    basic = P(Q.ADR_BASIC, "2022-01-01", "2027-01-01")
    ok = P(Q.ADR_TANK, "2022-01-01", "2027-01-01")
    longer = P(Q.ADR_CLASS1, "2022-06-01", "2027-01-02")
    shorter = P(Q.ADR_CLASS7, "2022-06-01", "2026-06-01")
    assert adr_special_scopes_outlasting_basic([basic, ok, shorter]) == []
    assert adr_special_scopes_outlasting_basic([basic, ok, longer, shorter]) == [longer]
    orphan = P(Q.ADR_TANK, "2022-01-01", "2027-01-01")
    assert adr_special_scopes_outlasting_basic([orphan]) == [orphan]  # no basic at all
    assert adr_special_scopes_outlasting_basic([basic]) == []


def test_validate_adr_qualifications() -> None:
    basic = P(Q.ADR_BASIC, "2022-01-01", "2027-01-01")
    validate_adr_qualifications([], TODAY)
    validate_adr_qualifications([basic, P(Q.ADR_TANK, "2022-01-01", "2027-01-01")], TODAY)
    with pytest.raises(ValueError, match="adr_tank needs an adr_basic valid on the same day"):
        validate_adr_qualifications([P(Q.ADR_TANK, "2022-01-01", "2027-01-01")], TODAY)
    with pytest.raises(ValueError, match=r"adr_class7 .* must not outlast"):
        validate_adr_qualifications([basic, P(Q.ADR_CLASS7, "2022-01-01", "2028-01-01")], TODAY)


# --- default validity (D69)


def test_add_months_clamps_to_month_end() -> None:
    assert add_months(date(2026, 1, 15), 1) == date(2026, 2, 15)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # leap year
    assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)
    assert add_months(date(2026, 3, 1), 12) == date(2027, 3, 1)
    assert add_months(date(2026, 3, 1), 0) == date(2026, 3, 1)


def test_suggested_valid_until_is_the_last_valid_day() -> None:
    assert suggest_valid_until(date(2026, 1, 15), 1) == date(2026, 2, 14)
    assert suggest_valid_until(date(2026, 1, 1), 12) == date(2026, 12, 31)
    assert suggest_gdp_valid_until(date(2026, 3, 10), 12) == date(2027, 3, 9)
    assert suggest_gdp_valid_until(date(2026, 3, 10), 24) == date(2028, 3, 9)
    with pytest.raises(ValueError):
        suggest_valid_until(TODAY, 0)
