from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from domain.time_types import (
    DEFAULT_MARGIN,
    PRIORITY,
    CheckLevel,
    OrderTime,
    TimeCheckReason,
    TimeType,
    evaluate,
    priority,
)

HEL = ZoneInfo("Europe/Helsinki")
BER = ZoneInfo("Europe/Berlin")
NOV20 = date(2026, 11, 20)


def at(hour: int, minute: int = 0, day: int = 20, tz: ZoneInfo = HEL, month: int = 11) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=tz)


# --- priority -----------------------------------------------------------------------------


def test_priority_order_is_fix_termin_eta_to_be_agreed() -> None:
    assert PRIORITY == (TimeType.FIX, TimeType.TERMIN, TimeType.ETA, TimeType.TO_BE_AGREED)
    assert [priority(t) for t in PRIORITY] == [0, 1, 2, 3]


def test_priority_sorts_most_binding_first() -> None:
    mixed = [TimeType.TO_BE_AGREED, TimeType.ETA, TimeType.FIX, TimeType.TERMIN]
    assert sorted(mixed, key=priority) == list(PRIORITY)


def test_default_margin_is_30_minutes() -> None:
    assert timedelta(minutes=30) == DEFAULT_MARGIN


# --- structure ----------------------------------------------------------------------------


def test_constructors_build_valid_times() -> None:
    assert OrderTime.fix(NOV20).day == NOV20
    assert OrderTime.termin(at(14), at(16)).end == at(16)
    assert OrderTime.termin(at(14)).end is None
    assert OrderTime.eta(NOV20).day == NOV20
    empty = OrderTime.to_be_agreed()
    assert (empty.day, empty.start, empty.end) == (None, None, None)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"time_type": TimeType.FIX},
        {"time_type": TimeType.FIX, "day": NOV20, "start": at(10)},
        {"time_type": TimeType.TERMIN},
        {"time_type": TimeType.TERMIN, "end": at(12)},
        {"time_type": TimeType.TERMIN, "start": at(12), "end": at(8)},
        {"time_type": TimeType.TERMIN, "start": at(12), "day": NOV20},
        {"time_type": TimeType.ETA},
        {"time_type": TimeType.ETA, "day": NOV20, "start": at(10)},
        {"time_type": TimeType.TO_BE_AGREED, "start": at(10)},
        {"time_type": TimeType.TO_BE_AGREED, "day": NOV20},
    ],
)
def test_invalid_structures_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        OrderTime(**kwargs)  # type: ignore[arg-type]


def test_naive_times_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        OrderTime.termin(datetime(2026, 11, 20, 14))
    with pytest.raises(ValueError, match="timezone-aware"):
        OrderTime.termin(datetime(2026, 11, 20, 14), at(16))
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate(OrderTime.fix(NOV20), datetime(2026, 11, 20, 9), HEL)


def test_negative_margin_is_rejected() -> None:
    with pytest.raises(ValueError, match="margin"):
        evaluate(OrderTime.termin(at(14)), at(9), HEL, margin=timedelta(minutes=-1))


# --- FIX: one exact date, strict both ways ------------------------------------------------


