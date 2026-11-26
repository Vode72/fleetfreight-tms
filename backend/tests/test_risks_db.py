"""Constraints of the 2B-3e risk tables (D95), checked against the migrated schema."""

import uuid
from datetime import date
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from domain.risks import DEMO_WAIT_NOTE

pytestmark = pytest.mark.usefixtures("clean_registers")


def _insert(engine: Engine, table: str, returning: str = "id", **values: Any) -> Any:
    columns = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    with engine.begin() as conn:
        sql = f"INSERT INTO {table} ({columns}) VALUES ({params}) RETURNING {returning}"
        return conn.execute(text(sql), values).scalar()


def _rejected(engine: Engine, table: str, **values: Any) -> None:
    with pytest.raises(IntegrityError):
        _insert(engine, table, "1", **values)


def _report(engine: Engine, **kw: Any) -> uuid.UUID:
    values = {
        "source_name": "Demo source",
        "report_month": date(2026, 6, 1),
        "source_url": "https://example.com/june",
        "checked_on": date(2026, 11, 24),
        **kw,
    }
    return _insert(engine, "cargo_crime_reports", **values)  # type: ignore[no-any-return]


def test_report_month_is_the_first_day_and_unique_per_source(test_engine: Engine) -> None:
    _report(test_engine)
    _rejected(
        test_engine,
        "cargo_crime_reports",
        source_name="Demo source",
        report_month=date(2026, 6, 1),
        source_url="https://example.com/again",
        checked_on=date(2026, 11, 24),
    )
    with pytest.raises(IntegrityError):
        _report(test_engine, report_month=date(2026, 7, 2))
    with pytest.raises(IntegrityError):
        _report(test_engine, report_month=date(2026, 8, 1), source_url="http://example.com")


def test_counts_are_not_negative_and_one_per_country(test_engine: Engine) -> None:
    report = _report(test_engine)
    _insert(
        test_engine,
        "cargo_crime_counts",
        "country",
        report_id=report,
        country="DE",
        incident_count=440,
    )
    _rejected(test_engine, "cargo_crime_counts", report_id=report, country="DE", incident_count=1)
    _rejected(test_engine, "cargo_crime_counts", report_id=report, country="IT", incident_count=-1)
    _rejected(test_engine, "cargo_crime_counts", report_id=report, country="it", incident_count=1)
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM cargo_crime_reports WHERE id = :id"), {"id": report})


def _area(**kw: Any) -> dict[str, Any]:
    return {
        "country": "NL",
        "road_ref": "A2",
        "level": 4,
        "source_type": "data",
        "basis": "Named hotspot",
        "source_url": "https://example.com/report",
        "checked_on": date(2026, 11, 24),
        "valid_from": date(2026, 1, 1),
        **kw,
    }


@pytest.mark.parametrize(
    "kw",
    [
        {"level": 0},
        {"level": 6},
        {"source_type": "rumour"},
        {"source_url": None},
        {"source_url": "http://example.com"},
        {"basis": " "},
        {"region": "BE-VAN"},
        {"road_ref": " "},
        {"valid_until": date(2025, 12, 31)},
        {"checked_on": date(2025, 12, 31)},
    ],
)
def test_risk_area_checks(test_engine: Engine, kw: dict[str, Any]) -> None:
    _rejected(test_engine, "risk_areas", **_area(**kw))


def test_expert_estimate_needs_no_link_and_periods_do_not_overlap(test_engine: Engine) -> None:
    _insert(test_engine, "risk_areas", **_area(valid_until=date(2026, 6, 30)))
    _rejected(test_engine, "risk_areas", **_area(valid_from=date(2026, 6, 30)))
    _insert(test_engine, "risk_areas", **_area(valid_from=date(2026, 7, 1), level=5))
    # the same road in another country, or the whole country, is another area
    _insert(test_engine, "risk_areas", **_area(country="BE"))
    _insert(
        test_engine,
        "risk_areas",
        **_area(road_ref=None, source_type="expert_estimate", source_url=None, level=2),
    )
    _rejected(
        test_engine,
        "risk_areas",
        **_area(road_ref=None, source_type="expert_estimate", source_url=None),
    )


def _crossing(engine: Engine) -> uuid.UUID:
    location_id = _insert(
        engine,
        "locations",
        type="border_crossing",
        name="Demo Crossing",
        country="SE",
        timezone="Europe/Stockholm",
    )
    _insert(
        engine,
        "border_crossing_details",
        "location_id",
        location_id=location_id,
        other_country="NO",
    )
    return location_id  # type: ignore[no-any-return]


def _wait(location_id: uuid.UUID, **kw: Any) -> dict[str, Any]:
    return {
        "location_id": location_id,
        "direction": "exit",
        "observed_at": "2026-11-02T07:00:00+01:00",
        "wait_minutes": 45,
        "source_type": "manual",
        **kw,
    }


@pytest.mark.parametrize(
    "kw",
    [
        {"direction": "north"},
        {"wait_minutes": -1},
        {"source_type": "guess"},
        {"source_type": "official_feed"},
        {"source_type": "historical_avg"},
        {"source_url": "http://example.com"},
        {"source_type": "demo"},
        {"source_type": "demo", "note": "Measured."},
    ],
)
def test_wait_observation_checks(test_engine: Engine, kw: dict[str, Any]) -> None:
    _rejected(test_engine, "border_wait_observations", **_wait(_crossing(test_engine), **kw))


def test_wait_observations(test_engine: Engine) -> None:
    crossing = _crossing(test_engine)
    _insert(test_engine, "border_wait_observations", **_wait(crossing))
    _rejected(test_engine, "border_wait_observations", **_wait(crossing))
    _insert(
        test_engine,
        "border_wait_observations",
        **_wait(crossing, source_type="demo", note=DEMO_WAIT_NOTE),
    )
    _insert(
        test_engine,
        "border_wait_observations",
        **_wait(crossing, source_type="official_feed", source_url="https://example.com/feed"),
    )
    # only border crossings with details
    other = _insert(
        test_engine,
        "locations",
        type="parking",
        name="Demo P",
        country="SE",
        timezone="Europe/Stockholm",
    )
    _rejected(test_engine, "border_wait_observations", **_wait(other))
