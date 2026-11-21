"""Load reference data: countries, country rules, holidays and road restrictions (2B-3a, D84).

Usage (from the backend directory):
    uv run python -m scripts.seed_reference_data

Unlike the demo data this is real public information, needed in every environment, so it runs in
production too. The rows live in versioned JSON files in `reference_data/`; every holiday and
restriction row carries the official source it was taken from and the day it was checked. Legal
values are never written from memory (CLAUDE.md, D84).

Idempotent: countries are matched by code, country rules by country and validity start,
holidays by country, region and date, restrictions by their code. Only missing rows are created;
existing rows are left as they are, except that a value not recorded yet (NULL, e.g. a
restriction's solo tractor rule, D85, or a country's speed limit) is filled in, and an open
country rule period is closed when the file gives it an end (a later period follows, D67). A
rule that changes gets a new row with its own validity period, not an edit. A restriction's windows
are created with the restriction.

Every row is checked against the domain rules (domain/restrictions.py) before anything is
written; one invalid row stops the whole load.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from db.models import Country, CountryRule, PublicHoliday, RoadRestriction, RoadRestrictionWindow
from db.session import get_engine
from domain.countries import validate_country
from domain.locations import validate_timezone
from domain.restrictions import (
    BanWindow,
    Exemption,
    LimitUnit,
    LoadState,
    RestrictionType,
    SoloTractor,
    TollSystem,
    WeightBasis,
    WindowKind,
    month_day,
    validate_period,
    validate_restriction,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "reference_data"
_CODE_RE = re.compile(r"[A-Z]{2}-[A-Z0-9-]+")
_REGION_RE = re.compile(r"[A-Z]{2}-[A-Z0-9]{1,3}")
_EARLIEST_CHECK = date(2026, 1, 1)
TABLES = (
    "countries",
    "country_rules",
    "public_holidays",
    "road_restrictions",
    "road_restriction_windows",
)
# Country rule values that may be left unrecorded (NULL) and filled in later.
RULE_VALUES = (
    "truck_speed_motorway_kmh",
    "truck_speed_other_kmh",
    "speed_over_gross_weight_kg",
    "speed_weight_basis",
    "max_gross_weight_kg",
    "max_length_mm",
    "hct_allowed",
    "winter_equipment_start",
    "winter_equipment_end",
    "toll_system",
    "posted_worker_declaration",
    "cabotage_note",
)
# Reported besides the tables: values filled into existing rows that had none recorded.
FILLED = "filled_values"


@dataclass(frozen=True)
class ReferenceData:
    countries: list[dict[str, Any]]
    holidays: list[dict[str, Any]]
    restrictions: list[dict[str, Any]]
    rules: list[dict[str, Any]] = field(default_factory=list)


def _time(value: str | None) -> time | None:
    return None if value is None else time.fromisoformat(value)


def _window(raw: dict[str, Any]) -> BanWindow:
    start = _time(raw["start"])
    if start is None:
        raise ValueError("a window needs a start time")
    return BanWindow(
        kind=WindowKind(raw["kind"]),
        start=start,
        end=_time(raw.get("end")),
        weekdays=tuple(raw.get("weekdays", ())),
        season_start=raw.get("season_start"),
        season_end=raw.get("season_end"),
        on_date=date.fromisoformat(raw["on_date"]) if raw.get("on_date") else None,
    )


def _check_source(row: dict[str, Any], what: str, today: date) -> None:
    if not str(row.get("source_url", "")).startswith("https://"):
        raise ValueError(f"{what}: source_url must be an https link")
    checked = date.fromisoformat(row["checked_on"])
    if not _EARLIEST_CHECK <= checked <= today:
        raise ValueError(f"{what}: checked_on must be between {_EARLIEST_CHECK} and today")


def _check_region(region: str | None, country: str, what: str) -> None:
    if region is not None and (
        not _REGION_RE.fullmatch(region) or not region.startswith(f"{country}-")
    ):
        raise ValueError(f"{what}: region must be an ISO 3166-2 code of the country")


def _check_rule(r: dict[str, Any], codes: set[str], today: date) -> None:
    what = f"country rule {r['country']} {r['valid_from']}"
    if r["country"] not in codes:
        raise ValueError(f"{what}: unknown country")
    for key in ("truck_speed_motorway_kmh", "truck_speed_other_kmh"):
        if r.get(key) is not None and not 1 <= r[key] <= 200:
            raise ValueError(f"{what}: {key} must be 1-200 km/h")
    over, basis = r.get("speed_over_gross_weight_kg"), r.get("speed_weight_basis")
    if (over is None) != (basis is None):
        raise ValueError(f"{what}: speed vehicle class needs both a weight and a basis")
    if basis is not None:
        WeightBasis(basis)
    has_speed = any(
        r.get(k) is not None for k in ("truck_speed_motorway_kmh", "truck_speed_other_kmh")
    )
    if has_speed and over is None:
        raise ValueError(f"{what}: a recorded speed needs its vehicle class (D87)")
    for key in ("speed_over_gross_weight_kg", "max_gross_weight_kg", "max_length_mm"):
        if r.get(key) is not None and r[key] <= 0:
            raise ValueError(f"{what}: {key} must be positive")
    start, end = r.get("winter_equipment_start"), r.get("winter_equipment_end")
    if (start is None) != (end is None):
        raise ValueError(f"{what}: winter season needs both a start and an end")
    if start is not None and end is not None:
        month_day(start)
        month_day(end)
    if r.get("toll_system") is not None:
        TollSystem(r["toll_system"])
    validate_period(
        date.fromisoformat(r["valid_from"]),
        date.fromisoformat(r["valid_until"]) if r["valid_until"] else None,
    )
    _check_source(r, what, today)


def load_files(data_dir: Path = DATA_DIR, today: date | None = None) -> ReferenceData:
    """Read and validate the JSON files; raises ValueError on the first invalid row."""
    today = today or date.today()

    def read(name: str) -> list[dict[str, Any]]:
        rows = json.loads((data_dir / name).read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{name} must hold a list")
        return rows

    data = ReferenceData(
        read("countries.json"),
        read("public_holidays.json"),
        read("road_restrictions.json"),
        read("country_rules.json"),
    )
    codes = set()
    for c in data.countries:
        validate_country(c["code"])
        validate_timezone(c["time_zone"])
        if len(c["currency"]) != 3 or not c["currency"].isupper():
            raise ValueError(f"{c['code']}: currency must be a three-letter code")
        codes.add(c["code"])

    seen_rules = Counter((r["country"], r["valid_from"]) for r in data.rules)
    if rule_dupes := [k for k, n in seen_rules.items() if n > 1]:
        raise ValueError(f"duplicate country rules: {rule_dupes}")
    for r in data.rules:
        _check_rule(r, codes, today)

    seen_holidays = Counter((h["country"], h["region"], h["date"]) for h in data.holidays)
    if dupes := [k for k, n in seen_holidays.items() if n > 1]:
        raise ValueError(f"duplicate holidays: {dupes}")
    for h in data.holidays:
        what = f"holiday {h['country']} {h['date']}"
        if h["country"] not in codes:
            raise ValueError(f"{what}: unknown country")
        _check_region(h["region"], h["country"], what)
        date.fromisoformat(h["date"])
        _check_source(h, what, today)

    seen_codes = Counter(r["code"] for r in data.restrictions)
    if dupes := [k for k, n in seen_codes.items() if n > 1]:
        raise ValueError(f"duplicate restriction codes: {dupes}")
    for r in data.restrictions:
        what = f"restriction {r['code']}"
        if not _CODE_RE.fullmatch(r["code"]):
            raise ValueError(f"{what}: code must look like DE-SUNDAY-HOLIDAY-BAN")
        if r["country"] not in codes or not r["code"].startswith(f"{r['country']}-"):
            raise ValueError(f"{what}: unknown country or code not prefixed by it")
        _check_region(r.get("region"), r["country"], what)
        over = r.get("over_gross_weight_kg")
        if over is not None and over <= 0:
            raise ValueError(f"{what}: over_gross_weight_kg must be positive")
        rtype = RestrictionType(r["restriction_type"])
        unit = LimitUnit(r["limit_unit"]) if r.get("limit_unit") else None
        validate_restriction(rtype, r.get("limit_value"), unit, r.get("tunnel_category"))
        LoadState(r["load_state"])
        if r.get("solo_tractor") is not None:
            SoloTractor(r["solo_tractor"])
            if rtype is not RestrictionType.DRIVING_BAN:
                raise ValueError(f"{what}: only a driving ban has a solo tractor rule")
        WeightBasis(r.get("weight_basis", WeightBasis.VEHICLE.value))
        for e in r["exemptions"]:
            Exemption(e)
        validate_period(
            date.fromisoformat(r["valid_from"]),
            date.fromisoformat(r["valid_until"]) if r["valid_until"] else None,
        )
        _check_source(r, what, today)
        windows = r.get("windows", [])
        if windows and rtype is not RestrictionType.DRIVING_BAN:
            raise ValueError(f"{what}: only a driving ban has windows")
        if rtype is RestrictionType.DRIVING_BAN and not windows:
            raise ValueError(f"{what}: a driving ban needs windows")
        for w in windows:
            _window(w)
    return data


def _take_source(row: CountryRule | RoadRestriction, raw: dict[str, Any]) -> None:
    """A filled-in value comes from the file row, so the row now cites that source and check day."""
    row.source_url = raw["source_url"]
    row.checked_on = date.fromisoformat(raw["checked_on"])
    row.note = raw.get("note")


def seed_reference_data(session: Session, data: ReferenceData | None = None) -> Counter[str]:
    """Create the missing reference rows; returns how many rows were created per table."""
    data = data or load_files()
    created: Counter[str] = Counter(dict.fromkeys(TABLES, 0))

    existing_countries = set(session.scalars(select(Country.code)))
    for c in data.countries:
        if c["code"] not in existing_countries:
            session.add(Country(**c))
            created["countries"] += 1
    session.flush()

    existing_rules = {(x.country, x.valid_from): x for x in session.scalars(select(CountryRule))}
    for r in data.rules:
        valid_from = date.fromisoformat(r["valid_from"])
        if (rule := existing_rules.get((r["country"], valid_from))) is not None:
            # Fill values not recorded yet (NULL); never overwrite a recorded one.
            filled = [n for n in RULE_VALUES if getattr(rule, n) is None and r.get(n) is not None]
            for name in filled:
                setattr(rule, name, r[name])
            if rule.valid_until is None and r["valid_until"]:
                # An open period is closed when a later period starts (D67).
                rule.valid_until = date.fromisoformat(r["valid_until"])
                filled.append("valid_until")
            if filled:
                _take_source(rule, r)
                created[FILLED] += len(filled)
                session.flush()  # a closed period must be stored before the next one is added
            continue
        session.add(
            CountryRule(
                country=r["country"],
                valid_from=valid_from,
                valid_until=date.fromisoformat(r["valid_until"]) if r["valid_until"] else None,
                **{name: r.get(name) for name in RULE_VALUES},
                note=r.get("note"),
                source_url=r["source_url"],
                checked_on=date.fromisoformat(r["checked_on"]),
            )
        )
        created["country_rules"] += 1

    existing_holidays = {
        (h.country, h.region, h.holiday_date) for h in session.scalars(select(PublicHoliday))
    }
    for h in data.holidays:
        key = (h["country"], h["region"], date.fromisoformat(h["date"]))
        if key in existing_holidays:
            continue
        session.add(
            PublicHoliday(
                country=h["country"],
                region=h["region"],
                holiday_date=key[2],
                name_local=h["name_local"],
                name_en=h.get("name_en"),
                source_url=h["source_url"],
                checked_on=date.fromisoformat(h["checked_on"]),
            )
        )
        created["public_holidays"] += 1

    existing = {x.code: x for x in session.scalars(select(RoadRestriction))}
    for r in data.restrictions:
        if (current := existing.get(r["code"])) is not None:
            # Fill a value that was not recorded yet (NULL); never overwrite a recorded one.
            if current.solo_tractor is None and r.get("solo_tractor") is not None:
                current.solo_tractor = r["solo_tractor"]
                _take_source(current, r)
                created["filled_values"] += 1
            continue
        restriction = RoadRestriction(
            code=r["code"],
            country=r["country"],
            region=r.get("region"),
            road_ref=r.get("road_ref"),
            section=r.get("section"),
            restriction_type=r["restriction_type"],
            limit_value=r.get("limit_value"),
            limit_unit=r.get("limit_unit"),
            tunnel_category=r.get("tunnel_category"),
            over_gross_weight_kg=r.get("over_gross_weight_kg"),
            weight_basis=r.get("weight_basis", WeightBasis.VEHICLE.value),
            with_trailer_any_weight=r.get("with_trailer_any_weight", False),
            solo_tractor=r.get("solo_tractor"),
            adr_only=r.get("adr_only", False),
            load_state=r["load_state"],
            exemptions=list(r["exemptions"]),
            note=r.get("note"),
            valid_from=date.fromisoformat(r["valid_from"]),
            valid_until=date.fromisoformat(r["valid_until"]) if r["valid_until"] else None,
            source_url=r["source_url"],
            checked_on=date.fromisoformat(r["checked_on"]),
        )
        session.add(restriction)
        session.flush()  # the windows need the id
        created["road_restrictions"] += 1
        for raw in r.get("windows", []):
            w = _window(raw)
            session.add(
                RoadRestrictionWindow(
                    restriction_id=restriction.id,
                    restriction_type=restriction.restriction_type,
                    kind=w.kind.value,
                    weekdays=list(w.weekdays),
                    start_time=w.start,
                    end_time=w.end,
                    season_start=w.season_start,
                    season_end=w.season_end,
                    on_date=w.on_date,
                )
            )
            created["road_restriction_windows"] += 1

    session.commit()
    return created


def main() -> int:
    data = load_files()
    with sessionmaker(bind=get_engine())() as session:
        created = seed_reference_data(session, data)
    for table in TABLES:
        print(f"{table}: {created[table]} created")
    print(f"{FILLED}: {created[FILLED]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
