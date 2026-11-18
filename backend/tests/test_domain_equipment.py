import re
import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import CheckConstraint

from db.models import (
    EquipmentQualification,
    LoadUnit,
    ReeferUnit,
    Truck,
    in_list,
)
from domain.equipment import (
    LOAD_UNIT_ONLY_QUALIFICATIONS,
    BodyType,
    CouplingType,
    EquipmentQualificationType,
    EquipmentSubject,
    LoadUnitType,
    ModelCode,
    Ownership,
    PartitionSpec,
    PowerSource,
    ReeferPosition,
    TruckType,
    is_thermo,
    lease_valid_on,
    partition_positions,
    side_loading_possible,
    validate_compartment,
    validate_compartment_pallet_places,
    validate_compartment_set,
    validate_equipment_qualification,
    validate_equipment_subject,
    validate_fixed_body_host,
    validate_lease,
    validate_load_unit,
    validate_model_code,
    validate_partition,
    validate_reefer_unit_allowed,
    validate_reefer_units,
    validate_truck,
    validate_vehicle,
    validate_zones,
)

MIGRATION = next(
    (Path(__file__).parents[1] / "migrations/versions").glob("d3ad319be9a8_create_fleet_tables.py")
)

# (model, constraint name, column, domain enum)
ENUM_CHECKS = [
    (Truck, "ck_trucks_type", "type", TruckType),
    (LoadUnit, "ck_load_units_type", "type", LoadUnitType),
    (LoadUnit, "ck_load_units_body_type", "body_type", BodyType),
    (LoadUnit, "ck_load_units_ownership", "ownership", Ownership),
    (LoadUnit, "ck_load_units_coupling_type", "coupling_type", CouplingType),
    (LoadUnit, "ck_load_units_model_code", "model_code", ModelCode),
    (ReeferUnit, "ck_reefer_units_position", "position", ReeferPosition),
    (ReeferUnit, "ck_reefer_units_power_source", "power_source", PowerSource),
    (
        EquipmentQualification,
        "ck_equipment_qualifications_type",
        "type",
        EquipmentQualificationType,
    ),
]


def test_allowed_values() -> None:
    assert {v.value for v in TruckType} == {"tractor", "rigid_truck"}
    assert {v.value for v in LoadUnitType} == {"trailer", "fixed_body"}
    assert {v.value for v in BodyType} == {"curtainsider", "mega", "side_opening", "box", "reefer"}
    assert {v.value for v in Ownership} == {
        "own",
        "leased",
        "rented",
        "partner",
        "customer_owned",
    }
    assert {v.value for v in CouplingType} == {
        "semi_trailer",
        "full_trailer",
        "centre_axle_trailer",
    }
    assert {v.value for v in PowerSource} == {"diesel", "electric", "hybrid"}
    assert {v.value for v in EquipmentQualificationType} == {
        "atp",
        "inspection",
        "tail_lift_inspection",
        "gdp_temperature_mapping",
        "adr_vehicle_approval",
        "reefer_service",
    }
    assert {v.value for v in ModelCode} == {"FB", "FD", "FS", "CS", "MEGA", "COIL"}
    assert {v.value for v in ReeferPosition} == {"front", "rear"}


@pytest.mark.parametrize(("model", "name", "column", "enum"), ENUM_CHECKS)
def test_model_and_migration_check_lists_match_domain(
    model: type, name: str, column: str, enum: type[StrEnum]
) -> None:
    checks = {
        c.name: str(c.sqltext)
        for c in model.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }
    expected = in_list(column, enum)
    assert checks[name] == expected
    migration = re.sub(r'"\s*"', "", MIGRATION.read_text(encoding="utf-8"))
    assert f'"{expected}"' in migration
    for value in enum:
        assert f"'{value.value}'" in checks[name]


