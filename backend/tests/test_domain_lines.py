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
    service_dates,
    validate_calls,
    validate_route,
    validate_stops,
    validate_vessel,
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
        {"accompanied": True, "driver_cabins": False},
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
