"""Constraints of the 2B-2 fleet tables, checked against the migrated PostgreSQL schema."""

import uuid
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from domain.equipment import (
    BodyType,
    CouplingType,
    EquipmentQualificationType,
    EvaporatorPosition,
    ModelCode,
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
        "coupling_type": "semi_trailer",
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


@pytest.mark.parametrize(
    "value", [o.value for o in Ownership if o.value in ("own", "partner", "customer_owned")]
)
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
        coupling_type="full_trailer",  # a semi-trailer cannot have a tail lift (D25)
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


@pytest.mark.parametrize("value", [c.value for c in CouplingType])
def test_coupling_type_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _trailer(test_engine, carrier, coupling_type=value)
    _rejected(_trailer, test_engine, carrier, coupling_type="pintle")


def test_trailer_needs_a_coupling_type_and_a_fixed_body_has_none(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    _rejected(_trailer, test_engine, carrier, coupling_type=None)
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _rejected(_body, test_engine, carrier, truck, coupling_type="full_trailer")
    _body(test_engine, carrier, truck)


def test_semi_trailer_cannot_have_a_tail_lift_d25(test_engine: Engine, carrier: uuid.UUID) -> None:
    _rejected(_trailer, test_engine, carrier, coupling_type="semi_trailer", tail_lift=True)
    _trailer(test_engine, carrier, coupling_type="semi_trailer", tail_lift=False)
    for coupling in ("full_trailer", "centre_axle_trailer"):
        _trailer(test_engine, carrier, coupling_type=coupling, tail_lift=True)
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _body(test_engine, carrier, truck, tail_lift=True)  # a fixed body may have one


def test_kingpin_position(test_engine: Engine, carrier: uuid.UUID) -> None:
    _trailer(test_engine, carrier, kingpin_from_front_m="1.60")
    _trailer(test_engine, carrier)  # optional
    _rejected(_trailer, test_engine, carrier, kingpin_from_front_m="0")
    _rejected(_trailer, test_engine, carrier, kingpin_from_front_m="13.60")  # = external length
    _rejected(_trailer, test_engine, carrier, kingpin_from_front_m="14.00")
    _rejected(
        _trailer, test_engine, carrier, coupling_type="full_trailer", kingpin_from_front_m="1.6"
    )
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _rejected(_body, test_engine, carrier, truck, kingpin_from_front_m="1.6")


def test_external_height_and_width(test_engine: Engine, carrier: uuid.UUID) -> None:
    _trailer(test_engine, carrier, external_height_m="3.95", external_width_m="2.55")
    _trailer(test_engine, carrier)  # optional
    _rejected(_trailer, test_engine, carrier, external_height_m="0")
    _rejected(_trailer, test_engine, carrier, external_width_m="-1")
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _body(test_engine, carrier, truck, external_height_m="3.60", external_width_m="2.55")


def test_fixed_body_is_not_rail_craneable(test_engine: Engine, carrier: uuid.UUID) -> None:
    truck = _truck(test_engine, carrier, type="rigid_truck")
    _rejected(_body, test_engine, carrier, truck, rail_craneable=True)
    _body(test_engine, carrier, truck, rail_craneable=False)
    _trailer(test_engine, carrier, rail_craneable=True)


# --- truck features (D55, D61)


def test_tractor_features(test_engine: Engine, carrier: uuid.UUID) -> None:
    _truck(test_engine, carrier, fifth_wheel_from_front_m="3.70", low_fifth_wheel=True)
    _truck(test_engine, carrier)  # all optional
    _rejected(_truck, test_engine, carrier, fifth_wheel_from_front_m="0")
    _rejected(_truck, test_engine, carrier, fifth_wheel_from_front_m="6.30")  # beyond the length
    _rejected(_truck, test_engine, carrier, type="rigid_truck", fifth_wheel_from_front_m="3.7")
    _rejected(_truck, test_engine, carrier, type="rigid_truck", low_fifth_wheel=True)
    _rejected(_truck, test_engine, carrier, drawbar_hitch=True)  # a tractor has no drawbar hitch
    _truck(test_engine, carrier, type="rigid_truck", drawbar_hitch=True)


def test_truck_defaults_for_the_new_flags(test_engine: Engine, carrier: uuid.UUID) -> None:
    _truck(test_engine, carrier)
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT low_fifth_wheel, drawbar_hitch, max_combination_weight_kg, home_location_id"
                " FROM trucks"
            )
        ).one()
    assert tuple(row) == (False, False, None, None)