def test_load_unit_only_types_match_model_and_migration() -> None:
    types = ", ".join(f"'{t.value}'" for t in sorted(LOAD_UNIT_ONLY_QUALIFICATIONS))
    expected = f"type NOT IN ({types}) OR load_unit_id IS NOT NULL"
    checks = {
        c.name: str(c.sqltext)
        for c in EquipmentQualification.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(c, CheckConstraint)
    }
    assert checks["ck_equipment_qualifications_load_unit_only_types"] == expected
    migration = re.sub(r'"\s*"', "", MIGRATION.read_text(encoding="utf-8"))
    assert expected.split(" OR ")[0] in migration  # the type list is the same in the migration
    assert {
        EquipmentQualificationType.ATP,
        EquipmentQualificationType.TAIL_LIFT_INSPECTION,
        EquipmentQualificationType.GDP_TEMPERATURE_MAPPING,
    } == LOAD_UNIT_ONLY_QUALIFICATIONS


def test_side_loading_follows_d36() -> None:
    assert {b for b in BodyType if side_loading_possible(b)} == {
        BodyType.CURTAINSIDER,
        BodyType.MEGA,
        BodyType.SIDE_OPENING,
    }
    assert is_thermo(BodyType.REEFER) and not is_thermo(BodyType.BOX)


def test_validate_vehicle() -> None:
    validate_vehicle(
        length_m=Decimal("6.2"), kerb_weight_kg=7800, max_gross_weight_kg=7800, axles=2
    )
    for bad in (
        {"length_m": Decimal(0)},
        {"kerb_weight_kg": 0},
        {"max_gross_weight_kg": 7000},
        {"axles": 0},
    ):
        values = {
            "length_m": Decimal("6.2"),
            "kerb_weight_kg": 7800,
            "max_gross_weight_kg": 18000,
            "axles": 2,
        } | bad
        with pytest.raises(ValueError):
            validate_vehicle(**values)  # type: ignore[arg-type]


TRAILER: dict[str, Any] = {
    "unit_type": LoadUnitType.TRAILER,
    "truck_id": None,
    "external_length_m": Decimal("13.60"),
    "kerb_weight_kg": 6800,
    "max_gross_weight_kg": 39000,
    "axles": 3,
    "ownership": Ownership.OWN,
    "lease_valid_from": None,
    "lease_valid_until": None,
    "coupling_type": CouplingType.SEMI_TRAILER,
    "kingpin_from_front_m": Decimal("1.60"),
}
BODY: dict[str, Any] = TRAILER | {
    "unit_type": LoadUnitType.FIXED_BODY,
    "truck_id": uuid.uuid4(),
    "external_length_m": None,
    "kerb_weight_kg": None,
    "max_gross_weight_kg": None,
    "axles": None,
    "coupling_type": None,
    "kingpin_from_front_m": None,
}


def test_trailer_rules() -> None:
    validate_load_unit(**TRAILER)
    with pytest.raises(ValueError, match="must not reference a truck"):
        validate_load_unit(**TRAILER | {"truck_id": uuid.uuid4()})
    for missing in ("external_length_m", "kerb_weight_kg", "max_gross_weight_kg", "axles"):
        with pytest.raises(ValueError, match="trailer needs"):
            validate_load_unit(**TRAILER | {missing: None})
    with pytest.raises(ValueError):  # values still sane
        validate_load_unit(**TRAILER | {"max_gross_weight_kg": 100})


def test_fixed_body_rules() -> None:
    validate_load_unit(**BODY)
    with pytest.raises(ValueError, match="must reference its truck"):
        validate_load_unit(**BODY | {"truck_id": None})
    for field, value in (
        ("external_length_m", Decimal("6")),
        ("kerb_weight_kg", 1),
        ("max_gross_weight_kg", 1),
        ("axles", 2),
    ):
        with pytest.raises(ValueError, match="from its truck"):
            validate_load_unit(**BODY | {field: value})


def test_fixed_body_host() -> None:
    carrier = uuid.uuid4()
    validate_fixed_body_host(
        truck_type=TruckType.RIGID_TRUCK, truck_carrier_id=carrier, load_unit_carrier_id=carrier
    )
    with pytest.raises(ValueError, match="rigid truck"):
        validate_fixed_body_host(
            truck_type=TruckType.TRACTOR, truck_carrier_id=carrier, load_unit_carrier_id=carrier
        )
    with pytest.raises(ValueError, match="same carrier"):
        validate_fixed_body_host(
            truck_type=TruckType.RIGID_TRUCK,
            truck_carrier_id=carrier,
            load_unit_carrier_id=uuid.uuid4(),
        )


