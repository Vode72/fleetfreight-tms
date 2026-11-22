from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from domain.lines import (
    ADR_CLASSES,
    Call,
    LineMode,
    Stop,
    dates_to_generate,
    departure_times,
    departures_to_add,
    plan_departure,
    service_dates,
    validate_calls,
    validate_route,
    validate_schedule_periods,
    validate_stops,
    validate_vessel,
    vessel_overlaps,
)

T = time.fromisoformat
HEL, BER, STO = "Europe/Helsinki", "Europe/Berlin", "Europe/Stockholm"


def test_route_units_and_defaults() -> None:
    validate_route(
        LineMode.FERRY,
        accompanied=True,
        unaccompanied=True,
        checkin_minutes=120,
        cutoff_minutes=180,
        dg_declaration_hours=24,
    )
    validate_route(
        LineMode.RAIL,
        accompanied=False,
        unaccompanied=True,
        checkin_minutes=None,
        cutoff_minutes=240,
        dg_declaration_hours=None,
    )
    bad = [
        (LineMode.FERRY, False, False, None, None, None),
        (LineMode.RAIL, True, True, None, None, None),  # rail carries no tractors (D63)
        (LineMode.FERRY, False, True, 60, None, None),  # check-in is for accompanied units
        (LineMode.FERRY, True, False, None, 60, None),  # cut-off is for unaccompanied units
        (LineMode.FERRY, True, True, -1, None, None),
        (LineMode.FERRY, True, True, None, None, -1),
    ]
    for mode, acc, unacc, checkin, cutoff, dg in bad:
        with pytest.raises(ValueError):
            validate_route(
                mode,
                accompanied=acc,
                unaccompanied=unacc,
                checkin_minutes=checkin,
                cutoff_minutes=cutoff,
                dg_declaration_hours=dg,
            )


def test_stops() -> None:
    validate_stops([Stop(1, True, False), Stop(2, True, True), Stop(3, False, True)])
    for stops in (
        [Stop(1, True, False)],
        [Stop(1, True, False), Stop(3, False, True)],
        [Stop(1, True, True), Stop(2, False, True)],
        [Stop(1, True, False), Stop(2, True, True)],
        [Stop(1, True, False), Stop(2, False, False), Stop(3, False, True)],
    ):
        with pytest.raises(ValueError):
            validate_stops(stops)


CALLS = [
    Call(1, None, None, 0, T("10:00")),
    Call(2, 0, T("14:45"), 0, T("15:00")),
    Call(3, 0, T("17:45"), None, None),
]


def test_calls_structure() -> None:
    validate_calls(CALLS)
    for calls in (
        [Call(1, None, None, 0, T("10:00"))],
        [Call(1, 0, T("09:00"), 0, T("10:00")), Call(2, 0, T("12:00"), None, None)],
        [Call(1, None, None, 1, T("10:00")), Call(2, 1, T("12:00"), None, None)],
        [Call(1, None, None, 0, T("10:00")), Call(2, 0, T("12:00"), 0, T("13:00"))],
        [Call(1, None, None, 0, T("10:00")), Call(2, 0, None, None, None)],
        [
            Call(1, None, None, 0, T("10:00")),
            Call(2, None, None, 0, T("13:00")),
            Call(3, 0, T("17:00"), None, None),
        ],
        [Call(1, None, None, 0, T("10:00")), Call(2, 15, T("12:00"), None, None)],
    ):
        with pytest.raises(ValueError):
            validate_calls(calls)


def test_departure_times_use_each_stops_time_zone() -> None:
    times = departure_times(date(2026, 11, 23), CALLS, [HEL, "Europe/Mariehamn", STO])
    assert times[0].arrives_at is None
    assert times[0].departs_at == datetime(2026, 11, 23, 10, 0, tzinfo=ZoneInfo(HEL))
    assert times[1].arrives_at == datetime(2026, 11, 23, 14, 45, tzinfo=ZoneInfo(HEL))
    # 17:45 in Sweden is 18:45 in Finland: 8 h 45 min after departure
    arrival = times[2].arrives_at
    assert arrival is not None and times[0].departs_at is not None
    assert arrival - times[0].departs_at == datetime(2000, 1, 1, 8, 45) - datetime(2000, 1, 1)
    assert times[2].departs_at is None


