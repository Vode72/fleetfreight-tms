from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from domain.time_types import (
    DEFAULT_MARGIN,
    PRIORITY,
    CheckLevel,
    OrderTime,
    TimeBound,
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


def bound(hour: int, minute: int = 0, day: int = 20, month: int = 11) -> TimeBound:
    return TimeBound(date(2026, month, day), time(hour, minute))


WINDOW_14_16 = OrderTime.termin(bound(14), bound(16))


# --- priority -----------------------------------------------------------------------------


def test_priority_order_is_fix_termin_eta_to_be_agreed() -> None:
    assert PRIORITY == (TimeType.FIX, TimeType.TERMIN, TimeType.ETA, TimeType.TO_BE_AGREED)
    assert [priority(t) for t in PRIORITY] == [0, 1, 2, 3]


def test_priority_sorts_most_binding_first() -> None:
    mixed = [TimeType.TO_BE_AGREED, TimeType.ETA, TimeType.FIX, TimeType.TERMIN]
    assert sorted(mixed, key=priority) == list(PRIORITY)


def test_default_margin_is_30_minutes() -> None:
    assert timedelta(minutes=30) == DEFAULT_MARGIN


# --- structure: the table in D80 ----------------------------------------------------------


def test_constructors_match_the_d80_table() -> None:
    fix = OrderTime.fix(NOV20)
    assert (fix.earliest, fix.latest) == (TimeBound(NOV20), TimeBound(NOV20))
    assert (WINDOW_14_16.earliest, WINDOW_14_16.latest) == (bound(14), bound(16))
    from_14 = OrderTime.termin(earliest=bound(14))
    assert (from_14.earliest, from_14.latest) == (bound(14), None)
    eta = OrderTime.eta(NOV20)
    assert (eta.earliest, eta.latest) == (None, TimeBound(NOV20))
    empty = OrderTime.to_be_agreed()
    assert (empty.earliest, empty.latest) == (None, None)


@pytest.mark.parametrize(
    ("time_type", "earliest", "latest"),
    [
        (TimeType.FIX, None, TimeBound(NOV20)),
        (TimeType.FIX, TimeBound(NOV20), TimeBound(date(2026, 11, 21))),
        (TimeType.FIX, bound(8), TimeBound(NOV20)),
        (TimeType.TERMIN, None, None),
        (TimeType.TERMIN, TimeBound(NOV20), bound(16)),
        (TimeType.TERMIN, bound(16), bound(14)),
        (TimeType.ETA, None, None),
        (TimeType.ETA, TimeBound(NOV20), TimeBound(NOV20)),
        (TimeType.ETA, None, bound(16)),
        (TimeType.TO_BE_AGREED, TimeBound(NOV20), None),
        (TimeType.TO_BE_AGREED, None, TimeBound(NOV20)),
    ],
)
def test_invalid_structures_are_rejected(
    time_type: TimeType, earliest: TimeBound | None, latest: TimeBound | None
) -> None:
    with pytest.raises(ValueError):
        OrderTime(time_type, earliest, latest)


def test_window_on_one_day_with_equal_times_is_allowed() -> None:
    assert OrderTime.termin(bound(14), bound(14)).latest == bound(14)


def test_bound_clock_time_must_be_local() -> None:
    with pytest.raises(ValueError, match="local"):
        TimeBound(NOV20, time(14, tzinfo=HEL))


def test_naive_and_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate(OrderTime.fix(NOV20), datetime(2026, 11, 20, 9), HEL)
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate(OrderTime.fix(NOV20), at(9), HEL, planned_handling=datetime(2026, 11, 20, 9))
    with pytest.raises(ValueError, match="margin"):
        evaluate(WINDOW_14_16, at(9), HEL, margin=timedelta(minutes=-1))
    with pytest.raises(ValueError, match="before arrival"):
        evaluate(WINDOW_14_16, at(14), HEL, planned_handling=at(13))


# --- FIX: one exact date, strict both ways ------------------------------------------------


@pytest.mark.parametrize("hour", [0, 7, 15, 23])
def test_fix_on_the_day_is_ok_at_any_hour(hour: int) -> None:
    result = evaluate(OrderTime.fix(NOV20), at(hour), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.ON_TIME
    assert result.mandatory


def test_fix_arriving_the_day_before_waits_for_the_day() -> None:
    result = evaluate(OrderTime.fix(NOV20), at(21, day=19), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.WAITS
    assert result.wait == timedelta(hours=3)
    assert result.handling_start == at(0)


def test_fix_unloading_before_the_day_blocks() -> None:
    result = evaluate(OrderTime.fix(NOV20), at(21, day=19), HEL, planned_handling=at(22, day=19))
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.BEFORE_EARLIEST


def test_fix_after_the_day_blocks() -> None:
    result = evaluate(OrderTime.fix(NOV20), at(0, 1, day=21), HEL)
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.LATE
    assert result.slack is None


def test_fix_has_no_margin() -> None:
    result = evaluate(OrderTime.fix(NOV20), at(23, 59), HEL, margin=timedelta(hours=5))
    assert result.level is CheckLevel.OK


def test_fix_uses_the_location_local_date() -> None:
    # 23:30 Berlin on the 20th is 00:30 on the 21st in Helsinki.
    planned = at(23, 30, day=20, tz=BER)
    assert evaluate(OrderTime.fix(NOV20), planned, BER).level is CheckLevel.OK
    assert evaluate(OrderTime.fix(NOV20), planned, HEL).level is CheckLevel.BLOCKED


# --- TERMIN: 20.11. 14:00-16:00 -----------------------------------------------------------


def test_termin_inside_window_is_ok() -> None:
    result = evaluate(WINDOW_14_16, at(14, 30), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.ON_TIME
    assert result.wait is None
    assert result.slack == timedelta(minutes=90)


def test_termin_early_arrival_waits_and_handles_at_window_start() -> None:
    result = evaluate(WINDOW_14_16, at(13), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.WAITS
    assert result.wait == timedelta(hours=1)
    assert result.handling_start == at(14)
    assert result.slack == timedelta(hours=2)


def test_termin_handling_before_window_blocks() -> None:
    result = evaluate(WINDOW_14_16, at(13), HEL, planned_handling=at(13, 30))
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.BEFORE_EARLIEST


def test_termin_near_window_end_is_a_risk() -> None:
    result = evaluate(WINDOW_14_16, at(15, 45), HEL)
    assert result.level is CheckLevel.RISK
    assert result.reason is TimeCheckReason.WITHIN_MARGIN
    assert result.slack == timedelta(minutes=15)


def test_termin_margin_boundary_at_window_end() -> None:
    assert evaluate(WINDOW_14_16, at(15, 30), HEL).level is CheckLevel.OK
    almost = at(15, 30) + timedelta(seconds=1)
    assert evaluate(WINDOW_14_16, almost, HEL).level is CheckLevel.RISK


def test_termin_after_window_blocks() -> None:
    result = evaluate(WINDOW_14_16, at(16, 5), HEL)
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.LATE
    assert result.slack == timedelta(minutes=-5)


def test_late_planned_handling_blocks_even_when_arrival_is_in_time() -> None:
    result = evaluate(WINDOW_14_16, at(15), HEL, planned_handling=at(16, 10))
    assert result.level is CheckLevel.BLOCKED


def test_window_narrower_than_the_margin_is_a_risk_with_wait() -> None:
    narrow = OrderTime.termin(bound(10), bound(10, 10))
    result = evaluate(narrow, at(9, 50), HEL)
    assert result.level is CheckLevel.RISK
    assert result.wait == timedelta(minutes=10)
    assert result.slack == timedelta(minutes=10)


def test_pickup_from_14_has_no_latest() -> None:
    from_14 = OrderTime.termin(earliest=bound(14))
    early = evaluate(from_14, at(12), HEL)
    assert (early.level, early.reason, early.wait) == (
        CheckLevel.OK,
        TimeCheckReason.WAITS,
        timedelta(hours=2),
    )
    assert evaluate(from_14, at(23), HEL).level is CheckLevel.OK


def test_termin_latest_only_is_a_deadline() -> None:
    by_16 = OrderTime.termin(latest=bound(16))
    assert evaluate(by_16, at(16, 1), HEL).level is CheckLevel.BLOCKED
    assert evaluate(by_16, at(15, 50), HEL).level is CheckLevel.RISK
    assert evaluate(by_16, at(9), HEL).level is CheckLevel.OK


def test_margin_is_a_parameter() -> None:
    by_14 = OrderTime.termin(latest=bound(14))
    assert evaluate(by_14, at(13), HEL, margin=timedelta(hours=2)).level is CheckLevel.RISK
    assert evaluate(by_14, at(13, 59), HEL, margin=timedelta(0)).level is CheckLevel.OK


def test_termin_bounds_are_local_to_the_location() -> None:
    # 14:00 at a Berlin location is 15:00 in Helsinki; arriving 15:30 Helsinki time is
    # 14:30 Berlin time, inside the Berlin window.
    result = evaluate(WINDOW_14_16, at(15, 30), BER)
    assert result.level is CheckLevel.OK
    assert result.slack == timedelta(minutes=90)


def test_slack_is_real_elapsed_time_across_autumn_dst_change() -> None:
    # Helsinki clocks go back 04:00 -> 03:00 on 25.10.2026: 02:00 to 10:00 is 9 real hours.
    by_10 = OrderTime.termin(latest=bound(10, day=25, month=10))
    assert evaluate(by_10, at(2, day=25, month=10), HEL).slack == timedelta(hours=9)


def test_wait_is_real_elapsed_time_across_spring_dst_change() -> None:
    # Helsinki clocks go forward 03:00 -> 04:00 on 29.3.2026: 02:00 to 10:00 is 7 real hours.
    from_10 = OrderTime.termin(earliest=bound(10, day=29, month=3))
    assert evaluate(from_10, at(2, day=29, month=3), HEL).wait == timedelta(hours=7)


# --- ETA ----------------------------------------------------------------------------------


def test_eta_same_or_earlier_day_is_ok() -> None:
    eta = OrderTime.eta(NOV20)
    assert evaluate(eta, at(23, 59), HEL).level is CheckLevel.OK
    earlier = evaluate(eta, at(10, day=19), HEL)
    assert earlier.level is CheckLevel.OK
    assert earlier.wait is None


def test_eta_later_day_is_only_a_risk() -> None:
    result = evaluate(OrderTime.eta(NOV20), at(0, 30, day=21), HEL)
    assert result.level is CheckLevel.RISK
    assert result.reason is TimeCheckReason.AFTER_ETA
    assert not result.mandatory


def test_eta_uses_the_location_local_date() -> None:
    planned = at(23, 30, day=20, tz=BER)  # 00:30 on the 21st in Helsinki
    eta = OrderTime.eta(NOV20)
    assert evaluate(eta, planned, BER).level is CheckLevel.OK
    assert evaluate(eta, planned, HEL).level is CheckLevel.RISK


# --- TO_BE_AGREED -------------------------------------------------------------------------


def test_to_be_agreed_is_a_non_mandatory_open() -> None:
    result = evaluate(OrderTime.to_be_agreed(), at(10), HEL)
    assert result.level is CheckLevel.OPEN
    assert result.reason is TimeCheckReason.TIME_TO_BE_AGREED
    assert not result.mandatory
    assert (result.handling_start, result.wait, result.slack) == (None, None, None)