def test_lease_rules() -> None:
    d = date.fromisoformat
    validate_lease(Ownership.OWN, None, None)
    validate_lease(Ownership.PARTNER, None, None)
    validate_lease(Ownership.LEASED, d("2026-01-01"), d("2026-12-31"))
    validate_lease(Ownership.RENTED, d("2026-01-01"), None)  # open-ended
    validate_lease(Ownership.RENTED, d("2026-01-01"), d("2026-01-01"))  # a single day
    with pytest.raises(ValueError):
        validate_lease(Ownership.LEASED, None, None)
    with pytest.raises(ValueError):
        validate_lease(Ownership.LEASED, d("2026-02-01"), d("2026-01-31"))
    with pytest.raises(ValueError):
        validate_lease(Ownership.OWN, d("2026-01-01"), None)
    with pytest.raises(ValueError):
        validate_lease(Ownership.PARTNER, None, d("2026-01-01"))


def test_lease_valid_on_is_inclusive_at_both_ends() -> None:
    d = date.fromisoformat
    args = (Ownership.LEASED, d("2026-01-01"), d("2026-12-31"))
    assert lease_valid_on(*args, d("2026-01-01"))
    assert lease_valid_on(*args, d("2026-12-31"))
    assert not lease_valid_on(*args, d("2025-12-31"))
    assert not lease_valid_on(*args, d("2027-01-01"))
    assert lease_valid_on(Ownership.RENTED, d("2026-01-01"), None, d("2040-01-01"))
    assert lease_valid_on(Ownership.OWN, None, None, d("2026-01-01"))


def test_compartment_rules() -> None:
    validate_compartment(1, Decimal("-25.0"), Decimal("-18.0"))
    validate_compartment(1, Decimal("4.0"), Decimal("4.0"))
    with pytest.raises(ValueError):
        validate_compartment(0, Decimal("0"), Decimal("1"))
    with pytest.raises(ValueError):
        validate_compartment(1, Decimal("5"), Decimal("4"))


def test_compartment_set_rules() -> None:
    validate_compartment_set(BodyType.REEFER, [1, 2])
    validate_compartment_set(BodyType.REEFER, [2, 1])
    validate_compartment_set(BodyType.CURTAINSIDER, [])
    with pytest.raises(ValueError, match="only a reefer"):
        validate_compartment_set(BodyType.BOX, [1])
    for numbers in ([2], [1, 3], [1, 1]):
        with pytest.raises(ValueError, match=r"1\.\.n"):
            validate_compartment_set(BodyType.REEFER, numbers)


def test_reefer_unit_only_on_a_reefer_body() -> None:
    validate_reefer_unit_allowed(BodyType.REEFER)
    with pytest.raises(ValueError):
        validate_reefer_unit_allowed(BodyType.MEGA)


def test_equipment_subject_rules() -> None:
    one, two = uuid.uuid4(), uuid.uuid4()
    validate_equipment_subject(
        truck_id=one, dolly_id=None, load_unit_id=None, qtype=EquipmentQualificationType.INSPECTION
    )
    validate_equipment_subject(
        truck_id=None, dolly_id=None, load_unit_id=one, qtype=EquipmentQualificationType.ATP
    )
    with pytest.raises(ValueError, match="exactly one"):
        validate_equipment_subject(
            truck_id=None,
            dolly_id=None,
            load_unit_id=None,
            qtype=EquipmentQualificationType.INSPECTION,
        )
    with pytest.raises(ValueError, match="exactly one"):
        validate_equipment_subject(
            truck_id=one,
            dolly_id=None,
            load_unit_id=two,
            qtype=EquipmentQualificationType.INSPECTION,
        )
    for qtype in LOAD_UNIT_ONLY_QUALIFICATIONS:
        with pytest.raises(ValueError, match="load unit only"):
            validate_equipment_subject(truck_id=one, dolly_id=None, load_unit_id=None, qtype=qtype)
        with pytest.raises(ValueError, match="load unit only"):
            validate_equipment_subject(truck_id=None, dolly_id=one, load_unit_id=None, qtype=qtype)
    # ADR approval and inspection apply to every kind of subject
    for kw in ({"truck_id": one}, {"dolly_id": one}, {"load_unit_id": one}):
        for qtype in (
            EquipmentQualificationType.INSPECTION,
            EquipmentQualificationType.ADR_VEHICLE_APPROVAL,
        ):
            validate_equipment_subject(
                **{"truck_id": None, "dolly_id": None, "load_unit_id": None} | kw,
                qtype=qtype,
            )


