"""Constraints of the 2B-3c line tables (D94), checked against the migrated schema."""

from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.usefixtures("clean_registers")


def _exec(engine: Engine, sql: str, **values: Any) -> Any:
    with engine.begin() as conn:
        return conn.execute(text(sql), values).scalar()


def _insert(engine: Engine, table: str, returning: str = "id", **values: Any) -> Any:
    columns = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    sql = f"INSERT INTO {table} ({columns}) VALUES ({params}) RETURNING {returning}"
    return _exec(engine, sql, **values)


def _rejected(fn: Any, *args: Any, **kw: Any) -> None:
    with pytest.raises(IntegrityError):
        fn(*args, **kw)


def _place(engine: Engine, name: str, location_type: str = "port") -> Any:
    return _insert(
        engine,
        "locations",
        type=location_type,
        name=name,
        country="FI",
        timezone="Europe/Helsinki",
    )


def _operator(engine: Engine, name: str = "Demo Ferry", mode: str = "ferry") -> Any:
    return _insert(engine, "line_operators", name=name, mode=mode)


def _route(engine: Engine, operator: Any, name: str = "Demo A-B", **kw: Any) -> Any:
    values = {
        "operator_id": operator,
        "mode": "ferry",
        "name": name,
        "accompanied": True,
        "unaccompanied": True,
        **kw,
    }
    return _insert(engine, "line_routes", **values)


def _stop(engine: Engine, route: Any, sequence: int, place: Any, **kw: Any) -> Any:
    values = {
        "route_id": route,
        "sequence": sequence,
        "route_mode": "ferry",
        "location_id": place,
        "location_type": "port",
        "loading": sequence == 1,
        "unloading": sequence != 1,
        **kw,
    }
    return _insert(engine, "line_route_stops", returning="sequence", **values)


def _line(engine: Engine) -> tuple[Any, Any]:
    operator = _operator(engine)
    route = _route(engine, operator)
    _stop(engine, route, 1, _place(engine, "Demo Port A"))
    _stop(engine, route, 2, _place(engine, "Demo Port B"))
    return operator, route


def test_route_mode_follows_operator(test_engine: Engine) -> None:
    rail = _operator(test_engine, "Demo Rail X", "rail")
    _rejected(_route, test_engine, rail)  # a ferry route of a rail operator
    _route(test_engine, rail, "Demo Rail A-B", mode="rail", accompanied=False)
    _rejected(_route, test_engine, rail, "Demo Rail C", mode="rail")  # accompanied rail


def test_route_defaults(test_engine: Engine) -> None:
    operator = _operator(test_engine)
    _route(test_engine, operator, checkin_minutes=120, cutoff_minutes=180, dg_declaration_hours=24)
    bad: list[dict[str, Any]] = [
        {"accompanied": False, "unaccompanied": False},
        {"accompanied": False, "checkin_minutes": 60},
        {"unaccompanied": False, "cutoff_minutes": 60},
        {"cutoff_minutes": -1},
        {"dg_declaration_hours": -1},
    ]
    for number, kw in enumerate(bad):
        _rejected(_route, test_engine, operator, f"Demo Bad {number}", **kw)


def test_stops_are_ports_for_ferries_and_rail_terminals_for_rail(test_engine: Engine) -> None:
    _, route = _line(test_engine)
    terminal = _place(test_engine, "Demo Rail Terminal X", "rail_terminal")
    _rejected(_stop, test_engine, route, 3, terminal, location_type="rail_terminal")
    _rejected(_stop, test_engine, route, 3, terminal)  # type must match the location
    port = _place(test_engine, "Demo Port C")
    _rejected(_stop, test_engine, route, 3, port, loading=False, unloading=False)
    _rejected(_stop, test_engine, route, 0, port)


def _vessel(engine: Engine, operator: Any, name: str = "Demo Ship", **kw: Any) -> Any:
    values = {
        "operator_id": operator,
        "name": name,
        "vessel_type": "ropax",
        "accompanied": True,
        "unaccompanied": True,
        "driver_cabins": True,
        **kw,
    }
    return _insert(engine, "vessels", **values)


def test_vessels_belong_to_ferry_operators(test_engine: Engine) -> None:
    ferry = _operator(test_engine)
    rail = _operator(test_engine, "Demo Rail X", "rail")
    _vessel(test_engine, ferry, lane_metres=3000, reefer_plug_count=0)
    _rejected(_vessel, test_engine, rail, "Demo Train")
    bad: list[dict[str, Any]] = [
        {"vessel_type": "tanker"},
        {"lane_metres": 0},
        {"deck_height_mm": 0},
        {"reefer_plug_count": -1},
        {"accompanied": False, "unaccompanied": False},
        {"accompanied": False, "driver_cabins": True},  # cabins are for drivers
    ]
    for number, kw in enumerate(bad):
        _rejected(_vessel, test_engine, ferry, f"Demo Bad {number}", **kw)


def test_vessel_adr_classes(test_engine: Engine) -> None:
    vessel = _vessel(test_engine, _operator(test_engine))
    for adr_class, acceptance in (("1", "forbidden"), ("7", "pre_approval"), ("4.1", "allowed")):
        _insert(
            test_engine,
            "vessel_adr_classes",
            returning="adr_class",
            vessel_id=vessel,
            adr_class=adr_class,
            acceptance=acceptance,
        )
    for adr_class, acceptance in (("10", "allowed"), ("3", "maybe")):
        _rejected(
            _insert,
            test_engine,
            "vessel_adr_classes",
            returning="adr_class",
            vessel_id=vessel,
            adr_class=adr_class,
            acceptance=acceptance,
        )


