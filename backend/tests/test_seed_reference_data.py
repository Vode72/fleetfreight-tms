import copy
import json
from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from db.models import (
    Country,
    CountryRule,
    PublicHoliday,
    RoadRestriction,
    RoadRestrictionWindow,
)
from domain.restrictions import WindowKind
from scripts.seed_reference_data import ReferenceData, load_files, seed_reference_data

pytestmark = pytest.mark.usefixtures("clean_reference")

DEMO_COUNTRIES = {"FI", "SE", "EE", "LV", "LT", "PL", "DE", "NL", "BE", "DK", "FR", "ES", "IT"}


def _session(engine: Engine):  # type: ignore[no-untyped-def]
    return sessionmaker(bind=engine)()


def test_files_are_valid_and_cover_the_demo_countries() -> None:
    data = load_files()
    assert {c["code"] for c in data.countries} == DEMO_COUNTRIES
    assert all(
        r["source_url"].startswith("https://")
        for r in data.holidays + data.restrictions + data.rules
    )
    assert {r["country"] for r in data.rules} == DEMO_COUNTRIES


def test_seed_is_idempotent(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        first = seed_reference_data(session)
    with _session(test_engine) as session:
        second = seed_reference_data(session)
    assert first["countries"] == 13
    assert first["country_rules"] == 13
    assert first["road_restrictions"] == len(load_files().restrictions)
    assert first["road_restriction_windows"] > 0
    assert sum(second.values()) == 0  # nothing created, nothing filled


def test_seed_content_matches_the_sources(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session)
        de = session.scalars(
            select(RoadRestriction).where(RoadRestriction.code == "DE-SUNDAY-HOLIDAY-BAN")
        ).one()
        assert de.over_gross_weight_kg == 7500
        assert (de.weight_basis, de.with_trailer_any_weight) == ("vehicle", True)
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
        assert (poland.weight_basis, poland.with_trailer_any_weight) == ("combination", False)
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
        "country_rules.json": copy.deepcopy(data.rules),
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
        (lambda d: d["road_restrictions.json"][0].update(code="DE-bad code"), "code must"),
        (lambda d: d["road_restrictions.json"][0].update(region="DE-toolong"), "ISO 3166-2"),
        (lambda d: d["road_restrictions.json"][0].update(over_gross_weight_kg=0), "positive"),
        (lambda d: d["public_holidays.json"][0].update(checked_on="2099-01-01"), "checked_on"),
        (
            lambda d: d["road_restrictions.json"][0]["windows"][0].update(weekdays=[7, 7]),
            "distinct",
        ),
        (lambda d: d["country_rules.json"][0].update(truck_speed_other_kmh=0), "1-200"),
        (lambda d: d["country_rules.json"][0].update(country="XX"), "unknown country"),
        (
            lambda d: d["country_rules.json"][0].update(
                speed_over_gross_weight_kg=None, speed_weight_basis=None
            ),
            "vehicle class",
        ),
        (lambda d: d["country_rules.json"][0].update(speed_weight_basis=None), "both a weight"),
        (lambda d: d["country_rules.json"][0].update(speed_weight_basis="axle"), "axle"),
        (lambda d: d["country_rules.json"][0].update(toll_system="bridge"), "bridge"),
        (lambda d: d["country_rules.json"][0].update(max_length_mm=-1), "positive"),
        (
            lambda d: d["country_rules.json"][0].update(
                winter_equipment_start=1201, winter_equipment_end=None
            ),
            "both a start and an end",
        ),
        (
            lambda d: d["country_rules.json"][0].update(
                winter_equipment_start=1301, winter_equipment_end=301
            ),
            "MMDD",
        ),
        (lambda d: d["country_rules.json"].append(d["country_rules.json"][0]), "duplicate"),
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


def test_holidays_follow_easter() -> None:
    """Movable feasts in the files match Easter (5.4.2026, 28.3.2027)."""
    easter = {2026: date(2026, 4, 5), 2027: date(2027, 3, 28)}
    offsets = {
        "Karfreitag": -2,
        "Ostermontag": 1,
        "Christi Himmelfahrt": 39,
        "Pfingstmontag": 50,
        "Fronleichnam": 60,
        "Lundi de Pâques": 1,
        "Ascension": 39,
        "Lundi de Pentecôte": 50,
        "Wielkanoc": 0,
        "Poniedziałek Wielkanocny": 1,
        "Zielone Świątki": 49,
        "Boże Ciało": 60,
    }
    seen = set()
    for h in load_files().holidays:
        if h["name_local"] in offsets:
            day = date.fromisoformat(h["date"])
            assert (day - easter[day.year]).days == offsets[h["name_local"]], h
            seen.add(h["name_local"])
    assert seen == set(offsets)


def test_country_rule_periods_must_not_overlap(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session, ReferenceData(load_files().countries, [], []))

        def rule(start: date, end: date | None) -> CountryRule:
            return CountryRule(
                country="FI",
                valid_from=start,
                valid_until=end,
                toll_system="none",
                source_url="https://example.com",
                checked_on=date(2026, 11, 19),
            )

        session.add_all([rule(date(2026, 1, 1), date(2026, 6, 30)), rule(date(2026, 7, 1), None)])
        session.commit()  # adjacent periods and an open end are fine
        session.add(rule(date(2027, 1, 1), date(2027, 12, 31)))
        with pytest.raises(IntegrityError):
            session.commit()


def test_holiday_unique_also_without_region(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session, ReferenceData(load_files().countries, [], []))
        for _ in range(2):
            session.add(
                PublicHoliday(
                    country="FI",
                    region=None,
                    holiday_date=date(2026, 12, 6),
                    name_local="Itsenäisyyspäivä",
                    source_url="https://example.com",
                    checked_on=date(2026, 11, 19),
                )
            )
        with pytest.raises(IntegrityError):
            session.commit()


def _ban(session) -> RoadRestriction:  # type: ignore[no-untyped-def]
    seed_reference_data(session, ReferenceData(load_files().countries, [], []))
    ban = RoadRestriction(
        code="FI-TEST-BAN",
        country="FI",
        restriction_type="driving_ban",
        valid_from=date(2026, 1, 1),
        source_url="https://example.com",
        checked_on=date(2026, 11, 19),
    )
    session.add(ban)
    session.commit()
    return ban


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "weekdays", "weekdays": []},
        {"kind": "weekdays", "weekdays": [8]},
        {"kind": "public_holiday", "weekdays": [7]},
        {"kind": "public_holiday", "start_time": time(22), "end_time": time(6)},
        {"kind": "public_holiday", "season_start": 701},
        {"kind": "public_holiday", "season_start": 1301, "season_end": 1302},
        {"kind": "public_holiday", "season_start": 732, "season_end": 801},
        {"kind": "date"},
        {"kind": "public_holiday", "on_date": date(2026, 1, 1)},
        {"kind": "date", "on_date": date(2026, 1, 1), "season_start": 101, "season_end": 131},
        {"kind": "public_holiday", "restriction_type": "bridge"},
    ],
)
def test_window_checks(test_engine: Engine, fields: dict[str, object]) -> None:
    with _session(test_engine) as session:
        ban = _ban(session)
        row = {"restriction_id": ban.id, "start_time": time(0)} | fields
        session.add(RoadRestrictionWindow(**row))
        with pytest.raises(IntegrityError):
            session.commit()