def test_departure_times_must_run_forward() -> None:
    calls = [Call(1, None, None, 0, T("10:00")), Call(2, 0, T("09:30"), None, None)]
    # 09:30 in Berlin is 10:30 in Helsinki: forward
    departure_times(date(2026, 11, 23), calls, [HEL, BER])
    with pytest.raises(ValueError, match="forward"):
        departure_times(date(2026, 11, 23), calls, [HEL, HEL])
    with pytest.raises(ValueError, match="time zone"):
        departure_times(date(2026, 11, 23), calls, [HEL])


def test_spring_forward_moves_a_missing_local_time_one_hour_on() -> None:
    calls = [Call(1, None, None, 0, T("03:30")), Call(2, 0, T("06:00"), None, None)]
    # 29.3.2026: in Helsinki 03:00-04:00 does not exist
    times = departure_times(date(2026, 3, 29), calls, [HEL, HEL])
    departs = times[0].departs_at
    assert departs is not None
    assert departs.astimezone(ZoneInfo("UTC")).hour == 1  # 04:30 EEST


def test_service_dates() -> None:
    # Mondays in a two-week window within the validity
    assert service_dates(1, date(2026, 1, 1), None, date(2026, 11, 22), date(2026, 12, 6)) == [
        date(2026, 11, 23),
        date(2026, 11, 30),
    ]
    assert service_dates(
        7, date(2026, 11, 29), date(2026, 11, 29), date(2026, 11, 1), date(2026, 12, 31)
    ) == [date(2026, 11, 29)]
    with pytest.raises(ValueError):
        service_dates(0, date(2026, 1, 1), None, date(2026, 1, 1), date(2026, 1, 31))


def test_only_missing_departures_are_generated() -> None:
    planned = [date(2026, 11, 23), date(2026, 11, 30), date(2026, 12, 7)]
    assert dates_to_generate(planned, [date(2026, 11, 30), date(2026, 11, 16)]) == [
        date(2026, 11, 23),
        date(2026, 12, 7),
    ]


def test_vessel() -> None:
    validate_vessel(  # short crossing: drivers travel without cabins
        lane_metres=1900,
        deck_height_mm=None,
        reefer_plug_count=None,
        accompanied=True,
        unaccompanied=True,
        driver_cabins=False,
    )
    validate_vessel(
        lane_metres=3000,
        deck_height_mm=None,
        reefer_plug_count=0,
        accompanied=False,
        unaccompanied=True,
        driver_cabins=False,
    )
    for kw in (
        {"lane_metres": 0},
        {"deck_height_mm": -1},
        {"reefer_plug_count": -1},
        {"accompanied": False, "unaccompanied": False},
        {"accompanied": False, "driver_cabins": True},
    ):
        values: dict[str, object] = {
            "lane_metres": 3000,
            "deck_height_mm": 4800,
            "reefer_plug_count": 10,
            "accompanied": True,
            "unaccompanied": True,
            "driver_cabins": True,
            **kw,
        }
        with pytest.raises(ValueError):
            validate_vessel(**values)  # type: ignore[arg-type]


def test_adr_classes_are_the_thirteen_classes() -> None:
    assert len(ADR_CLASSES) == 13 and len(set(ADR_CLASSES)) == 13