def test_max_combination_weight(test_engine: Engine, carrier: uuid.UUID) -> None:
    _truck(test_engine, carrier, max_combination_weight_kg=60000)
    _truck(test_engine, carrier, max_combination_weight_kg=26000)  # equal to the truck's own limit
    _rejected(_truck, test_engine, carrier, max_combination_weight_kg=25000)


def test_truck_home_location_is_restrict(test_engine: Engine, carrier: uuid.UUID) -> None:
    from tests.test_registers_db import _location

    home = _location(test_engine, "Demo Home Depot")
    _truck(test_engine, carrier, home_location_id=home)
    _rejected(_truck, test_engine, carrier, home_location_id=uuid.uuid4())
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM locations WHERE id = :i"), {"i": home})


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


def test_compartment_pallet_places_and_control_flag(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _compartment(test_engine, unit, 1)  # places optional, not independently controlled by default
    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT pallet_places, independently_controlled, evaporator_id FROM compartments")
        ).one()
    assert tuple(row) == (None, False, None)
    _compartment(test_engine, unit, 2, pallet_places=20, independently_controlled=True)
    _compartment(test_engine, unit, 3, pallet_places=0)
    _rejected(_compartment, test_engine, unit, 4, pallet_places=-1)


def test_compartment_evaporator_must_belong_to_the_same_load_unit(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    other = _trailer(test_engine, carrier, body_type="reefer")
    machine = _reefer(test_engine, unit)
    front = _evaporator(test_engine, machine, unit, "front")
    rear = _evaporator(test_engine, machine, unit, "rear")
    other_front = _evaporator(test_engine, _reefer(test_engine, other), other, "front")
    _compartment(test_engine, unit, 1, evaporator_id=front)
    _compartment(test_engine, unit, 2, evaporator_id=rear)
    _compartment(test_engine, unit, 3)  # optional
    assert (
        _violated(lambda: _compartment(test_engine, unit, 4, evaporator_id=other_front))
        == "fk_compartments_evaporator_id"
    )
    # one evaporator serves at most one compartment
    assert (
        _violated(lambda: _compartment(test_engine, unit, 5, evaporator_id=front))
        == "uq_compartments_evaporator_id"
    )
    _rejected(_compartment, test_engine, unit, 6, evaporator_id=uuid.uuid4())


def test_reefer_unit_and_evaporator_in_use_cannot_be_deleted(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    machine = _reefer(test_engine, unit)
    evaporator = _evaporator(test_engine, machine, unit)
    _compartment(test_engine, unit, 1, evaporator_id=evaporator)
    for table, row in (("reefer_evaporators", evaporator), ("reefer_units", machine)):
        with pytest.raises(IntegrityError), test_engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": row})


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
    values = {
        "load_unit_id": unit,
        "unit_name": "Demo Chill 300",
        "power_source": "diesel",
        **kw,
    }
    return _insert(engine, "reefer_units", **values)


def _evaporator(
    engine: Engine, machine: uuid.UUID, unit: uuid.UUID, position: str = "front", **kw: Any
) -> uuid.UUID:
    values = {"reefer_unit_id": machine, "load_unit_id": unit, "position": position, **kw}
    return _insert(engine, "reefer_evaporators", **values)


@pytest.mark.parametrize("value", [p.value for p in PowerSource])
def test_reefer_power_source_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    _reefer(test_engine, _trailer(test_engine, carrier, body_type="reefer"), power_source=value)


def test_one_reefer_unit_per_load_unit(test_engine: Engine, carrier: uuid.UUID) -> None:
    """D76: one machine, at the front; the zones come from its evaporators."""
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _reefer(test_engine, unit)
    assert _violated(lambda: _reefer(test_engine, unit)) == "uq_reefer_units_load_unit_id"
    _reefer(test_engine, _trailer(test_engine, carrier, body_type="reefer"))


def test_reefer_unit_constraints(test_engine: Engine, carrier: uuid.UUID) -> None:
    other = _trailer(test_engine, carrier, body_type="reefer")
    _rejected(_reefer, test_engine, other, power_source="gas")
    _rejected(_reefer, test_engine, other, unit_name=" ")
    _rejected(_reefer, test_engine, uuid.uuid4())


@pytest.mark.parametrize("value", [p.value for p in EvaporatorPosition])
def test_evaporator_position_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    _evaporator(test_engine, _reefer(test_engine, unit), unit, value)


def test_evaporators_one_per_position_on_the_same_load_unit(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    machine = _reefer(test_engine, unit)
    _evaporator(test_engine, machine, unit, "front")
    _evaporator(test_engine, machine, unit, "rear")
    assert _violated(lambda: _evaporator(test_engine, machine, unit, "front")) == (
        "uq_reefer_evaporators_reefer_unit_id_position"
    )
    assert _violated(lambda: _evaporator(test_engine, machine, unit, "middle")) == (
        "ck_reefer_evaporators_position"
    )
    # the machine must belong to the evaporator's load unit
    other_machine = _reefer(test_engine, _trailer(test_engine, carrier, body_type="reefer"))
    assert _violated(lambda: _evaporator(test_engine, other_machine, unit, "front")) == (
        "fk_reefer_evaporators_reefer_unit_id"
    )
    _rejected(_evaporator, test_engine, machine, unit, None)


# --- load unit model code, side doors and partition (D75, D76)


@pytest.mark.parametrize("value", [m.value for m in ModelCode])
def test_model_code_accepts_domain_values(
    test_engine: Engine, carrier: uuid.UUID, value: str
) -> None:
    thermo = value in ("FB", "FD", "FS")
    _trailer(
        test_engine,
        carrier,
        model_code=value,
        body_type="reefer" if thermo else "curtainsider",
        side_doors=value == "FS",
        partition=value == "FD",
    )
    _rejected(_trailer, test_engine, carrier, model_code="XX")


def test_model_code_is_optional_and_fits_the_body(test_engine: Engine, carrier: uuid.UUID) -> None:
    _trailer(test_engine, carrier)  # NULL is allowed
    _trailer(test_engine, carrier, body_type="side_opening")
    assert (
        _violated(lambda: _trailer(test_engine, carrier, model_code="FB", body_type="curtainsider"))
        == "ck_load_units_model_code_body"
    )
    assert (
        _violated(lambda: _trailer(test_engine, carrier, model_code="CS", body_type="reefer"))
        == "ck_load_units_model_code_body"
    )


def test_the_code_does_not_define_features_except_fs_side_doors(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    # MEGA with a coil well: features are separate columns, not a MEGA_COIL model
    _trailer(test_engine, carrier, body_type="mega", model_code="MEGA", coil_well=True)
    _trailer(test_engine, carrier, body_type="mega", model_code="MEGA", coil_well=False)
    _trailer(
        test_engine, carrier, body_type="reefer", model_code="FD", side_doors=False, partition=True
    )
    _trailer(test_engine, carrier, body_type="reefer", model_code="FB", side_doors=True)
    assert (
        _violated(lambda: _trailer(test_engine, carrier, body_type="reefer", model_code="FS"))
        == "ck_load_units_fs_side_doors"
    )


def test_partition_defaults_and_values(test_engine: Engine, carrier: uuid.UUID) -> None:
    _trailer(test_engine, carrier, body_type="reefer")
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT partition, partition_thickness_mm, partition_step_pallet_rows,"
                " min_pallets_front, min_pallets_rear, side_doors FROM load_units"
            )
        ).one()
    assert tuple(row) == (False, 50, 1, 4, 4, False)
    fd = {"body_type": "reefer", "model_code": "FD", "partition": True}
    _trailer(test_engine, carrier, **fd, min_pallets_front=0, min_pallets_rear=0)
    _trailer(test_engine, carrier, **fd, partition_max_rear_share="0.333")
    _trailer(test_engine, carrier, **fd, partition_max_rear_share="1")
    for bad in (
        {"partition_thickness_mm": 0},
        {"partition_step_pallet_rows": 0},
        {"min_pallets_front": -1},
        {"min_pallets_rear": -1},
        {"partition_max_rear_share": "0"},
        {"partition_max_rear_share": "1.001"},
    ):
        assert _violated(partial(_trailer, test_engine, carrier, **fd, **bad)) == (
            "ck_load_units_partition_values"
        )


def test_max_rear_share_needs_a_partition(test_engine: Engine, carrier: uuid.UUID) -> None:
    assert _violated(
        partial(_trailer, test_engine, carrier, body_type="reefer", partition_max_rear_share="0.5")
    ) == ("ck_load_units_partition_values")


def test_only_fd_has_a_partition_and_every_fd_has_one(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    """D76: the database refuses a partition outside FD and an FD without one."""
    for kw in (
        {"partition": True},  # no model code
        {"body_type": "reefer", "model_code": "FB", "partition": True},
        {"body_type": "reefer", "model_code": "FS", "side_doors": True, "partition": True},
        {"body_type": "reefer", "model_code": "FD", "partition": False},
    ):
        assert _violated(partial(_trailer, test_engine, carrier, **kw)) == (
            "ck_load_units_partition_fd"
        )


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
    unit = _trailer(test_engine, carrier, body_type="reefer")
    if value == "reefer_service":  # takes a reefer unit only
        _equipment(test_engine, type=value, reefer_unit_id=_reefer(test_engine, unit))
    else:
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
    machine = _reefer(test_engine, _trailer(test_engine, carrier, body_type="reefer"))
    _equipment(test_engine, type="reefer_service", reefer_unit_id=machine)  # the fourth subject
    _rejected(
        _equipment, test_engine, type="reefer_service", reefer_unit_id=machine, truck_id=truck
    )
    _rejected(
        _equipment, test_engine, type="reefer_service", reefer_unit_id=machine, load_unit_id=unit
    )
    _rejected(_equipment, test_engine, type="reefer_service", reefer_unit_id=uuid.uuid4())


def test_reefer_service_is_for_reefer_units_only_and_they_take_nothing_else(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    machine = _reefer(test_engine, unit)
    name = "ck_equipment_qualifications_reefer_service"
    assert (
        _violated(lambda: _equipment(test_engine, type="reefer_service", load_unit_id=unit)) == name
    )
    assert (
        _violated(
            lambda: _equipment(
                test_engine, type="reefer_service", truck_id=_truck(test_engine, carrier)
            )
        )
        == name
    )
    assert (
        _violated(
            lambda: _equipment(
                test_engine, type="reefer_service", dolly_id=_dolly(test_engine, carrier)
            )
        )
        == name
    )
    either = {name, "ck_equipment_qualifications_load_unit_only_types"}  # both CHECKs apply
    for qtype in ("atp", "inspection", "gdp_temperature_mapping", "tail_lift_inspection"):
        assert (
            _violated(partial(_equipment, test_engine, type=qtype, reefer_unit_id=machine))
            in either
        )
    _equipment(test_engine, type="reefer_service", reefer_unit_id=machine)


def test_reefer_service_history_and_overlap(test_engine: Engine, carrier: uuid.UUID) -> None:
    unit = _trailer(test_engine, carrier, body_type="reefer")
    front = _reefer(test_engine, unit)
    rear = _reefer(test_engine, _trailer(test_engine, carrier, body_type="reefer"))
    kw: dict[str, Any] = {"type": "reefer_service"}
    _equipment(
        test_engine, reefer_unit_id=front, valid_from="2026-01-01", valid_until="2026-06-30", **kw
    )
    assert (
        _violated(
            lambda: _equipment(
                test_engine,
                reefer_unit_id=front,
                valid_from="2026-06-30",
                valid_until="2026-12-31",
                **kw,
            )
        )
        == "ex_equipment_qualifications_no_overlap"
    )
    _equipment(
        test_engine, reefer_unit_id=front, valid_from="2026-07-01", valid_until="2027-06-30", **kw
    )
    # the other machine has its own history
    _equipment(
        test_engine, reefer_unit_id=rear, valid_from="2026-01-01", valid_until="2026-06-30", **kw
    )
    # a machine's service and the body's ATP are separate subjects
    _equipment(test_engine, type="atp", load_unit_id=unit, valid_from="2026-01-01")


def test_reefer_unit_with_service_periods_cannot_be_deleted(
    test_engine: Engine, carrier: uuid.UUID
) -> None:
    machine = _reefer(test_engine, _trailer(test_engine, carrier, body_type="reefer"))
    _equipment(test_engine, type="reefer_service", reefer_unit_id=machine)
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM reefer_units WHERE id = :i"), {"i": machine})


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
        "ck_load_units_coupling_link": lambda: _trailer(e, carrier, coupling_type=None),
        "ck_load_units_semi_trailer_no_tail_lift": lambda: _trailer(e, carrier, tail_lift=True),
        "ck_load_units_kingpin": lambda: _trailer(e, carrier, kingpin_from_front_m="20"),
        "ck_load_units_fixed_body_no_rail": lambda: _body(
            e, carrier, _truck(e, carrier, type="rigid_truck"), rail_craneable=True
        ),
        "ck_trucks_drawbar_hitch_rigid": lambda: _truck(e, carrier, drawbar_hitch=True),
        "ck_trucks_fifth_wheel": lambda: _truck(e, carrier, fifth_wheel_from_front_m="9"),
    }
    for expected, insert in cases.items():
        assert _violated(insert) == expected