def test_coupling_rules() -> None:
    full = TRAILER | {"coupling_type": CouplingType.FULL_TRAILER, "kingpin_from_front_m": None}
    validate_load_unit(**full)
    validate_load_unit(**full | {"tail_lift": True})
    centre = full | {"coupling_type": CouplingType.CENTRE_AXLE_TRAILER}
    validate_load_unit(**centre | {"tail_lift": True})
    with pytest.raises(ValueError, match="coupling_type"):
        validate_load_unit(**TRAILER | {"coupling_type": None, "kingpin_from_front_m": None})
    with pytest.raises(ValueError, match="coupling"):
        validate_load_unit(**BODY | {"coupling_type": CouplingType.SEMI_TRAILER})


def test_a_semi_trailer_has_no_tail_lift_d25() -> None:
    validate_load_unit(**TRAILER | {"tail_lift": False})
    with pytest.raises(ValueError, match="D25"):
        validate_load_unit(**TRAILER | {"tail_lift": True})


def test_kingpin_rules() -> None:
    with pytest.raises(ValueError, match="semi-trailer only"):
        validate_load_unit(
            **TRAILER
            | {"coupling_type": CouplingType.FULL_TRAILER, "kingpin_from_front_m": Decimal("1.6")}
        )
    for bad in (Decimal(0), Decimal("13.60"), Decimal("14")):  # not inside the outer length
        with pytest.raises(ValueError, match="inside"):
            validate_load_unit(**TRAILER | {"kingpin_from_front_m": bad})
    validate_load_unit(**TRAILER | {"kingpin_from_front_m": None})


def test_a_fixed_body_is_not_rail_craneable() -> None:
    validate_load_unit(**BODY | {"rail_craneable": False})
    with pytest.raises(ValueError, match="rail"):
        validate_load_unit(**BODY | {"rail_craneable": True})
    validate_load_unit(**TRAILER | {"rail_craneable": True})


def test_customer_owned_has_no_lease_dates() -> None:
    validate_lease(Ownership.CUSTOMER_OWNED, None, None)
    with pytest.raises(ValueError):
        validate_lease(Ownership.CUSTOMER_OWNED, date(2026, 1, 1), None)
    assert lease_valid_on(Ownership.CUSTOMER_OWNED, None, None, date(2026, 1, 1))


TRUCK: dict[str, Any] = {
    "truck_type": TruckType.TRACTOR,
    "length_m": Decimal("6.20"),
    "fifth_wheel_from_front_m": Decimal("3.70"),
    "low_fifth_wheel": True,
    "drawbar_hitch": False,
    "max_gross_weight_kg": 26000,
    "max_combination_weight_kg": 60000,
}
RIGID: dict[str, Any] = TRUCK | {
    "truck_type": TruckType.RIGID_TRUCK,
    "fifth_wheel_from_front_m": None,
    "low_fifth_wheel": False,
    "drawbar_hitch": True,
}


def test_truck_features() -> None:
    validate_truck(**TRUCK)
    validate_truck(**RIGID)
    validate_truck(**TRUCK | {"max_combination_weight_kg": None})
    validate_truck(**TRUCK | {"max_combination_weight_kg": 26000})
    for bad in (
        TRUCK | {"max_combination_weight_kg": 25000},
        TRUCK | {"fifth_wheel_from_front_m": Decimal(0)},
        TRUCK | {"fifth_wheel_from_front_m": Decimal("6.30")},  # beyond the truck's length
        TRUCK | {"drawbar_hitch": True},  # tractor with a drawbar hitch
        RIGID | {"fifth_wheel_from_front_m": Decimal("3")},
        RIGID | {"low_fifth_wheel": True},
    ):
        with pytest.raises(ValueError):
            validate_truck(**bad)


