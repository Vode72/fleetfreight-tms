"""Fleet: trucks, dollies, load units, compartments and equipment qualifications (D36, D39, D47,
D60, D61, D63, D67, D70). Pure domain module.

The allowed values are stored in the database (CHECK constraints in db/models.py and the
migration); tests/test_domain_equipment.py keeps both in step.

A *load unit* (D60) is the thing a trip follows: a trailer, or the fixed body of a rigid truck.
Vehicle-level data (kerb weight, gross weight, axles, outer length) of a fixed body belongs to its
truck and is stored only there, so a rigid truck is never counted twice.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum


class TruckType(StrEnum):
    TRACTOR = "tractor"
    RIGID_TRUCK = "rigid_truck"


class LoadUnitType(StrEnum):
    TRAILER = "trailer"
    # The body of a rigid truck (D39). A swap body would be a new type in the same table (D60).
    FIXED_BODY = "fixed_body"


class BodyType(StrEnum):
    CURTAINSIDER = "curtainsider"
    MEGA = "mega"
    SIDE_OPENING = "side_opening"
    BOX = "box"
    # Thermo body with one or more temperature compartments (D47).
    REEFER = "reefer"


class Ownership(StrEnum):
    OWN = "own"
    LEASED = "leased"
    RENTED = "rented"
    # Belongs to a partner (subcontractor) carrier.
    PARTNER = "partner"


class PowerSource(StrEnum):
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"


class EquipmentQualificationType(StrEnum):
    ATP = "atp"
    INSPECTION = "inspection"
    TAIL_LIFT_INSPECTION = "tail_lift_inspection"
    GDP_TEMPERATURE_MAPPING = "gdp_temperature_mapping"
    ADR_VEHICLE_APPROVAL = "adr_vehicle_approval"


# These only make sense for a load unit (the body, not the tractor or the dolly); the database
# enforces it with a CHECK on equipment_qualifications.
LOAD_UNIT_ONLY_QUALIFICATIONS: frozenset[EquipmentQualificationType] = frozenset(
    {
        EquipmentQualificationType.ATP,
        EquipmentQualificationType.TAIL_LIFT_INSPECTION,
        EquipmentQualificationType.GDP_TEMPERATURE_MAPPING,
    }
)

_LEASED_OWNERSHIPS = (Ownership.LEASED, Ownership.RENTED)


def side_loading_possible(body_type: BodyType) -> bool:
    """D36: curtainsider, mega and side-opening bodies allow side loading; a box does not."""
    return body_type in (BodyType.CURTAINSIDER, BodyType.MEGA, BodyType.SIDE_OPENING)


def is_thermo(body_type: BodyType) -> bool:
    """Only a reefer body may have compartments and a reefer unit (D47)."""
    return body_type is BodyType.REEFER


def validate_vehicle(
    *, length_m: Decimal, kerb_weight_kg: int, max_gross_weight_kg: int, axles: int
) -> None:
    """Data sanity for a truck, dolly or trailer (mirrors the CHECKs). No legal limits here."""
    if length_m <= 0:
        raise ValueError("length_m must be positive")
    if kerb_weight_kg <= 0:
        raise ValueError("kerb_weight_kg must be positive")
    if max_gross_weight_kg < kerb_weight_kg:
        raise ValueError("max_gross_weight_kg must not be below kerb_weight_kg")
    if axles < 1:
        raise ValueError("axles must be at least 1")


def validate_load_unit(
    *,
    unit_type: LoadUnitType,
    truck_id: uuid.UUID | None,
    external_length_m: Decimal | None,
    kerb_weight_kg: int | None,
    max_gross_weight_kg: int | None,
    axles: int | None,
    ownership: Ownership,
    lease_valid_from: date | None,
    lease_valid_until: date | None,
) -> None:
    """The single-row rules of a load unit (D60); the database has the same CHECKs.

    - trailer: no truck; outer length, kerb weight, gross weight and axles are required.
    - fixed_body: a truck is required; those four vehicle-level fields must be empty (the truck
      holds them).
    - leased / rented: lease_valid_from is required (the end may be open); own / partner: no lease
      dates.
    """
    vehicle_fields = (external_length_m, kerb_weight_kg, max_gross_weight_kg, axles)
    if unit_type is LoadUnitType.TRAILER:
        if truck_id is not None:
            raise ValueError("a trailer must not reference a truck")
        if any(v is None for v in vehicle_fields):
            raise ValueError(
                "a trailer needs external_length_m, kerb_weight_kg, max_gross_weight_kg and axles"
            )
        assert external_length_m is not None and kerb_weight_kg is not None  # for mypy
        assert max_gross_weight_kg is not None and axles is not None
        validate_vehicle(
            length_m=external_length_m,
            kerb_weight_kg=kerb_weight_kg,
            max_gross_weight_kg=max_gross_weight_kg,
            axles=axles,
        )
    else:
        if truck_id is None:
            raise ValueError("a fixed body must reference its truck")
        if any(v is not None for v in vehicle_fields):
            raise ValueError(
                "a fixed body takes length, weights and axles from its truck: leave them empty"
            )
    validate_lease(ownership, lease_valid_from, lease_valid_until)


def validate_lease(ownership: Ownership, valid_from: date | None, valid_until: date | None) -> None:
    if ownership in _LEASED_OWNERSHIPS:
        if valid_from is None:
            raise ValueError(f"{ownership.value} needs lease_valid_from")
        if valid_until is not None and valid_from > valid_until:
            raise ValueError("lease_valid_from must not be after lease_valid_until")
    elif valid_from is not None or valid_until is not None:
        raise ValueError(f"{ownership.value} must not have lease dates")


def lease_valid_on(
    ownership: Ownership, valid_from: date | None, valid_until: date | None, day: date
) -> bool:
    """Own and partner load units need no lease (always True); otherwise the lease must cover
    `day` (both ends inclusive, no end date = open-ended)."""
    if ownership not in _LEASED_OWNERSHIPS:
        return True
    if valid_from is None or day < valid_from:
        return False
    return valid_until is None or day <= valid_until


def validate_fixed_body_host(
    *,
    truck_type: TruckType,
    truck_carrier_id: uuid.UUID,
    load_unit_carrier_id: uuid.UUID,
) -> None:
    """A fixed body sits on a rigid truck of the same carrier. Spans two tables, so only services
    and the seed can check it."""
    if truck_type is not TruckType.RIGID_TRUCK:
        raise ValueError("a fixed body belongs to a rigid truck, not a tractor")
    if truck_carrier_id != load_unit_carrier_id:
        raise ValueError("a fixed body must have the same carrier as its truck")


def validate_compartment(number: int, temperature_min: Decimal, temperature_max: Decimal) -> None:
    if number < 1:
        raise ValueError("compartment number must be at least 1")
    if temperature_min > temperature_max:
        raise ValueError("temperature_min must not be above temperature_max")


def validate_compartment_set(body_type: BodyType, numbers: Sequence[int]) -> None:
    """Compartments belong to a thermo body only; numbers run 1..n without gaps or repeats."""
    if numbers and not is_thermo(body_type):
        raise ValueError("only a reefer body has compartments")
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        raise ValueError("compartment numbers must be 1..n without gaps or repeats")


def validate_reefer_unit_allowed(body_type: BodyType) -> None:
    if not is_thermo(body_type):
        raise ValueError("only a reefer body has a reefer unit")


def validate_equipment_subject(
    *,
    truck_id: uuid.UUID | None,
    dolly_id: uuid.UUID | None,
    load_unit_id: uuid.UUID | None,
    qtype: EquipmentQualificationType,
) -> None:
    """Exactly one subject, and a type that applies to it (mirrors the CHECKs)."""
    if sum(x is not None for x in (truck_id, dolly_id, load_unit_id)) != 1:
        raise ValueError("exactly one of truck_id, dolly_id and load_unit_id is required")
    if qtype in LOAD_UNIT_ONLY_QUALIFICATIONS and load_unit_id is None:
        raise ValueError(f"{qtype.value} applies to a load unit only")
