"""Constraints of routing_preferences and ltl_linehauls (2B-3c part 2, D64, D96)."""

from typing import Any

import pytest
from sqlalchemy import Engine

from tests.test_lines_db import _insert, _operator, _place, _rejected, _route, _stop

pytestmark = pytest.mark.usefixtures("clean_registers")


def _terminal(engine: Engine, name: str) -> Any:
    return _insert(
        engine,
        "locations",
        type="terminal",
        name=name,
        country="FI",
        timezone="Europe/Helsinki",
        loading_docks=2,
        cold_storage=False,
    )


def _setup(engine: Engine) -> dict[str, Any]:
    ferry = _operator(engine)
    route = _route(engine, ferry)
    port = _place(engine, "Demo Port G")
    _stop(engine, route, 1, _place(engine, "Demo Port H"))
    _stop(engine, route, 2, port)
    rail = _operator(engine, "Demo Rail Op", "rail")
    rail_route = _route(engine, rail, "Demo Rail G-V", mode="rail", accompanied=False)
    return {
        "port": port,
        "route": route,
        "rail_route": rail_route,
        "rail_terminal": _place(engine, "Demo Rail Terminal G", "rail_terminal"),
        "border": _place(engine, "Demo Border G", "border_crossing"),
        "terminal": _terminal(engine, "Demo Terminal G"),
        "terminal2": _terminal(engine, "Demo Terminal H"),
    }


def _pref(engine: Engine, s: dict[str, Any], **kw: Any) -> Any:
    values: dict[str, Any] = {
        "origin_country": "FI",
        "destination_country": "DE",
        "priority": 1,
        "gateway_location_id": s["port"],
        "gateway_location_type": "port",
        "valid_from": "2026-01-01",
    }
    values.update(kw)
    return _insert(
        engine, "routing_preferences", **{k: v for k, v in values.items() if v is not None}
    )


def test_routing_preference_variants(test_engine: Engine) -> None:
    s = _setup(test_engine)
    _pref(test_engine, s)
    _pref(test_engine, s, origin_country=None, postal_prefix="20")
    _pref(
        test_engine,
        s,
        destination_country="IT",
        line_route_id=s["route"],
        line_route_mode="ferry",
        onward_mode="rail",
        onward_route_id=s["rail_route"],
        onward_route_mode="rail",
    )
    # Road only through a border crossing.
    _pref(
        test_engine,
        s,
        destination_country="SE",
        gateway_location_id=None,
        gateway_location_type=None,
        via_location_id=s["border"],
        via_location_type="border_crossing",
    )
    _pref(
        test_engine,
        s,
        gateway_location_id=s["rail_terminal"],
        gateway_location_type="rail_terminal",
    )


@pytest.mark.parametrize(
    "kw",
    [
        {"destination_country": "de"},
        {"origin_country": "DE"},
        {"postal_prefix": "20 1"},
        {"priority": 0},
        {"onward_mode": "sea"},
        {"valid_until": "2025-12-31"},
    ],
)
def test_routing_preference_value_checks(test_engine: Engine, kw: dict[str, Any]) -> None:
    s = _setup(test_engine)
    _rejected(_pref, test_engine, s, **kw)


def test_routing_preference_leg_checks(test_engine: Engine) -> None:
    s = _setup(test_engine)
    # Gateway must be a port or rail terminal; the type must match the row (composite key).
    _rejected(
        _pref, test_engine, s, gateway_location_id=s["terminal"], gateway_location_type="terminal"
    )
    _rejected(_pref, test_engine, s, gateway_location_type="rail_terminal")
    # Neither gateway nor crossing.
    _rejected(_pref, test_engine, s, gateway_location_id=None, gateway_location_type=None)
    # A ferry route needs a gateway; a rail route is not a ferry route.
    _rejected(
        _pref,
        test_engine,
        s,
        gateway_location_id=None,
        gateway_location_type=None,
        via_location_id=s["border"],
        via_location_type="border_crossing",
        line_route_id=s["route"],
        line_route_mode="ferry",
    )
    _rejected(_pref, test_engine, s, line_route_id=s["rail_route"], line_route_mode="rail")
    # Onward rail needs a rail route and only rail has one.
    _rejected(_pref, test_engine, s, onward_mode="rail")
    _rejected(_pref, test_engine, s, onward_route_id=s["rail_route"], onward_route_mode="rail")
    _rejected(
        _pref,
        test_engine,
        s,
        onward_mode="rail",
        onward_route_id=s["route"],
        onward_route_mode="ferry",
    )
    # An id without its type or mode would skip the composite foreign key (MATCH SIMPLE).
    _rejected(_pref, test_engine, s, gateway_location_type=None)
    _rejected(_pref, test_engine, s, destination_country="SE", via_location_id=s["border"])
    _rejected(_pref, test_engine, s, line_route_id=s["route"])
    _rejected(_pref, test_engine, s, onward_mode="rail", onward_route_id=s["rail_route"])
    _rejected(_pref, test_engine, s, line_route_mode="ferry")
    # The crossing must be a border crossing.
    _rejected(_pref, test_engine, s, via_location_id=s["terminal"], via_location_type="terminal")


def _linehaul(engine: Engine, s: dict[str, Any], **kw: Any) -> Any:
    values: dict[str, Any] = {
        "origin_terminal_id": s["terminal"],
        "destination_terminal_id": s["terminal2"],
        "weekdays": [1, 2, 3, 4, 5],
        "departure_time": "21:00",
        "cutoff_time": "18:00",
        "arrival_day": 1,
        "arrival_time": "03:00",
        "delivery_days": 1,
        "valid_from": "2026-01-01",
    }
    values.update(kw)
    return _insert(engine, "ltl_linehauls", **values)


def test_linehaul_checks(test_engine: Engine) -> None:
    s = _setup(test_engine)
    _linehaul(test_engine, s)
    _linehaul(test_engine, s, arrival_day=0, arrival_time="23:00", weekdays=[7])
    bad: list[dict[str, Any]] = [
        {"destination_terminal_id": s["terminal"]},
        {"origin_terminal_id": s["port"]},  # not a terminal (composite key with type)
        {"origin_terminal_id": s["port"], "origin_terminal_type": "port"},
        {"weekdays": []},
        {"weekdays": [0, 1]},
        {"weekdays": [8]},
        {"cutoff_time": "21:30"},
        {"arrival_day": 0, "arrival_time": "20:00"},
        {"arrival_day": 15},
        {"delivery_days": -1},
        {"valid_until": "2025-12-31"},
    ]
    for kw in bad:
        _rejected(_linehaul, test_engine, s, **kw)