def test_compartment_pallet_places() -> None:
    validate_compartment_pallet_places(32, [12, 20])
    validate_compartment_pallet_places(32, [12, None])
    validate_compartment_pallet_places(None, [12, 20])
    validate_compartment_pallet_places(32, [])
    with pytest.raises(ValueError, match="exceed"):
        validate_compartment_pallet_places(32, [12, 21])
    with pytest.raises(ValueError, match="negative"):
        validate_compartment_pallet_places(32, [-1])


LOAD = {"kind": "load_unit"}


@pytest.mark.parametrize(
    "qtype", [EquipmentQualificationType.ATP, EquipmentQualificationType.GDP_TEMPERATURE_MAPPING]
)
def test_atp_and_gdp_mapping_only_for_reefer_bodies(qtype: EquipmentQualificationType) -> None:
    validate_equipment_qualification(EquipmentSubject("load_unit", BodyType.REEFER), qtype)
    for body in (BodyType.CURTAINSIDER, BodyType.BOX, BodyType.MEGA, BodyType.SIDE_OPENING):
        with pytest.raises(ValueError, match="reefer"):
            validate_equipment_qualification(EquipmentSubject("load_unit", body), qtype)
    with pytest.raises(ValueError):  # no body type known
        validate_equipment_qualification(EquipmentSubject("load_unit"), qtype)
    for kind in ("truck", "dolly"):
        with pytest.raises(ValueError, match="load unit only"):
            validate_equipment_qualification(EquipmentSubject(kind), qtype)


def test_tail_lift_inspection_only_with_a_tail_lift() -> None:
    qtype = EquipmentQualificationType.TAIL_LIFT_INSPECTION
    validate_equipment_qualification(EquipmentSubject("load_unit", BodyType.BOX, True), qtype)
    validate_equipment_qualification(EquipmentSubject("load_unit", BodyType.REEFER, True), qtype)
    with pytest.raises(ValueError, match="tail lift"):
        validate_equipment_qualification(EquipmentSubject("load_unit", BodyType.BOX, False), qtype)
    with pytest.raises(ValueError, match="load unit only"):
        validate_equipment_qualification(EquipmentSubject("truck", None, True), qtype)


@pytest.mark.parametrize(
    "qtype",
    [EquipmentQualificationType.INSPECTION, EquipmentQualificationType.ADR_VEHICLE_APPROVAL],
)
def test_inspection_and_adr_approval_apply_to_everything(qtype: EquipmentQualificationType) -> None:
    for subject in (
        EquipmentSubject("truck"),
        EquipmentSubject("dolly"),
        EquipmentSubject("load_unit", BodyType.CURTAINSIDER),
        EquipmentSubject("load_unit", BodyType.BOX, True),
    ):
        validate_equipment_qualification(subject, qtype)


# --- D75: model code


def test_model_code_fits_the_body() -> None:
    for code in (ModelCode.FB, ModelCode.FD):
        validate_model_code(code, BodyType.REEFER)
    validate_model_code(ModelCode.FS, BodyType.REEFER, side_doors=True)
    validate_model_code(ModelCode.CS, BodyType.CURTAINSIDER)
    validate_model_code(ModelCode.MEGA, BodyType.MEGA)
    validate_model_code(ModelCode.COIL, BodyType.CURTAINSIDER)
    validate_model_code(ModelCode.COIL, BodyType.MEGA)
    for body in BodyType:  # no code is always fine
        validate_model_code(None, body)
    for bad_body in (BodyType.CURTAINSIDER, BodyType.BOX, BodyType.MEGA, BodyType.SIDE_OPENING):
        for code in (ModelCode.FB, ModelCode.FD, ModelCode.FS):
            with pytest.raises(ValueError, match="thermo"):
                validate_model_code(code, bad_body, side_doors=True)
    for code in (ModelCode.CS, ModelCode.MEGA, ModelCode.COIL):
        with pytest.raises(ValueError, match="not a thermo"):
            validate_model_code(code, BodyType.REEFER)
    with pytest.raises(ValueError, match="CS"):
        validate_model_code(ModelCode.CS, BodyType.MEGA)
    with pytest.raises(ValueError, match="MEGA"):
        validate_model_code(ModelCode.MEGA, BodyType.CURTAINSIDER)


