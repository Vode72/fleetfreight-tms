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


def at(hour: int, minute: int = 0, day: int = 20, tz: ZoneInfo = HEL) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=tz)


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
    assert OrderTime.fix(at(10)).start == OrderTime.fix(at(10)).end
    assert OrderTime.termin(at(8), at(12)).end == at(12)
    assert OrderTime.termin(at(8)).end is None
    assert OrderTime.eta(date(2026, 11, 20)).eta_date == date(2026, 11, 20)
    empty = OrderTime.to_be_agreed()
    assert (empty.start, empty.end, empty.eta_date) == (None, None, None)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"time_type": TimeType.FIX},
        {"time_type": TimeType.FIX, "start": at(10)},
        {"time_type": TimeType.FIX, "start": at(10), "end": at(11)},
        {"time_type": TimeType.TERMIN},
        {"time_type": TimeType.TERMIN, "end": at(12)},
        {"time_type": TimeType.TERMIN, "start": at(12), "end": at(8)},
        {"time_type": TimeType.ETA},
        {"time_type": TimeType.ETA, "eta_date": date(2026, 11, 20), "start": at(10)},
        {"time_type": TimeType.TO_BE_AGREED, "start": at(10)},
        {"time_type": TimeType.TO_BE_AGREED, "eta_date": date(2026, 11, 20)},
        {"time_type": TimeType.FIX, "start": at(10), "end": at(10), "eta_date": date(2026, 11, 20)},
    ],
)
def test_invalid_structures_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        OrderTime(**kwargs)  # type: ignore[arg-type]


def test_naive_times_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        OrderTime.fix(datetime(2026, 11, 20, 10))
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate(OrderTime.fix(at(10)), datetime(2026, 11, 20, 9), HEL)


def test_negative_margin_is_rejected() -> None:
    with pytest.raises(ValueError, match="margin"):
        evaluate(OrderTime.fix(at(10)), at(9), HEL, margin=timedelta(minutes=-1))


# --- FIX ----------------------------------------------------------------------------------


def test_fix_late_blocks() -> None:
    result = evaluate(OrderTime.fix(at(10)), at(10, 1), HEL)
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.LATE
    assert result.mandatory
    assert result.slack == timedelta(minutes=-1)


@pytest.mark.parametrize("arrival_minute", [31, 45, 59])  # 09:31-09:59, before 10:00
def test_fix_within_margin_is_a_risk(arrival_minute: int) -> None:
    result = evaluate(OrderTime.fix(at(10)), at(9, arrival_minute), HEL)
    assert result.level is CheckLevel.RISK
    assert result.reason is TimeCheckReason.WITHIN_MARGIN
    assert result.early_by == timedelta(minutes=60 - arrival_minute)


def test_fix_exactly_on_time_has_no_margin_left() -> None:
    result = evaluate(OrderTime.fix(at(10)), at(10), HEL)
    assert result.level is CheckLevel.RISK
    assert result.slack == timedelta(0)


def test_fix_exactly_at_the_margin_is_ok() -> None:
    result = evaluate(OrderTime.fix(at(10)), at(9, 30), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.EARLY
    assert result.early_by == timedelta(minutes=30)


def test_fix_early_arrival_is_ok_and_shows_the_wait() -> None:
    result = evaluate(OrderTime.fix(at(10)), at(7), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.EARLY
    assert result.early_by == timedelta(hours=3)


def test_fix_compares_instants_across_time_zones() -> None:
    # 10:00 in Helsinki is 09:00 in Berlin; arriving 09:15 Berlin time is late.
    result = evaluate(OrderTime.fix(at(10)), at(9, 15, tz=BER), HEL)
    assert result.level is CheckLevel.BLOCKED


def test_margin_is_a_parameter() -> None:
    result = evaluate(OrderTime.fix(at(10)), at(9, 30), HEL, margin=timedelta(hours=1))
    assert result.level is CheckLevel.RISK
    result = evaluate(OrderTime.fix(at(10)), at(9, 59), HEL, margin=timedelta(0))
    assert result.level is CheckLevel.OK


# --- TERMIN -------------------------------------------------------------------------------


def test_termin_inside_window_is_ok() -> None:
    result = evaluate(OrderTime.termin(at(8), at(12)), at(9), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.ON_TIME
    assert result.early_by is None
    assert result.mandatory


def test_termin_before_window_is_ok_and_waits() -> None:
    result = evaluate(OrderTime.termin(at(8), at(12)), at(7), HEL)
    assert result.level is CheckLevel.OK
    assert result.reason is TimeCheckReason.EARLY
    assert result.early_by == timedelta(hours=1)


def test_termin_near_window_end_is_a_risk() -> None:
    result = evaluate(OrderTime.termin(at(8), at(12)), at(11, 45), HEL)
    assert result.level is CheckLevel.RISK
    assert result.reason is TimeCheckReason.WITHIN_MARGIN
    assert result.slack == timedelta(minutes=15)


def test_termin_after_window_blocks() -> None:
    result = evaluate(OrderTime.termin(at(8), at(12)), at(12, 5), HEL)
    assert result.level is CheckLevel.BLOCKED
    assert result.reason is TimeCheckReason.LATE


def test_termin_single_time_behaves_like_a_deadline() -> None:
    assert evaluate(OrderTime.termin(at(14)), at(14, 1), HEL).level is CheckLevel.BLOCKED
    assert evaluate(OrderTime.termin(at(14)), at(13, 50), HEL).level is CheckLevel.RISK
    assert evaluate(OrderTime.termin(at(14)), at(12), HEL).level is CheckLevel.OK


# --- ETA ----------------------------------------------------------------------------------


def test_eta_same_or_earlier_day_is_ok() -> None:
    eta = OrderTime.eta(date(2026, 11, 20))
    assert evaluate(eta, at(23, 59), HEL).level is CheckLevel.OK
    assert evaluate(eta, at(10, day=19), HEL).level is CheckLevel.OK


def test_eta_later_day_is_only_a_risk() -> None:
    result = evaluate(OrderTime.eta(date(2026, 11, 20)), at(0, 30, day=21), HEL)
    assert result.level is CheckLevel.RISK
    assert result.reason is TimeCheckReason.AFTER_ETA
    assert not result.mandatory


def test_eta_uses_the_location_local_date() -> None:
    # 23:30 Berlin on the 20th is 00:30 on the 21st in Helsinki.
    planned = at(23, 30, day=20, tz=BER)
    eta = OrderTime.eta(date(2026, 11, 20))
    assert evaluate(eta, planned, BER).level is CheckLevel.OK
    assert evaluate(eta, planned, HEL).level is CheckLevel.RISK


# --- TO_BE_AGREED -------------------------------------------------------------------------


def test_to_be_agreed_is_a_non_mandatory_open() -> None:
    result = evaluate(OrderTime.to_be_agreed(), at(10), HEL)
    assert result.level is CheckLevel.OPEN
    assert result.reason is TimeCheckReason.TIME_TO_BE_AGREED
    assert not result.mandatory
    assert result.slack is None and result.early_by is None
