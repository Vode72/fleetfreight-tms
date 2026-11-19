from datetime import date, time

import pytest

from domain.restrictions import (
    ADR_TUNNEL_CATEGORIES,
    UNIT_BY_TYPE,
    BanWindow,
    LimitUnit,
    RestrictionType,
    WindowKind,
    month_day,
    validate_period,
    validate_restriction,
)

VALUELESS = [
    RestrictionType.DRIVING_BAN,
    RestrictionType.HCT_ROUTE,
    RestrictionType.ENVIRONMENTAL_ZONE,
]


@pytest.mark.parametrize(("restriction_type", "unit"), list(UNIT_BY_TYPE.items()))
def test_limits_need_a_positive_value_in_their_unit(
    restriction_type: RestrictionType, unit: LimitUnit
) -> None:
    validate_restriction(restriction_type, 11500, unit, None)
    with pytest.raises(ValueError, match="positive"):
        validate_restriction(restriction_type, None, unit, None)
    with pytest.raises(ValueError, match="positive"):
        validate_restriction(restriction_type, 0, unit, None)
    other = LimitUnit.MM if unit is LimitUnit.KG else LimitUnit.KG
    with pytest.raises(ValueError, match="given in"):
        validate_restriction(restriction_type, 11500, other, None)


def test_weights_are_in_kilograms_and_dimensions_in_millimetres() -> None:
    assert UNIT_BY_TYPE[RestrictionType.GROSS_WEIGHT] is LimitUnit.KG
    assert UNIT_BY_TYPE[RestrictionType.BRIDGE] is LimitUnit.KG
    assert UNIT_BY_TYPE[RestrictionType.HEIGHT] is LimitUnit.MM
    assert UNIT_BY_TYPE[RestrictionType.LENGTH] is LimitUnit.MM


@pytest.mark.parametrize("restriction_type", VALUELESS)
def test_bans_routes_and_zones_have_no_value(restriction_type: RestrictionType) -> None:
    validate_restriction(restriction_type, None, None, None)
    with pytest.raises(ValueError, match="no limit value"):
        validate_restriction(restriction_type, 1000, LimitUnit.KG, None)
    with pytest.raises(ValueError, match="tunnel category"):
        validate_restriction(restriction_type, None, None, "C")


def test_every_type_is_either_a_limit_valueless_or_a_tunnel() -> None:
    assert set(RestrictionType) == set(UNIT_BY_TYPE) | set(VALUELESS) | {RestrictionType.ADR_TUNNEL}


@pytest.mark.parametrize("category", ADR_TUNNEL_CATEGORIES)
def test_adr_tunnel_needs_category_b_to_e(category: str) -> None:
    validate_restriction(RestrictionType.ADR_TUNNEL, None, None, category)


@pytest.mark.parametrize("category", [None, "A", "F", "c"])
def test_adr_tunnel_rejects_other_categories(category: str | None) -> None:
    with pytest.raises(ValueError, match="B, C, D or E"):
        validate_restriction(RestrictionType.ADR_TUNNEL, None, None, category)


def test_period_end_not_before_start() -> None:
    validate_period(date(2026, 1, 1), None)
    validate_period(date(2026, 1, 1), date(2026, 1, 1))
    with pytest.raises(ValueError):
        validate_period(date(2026, 1, 2), date(2026, 1, 1))


@pytest.mark.parametrize(("value", "expected"), [(101, (1, 1)), (229, (2, 29)), (1231, (12, 31))])
def test_month_day_accepts_real_days(value: int, expected: tuple[int, int]) -> None:
    assert month_day(value) == expected


@pytest.mark.parametrize("value", [0, 100, 132, 230, 1301, 1232])
def test_month_day_rejects_impossible_days(value: int) -> None:
    with pytest.raises(ValueError, match="MMDD"):
        month_day(value)


def test_weekday_window_for_a_sunday_ban() -> None:
    window = BanWindow(WindowKind.WEEKDAYS, time(0), time(22), weekdays=(7,))
    assert window.weekdays == (7,)


def test_whole_day_window_has_no_end() -> None:
    assert BanWindow(WindowKind.PUBLIC_HOLIDAY, time(0)).end is None


def test_summer_saturday_window_with_a_season() -> None:
    window = BanWindow(
        WindowKind.WEEKDAYS, time(7), time(20), weekdays=(6,), season_start=701, season_end=831
    )
    assert (window.season_start, window.season_end) == (701, 831)


def test_season_may_run_over_the_new_year() -> None:
    BanWindow(WindowKind.WEEKDAYS, time(0), weekdays=(1,), season_start=1201, season_end=331)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": WindowKind.WEEKDAYS, "start": time(22), "end": time(6), "weekdays": (6,)},
        {"kind": WindowKind.WEEKDAYS, "start": time(8), "end": time(8), "weekdays": (6,)},
        {"kind": WindowKind.WEEKDAYS, "start": time(0)},
        {"kind": WindowKind.WEEKDAYS, "start": time(0), "weekdays": (0,)},
        {"kind": WindowKind.WEEKDAYS, "start": time(0), "weekdays": (8,)},
        {"kind": WindowKind.WEEKDAYS, "start": time(0), "weekdays": (6, 6)},
        {"kind": WindowKind.PUBLIC_HOLIDAY, "start": time(0), "weekdays": (7,)},
        {"kind": WindowKind.PUBLIC_HOLIDAY, "start": time(0), "season_start": 701},
        {
            "kind": WindowKind.PUBLIC_HOLIDAY,
            "start": time(0),
            "season_start": 701,
            "season_end": 931,
        },
    ],
)
def test_invalid_windows_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        BanWindow(**kwargs)  # type: ignore[arg-type]


def test_date_window_for_a_published_ban_day() -> None:
    window = BanWindow(WindowKind.DATE, time(9), time(22), on_date=date(2026, 1, 1))
    assert window.on_date == date(2026, 1, 1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": WindowKind.DATE, "start": time(9)},
        {
            "kind": WindowKind.WEEKDAYS,
            "start": time(9),
            "weekdays": (7,),
            "on_date": date(2026, 1, 4),
        },
        {
            "kind": WindowKind.DATE,
            "start": time(9),
            "on_date": date(2026, 1, 1),
            "season_start": 101,
            "season_end": 131,
        },
    ],
)
def test_date_window_rules(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        BanWindow(**kwargs)  # type: ignore[arg-type]
