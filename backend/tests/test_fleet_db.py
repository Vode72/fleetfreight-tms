"""Constraints of the 2B-2 fleet tables, checked against the migrated PostgreSQL schema."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from domain.equipment import (
    BodyType,
    EquipmentQualificationType,
    Ownership,
    PowerSource,
    TruckType,
)
from tests.test_registers_db import _carrier, _insert

pytestmark = pytest.mark.usefixtures("clean_registers")


def _rejected(fn: Any, *args: Any, **kw: Any) -> None:
    with pytest.raises(IntegrityError):
        fn(*args, **kw)


_counter = iter(range(1, 10_000))


def _reg(prefix: str) -> str:
    return f"DEMO-{prefix}-{next(_counter):03d}"


def _truck(engine: Engine, carrier: uuid.UUID, **kw: Any) -> uuid.UUID:
    values = {
        "carrier_id": carrier,
        "registration": _reg("TRK"),
        "type": "tractor",
        "length_m": "6.20",
        "kerb_weight_kg": 7800,
        "max_gross_weight_kg": 26000,
        "axles": 3,
        **kw,
    }
    return _insert(engine, "trucks", **values)


def _dolly(engine: Engine, carrier: uuid.UUID, **kw: Any) -> uuid.UUID:
    values = {
        "carrier_id": carrier,
        "registration": _reg("DOL"),
        "length_m": "4.20",
        "kerb_weight_kg": 2000,
        "max_gross_weight_kg": 18000,
        "axles": 2,
        **kw,
    }
    return _insert(engine, "dollies", **values)


def _trailer(engine: Engine, carrier: uuid.UUID, **kw: Any) -> uuid.UUID:
    values = {
        "type": "trailer",
        "carrier_id": carrier,
        "registration": _reg("TRL"),
        "body_type": "curtainsider",
        "internal_length_m": "13.40",
        "internal_width_m": "2.48",
        "internal_height_m": "2.75",
        "external_length_m": "13.60",
        "kerb_weight_kg": 6800,
        "max_gross_weight_kg": 39000,
        "axles": 3,
        **kw,
    }
    return _insert(engine, "load_units", **values)


def _body(engine: Engine, carrier: uuid.UUID, truck: uuid.UUID | None, **kw: Any) -> uuid.UUID:
    values = {
        "type": "fixed_body",
        "truck_id": truck,
        "carrier_id": carrier,
        "registration": _reg("BOD"),
        "body_type": "box",
        "internal_length_m": "6.20",
        "internal_width_m": "2.45",
        "internal_height_m": "2.40",
        **kw,
    }
    return _insert(engine, "load_units", **values)


@pytest.fixture
def carrier(test_engine: Engine) -> uuid.UUID:
    return _carrier(test_engine)


# --- trucks and dollies


@pytest.mark.parametrize("value", [t.value for t in TruckType])
def test_truck_type_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _truck(test_engine, carrier, type=value)


def test_truck_defaults_and_timestamps(test_engine: Engine, carrier: uuid.UUID) -> None:
    _truck(test_engine, carrier)
    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT archived_at, created_at, updated_at FROM trucks")).one()
    assert row.archived_at is None
    assert row.created_at.tzinfo is not None and row.updated_at.tzinfo is not None


def test_truck_constraints(test_engine: Engine, carrier: uuid.UUID) -> None:
    _rejected(_truck, test_engine, carrier, type="van")
    _rejected(_truck, test_engine, carrier, registration=" ")
    _rejected(_truck, test_engine, carrier, length_m="0")
    _rejected(_truck, test_engine, carrier, kerb_weight_kg=0)
    _rejected(_truck, test_engine, carrier, kerb_weight_kg=9000, max_gross_weight_kg=8000)
    _rejected(_truck, test_engine, carrier, axles=0)
    _rejected(_truck, test_engine, uuid.uuid4())  # carrier FK
    _rejected(_truck, test_engine, carrier, carrier_id=None)


def test_registrations_are_unique(test_engine: Engine, carrier: uuid.UUID) -> None:
    _truck(test_engine, carrier, registration="DEMO-TRK-900")
    _rejected(_truck, test_engine, carrier, registration="DEMO-TRK-900")
    _dolly(test_engine, carrier, registration="DEMO-DOL-900")
    _rejected(_dolly, test_engine, carrier, registration="DEMO-DOL-900")
    _trailer(test_engine, carrier, registration="DEMO-TRL-900")
    _rejected(_trailer, test_engine, carrier, registration="DEMO-TRL-900")


def test_dolly_constraints(test_engine: Engine, carrier: uuid.UUID) -> None:
    _dolly(test_engine, carrier)
    _rejected(_dolly, test_engine, carrier, length_m="-1")
    _rejected(_dolly, test_engine, carrier, max_gross_weight_kg=1000)
    _rejected(_dolly, test_engine, carrier, registration="")


def test_length_keeps_decimal_precision(test_engine: Engine, carrier: uuid.UUID) -> None:
    _truck(test_engine, carrier, length_m="6.25")
    with test_engine.connect() as conn:
        assert str(conn.execute(text("SELECT length_m FROM trucks")).scalar()) == "6.25"


# --- load units (D60)


@pytest.mark.parametrize("value", [b.value for b in BodyType])
def test_body_type_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _trailer(test_engine, carrier, body_type=value)


@pytest.mark.parametrize("value", [o.value for o in Ownership if o.value in ("own", "partner")])
def test_ownership_without_lease_dates(test_engine: Engine, carrier: uuid.UUID, value: str) -> None:
    _trailer(test_engine, carrier, ownership=value)
    _rejected(_trailer, test_engine, carrier, ownership=value, lease_valid_from="2026-01-01")
    _rejected(_trailer, test_engine, carrier, ownership=value, lease_valid_until="2026-01-01")


@pytest.mark.parametrize("value", ["leased", "rented"])
def test_leased_and_rented_need_a_lease_start(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _rejected(_trailer, test_engine, carrier, ownership=value)
    _trailer(test_engine, carrier, ownership=value, lease_valid_from="2026-01-01")  # open end
    _trailer(
        test_engine,
        carrier,
        ownership=value,
        lease_valid_from="2026-01-01",
        lease_valid_until="2026-12-31",
    )
    _trailer(  # a one-day lease: both ends inclusive
        test_engine,
        carrier,
        ownership=value,
        lease_valid_from="2026-03-01",
        lease_valid_until="2026-03-01",
    )


def test_lease_period_must_not_be_reversed(test_engine: Engine, carrier: uuid.UUID) -> None:
    _rejected(
        _trailer,
        test_engine,
        carrier,
        ownership="leased",
        lease_valid_from="2026-02-01",
        lease_valid_until="2026-01-31",
    )


def test_unknown_values_are_rejected(test_engine: Engine, carrier: uuid.UUID) -> None:
    _rejected(_trailer, test_engine, carrier, body_type="tanker")
    _rejected(_trailer, test_engine, carrier, ownership="borrowed")
    _rejected(_trailer, test_engine, carrier, type="swap_body")
    _rejected(_trailer, test_engine, carrier, registration="  ")


def test_load_unit_defaults(test_engine: Engine, carrier: uuid.UUID) -> None:
    _trailer(test_engine, carrier)
    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM load_units")).one()
    assert row.ownership == "own"
    for flag in ("xl_certified", "coil_well", "tir_cable", "top_loading", "tail_lift"):
        assert row._mapping[flag] is False
    assert row.rail_craneable is False
    assert row.archived_at is None


def test_trailer_must_not_have_a_truck_and_needs_vehicle_fields(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _rejected(_trailer, test_engine, carrier, truck_id=truck)
    for field in ("external_length_m", "kerb_weight_kg", "max_gross_weight_kg", "axles"):
        _rejected(_trailer, test_engine, carrier, **{field: None})


def test_trailer_vehicle_values_must_be_sane(test_engine: Engine, carrier: uuid.UUID) -> None:
    _rejected(_trailer, test_engine, carrier, external_length_m="0")
    _rejected(_trailer, test_engine, carrier, kerb_weight_kg=0)
    _rejected(_trailer, test_engine, carrier, kerb_weight_kg=9000, max_gross_weight_kg=8000)
    _rejected(_trailer, test_engine, carrier, axles=0)


def test_fixed_body_needs_a_truck_and_has_no_vehicle_fields(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _body(test_engine, carrier, truck)
    _rejected(_body, test_engine, carrier, None)  # no truck
    other = _truck(test_engine, carrier, type="rigid_truck")
    for field, value in (
        ("external_length_m", "6.0"),
        ("kerb_weight_kg", 1000),
        ("max_gross_weight_kg", 2000),
        ("axles", 2),
    ):
        _rejected(_body, test_engine, carrier, other, **{field: value})


def test_one_fixed_body_per_truck_but_many_trailers(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _body(test_engine, carrier, truck)
    _rejected(_body, test_engine, carrier, truck)
    other = _truck(test_engine, carrier, type="rigid_truck")
    _body(test_engine, carrier, other)
    for _ in range(3):  # NULL truck_id on trailers does not collide
        _trailer(test_engine, carrier)


def test_load_unit_references_exist(test_engine: Engine, carrier: uuid.UUID) -> None:
    _rejected(_trailer, test_engine, uuid.uuid4())
    _rejected(_body, test_engine, carrier, uuid.uuid4())


def test_cargo_space_values(test_engine: Engine, carrier: uuid.UUID) -> None:
    _trailer(test_engine, carrier, door_height_m="2.65", ldm="13.40", pallet_places=33)
    _trailer(test_engine, carrier, pallet_places=0)
    for bad in (
        {"internal_length_m": "0"},
        {"internal_width_m": "-1"},
        {"internal_height_m": "0"},
        {"door_height_m": "0"},
        {"ldm": "0"},
        {"pallet_places": -1},
    ):
        _rejected(_trailer, test_engine, carrier, **bad)


def test_special_features_and_rail_flag_are_stored(test_engine: Engine, carrier: uuid.UUID) -> None:
    _trailer(
        test_engine,
        carrier,
        xl_certified=True,
        coil_well=True,
        tir_cable=True,
        top_loading=True,
        tail_lift=True,
        rail_craneable=True,
    )
    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM load_units")).one()
    assert all(
        row._mapping[f]
        for f in ("xl_certified", "coil_well", "tir_cable", "top_loading", "tail_lift")
    )
    assert row.rail_craneable is True


def test_trucks_and_load_units_in_use_cannot_be_deleted(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    truck = _truck(test_engine, carrier, type="rigid_truck")
    body = _body(test_engine, carrier, truck)
    for table, row_id in (("trucks", truck), ("carriers", carrier)):
        with pytest.raises(IntegrityError), test_engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": row_id})
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM load_units WHERE id = :i"), {"i": body})
        conn.execute(text("DELETE FROM trucks WHERE id = :i"), {"i": truck})  # now free


# --- compartments and reefer units


def _compartment(engine: Engine, unit: uuid.UUID, number: int = 1, **kw: Any) -> uuid.UUID:
    values = {
        "load_unit_id": unit,
        "number": number,
        "temperature_min": "-25.0",
        "temperature_max": "-18.0",
        **kw,
    }
    return _insert(engine, "compartments", **values)


def test_compartments(test_engine: Engine, carrier: uuid.UUID) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _compartment(test_engine, unit, 1)
    _compartment(test_engine, unit, 2, temperature_min="2.0", temperature_max="8.0")
    _rejected(_compartment, test_engine, unit, 2)  # number unique per load unit
    other = _trailer(test_engine, carrier, body_type="reefer")
    _compartment(test_engine, other, 1)  # same number on another load unit is fine
    _rejected(_compartment, test_engine, unit, 3, temperature_min="5", temperature_max="4")
    _compartment(test_engine, unit, 3, temperature_min="4", temperature_max="4")
    _rejected(_compartment, test_engine, unit, 0)
    _rejected(_compartment, test_engine, uuid.uuid4(), 1)


def test_compartment_temperature_keeps_decimal(test_engine: Engine, carrier: uuid.UUID) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _compartment(test_engine, unit, 1, temperature_min="-25.5", temperature_max="-18.5")
    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT temperature_min, temperature_max FROM compartments")).one()
    assert (str(row[0]), str(row[1])) == ("-25.5", "-18.5")


def test_load_unit_with_compartments_cannot_be_deleted(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _compartment(test_engine, unit)
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM load_units WHERE id = :i"), {"i": unit})


def _reefer(engine: Engine, unit: uuid.UUID, **kw: Any) -> uuid.UUID:
    values = {"load_unit_id": unit, "unit_name": "Demo Chill 300", "power_source": "diesel", **kw}
    return _insert(engine, "reefer_units", **values)


@pytest.mark.parametrize("value", [p.value for p in PowerSource])
def test_reefer_power_source_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _reefer(test_engine, _trailer(test_engine, carrier, body_type="reefer"), power_source=value)


def test_reefer_unit_constraints(test_engine: Engine, carrier: uuid.UUID) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _reefer(test_engine, unit)
    _rejected(_reefer, test_engine, unit)  # at most one per load unit
    other = _trailer(test_engine, carrier, body_type="reefer")
    _rejected(_reefer, test_engine, other, power_source="gas")
    _rejected(_reefer, test_engine, other, unit_name=" ")
    _rejected(_reefer, test_engine, uuid.uuid4())


# --- equipment qualifications (D70, D67)


def _equipment(engine: Engine, **kw: Any) -> uuid.UUID:
    values = {
        "type": "inspection",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31",
        **kw,
    }
    return _insert(engine, "equipment_qualifications", **values)


@pytest.mark.parametrize("value", [t.value for t in EquipmentQualificationType])
def test_equipment_type_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    unit = _trailer(test_engine, carrier)
    _equipment(test_engine, type=value, load_unit_id=unit)
    _rejected(_equipment, test_engine, type="paint_job", load_unit_id=unit)


def test_exactly_one_subject(test_engine: Engine, carrier: uuid.UUID) -> None:
    truck, dolly = _truck(test_engine, carrier), _dolly(test_engine, carrier)
    unit = _trailer(test_engine, carrier)
    _equipment(test_engine, truck_id=truck)
    _equipment(test_engine, dolly_id=dolly)
    _equipment(test_engine, load_unit_id=unit)
    _rejected(_equipment, test_engine)  # none
    _rejected(_equipment, test_engine, truck_id=truck, dolly_id=dolly)
    _rejected(_equipment, test_engine, truck_id=truck, load_unit_id=unit)
    _rejected(_equipment, test_engine, dolly_id=dolly, load_unit_id=unit)
    _rejected(_equipment, test_engine, truck_id=truck, dolly_id=dolly, load_unit_id=unit)
    _rejected(_equipment, test_engine, truck_id=uuid.uuid4())  # FK


@pytest.mark.parametrize("value", ["atp", "tail_lift_inspection", "gdp_temperature_mapping"])
def test_load_unit_only_types_are_rejected_for_trucks_and_dollies(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _rejected(_equipment, test_engine, type=value, truck_id=_truck(test_engine, carrier))
    _rejected(_equipment, test_engine, type=value, dolly_id=_dolly(test_engine, carrier))
    _equipment(test_engine, type=value, load_unit_id=_trailer(test_engine, carrier))


@pytest.mark.parametrize("value", ["inspection", "adr_vehicle_approval"])
def test_general_types_apply_to_every_subject(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _equipment(test_engine, type=value, truck_id=_truck(test_engine, carrier))
    _equipment(test_engine, type=value, dolly_id=_dolly(test_engine, carrier))
    _equipment(test_engine, type=value, load_unit_id=_trailer(test_engine, carrier))


def test_period_must_not_be_reversed_and_may_be_one_day(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    truck = _truck(test_engine, carrier)
    _rejected(
        _equipment, test_engine, truck_id=truck, valid_from="2026-02-02", valid_until="2026-02-01"
    )
    _equipment(test_engine, truck_id=truck, valid_from="2026-02-01", valid_until="2026-02-01")


def test_class_code_and_document_ref(test_engine: Engine, carrier: uuid.UUID) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _equipment(test_engine, type="atp", load_unit_id=unit, class_code="FRC", document_ref="DEMO-1")
    _rejected(
        _equipment, test_engine, type="gdp_temperature_mapping", load_unit_id=unit, class_code=" "
    )


@pytest.mark.parametrize("kind", ["truck", "dolly", "load_unit"])
def test_overlapping_periods_of_one_subject_and_type_are_rejected(
    test_engine: Engine, carrier: uuid.UUID, kind: str
) -> None:
    make = {"truck": _truck, "dolly": _dolly, "load_unit": _trailer}[kind]
    subject = {f"{kind}_id": make(test_engine, carrier)}
    _equipment(test_engine, **subject, valid_from="2026-01-01", valid_until="2026-06-30")
    # one shared day (the end day is inclusive) is an overlap
    _rejected(_equipment, test_engine, **subject, valid_from="2026-06-30", valid_until="2026-12-31")
    # inside the period
    _rejected(_equipment, test_engine, **subject, valid_from="2026-02-01", valid_until="2026-03-01")
    # the day after is fine: this is a renewal and the history is kept
    _equipment(test_engine, **subject, valid_from="2026-07-01", valid_until="2027-06-30")
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM equipment_qualifications")).scalar() == 2


def test_overlap_rule_is_per_subject_and_type(test_engine: Engine, carrier: uuid.UUID) -> None:
    truck_a, truck_b = _truck(test_engine, carrier), _truck(test_engine, carrier)
    _equipment(test_engine, truck_id=truck_a)
    _equipment(test_engine, truck_id=truck_b)  # another subject, same period
    _equipment(test_engine, type="adr_vehicle_approval", truck_id=truck_a)  # another type
    _rejected(_equipment, test_engine, truck_id=truck_a)


def test_overlap_is_checked_across_subject_columns_without_collisions(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    """The coalesce() key keeps a truck's and a load unit's periods apart."""
    truck, unit = _truck(test_engine, carrier), _trailer(test_engine, carrier)
    _equipment(test_engine, truck_id=truck)
    _equipment(test_engine, load_unit_id=unit)


def test_updating_a_period_into_an_overlap_is_rejected(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    truck = _truck(test_engine, carrier)
    _equipment(test_engine, truck_id=truck, valid_from="2026-01-01", valid_until="2026-06-30")
    later = _equipment(
        test_engine, truck_id=truck, valid_from="2026-07-01", valid_until="2026-12-31"
    )
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(
            text("UPDATE equipment_qualifications SET valid_from = '2026-06-01' WHERE id = :i"),
            {"i": later},
        )


def test_equipment_with_periods_cannot_be_deleted(test_engine: Engine, carrier: uuid.UUID) -> None:
    """D72: history is archived with the subject; periods are not deleted by cascade."""
    truck = _truck(test_engine, carrier)
    _equipment(test_engine, truck_id=truck)
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM trucks WHERE id = :i"), {"i": truck})


def _violated(insert: Callable[[], uuid.UUID]) -> str:
    with pytest.raises(IntegrityError) as info:
        insert()
    return str(info.value.orig.diag.constraint_name)  # type: ignore[union-attr]


def test_each_rule_is_enforced_by_the_intended_constraint(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    """Guards against a rejection that comes from some other, accidental constraint."""
    e = test_engine
    rigid = _truck(e, carrier, type="rigid_truck")
    unit = _trailer(e, carrier)
    truck = _truck(e, carrier)
    _body(e, carrier, rigid)
    _equipment(e, truck_id=truck)
    cases: dict[str, Callable[[], uuid.UUID]] = {
        "ck_load_units_truck_link": lambda: _trailer(e, carrier, truck_id=rigid),
        "ck_load_units_vehicle_fields": lambda: _trailer(e, carrier, axles=None),
        "uq_load_units_truck_id": lambda: _body(e, carrier, rigid),
        "ck_load_units_lease_by_ownership": lambda: _trailer(e, carrier, ownership="leased"),
        "ck_load_units_lease_period": lambda: _trailer(
            e,
            carrier,
            ownership="rented",
            lease_valid_from="2026-02-01",
            lease_valid_until="2026-01-01",
        ),
        "ck_equipment_qualifications_one_subject": lambda: _equipment(
            e, truck_id=truck, load_unit_id=unit
        ),
        "ck_equipment_qualifications_load_unit_only_types": lambda: _equipment(
            e, type="atp", truck_id=truck
        ),
        "ex_equipment_qualifications_no_overlap": lambda: _equipment(e, truck_id=truck),
    }
    for expected, insert in cases.items():
        assert _violated(insert) == expected
