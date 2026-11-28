"""Cargo crime risk and border waits (2B-3e, D95): pure domain rules."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import CheckConstraint

from db.models import BorderWaitObservation, RiskArea, in_list
from domain.risks import (
    DEMO_WAIT_NOTE,
    CountryRisk,
    RiskLevelSettings,
    RiskSourceType,
    WaitDirection,
    WaitObservation,
    WaitSourceType,
    country_risk,
    effective_risk_level,
    expected_wait,
    level_for_monthly_count,
    validate_incident_count,
    validate_report_month,
    validate_risk_area,
    validate_wait_observation,
)
from domain.risks import RiskArea as Area

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations/versions/7767d6908268_cargo_crime_risk_and_border_waits.py"
)
ENUM_CHECKS = [
    (RiskArea, "ck_risk_areas_source_type", "source_type", RiskSourceType),
    (BorderWaitObservation, "ck_border_wait_observations_direction", "direction", WaitDirection),
    (
        BorderWaitObservation,
        "ck_border_wait_observations_source_type",
        "source_type",
        WaitSourceType,
    ),
]


@pytest.mark.parametrize(("model", "name", "column", "enum"), ENUM_CHECKS)
def test_check_lists_match_domain(model: Any, name: str, column: str, enum: type[StrEnum]) -> None:
    checks = {
        c.name: str(c.sqltext)
        for c in model.__table__.constraints
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }
    expected = in_list(column, enum)
    assert checks[name] == expected
    migration = re.sub(r'"\s*"', "", MIGRATION.read_text(encoding="utf-8"))
    assert f'"{expected}"' in migration


def test_demo_note_is_the_same_in_the_migration() -> None:
    migration = re.sub(r'"\s*"', "", MIGRATION.read_text(encoding="utf-8"))
    assert f"'{DEMO_WAIT_NOTE}'" in migration


# --- country level -------------------------------------------------------------------------

SETTINGS = RiskLevelSettings(window_months=6, min_months=3, thresholds=(10, 40, 100, 200))


def _reports(*months: tuple[date, dict[str, int]]) -> dict[date, dict[str, int]]:
    return dict(months)


def test_level_for_monthly_count_uses_lower_bounds() -> None:
    assert level_for_monthly_count(Decimal("9.9"), SETTINGS) == 1
    assert level_for_monthly_count(Decimal(10), SETTINGS) == 2
    assert level_for_monthly_count(Decimal(100), SETTINGS) == 4
    assert level_for_monthly_count(Decimal(5000), SETTINGS) == 5


def test_country_risk_uses_the_median_of_named_months_in_the_window() -> None:
    reports = _reports(
        (date(2026, 4, 1), {"FR": 100}),
        (date(2026, 5, 1), {"FR": 50}),
        (date(2026, 6, 1), {"FR": 60, "DE": 300}),
        (date(2026, 10, 1), {"FR": 1000}),  # the current month is not complete yet
    )
    risk = country_risk("FR", reports, date(2026, 10, 15), SETTINGS)
    assert risk == CountryRisk("FR", 3, 3, Decimal("60.0"))


def test_one_anomalous_month_does_not_lift_the_level() -> None:
    reports = _reports(
        (date(2026, 7, 1), {"IT": 20}),
        (date(2026, 8, 1), {"IT": 900}),  # reporting anomaly; an average would give level 5
        (date(2026, 9, 1), {"IT": 25}),
    )
    risk = country_risk("IT", reports, date(2026, 10, 1), SETTINGS)
    assert risk == CountryRisk("IT", 2, 3, Decimal("25.0"))


def test_even_number_of_months_uses_the_midpoint() -> None:
    reports = _reports(
        (date(2026, 6, 1), {"PL": 40}),
        (date(2026, 7, 1), {"PL": 51}),
        (date(2026, 8, 1), {"PL": 60}),
        (date(2026, 9, 1), {"PL": 70}),
    )
    risk = country_risk("PL", reports, date(2026, 10, 1), SETTINGS)
    assert risk == CountryRisk("PL", 3, 4, Decimal("55.5"))


def test_even_midpoint_below_a_threshold_stays_on_the_lower_level() -> None:
    reports = _reports(
        (date(2026, 7, 1), {"LT": 30}),
        (date(2026, 8, 1), {"LT": 39}),
        (date(2026, 9, 1), {"LT": 40}),
        (date(2026, 6, 1), {"LT": 60}),
    )
    risk = country_risk("LT", reports, date(2026, 10, 1), SETTINGS)
    assert risk == CountryRisk("LT", 2, 4, Decimal("39.5"))


def test_unnamed_month_is_skipped_not_zero() -> None:
    reports = _reports(
        (date(2026, 7, 1), {"NL": 45}),
        (date(2026, 8, 1), {"DE": 200}),  # NL not named: unknown, not 0
        (date(2026, 9, 1), {"NL": 53}),
    )
    risk = country_risk("NL", reports, date(2026, 10, 1), SETTINGS)
    assert risk.level is None and risk.months_used == 2


def test_months_outside_the_window_do_not_count() -> None:
    reports = _reports(
        (date(2026, 1, 1), {"IT": 900}),  # 9 months back, window is 6
        (date(2026, 7, 1), {"IT": 20}),
        (date(2026, 8, 1), {"IT": 20}),
        (date(2026, 9, 1), {"IT": 20}),
    )
    assert country_risk("IT", reports, date(2026, 10, 1), SETTINGS).level == 2


def test_country_without_reports_is_unknown() -> None:
    assert country_risk("FI", {}, date(2026, 10, 1)).level is None


def test_report_month_must_be_the_first_day() -> None:
    with pytest.raises(ValueError):
        validate_report_month(date(2026, 3, 2))
    with pytest.raises(ValueError):
        country_risk("FR", {date(2026, 3, 2): {"FR": 1}}, date(2026, 10, 1))


def test_negative_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_incident_count(-1)


@pytest.mark.parametrize(
    "kw",
    [
        {"window_months": 3, "min_months": 4},
        {"min_months": 0},
        {"thresholds": (10, 10, 20, 30)},
        {"thresholds": (40, 10, 100, 200)},
        {"thresholds": (0, 10, 100, 200)},
    ],
)
def test_invalid_settings(kw: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        RiskLevelSettings(**kw)


# --- risk areas ----------------------------------------------------------------------------

DAY = date(2026, 11, 24)
AREAS = [
    Area("FR", "FR-ARA", None, 4, date(2026, 1, 1), None),
    Area("ES", "ES-CT", "AP-7", 4, date(2026, 1, 1), None),
    Area("FR", None, None, 2, date(2026, 1, 1), None),
    Area("BE", None, "E19", 5, date(2026, 1, 1), date(2026, 6, 30)),
]


def test_higher_level_wins_over_the_country() -> None:
    level = effective_risk_level(3, AREAS, country="FR", region="FR-ARA", road_ref="A7", day=DAY)
    assert level == 4


def test_low_area_does_not_lower_a_high_country() -> None:
    assert (
        effective_risk_level(5, AREAS, country="FR", region="FR-ARA", road_ref=None, day=DAY) == 5
    )


def test_road_area_only_on_that_road() -> None:
    kw: dict[str, Any] = {"country": "ES", "region": "ES-CT", "day": DAY}
    assert effective_risk_level(None, AREAS, road_ref="AP-7", **kw) == 4
    assert effective_risk_level(None, AREAS, road_ref="C-32", **kw) is None


def test_expired_area_no_longer_applies() -> None:
    kw: dict[str, Any] = {"country": "BE", "region": None, "road_ref": "E19"}
    assert effective_risk_level(None, AREAS, day=date(2026, 6, 30), **kw) == 5
    assert effective_risk_level(None, AREAS, day=date(2026, 7, 1), **kw) is None


def test_nothing_known_is_unknown() -> None:
    assert effective_risk_level(None, [], country="FI", region=None, road_ref=None, day=DAY) is None


def _area(**kw: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "country": "NL",
        "region": None,
        "road_ref": "A2",
        "level": 4,
        "source_type": RiskSourceType.DATA,
        "basis": "Named hotspot",
        "source_url": "https://example.com/report",
        "valid_from": DAY,
        "valid_until": None,
    }
    values.update(kw)
    return values


def test_valid_risk_area() -> None:
    validate_risk_area(**_area())
    validate_risk_area(**_area(source_type=RiskSourceType.EXPERT_ESTIMATE, source_url=None))


@pytest.mark.parametrize(
    "kw",
    [
        {"country": "nl"},
        {"region": "BE-VAN"},
        {"region": "NL"},
        {"road_ref": " "},
        {"level": 0},
        {"level": 6},
        {"basis": "  "},
        {"source_url": "http://example.com"},
        {"source_url": None},
        {"valid_until": DAY - timedelta(days=1)},
    ],
)
def test_invalid_risk_area(kw: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        validate_risk_area(**_area(**kw))


# --- border waits ---------------------------------------------------------------------------

STO = ZoneInfo("Europe/Stockholm")


def _obs(
    day: int,
    hour: int,
    minutes: int,
    source: WaitSourceType = WaitSourceType.MANUAL,
    direction: WaitDirection = WaitDirection.EXIT,
) -> WaitObservation:
    return WaitObservation(
        datetime(2026, 11, day, hour, 10, tzinfo=STO), direction, minutes, source
    )


def test_expected_wait_is_the_median_of_the_same_weekday_and_hour() -> None:
    observations = [_obs(2, 7, 40), _obs(9, 7, 60), _obs(16, 7, 45), _obs(3, 7, 500), _obs(2, 8, 5)]
    estimate = expected_wait(
        observations,
        direction=WaitDirection.EXIT,
        at=datetime(2026, 11, 23, 7, 30, tzinfo=STO),  # a Monday
        time_zone="Europe/Stockholm",
    )
    assert estimate is not None
    assert (estimate.minutes, estimate.sample_size, estimate.is_demo) == (45, 3, False)


def test_local_time_of_the_crossing_decides_the_slot() -> None:
    observations = [_obs(2, 7, 40)]
    at = datetime(2026, 11, 23, 6, 30, tzinfo=ZoneInfo("UTC"))  # 07:30 in Stockholm
    estimate = expected_wait(
        observations, direction=WaitDirection.EXIT, at=at, time_zone="Europe/Stockholm"
    )
    assert estimate is not None and estimate.minutes == 40


def test_demo_values_are_not_mixed_with_real_ones() -> None:
    at = datetime(2026, 11, 23, 7, 0, tzinfo=STO)
    demo = [_obs(2, 7, 90, WaitSourceType.DEMO), _obs(9, 7, 80, WaitSourceType.DEMO)]
    only_demo = expected_wait(
        demo, direction=WaitDirection.EXIT, at=at, time_zone="Europe/Stockholm"
    )
    assert only_demo is not None and only_demo.is_demo and only_demo.minutes == 85
    mixed = expected_wait(
        [*demo, _obs(16, 7, 30)], direction=WaitDirection.EXIT, at=at, time_zone="Europe/Stockholm"
    )
    assert mixed is not None and (mixed.minutes, mixed.is_demo, mixed.sample_size) == (30, False, 1)


def test_other_direction_or_slot_gives_no_estimate() -> None:
    at = datetime(2026, 11, 23, 7, 0, tzinfo=STO)
    observations = [_obs(2, 7, 40, direction=WaitDirection.ENTRY)]
    assert (
        expected_wait(
            observations, direction=WaitDirection.EXIT, at=at, time_zone="Europe/Stockholm"
        )
        is None
    )
    with pytest.raises(ValueError):
        expected_wait(
            observations, direction=WaitDirection.EXIT, at=datetime(2026, 11, 23), time_zone="UTC"
        )


@pytest.mark.parametrize(
    "kw",
    [
        {"observed_at": datetime(2026, 11, 2, 7)},
        {"wait_minutes": -1},
        {"source_url": "http://example.com"},
        {"source_type": WaitSourceType.OFFICIAL_FEED},
        {"source_type": WaitSourceType.HISTORICAL_AVG},
        {"source_type": WaitSourceType.DEMO},
    ],
)
def test_invalid_wait_observation(kw: dict[str, Any]) -> None:
    values: dict[str, Any] = {
        "observed_at": datetime(2026, 11, 2, 7, tzinfo=STO),
        "wait_minutes": 30,
        "source_type": WaitSourceType.MANUAL,
        "source_url": None,
        "note": None,
    }
    values.update(kw)
    with pytest.raises(ValueError):
        validate_wait_observation(**values)


def test_valid_demo_observation() -> None:
    validate_wait_observation(
        observed_at=datetime(2026, 11, 2, 7, tzinfo=STO),
        wait_minutes=30,
        source_type=WaitSourceType.DEMO,
        source_url=None,
        note=DEMO_WAIT_NOTE,
    )


def test_even_count_median_rounds_half_up() -> None:
    at = datetime(2026, 11, 23, 7, 0, tzinfo=STO)
    estimate = expected_wait(
        [_obs(2, 7, 35), _obs(9, 7, 40)],
        direction=WaitDirection.EXIT,
        at=at,
        time_zone="Europe/Stockholm",
    )
    assert estimate is not None and estimate.minutes == 38  # 37.5


def test_old_observations_are_left_out() -> None:
    at = datetime(2026, 11, 23, 7, 0, tzinfo=STO)
    old = WaitObservation(
        datetime(2026, 6, 1, 7, 0, tzinfo=STO), WaitDirection.EXIT, 300, WaitSourceType.MANUAL
    )
    estimate = expected_wait(
        [old, _obs(16, 7, 30)], direction=WaitDirection.EXIT, at=at, time_zone="Europe/Stockholm"
    )
    assert estimate is not None and (estimate.minutes, estimate.sample_size) == (30, 1)
    with pytest.raises(ValueError):
        expected_wait([old], direction=WaitDirection.EXIT, at=at, time_zone="UTC", max_age_days=0)


def test_slot_follows_local_time_across_daylight_saving() -> None:
    # Monday 07:00 in summer time (UTC+2) and in winter time (UTC+1) are the same local slot.
    summer = WaitObservation(
        datetime(2026, 10, 19, 5, 0, tzinfo=ZoneInfo("UTC")),
        WaitDirection.EXIT,
        50,
        WaitSourceType.MANUAL,
    )
    at = datetime(2026, 11, 2, 6, 30, tzinfo=ZoneInfo("UTC"))  # 07:30 local, after the change
    estimate = expected_wait(
        [summer], direction=WaitDirection.EXIT, at=at, time_zone="Europe/Stockholm"
    )
    assert estimate is not None and estimate.minutes == 50


def test_observation_without_time_zone_is_rejected() -> None:
    with pytest.raises(ValueError):
        WaitObservation(datetime(2026, 11, 2, 7), WaitDirection.EXIT, 5, WaitSourceType.MANUAL)


def test_area_validity_includes_both_end_days() -> None:
    area = Area("FR", "FR-ARA", None, 4, date(2026, 1, 1), date(2026, 6, 30))
    assert area.applies("FR", "FR-ARA", None, date(2026, 1, 1))
    assert area.applies("FR", "FR-ARA", None, date(2026, 6, 30))
    assert not area.applies("FR", "FR-ARA", None, date(2025, 12, 31))
    assert not area.applies("FR", "FR-OCC", None, date(2026, 3, 1))


def test_country_region_and_road_rows_together() -> None:
    areas = [
        Area("FR", None, None, 2, date(2026, 1, 1), None),
        Area("FR", "FR-ARA", None, 3, date(2026, 1, 1), None),
        Area("FR", "FR-ARA", "A7", 5, date(2026, 1, 1), None),
    ]
    kw: dict[str, Any] = {"country": "FR", "day": DAY}
    assert effective_risk_level(None, areas, region="FR-OCC", road_ref="A9", **kw) == 2
    assert effective_risk_level(None, areas, region="FR-ARA", road_ref="A43", **kw) == 3
    assert effective_risk_level(None, areas, region="FR-ARA", road_ref="A7", **kw) == 5


def test_demo_note_can_sit_in_a_sql_literal() -> None:
    assert "'" not in DEMO_WAIT_NOTE