def _route_operator(engine: Engine, route: Any) -> Any:
    return _exec(engine, "SELECT operator_id FROM line_routes WHERE id = :id", id=route)


def _schedule(engine: Engine, route: Any, **kw: Any) -> Any:
    values = {
        "route_id": route,
        "route_mode": "ferry",
        "operator_id": _route_operator(engine, route),
        "weekday": 1,
        "valid_from": "2026-01-01",
    }
    return _insert(engine, "line_schedules", **{**values, **kw})


def test_schedules_and_calls(test_engine: Engine) -> None:
    operator, route = _line(test_engine)
    vessel = _vessel(test_engine, operator)
    schedule = _schedule(test_engine, route, vessel_id=vessel)
    _schedule(test_engine, route, weekday=3)  # vessel assigned per departure
    other_operator = _operator(test_engine, "Demo Other Ferry")
    foreign = _vessel(test_engine, other_operator, "Demo Foreign Ship")
    _rejected(_schedule, test_engine, route, vessel_id=foreign)  # vessel of another operator
    _rejected(_schedule, test_engine, route, operator_id=other_operator)  # not the route's
    _rejected(_schedule, test_engine, route, vessel_id=vessel, weekday=8)
    _rejected(_schedule, test_engine, route, vessel_id=vessel, valid_until="2025-12-31")

    def call(sequence: int, **kw: Any) -> Any:
        return _insert(
            test_engine,
            "line_schedule_calls",
            returning="sequence",
            schedule_id=schedule,
            route_id=route,
            sequence=sequence,
            **kw,
        )

    call(1, departure_day=0, departure_time="17:00")
    call(2, arrival_day=1, arrival_time="23:00")
    _rejected(call, 3, arrival_day=1, arrival_time="23:00")  # no such stop on the route
    other = _schedule(test_engine, route, vessel_id=vessel, weekday=2)
    for kw in (
        {},
        {"departure_day": 0},
        {"departure_day": 15, "departure_time": "10:00"},
        {"departure_day": 0, "departure_time": "10:00", "cutoff_minutes": -1},
    ):
        _rejected(
            _insert,
            test_engine,
            "line_schedule_calls",
            returning="sequence",
            schedule_id=other,
            route_id=route,
            sequence=1,
            **kw,
        )


def test_departures(test_engine: Engine) -> None:
    operator, route = _line(test_engine)
    vessel = _vessel(test_engine, operator)
    schedule = _schedule(test_engine, route, vessel_id=vessel)

    def departure(**kw: Any) -> Any:
        values = {
            "route_id": route,
            "route_mode": "ferry",
            "operator_id": operator,
            "service_date": "2026-11-23",
        }
        return _insert(test_engine, "line_departures", **{**values, **kw})

    first = departure(schedule_id=schedule, vessel_id=vessel)
    _rejected(departure, schedule_id=schedule)  # one departure per schedule and date
    departure()  # an extra departure entered by hand
    _rejected(departure, status="lost")
    _rejected(departure, cutoff_minutes=-1)
    foreign = _vessel(test_engine, _operator(test_engine, "Demo Other Ferry"), "Demo Foreign")
    _rejected(departure, vessel_id=foreign)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM line_departures LIMIT 1")).scalar() == (
            "planned"
        )

    def call(sequence: int, **kw: Any) -> Any:
        return _insert(
            test_engine,
            "line_departure_calls",
            returning="sequence",
            departure_id=first,
            route_id=route,
            sequence=sequence,
            **kw,
        )

    call(1, departs_at="2026-11-23T17:00+02:00", cutoff_at="2026-11-23T14:00+02:00")
    call(
        2,
        arrives_at="2026-11-24T23:00+01:00",
        estimated_arrives_at="2026-11-25T01:00+01:00",
        estimate_source="Demo operator notice",
        estimated_at="2026-11-24T12:00+01:00",
    )
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM line_departure_calls"))
    for kw in (
        {},
        {"arrives_at": "2026-11-23T18:00+02:00", "departs_at": "2026-11-23T17:00+02:00"},
        {"arrives_at": "2026-11-23T17:00+02:00", "departs_at": "2026-11-23T17:00+02:00"},
        {"departs_at": "2026-11-23T17:00+02:00", "cutoff_at": "2026-11-23T18:00+02:00"},
        {"departs_at": "2026-11-23T17:00+02:00", "estimated_departs_at": "2026-11-23T18:00+02:00"},
    ):
        _rejected(call, 1, **kw)
    _rejected(_exec, test_engine, "DELETE FROM line_schedules WHERE id = :id", id=schedule)


def test_rail_schedules_and_departures_have_no_vessel(test_engine: Engine) -> None:
    rail = _operator(test_engine, "Demo Rail X", "rail")
    route = _route(test_engine, rail, "Demo Rail A-B", mode="rail", accompanied=False)
    ferry_vessel = _vessel(test_engine, _operator(test_engine))
    _schedule(test_engine, route, route_mode="rail")
    _rejected(_schedule, test_engine, route, route_mode="rail", vessel_id=ferry_vessel, weekday=2)
    _rejected(
        _insert,
        test_engine,
        "line_departures",
        route_id=route,
        route_mode="rail",
        operator_id=rail,
        service_date="2026-11-23",
        vessel_id=ferry_vessel,
    )
