import re
import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

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
    EquipmentQualificationType,
    LoadUnitType,
    Ownership,
    PowerSource,
    TruckType,
    is_thermo,
    lease_valid_on,
    side_loading_possible,
    validate_compartment,
    validate_compartment_set,
    validate_equipment_subject,
    validate_fixed_body_host,
    validate_lease,
    validate_load_unit,
    validate_reefer_unit_allowed,
    validate_vehicle,
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
    assert {v.value for v in Ownership} == {"own", "leased", "rented", "partner"}
    assert {v.value for v in PowerSource} == {"diesel", "electric", "hybrid"}
    assert {v.value for v in EquipmentQualificationType} == {
        "atp",
        "inspection",
        "tail_lift_inspection",
        "gdp_temperature_mapping",
        "adr_vehicle_approval",
    }


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


TRAILER = {
    "unit_type": LoadUnitType.TRAILER,
    "truck_id": None,
    "external_length_m": Decimal("13.60"),
    "kerb_weight_kg": 6800,
    "max_gross_weight_kg": 39000,
    "axles": 3,
    "ownership": Ownership.OWN,
    "lease_valid_from": None,
    "lease_valid_until": None,
}
BODY = TRAILER | {
    "unit_type": LoadUnitType.FIXED_BODY,
    "truck_id": uuid.uuid4(),
    "external_length_m": None,
    "kerb_weight_kg": None,
    "max_gross_weight_kg": None,
    "axles": None,
}


def test_trailer_rules() -> None:
    validate_load_unit(**TRAILER)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not reference a truck"):
        validate_load_unit(**TRAILER | {"truck_id": uuid.uuid4()})  # type: ignore[arg-type]
    for missing in ("external_length_m", "kerb_weight_kg", "max_gross_weight_kg", "axles"):
        with pytest.raises(ValueError, match="trailer needs"):
            validate_load_unit(**TRAILER | {missing: None})  # type: ignore[arg-type]
    with pytest.raises(ValueError):  # values still sane
        validate_load_unit(**TRAILER | {"max_gross_weight_kg": 100})  # type: ignore[arg-type]


def test_fixed_body_rules() -> None:
    validate_load_unit(**BODY)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must reference its truck"):
        validate_load_unit(**BODY | {"truck_id": None})  # type: ignore[arg-type]
    for field, value in (
        ("external_length_m", Decimal("6")),
        ("kerb_weight_kg", 1),
        ("max_gross_weight_kg", 1),
        ("axles", 2),
    ):
        with pytest.raises(ValueError, match="from its truck"):
            validate_load_unit(**BODY | {field: value})  # type: ignore[arg-type]


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
