import copy
import json
from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from db.models import Country, PublicHoliday, RoadRestriction, RoadRestrictionWindow
from domain.restrictions import WindowKind
from scripts.seed_reference_data import ReferenceData, load_files, seed_reference_data

pytestmark = pytest.mark.usefixtures("clean_reference")

DEMO_COUNTRIES = {"FI", "SE", "EE", "LV", "LT", "PL", "DE", "NL", "BE", "DK", "FR", "ES", "IT"}


def _session(engine: Engine):  # type: ignore[no-untyped-def]
    return sessionmaker(bind=engine)()


def test_files_are_valid_and_cover_the_demo_countries() -> None:
    data = load_files()
    assert {c["code"] for c in data.countries} == DEMO_COUNTRIES
    assert all(r["source_url"].startswith("https://") for r in data.holidays + data.restrictions)


def test_seed_is_idempotent(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        first = seed_reference_data(session)
    with _session(test_engine) as session:
        second = seed_reference_data(session)
    assert first["countries"] == 13
    assert first["road_restrictions"] == len(load_files().restrictions)
    assert first["road_restriction_windows"] > 0
    assert sum(second.values()) == 0


def test_seed_content_matches_the_sources(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session)
        de = session.scalars(
            select(RoadRestriction).where(RoadRestriction.code == "DE-SUNDAY-HOLIDAY-BAN")
        ).one()
        assert de.over_gross_weight_kg == 7500
        windows = session.scalars(
            select(RoadRestrictionWindow).where(RoadRestrictionWindow.restriction_id == de.id)
        ).all()
        assert {(w.kind, tuple(w.weekdays), w.start_time, w.end_time) for w in windows} == {
            (WindowKind.WEEKDAYS.value, (7,), time(0), time(22)),
            (WindowKind.PUBLIC_HOLIDAY.value, (), time(0), time(22)),
        }
        italy = session.scalars(
            select(RoadRestriction).where(RoadRestriction.code == "IT-BAN-CALENDAR-2026")
        ).one()
        it_windows = session.scalars(
            select(RoadRestrictionWindow).where(RoadRestrictionWindow.restriction_id == italy.id)
        ).all()
        assert len(it_windows) == 79
        assert all(w.on_date is not None and w.on_date.year == 2026 for w in it_windows)
        poland = session.scalars(
            select(RoadRestriction).where(RoadRestriction.code == "PL-HOLIDAY-BAN")
        ).one()
        assert poland.over_gross_weight_kg == 12000
        # Easter 2026 is 5 April: Easter Monday is a ban day in DE, FR and PL.
        easter_monday = session.scalars(
            select(PublicHoliday.country).where(PublicHoliday.holiday_date == date(2026, 4, 6))
        ).all()
        assert set(easter_monday) == {"DE", "FR", "PL"}
        # Corpus Christi is a German ban day only in the listed states.
        corpus = session.scalars(
            select(PublicHoliday.region).where(
                PublicHoliday.country == "DE", PublicHoliday.holiday_date == date(2026, 6, 4)
            )
        ).all()
        assert set(corpus) == {"DE-BW", "DE-BY", "DE-HE", "DE-NW", "DE-RP", "DE-SL"}


def test_existing_rows_are_not_overwritten(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session)
        session.execute(text("UPDATE countries SET name_fi = 'Muokattu' WHERE code = 'FI'"))
        session.commit()
        seed_reference_data(session)
        assert session.get(Country, "FI").name_fi == "Muokattu"


def _bad(tmp_path: Path, change) -> Path:  # type: ignore[no-untyped-def]
    data = load_files()
    raw = {
        "countries.json": copy.deepcopy(data.countries),
        "public_holidays.json": copy.deepcopy(data.holidays),
        "road_restrictions.json": copy.deepcopy(data.restrictions),
    }
    change(raw)
    for name, rows in raw.items():
        (tmp_path / name).write_text(json.dumps(rows), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["road_restrictions.json"][0].update(source_url="http://x"), "https"),
        (lambda d: d["road_restrictions.json"][0].update(windows=[]), "needs windows"),
        (lambda d: d["road_restrictions.json"][0].update(code="XX-FOO"), "unknown country"),
        (
            lambda d: d["road_restrictions.json"][0]["windows"][0].update(
                start="22:00", end="06:00"
            ),
            "within one day",
        ),
        (lambda d: d["public_holidays.json"].append(d["public_holidays.json"][0]), "duplicate"),
        (lambda d: d["public_holidays.json"][0].update(region="FR-ARA"), "region"),
        (lambda d: d["countries.json"][0].update(time_zone="Mars/Base"), "time zone"),
    ],
)
def test_an_invalid_row_stops_the_load(tmp_path: Path, change, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=message):
        load_files(_bad(tmp_path, change))


def test_database_rejects_a_window_on_a_non_ban(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session, ReferenceData(load_files().countries, [], []))
        limit = RoadRestriction(
            code="FI-TEST-BRIDGE",
            country="FI",
            restriction_type="bridge",
            limit_value=40000,
            limit_unit="kg",
            valid_from=date(2026, 1, 1),
            source_url="https://example.com",
            checked_on=date(2026, 11, 19),
        )
        session.add(limit)
        session.commit()
        session.add(
            RoadRestrictionWindow(
                restriction_id=limit.id,
                restriction_type="bridge",
                kind="weekdays",
                weekdays=[7],
                start_time=time(0),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "fields",
    [
        {"restriction_type": "bridge", "limit_value": None, "limit_unit": None},
        {"restriction_type": "height", "limit_value": 4000, "limit_unit": "kg"},
        {"restriction_type": "driving_ban", "limit_value": 7500, "limit_unit": "kg"},
        {"restriction_type": "adr_tunnel"},
        {"restriction_type": "driving_ban", "tunnel_category": "C"},
        {"restriction_type": "driving_ban", "exemptions": ["sunday_drivers"]},
        {"restriction_type": "driving_ban", "region": "SE-AB"},
        {"restriction_type": "driving_ban", "source_url": "http://example.com"},
        {"restriction_type": "driving_ban", "code": "fi-lower"},
    ],
)
def test_database_checks_mirror_the_domain_rules(
    test_engine: Engine, fields: dict[str, object]
) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session, ReferenceData(load_files().countries, [], []))
        row = {
            "code": "FI-TEST",
            "country": "FI",
            "valid_from": date(2026, 1, 1),
            "source_url": "https://example.com",
            "checked_on": date(2026, 11, 19),
        } | fields
        session.add(RoadRestriction(**row))
        with pytest.raises(IntegrityError):
            session.commit()
