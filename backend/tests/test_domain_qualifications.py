from datetime import date

import pytest

from domain.qualifications import (
    DriverQualificationType as Q,
)
from domain.qualifications import (
    adr_special_scopes_outlasting_basic,
    adr_special_scopes_without_valid_basic,
    expires_within,
    holds_licence_c,
    holds_valid,
    is_valid_on,
    validate_adr_qualifications,
)

TODAY = date(2026, 11, 18)


def test_last_day_is_inclusive() -> None:
    assert is_valid_on(date(2026, 11, 18), TODAY)
    assert not is_valid_on(date(2026, 11, 17), TODAY)


def test_expires_within() -> None:
    assert expires_within(date(2026, 12, 18), TODAY, 30)
    assert not expires_within(date(2026, 12, 19), TODAY, 30)
    assert expires_within(TODAY, TODAY, 0)
    assert not expires_within(date(2026, 11, 17), TODAY, 30)  # already expired


# --- licence categories and ADR scopes
def test_ce_covers_c() -> None:
    assert holds_licence_c({Q.DRIVING_LICENCE_C: date(2027, 1, 1)}, TODAY)
    assert holds_licence_c({Q.DRIVING_LICENCE_CE: date(2027, 1, 1)}, TODAY)  # CE covers C
    assert not holds_licence_c({}, TODAY)
    assert not holds_licence_c({Q.DRIVING_LICENCE_CE: date(2026, 11, 17)}, TODAY)  # expired
    assert not holds_licence_c({Q.ADR_BASIC: date(2027, 1, 1)}, TODAY)


def test_c_does_not_cover_ce() -> None:
    assert not holds_valid({Q.DRIVING_LICENCE_C: date(2027, 1, 1)}, Q.DRIVING_LICENCE_CE, TODAY)


def test_special_scope_needs_valid_basic() -> None:
    ok = {Q.ADR_BASIC: date(2027, 1, 1), Q.ADR_TANK: date(2027, 1, 1)}
    assert adr_special_scopes_without_valid_basic(ok, TODAY) == []
    assert adr_special_scopes_without_valid_basic({Q.ADR_TANK: date(2027, 1, 1)}, TODAY) == [
        Q.ADR_TANK
    ]
    expired_basic = {Q.ADR_BASIC: date(2026, 11, 1), Q.ADR_CLASS1: date(2027, 1, 1)}
    assert adr_special_scopes_without_valid_basic(expired_basic, TODAY) == [Q.ADR_CLASS1]
    # an already expired special scope is not a violation here
    assert adr_special_scopes_without_valid_basic({Q.ADR_CLASS7: date(2026, 1, 1)}, TODAY) == []
    assert adr_special_scopes_without_valid_basic({}, TODAY) == []


def test_special_scope_must_not_outlast_basic() -> None:
    basic = date(2027, 1, 1)
    assert adr_special_scopes_outlasting_basic({Q.ADR_BASIC: basic, Q.ADR_TANK: basic}) == []
    assert adr_special_scopes_outlasting_basic(
        {Q.ADR_BASIC: basic, Q.ADR_TANK: date(2027, 1, 2), Q.ADR_CLASS7: date(2026, 6, 1)}
    ) == [Q.ADR_TANK]
    assert adr_special_scopes_outlasting_basic({Q.ADR_CLASS1: basic}) == [Q.ADR_CLASS1]
    assert adr_special_scopes_outlasting_basic({Q.ADR_BASIC: basic}) == []


def test_validate_adr_qualifications() -> None:
    basic = date(2027, 1, 1)
    validate_adr_qualifications({}, TODAY)
    validate_adr_qualifications({Q.ADR_BASIC: basic, Q.ADR_TANK: basic}, TODAY)
    with pytest.raises(ValueError, match="adr_tank needs a valid adr_basic"):
        validate_adr_qualifications({Q.ADR_TANK: basic}, TODAY)
    with pytest.raises(ValueError, match="adr_class7 must not outlast"):
        validate_adr_qualifications({Q.ADR_BASIC: basic, Q.ADR_CLASS7: date(2028, 1, 1)}, TODAY)