def test_the_code_alone_does_not_decide_features() -> None:
    """MEGA + coil well is a MEGA with a feature flag, not a separate MEGA_COIL model (D75)."""
    assert "MEGA_COIL" not in {c.value for c in ModelCode}
    # FD (two machines) and FB can both exist without side doors
    validate_model_code(ModelCode.FD, BodyType.REEFER, side_doors=False)
    validate_model_code(ModelCode.FB, BodyType.REEFER, side_doors=True)
    # only FS requires its side doors
    with pytest.raises(ValueError, match="side doors"):
        validate_model_code(ModelCode.FS, BodyType.REEFER, side_doors=False)


def test_side_loading_uses_the_side_doors_feature() -> None:
    assert not side_loading_possible(BodyType.REEFER)
    assert side_loading_possible(BodyType.REEFER, side_doors=True)  # Thermo Side
    assert not side_loading_possible(BodyType.BOX)
    assert side_loading_possible(BodyType.CURTAINSIDER)


# --- D76: reefer units, zones and the partition


def test_reefer_units_up_to_two_in_different_positions() -> None:
    F, R = ReeferPosition.FRONT, ReeferPosition.REAR
    validate_reefer_units(BodyType.REEFER, [])
    validate_reefer_units(BodyType.REEFER, [F])
    validate_reefer_units(BodyType.REEFER, [F, R])
    with pytest.raises(ValueError, match="at most 2"):
        validate_reefer_units(BodyType.REEFER, [F, R, F])
    with pytest.raises(ValueError, match="once"):
        validate_reefer_units(BodyType.REEFER, [F, F])
    with pytest.raises(ValueError, match="only a reefer"):
        validate_reefer_units(BodyType.BOX, [F])
    validate_reefer_units(BodyType.BOX, [])


def test_reefer_unit_count_follows_the_model_code() -> None:
    F, R = ReeferPosition.FRONT, ReeferPosition.REAR
    validate_reefer_units(BodyType.REEFER, [F], ModelCode.FB)
    validate_reefer_units(BodyType.REEFER, [F, R], ModelCode.FD)
    validate_reefer_units(BodyType.REEFER, [F], ModelCode.FS)
    validate_reefer_units(BodyType.REEFER, [F, R], ModelCode.FS)
    with pytest.raises(ValueError, match="FB"):
        validate_reefer_units(BodyType.REEFER, [F, R], ModelCode.FB)
    with pytest.raises(ValueError, match="FB"):
        validate_reefer_units(BodyType.REEFER, [], ModelCode.FB)
    with pytest.raises(ValueError, match="FD"):
        validate_reefer_units(BodyType.REEFER, [F], ModelCode.FD)


def test_two_machines_do_not_mean_two_zones() -> None:
    """D76: an FD trailer (two reefer units) with one compartment is valid."""
    F, R = ReeferPosition.FRONT, ReeferPosition.REAR
    validate_reefer_units(BodyType.REEFER, [F, R], ModelCode.FD)
    validate_zones(1, [False])  # one zone, two machines
    validate_zones(2, [True, True])  # two independent zones
    validate_zones(2, [False, False])  # two zones, not independently controlled
    validate_zones(2, [True, False])
    validate_zones(0, [])
    with pytest.raises(ValueError, match="at least two"):
        validate_zones(1, [True])
    with pytest.raises(ValueError, match="more control flags"):
        validate_zones(1, [False, False])


def _spec(**kw: object) -> PartitionSpec:
    return PartitionSpec(Decimal("13.10"), **kw)  # type: ignore[arg-type]


def test_partition_defaults_follow_d76() -> None:
    spec = _spec()
    assert (spec.thickness_mm, spec.step_pallet_rows, spec.min_pallets_front) == (50, 1, 4)
    assert spec.min_pallets_rear == 4 and spec.partition is False


def test_no_partition_means_no_positions() -> None:
    assert partition_positions(_spec(partition=False), 32) == []


def test_partition_positions_move_one_row_at_a_time() -> None:
    positions = partition_positions(_spec(partition=True), 32)
    # 16 rows of 2 pallets; each compartment keeps at least 4 pallets (2 rows): front 2..14 rows
    assert [p.front_rows for p in positions] == list(range(2, 15))
    assert [p.front_pallets for p in positions] == list(range(4, 29, 2))
    for p in positions:
        assert p.front_pallets + p.rear_pallets == 32
        assert p.front_pallets >= 4 and p.rear_pallets >= 4
        assert p.front_pallets == 2 * p.front_rows
    assert any((p.front_pallets, p.rear_pallets) == (12, 20) for p in positions)


