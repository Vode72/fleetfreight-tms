"""Routing suggestions and LTL linehauls (2B-3c part 2, D64, D96): pure domain rules."""

from datetime import date, time
from typing import Any

import pytest

from domain.routing import (
    OnwardMode,
    Preference,
    add_working_days,
    promised_delivery,
    runs_on,
    suggest,
    validate_gateway_on_route,
    validate_linehaul,
    validate_linehaul_periods,
    validate_preference,
    validate_thermo_linehaul,
)

D0 = date(2026, 1, 1)


def _pref_kw(**kw: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "origin_country": "FI",
        "destination_country": "DE",
        "postal_prefix": None,
        "priority": 1,
        "has_gateway": True,
        "has_line_route": False,
        "onward_mode": OnwardMode.ROAD,
        "has_onward_route": False,
        "has_via": False,
        "valid_from": D0,
        "valid_until": None,
    }
    values.update(kw)
    return values


def test_valid_preferences() -> None:
    validate_preference(**_pref_kw())
    validate_preference(**_pref_kw(origin_country=None, postal_prefix="20"))
    validate_preference(
        **_pref_kw(has_line_route=True, onward_mode=OnwardMode.RAIL, has_onward_route=True)
    )
    # Road only: a border crossing, no gateway.
    validate_preference(**_pref_kw(destination_country="SE", has_gateway=False, has_via=True))


@pytest.mark.parametrize(
    "kw",
    [
        {"destination_country": "de"},
        {"origin_country": "FIN"},
        {"origin_country": "DE"},
        {"postal_prefix": "20 1"},
        {"postal_prefix": "12345678901"},
        {"priority": 0},
        {"has_gateway": False},
        {"has_gateway": False, "has_via": True, "has_line_route": True},
        {"onward_mode": OnwardMode.RAIL},
        {"has_onward_route": True},
        {
            "has_gateway": False,
            "has_via": True,
            "onward_mode": OnwardMode.RAIL,
            "has_onward_route": True,
        },
        {"valid_until": date(2025, 12, 31)},
    ],
)
def test_invalid_preferences(kw: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        validate_preference(**_pref_kw(**kw))


def test_gateway_must_be_a_stop_of_the_route() -> None:
    validate_gateway_on_route("rostock", ["hanko", "rostock"])
    with pytest.raises(ValueError):
        validate_gateway_on_route("lubeck", ["hanko", "rostock"])


def _p(
    value: str,
    *,
    origin: str | None = "FI",
    dest: str = "FR",
    priority: int = 1,
    prefix: str | None = None,
    valid_from: date = D0,
    valid_until: date | None = None,
) -> Preference[str]:
    return Preference(origin, dest, prefix, priority, valid_from, valid_until, value)


def _suggest(prefs: list[Preference[str]], **kw: Any) -> list[str]:
    values: dict[str, Any] = {
        "origin_country": "FI",
        "destination_country": "FR",
        "postal_code": None,
        "on": date(2026, 11, 26),
    }
    values.update(kw)
    return suggest(prefs, **values)


def test_suggestions_are_ordered_by_priority_and_keep_equal_alternatives() -> None:
    prefs = [_p("lubeck", priority=2), _p("antwerpen"), _p("travemunde", priority=2)]
    assert _suggest(prefs) == ["antwerpen", "lubeck", "travemunde"]


def test_only_matching_country_pair_and_validity() -> None:
    prefs = [
        _p("old", valid_until=date(2026, 6, 30)),
        _p("future", valid_from=date(2027, 1, 1)),
        _p("other destination", dest="IT"),
        _p("import", origin="FR", dest="FI"),
        _p("current"),
    ]
    assert _suggest(prefs) == ["current"]
    assert _suggest(prefs, origin_country="FR", destination_country="FI") == ["import"]
    assert _suggest(prefs, destination_country="ES") == []


def test_more_specific_rows_replace_less_specific_ones() -> None:
    open_origin = _p("any origin", origin=None)
    country = _p("country")
    region = _p("region 75", prefix="75")
    city = _p("paris 750", prefix="750", priority=3)
    # A named origin replaces an open one.
    assert _suggest([open_origin, country]) == ["country"]
    assert _suggest([open_origin], origin_country="SE") == ["any origin"]
    # A matching postal prefix replaces the country level; the longest prefix wins.
    prefs = [open_origin, country, region, city]
    assert _suggest(prefs, postal_code="75 001") == ["paris 750"]
    assert _suggest(prefs, postal_code="75900") == ["region 75"]
    assert _suggest(prefs, postal_code="13001") == ["country"]
    assert _suggest(prefs) == ["country"]


def _lh_kw(**kw: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "origin_id": "central",
        "destination_id": "tampere",
        "weekdays": (1, 2, 3, 4, 5),
        "departure_time": time(21, 0),
        "cutoff_time": time(18, 0),
        "arrival_day": 1,
        "arrival_time": time(3, 0),
        "delivery_days": 1,
        "valid_from": D0,
        "valid_until": None,
    }
    values.update(kw)
    return values


def test_valid_linehauls() -> None:
    validate_linehaul(**_lh_kw())
    validate_linehaul(**_lh_kw(arrival_day=0, arrival_time=time(23, 30), cutoff_time=time(21, 0)))
    validate_linehaul(**_lh_kw(weekdays=(7,), delivery_days=0))


@pytest.mark.parametrize(
    "kw",
    [
        {"destination_id": "central"},
        {"weekdays": ()},
        {"weekdays": (0, 1)},
        {"weekdays": (8,)},
        {"weekdays": (1, 1)},
        {"cutoff_time": time(21, 30)},
        {"arrival_day": 0, "arrival_time": time(21, 0)},
        {"arrival_day": 15},
        {"delivery_days": -1},
        {"valid_until": date(2025, 1, 1)},
    ],
)
def test_invalid_linehauls(kw: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        validate_linehaul(**_lh_kw(**kw))


def test_runs_on_weekdays() -> None:
    assert runs_on((1, 2, 3, 4, 5), date(2026, 11, 27))  # Friday
    assert not runs_on((1, 2, 3, 4, 5), date(2026, 11, 28))  # Saturday


def test_delivery_promise_counts_working_days() -> None:
    friday, monday = date(2026, 11, 27), date(2026, 11, 30)
    assert promised_delivery(friday, 1, []) == monday
    assert promised_delivery(date(2026, 11, 26), 1, []) == friday
    assert promised_delivery(friday, 0, []) == friday
    # A weekday holiday moves the promise.
    christmas_eve = date(2026, 12, 24)  # Thursday
    holidays = [christmas_eve, date(2026, 12, 25)]
    assert promised_delivery(date(2026, 12, 23), 1, holidays) == date(2026, 12, 28)
    assert add_working_days(date(2026, 12, 23), 2, holidays) == date(2026, 12, 29)


def test_linehaul_periods_must_not_overlap() -> None:
    validate_linehaul_periods([(D0, date(2026, 6, 30)), (date(2026, 7, 1), None)])
    with pytest.raises(ValueError):
        validate_linehaul_periods([(D0, None), (date(2026, 7, 1), None)])
    with pytest.raises(ValueError):
        validate_linehaul_periods([(D0, date(2026, 7, 1)), (date(2026, 7, 1), None)])


def test_thermo_linehaul_runs_between_cold_terminals() -> None:
    validate_thermo_linehaul(True, True, True)
    validate_thermo_linehaul(False, False, True)
    with pytest.raises(ValueError):
        validate_thermo_linehaul(True, True, False)