@pytest.mark.parametrize("hour", [0, 7, 15, 23])
def test_fix_on_the_day_is_ok_at_any_hour(hour: int) -> None:
    result = evaluate(OrderTime.fix(NOV20), at(hour), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.ON_TIME
    assert result.mandatory
    assert result.days_off == 0


def test_fix_before_the_day_blocks() -> None:
    result = evaluate(OrderTime.fix(NOV20), at(23, 59, day=19), HEL)
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.BEFORE_FIX_DATE
    assert result.days_off == -1


def test_fix_after_the_day_blocks() -> None:
    result = evaluate(OrderTime.fix(NOV20), at(0, 1, day=21), HEL)
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.LATE
    assert result.days_off == 1


def test_fix_has_no_margin() -> None:
    result = evaluate(OrderTime.fix(NOV20), at(23, 59), HEL, margin=timedelta(hours=5))
    assert result.level is CheckLevel.OK


def test_fix_uses_the_location_local_date() -> None:
    # 23:30 Berlin on the 19th is 00:30 on the 20th in Helsinki.
    planned = at(23, 30, day=19, tz=BER)
    assert evaluate(OrderTime.fix(NOV20), planned, HEL).level is CheckLevel.OK
    assert evaluate(OrderTime.fix(NOV20), planned, BER).level is CheckLevel.BLOCKED


# --- TERMIN: date and time or window, e.g. 20.11. 14:00-16:00 -----------------------------


def test_termin_inside_window_is_ok() -> None:
    result = evaluate(OrderTime.termin(at(14), at(16)), at(14, 30), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.ON_TIME
    assert result.early_by is None
    assert result.mandatory


def test_termin_before_window_is_ok_and_waits() -> None:
    result = evaluate(OrderTime.termin(at(14), at(16)), at(13), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.EARLY
    assert result.early_by == timedelta(hours=1)


def test_termin_near_window_end_is_a_risk() -> None:
    result = evaluate(OrderTime.termin(at(14), at(16)), at(15, 45), HEL)
    assert result.level is CheckLevel.RISK
    assert result.reason is TimeCheckReason.WITHIN_MARGIN
    assert result.slack == timedelta(minutes=15)


def test_termin_margin_boundary_at_window_end() -> None:
    window = OrderTime.termin(at(14), at(16))
    assert evaluate(window, at(15, 30), HEL).level is CheckLevel.OK
    assert evaluate(window, at(15, 30) + timedelta(seconds=1), HEL).level is CheckLevel.RISK


def test_termin_after_window_blocks() -> None:
    result = evaluate(OrderTime.termin(at(14), at(16)), at(16, 5), HEL)
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.LATE
    assert result.slack == timedelta(minutes=-5)


def test_termin_single_time_is_the_latest_arrival() -> None:
    assert evaluate(OrderTime.termin(at(14)), at(14, 1), HEL).level is CheckLevel.BLOCKED
    assert evaluate(OrderTime.termin(at(14)), at(13, 50), HEL).level is CheckLevel.RISK
    early = evaluate(OrderTime.termin(at(14)), at(12), HEL)
    assert early.level is CheckLevel.OK
    assert early.reason is TimeCheckReason.EARLY
    assert early.early_by == timedelta(hours=2)


def test_early_arrival_to_a_window_narrower_than_the_margin_is_a_risk_with_wait() -> None:
    result = evaluate(OrderTime.termin(at(10), at(10, 10)), at(9, 50), HEL)
    assert result.level is CheckLevel.RISK
    assert result.early_by == timedelta(minutes=10)
    assert result.slack == timedelta(minutes=20)


def test_margin_is_a_parameter() -> None:
    window = OrderTime.termin(at(14))
    assert evaluate(window, at(13), HEL, margin=timedelta(hours=2)).level is CheckLevel.RISK
    assert evaluate(window, at(13, 59), HEL, margin=timedelta(0)).level is CheckLevel.OK


def test_termin_compares_instants_across_time_zones() -> None:
    # 14:00 in Helsinki is 13:00 in Berlin; arriving 13:15 Berlin time is late.
    result = evaluate(OrderTime.termin(at(14)), at(13, 15, tz=BER), HEL)
    assert result.level is CheckLevel.BLOCKED


def test_slack_is_real_elapsed_time_across_autumn_dst_change() -> None:
    # Helsinki clocks go back 04:00 -> 03:00 on 25.10.2026: 02:00 to 10:00 is 9 real hours.
    result = evaluate(OrderTime.termin(at(10, day=25, month=10)), at(2, day=25, month=10), HEL)
    assert result.slack == timedelta(hours=9)
    assert result.early_by == timedelta(hours=9)


def test_slack_is_real_elapsed_time_across_spring_dst_change() -> None:
    # Helsinki clocks go forward 03:00 -> 04:00 on 29.3.2026: 02:00 to 10:00 is 7 real hours.
    result = evaluate(OrderTime.termin(at(10, day=29, month=3)), at(2, day=29, month=3), HEL)
    assert result.slack == timedelta(hours=7)


def test_late_within_the_repeated_hour_still_blocks() -> None:
    # 03:30 on 25.10.2026 occurs twice in Helsinki; fold=1 is the later one, 1 h after fold=0.
    first = at(3, 30, day=25, month=10)
    assert evaluate(OrderTime.termin(first), first.replace(fold=1), HEL).level is CheckLevel.BLOCKED


def test_termin_window_order_is_checked_in_real_time() -> None:
    first = at(3, 30, day=25, month=10)
    with pytest.raises(ValueError, match="before its start"):
        OrderTime.termin(first.replace(fold=1), first.replace(minute=45))


# --- ETA ----------------------------------------------------------------------------------


def test_eta_same_or_earlier_day_is_ok() -> None:
    eta = OrderTime.eta(NOV20)
    assert evaluate(eta, at(23, 59), HEL).level is CheckLevel.OK
    earlier = evaluate(eta, at(10, day=19), HEL)
    assert earlier.level is CheckLevel.OK
    assert earlier.days_off == -1


def test_eta_later_day_is_only_a_risk() -> None:
    result = evaluate(OrderTime.eta(NOV20), at(0, 30, day=21), HEL)
    assert result.level is CheckLevel.RISK
    assert result.reason is TimeCheckReason.AFTER_ETA
    assert not result.mandatory
    assert result.days_off == 1


def test_eta_uses_the_location_local_date() -> None:
    # 23:30 Berlin on the 20th is 00:30 on the 21st in Helsinki.
    planned = at(23, 30, day=20, tz=BER)
    eta = OrderTime.eta(NOV20)
    assert evaluate(eta, planned, BER).level is CheckLevel.OK
    assert evaluate(eta, planned, HEL).level is CheckLevel.RISK


# --- TO_BE_AGREED -------------------------------------------------------------------------


def test_to_be_agreed_is_a_non_mandatory_open() -> None:
    result = evaluate(OrderTime.to_be_agreed(), at(10), HEL)
    assert result.level is CheckLevel.OPEN
    assert result.reason is TimeCheckReason.TIME_TO_BE_AGREED
    assert not result.mandatory
    assert (result.slack, result.early_by, result.days_off) == (None, None, None)