def test_partition_thickness_takes_length_off_the_rows() -> None:
    # 12.85 m: 16 rows of 0.80 m fit (12.80), but a 50 mm partition leaves 12.80 -> still 16 rows
    assert len(partition_positions(PartitionSpec(Decimal("12.85"), partition=True), 32)) == 13
    # 12.84 m: the partition leaves 12.79 m, so only 15 rows fit: one row less
    positions = partition_positions(PartitionSpec(Decimal("12.84"), partition=True), 32)
    assert max(p.front_pallets + p.rear_pallets for p in positions) == 30
    # a thicker partition costs more (900 mm = a whole row)
    thick = partition_positions(_spec(partition=True, thickness_mm=900), 32)
    assert max(p.front_pallets + p.rear_pallets for p in thick) == 30


def test_partition_places_are_also_limited_by_the_given_places() -> None:
    positions = partition_positions(_spec(partition=True), 20)
    assert max(p.front_pallets + p.rear_pallets for p in positions) == 20
    assert len(positions) == 7  # front rows 2..8 of 10


def test_partition_minimums_and_step() -> None:
    positions = partition_positions(
        _spec(partition=True, min_pallets_front=6, min_pallets_rear=10), 32
    )
    assert (positions[0].front_pallets, positions[-1].rear_pallets) == (6, 10)
    assert all(p.front_pallets >= 6 and p.rear_pallets >= 10 for p in positions)
    stepped = partition_positions(_spec(partition=True, step_pallet_rows=2), 32)
    assert [p.front_rows for p in stepped] == [2, 4, 6, 8, 10, 12, 14]
    assert partition_positions(_spec(partition=True, min_pallets_front=30), 32) == []  # no room
    assert partition_positions(_spec(partition=True), 0) == []


def test_partition_validation() -> None:
    for bad in ({"thickness_mm": 0}, {"step_pallet_rows": 0}, {"min_pallets_front": -1}):
        with pytest.raises(ValueError):
            partition_positions(_spec(partition=True, **bad), 32)
    with pytest.raises(ValueError):
        validate_partition(_spec(min_pallets_rear=-1))
    with pytest.raises(ValueError):
        partition_positions(_spec(partition=True), -1)


# --- D76: reefer service qualification


def test_reefer_service_only_for_reefer_units() -> None:
    qtype = EquipmentQualificationType.REEFER_SERVICE
    validate_equipment_qualification(EquipmentSubject("reefer_unit"), qtype)
    for subject in (
        EquipmentSubject("truck"),
        EquipmentSubject("dolly"),
        EquipmentSubject("load_unit", BodyType.REEFER),
    ):
        with pytest.raises(ValueError, match="reefer_service"):
            validate_equipment_qualification(subject, qtype)
    for other in EquipmentQualificationType:
        if other is not qtype:
            with pytest.raises(ValueError, match="reefer_service"):
                validate_equipment_qualification(EquipmentSubject("reefer_unit"), other)


def test_equipment_subject_with_four_kinds() -> None:
    one = uuid.uuid4()
    reefer = EquipmentQualificationType.REEFER_SERVICE
    validate_equipment_subject(
        truck_id=None, dolly_id=None, load_unit_id=None, reefer_unit_id=one, qtype=reefer
    )
    with pytest.raises(ValueError, match="exactly one"):
        validate_equipment_subject(
            truck_id=one, dolly_id=None, load_unit_id=None, reefer_unit_id=one, qtype=reefer
        )
    with pytest.raises(ValueError, match="reefer unit only"):
        validate_equipment_subject(
            truck_id=None,
            dolly_id=None,
            load_unit_id=one,
            reefer_unit_id=None,
            qtype=reefer,
        )
    with pytest.raises(ValueError, match="reefer unit only"):
        validate_equipment_subject(
            truck_id=None,
            dolly_id=None,
            load_unit_id=None,
            reefer_unit_id=one,
            qtype=EquipmentQualificationType.INSPECTION,
        )