def test_solo_tractor_rule_is_recorded_and_filled_into_older_rows(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session)
        rules = dict(
            session.execute(select(RoadRestriction.code, RoadRestriction.solo_tractor)).all()
        )
        assert rules["DE-SUNDAY-HOLIDAY-BAN"] == "exempt"
        assert rules["IT-BAN-CALENDAR-2026"] == "conditional"
        assert rules["PL-HOLIDAY-BAN"] == "not_exempt"
        assert rules["FR-WEEKEND-HOLIDAY-BAN"] is None  # not recorded
        # A row loaded before D85 has no value: the loader fills it but never overwrites.
        session.execute(
            text(
                "UPDATE road_restrictions SET solo_tractor = NULL"
                " WHERE code = 'DE-SUNDAY-HOLIDAY-BAN'"
            )
        )
        session.execute(
            text(
                "UPDATE road_restrictions SET solo_tractor = 'exempt' WHERE code = 'PL-HOLIDAY-BAN'"
            )
        )
        session.commit()
        created = seed_reference_data(session)
        assert created["filled_values"] == 1
        rules = dict(
            session.execute(select(RoadRestriction.code, RoadRestriction.solo_tractor)).all()
        )
        assert rules["DE-SUNDAY-HOLIDAY-BAN"] == "exempt"
        assert rules["PL-HOLIDAY-BAN"] == "exempt"