def test_autumn_repeated_hour_takes_the_first_occurrence_and_compares_in_utc() -> None:
    # 25.10.2026 in Helsinki: 03:00-04:00 occurs twice
    calls = [Call(1, None, None, 0, T("03:30")), Call(2, 0, T("03:10"), None, None)]
    with pytest.raises(ValueError, match="forward"):
        # 03:10 (first occurrence) is before 03:30 (first occurrence)
        departure_times(date(2026, 10, 25), calls, [HEL, HEL])
    times = departure_times(
        date(2026, 10, 25),
        [Call(1, None, None, 0, T("03:30")), Call(2, 0, T("02:40"), None, None)],
        [HEL, BER],  # 02:40 in Berlin (first occurrence, CEST) = 03:40 EEST in Helsinki
    )
    first, second = times[0].departs_at, times[1].arrives_at
    assert first is not None and second is not None
    assert second.astimezone(ZoneInfo("UTC")) > first.astimezone(ZoneInfo("UTC"))


def test_plan_departure_cutoffs() -> None:
    stops = [Stop(1, True, False), Stop(2, True, True), Stop(3, False, True)]
    plan = plan_departure(
        date(2026, 11, 23),
        CALLS,
        [HEL, "Europe/Mariehamn", STO],
        stops,
        route_cutoff_minutes=180,
        call_cutoff_minutes=[None, 60, None],
    )
    assert plan[0].cutoff_at == datetime(2026, 11, 23, 7, 0, tzinfo=ZoneInfo(HEL))
    assert plan[1].cutoff_at == datetime(2026, 11, 23, 14, 0, tzinfo=ZoneInfo(HEL))  # own
    assert plan[2].cutoff_at is None  # the last stop only unloads
    no_default = plan_departure(
        date(2026, 11, 23), CALLS, [HEL, HEL, STO], stops, route_cutoff_minutes=None
    )
    assert all(c.cutoff_at is None for c in no_default)
    with pytest.raises(ValueError):
        plan_departure(
            date(2026, 11, 23), CALLS, [HEL, HEL, STO], stops[:2], route_cutoff_minutes=1
        )


def test_schedule_periods_of_one_sailing_do_not_overlap() -> None:
    validate_schedule_periods(
        [
            (1, T("17:00"), date(2026, 1, 1), date(2026, 6, 30)),
            (1, T("17:00"), date(2026, 7, 1), None),
            (1, T("18:00"), date(2026, 1, 1), None),  # another sailing
            (2, T("17:00"), date(2026, 1, 1), None),
        ]
    )
    for periods in (
        [(1, T("17:00"), date(2026, 1, 1), None), (1, T("17:00"), date(2026, 7, 1), None)],
        [
            (1, T("17:00"), date(2026, 1, 1), date(2026, 7, 1)),
            (1, T("17:00"), date(2026, 7, 1), None),
        ],
    ):
        with pytest.raises(ValueError):
            validate_schedule_periods(periods)


def test_departures_to_add_skips_a_hand_entered_departure() -> None:
    zone = ZoneInfo(HEL)
    planned = [date(2026, 11, 23), date(2026, 11, 30)]
    firsts = {d: datetime.combine(d, T("17:00"), tzinfo=zone) for d in planned}
    by_hand = [datetime(2026, 11, 30, 15, 0, tzinfo=ZoneInfo("UTC"))]  # = 17:00 Helsinki
    assert departures_to_add(planned, [], by_hand, firsts) == [date(2026, 11, 23)]
    assert departures_to_add(planned, [date(2026, 11, 23)], [], firsts) == [date(2026, 11, 30)]


def test_vessel_overlaps() -> None:
    zone = ZoneInfo(HEL)

    def at(day: int, hour: int) -> datetime:
        return datetime(2026, 11, day, hour, tzinfo=zone)

    voyages = [
        ("a", at(23, 17), at(25, 0)),
        ("b", at(25, 1), at(26, 10)),  # after a
        ("c", at(24, 12), at(24, 20)),  # during a
    ]
    assert vessel_overlaps(voyages) == [("a", "c")]
    with pytest.raises(ValueError):
        vessel_overlaps([("x", at(23, 17), at(23, 17))])
