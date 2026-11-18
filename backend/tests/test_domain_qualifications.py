from datetime import date

from domain.qualifications import expires_within, is_valid_on

TODAY = date(2026, 11, 18)


def test_last_day_is_inclusive() -> None:
    assert is_valid_on(date(2026, 11, 18), TODAY)
    assert not is_valid_on(date(2026, 11, 17), TODAY)


def test_expires_within() -> None:
    assert expires_within(date(2026, 12, 18), TODAY, 30)
    assert not expires_within(date(2026, 12, 19), TODAY, 30)
    assert expires_within(TODAY, TODAY, 0)
    assert not expires_within(date(2026, 11, 17), TODAY, 30)  # already expired