def test_solo_tractor_rule_only_on_driving_bans(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session, ReferenceData(load_files().countries, [], []))
        session.add(
            RoadRestriction(
                code="FI-TEST-BRIDGE",
                country="FI",
                restriction_type="bridge",
                limit_value=40000,
                limit_unit="kg",
                solo_tractor="exempt",
                valid_from=date(2026, 1, 1),
                source_url="https://example.com",
                checked_on=date(2026, 11, 19),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_country_rules_are_recorded_and_filled_into_older_rows(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session)
        rules = {r.country: r for r in session.scalars(select(CountryRule))}
        assert (rules["DE"].truck_speed_motorway_kmh, rules["DE"].truck_speed_other_kmh) == (80, 60)
        assert (rules["IT"].truck_speed_motorway_kmh, rules["IT"].truck_speed_other_kmh) == (80, 70)
        # D87: the class the speeds apply to.
        assert (rules["IT"].speed_over_gross_weight_kg, rules["IT"].speed_weight_basis) == (
            12000,
            "vehicle",
        )
        assert (rules["DE"].speed_over_gross_weight_kg, rules["DE"].speed_weight_basis) == (
            7500,
            "combination",
        )
        assert (rules["FI"].truck_speed_motorway_kmh, rules["FI"].truck_speed_other_kmh) == (80, 80)
        # Sweden's heavy vehicle season crosses the new year; car-page seasons are not recorded.
        assert (rules["SE"].winter_equipment_start, rules["SE"].winter_equipment_end) == (1110, 410)
        assert rules["LT"].winter_equipment_start is None
        assert rules["NL"].truck_speed_motorway_kmh is None  # not recorded
        assert all(r.toll_system is None for r in rules.values())  # no official source yet
        assert all(r.posted_worker_declaration and r.cabotage_note for r in rules.values())
        # Unrecorded values are filled, recorded ones are never overwritten.
        session.execute(
            text(
                "UPDATE country_rules SET truck_speed_other_kmh = NULL,"
                " source_url = 'https://old.example.com', checked_on = '2026-01-02'"
                " WHERE country = 'PL'"
            )
        )
        session.execute(
            text("UPDATE country_rules SET truck_speed_other_kmh = 65 WHERE country = 'DE'")
        )
        session.commit()
        created = seed_reference_data(session)
        assert created["filled_values"] == 1
        assert created["country_rules"] == 0
        session.expire_all()
        rules = {r.country: r for r in session.scalars(select(CountryRule))}
        assert rules["PL"].truck_speed_other_kmh == 70
        # The filled value's source and check day replace the old ones.
        assert rules["PL"].source_url.startswith("https://europa.eu/youreurope/")
        assert rules["PL"].checked_on == date(2026, 11, 19)
        assert rules["DE"].truck_speed_other_kmh == 65


def test_toll_system_may_be_unrecorded_but_not_unknown(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session, ReferenceData(load_files().countries, [], []))
        session.add(
            CountryRule(
                country="FI",
                valid_from=date(2026, 1, 1),
                toll_system=None,
                source_url="https://example.com",
                checked_on=date(2026, 11, 19),
            )
        )
        session.commit()  # NULL = not recorded
        with pytest.raises(IntegrityError):
            session.execute(text("UPDATE country_rules SET toll_system = 'bridge'"))


def test_a_recorded_speed_needs_its_vehicle_class(test_engine: Engine) -> None:
    with _session(test_engine) as session:
        seed_reference_data(session, ReferenceData(load_files().countries, [], []))
        session.add(
            CountryRule(
                country="FI",
                valid_from=date(2026, 1, 1),
                truck_speed_other_kmh=80,
                source_url="https://example.com",
                checked_on=date(2026, 11, 19),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def _windows(session, code: str) -> list[RoadRestrictionWindow]:  # type: ignore[no-untyped-def]
    restriction = session.scalars(select(RoadRestriction).where(RoadRestriction.code == code)).one()
    return list(
        session.scalars(
            select(RoadRestrictionWindow).where(
                RoadRestrictionWindow.restriction_id == restriction.id
            )
        )
    )


def test_spain_section_bans_follow_the_dgt_annex(test_engine: Engine) -> None:
    """Spot checks against the DGT 2026 Annex II (BOE-A-2026-1255) and its amendment."""
    with _session(test_engine) as session:
        seed_reference_data(session)
        spain = session.scalars(
            select(RoadRestriction).where(RoadRestriction.country == "ES")
        ).all()
        assert len(spain) == 125  # 557 annex rows grouped by section and direction
        assert all(r.over_gross_weight_kg == 7500 for r in spain)
        # N-230 towards France: Fridays Jan-Mar and 4-18 Dec 17-24 h, plus dated bans.
        n230 = _windows(session, "ES-N-230-64-1-149-2-D")
        weekly = {
            (tuple(w.weekdays), w.season_start, w.season_end, w.start_time, w.end_time)
            for w in n230
            if w.kind == "weekdays"
        }
        assert weekly == {((5,), 101, 331, time(17), None), ((5,), 1204, 1218, time(17), None)}
        assert (date(2026, 4, 3), time(8), time(13)) in {
            (w.on_date, w.start_time, w.end_time) for w in n230
        }
        # Two windows on one day (Easter Sunday on the AP-4 towards Seville).
        ap4 = [w for w in _windows(session, "ES-AP-4-78-13-5-D") if w.on_date == date(2026, 4, 5)]
        assert {(w.start_time, w.end_time) for w in ap4} == {
            (time(10), time(13)),
            (time(16), time(20)),
        }
        # A-8 in Cantabria: the region's 28 July holiday joins the weekend period.
        assert date(2026, 7, 28) in {w.on_date for w in _windows(session, "ES-A-8-139-2-169-D")}
        # The Valencia Grand Prix moved from 20-22 to 27-29 November (BOE-A-2026-13892).
        cheste = {w.on_date for w in _windows(session, "ES-CV-50-72-5-76-B")}
        assert cheste == {date(2026, 11, 27), date(2026, 11, 28), date(2026, 11, 29)}
