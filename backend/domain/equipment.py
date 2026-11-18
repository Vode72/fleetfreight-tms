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
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal


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


class ModelCode(StrEnum):
    """Model code of a load unit (D75): a hybrid classification, kept apart from the features.

    The thermo codes FB (Thermo Box, one reefer unit), FD (Thermo Double, two reefer units) and FS
    (Thermo Side, side doors) are invented demo codes; CS (curtainsider), MEGA and COIL are common
    trade terms. A code does NOT determine the features: a MEGA trailer with a coil well is
    MEGA + `coil_well`, not a MEGA_COIL model. Compatibility is decided from the real features
    (columns), never from the code. NULL is allowed for body types with no code (box,
    side-opening, fixed bodies).
    """

    FB = "FB"
    FD = "FD"
    FS = "FS"
    CS = "CS"
    MEGA = "MEGA"
    COIL = "COIL"


THERMO_MODEL_CODES: frozenset[ModelCode] = frozenset({ModelCode.FB, ModelCode.FD, ModelCode.FS})


class ReeferPosition(StrEnum):
    """Where a reefer unit sits on the load unit (D76): at most one per position."""

    FRONT = "front"
    REAR = "rear"


# A EUR pallet (1200 x 800 mm) loaded lengthwise-across: a row is 800 mm deep and holds 2 pallets.
EUR_PALLET_ROW_DEPTH_M = Decimal("0.80")
EUR_PALLETS_PER_ROW = 2
MAX_REEFER_UNITS = 2


class CouplingType(StrEnum):
    """How a trailer is coupled to what pulls it (D55: full trailers are modelled too)."""

    # Fifth-wheel coupling: the kingpin sits on a tractor's (or a dolly's) fifth wheel.
    SEMI_TRAILER = "semi_trailer"
    # Drawbar trailer with its own front axle(s), pulled by a drawbar behind a rigid truck.
    FULL_TRAILER = "full_trailer"
    # Drawbar trailer whose axles sit near the middle of the body.
    CENTRE_AXLE_TRAILER = "centre_axle_trailer"


class Ownership(StrEnum):
    """Who owns the load unit, relative to its holder (`load_units.carrier_id`).

    The carrier is always the holder: the one that operates the unit and plans its trips.
    - own: the holder owns it.
    - leased / rented: the holder uses it under a lease or rental (lease dates apply).
    - partner: it belongs to a partner (subcontractor) carrier, which is also the holder.
    - customer_owned: it belongs to a customer or a line operator (their unit, used by the holder).
    """

    OWN = "own"
    LEASED = "leased"
    RENTED = "rented"
    PARTNER = "partner"
    CUSTOMER_OWNED = "customer_owned"


class PowerSource(StrEnum):
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"


class EquipmentQualificationType(StrEnum):
    ATP = "atp"
    # Service of a reefer unit (the machine, not the body); applies to reefer units only (D76).
    REEFER_SERVICE = "reefer_service"
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

# The reverse: a reefer unit takes only these types.
REEFER_UNIT_ONLY_QUALIFICATIONS: frozenset[EquipmentQualificationType] = frozenset(
    {EquipmentQualificationType.REEFER_SERVICE}
)

_LEASED_OWNERSHIPS = (Ownership.LEASED, Ownership.RENTED)


def side_loading_possible(body_type: BodyType, side_doors: bool = False) -> bool:
    """D36: curtainsider, mega and side-opening bodies allow side loading; a box does not.

    A reefer body (or any other) has side loading only when it has side doors. `side_doors` is a
    real feature column rather than something derived from the model code (D75: FS = Thermo Side
    has side doors, but the code is not what decides it).
    """
    return side_doors or body_type in (BodyType.CURTAINSIDER, BodyType.MEGA, BodyType.SIDE_OPENING)


def validate_model_code(
    model_code: ModelCode | None, body_type: BodyType, side_doors: bool = False
) -> None:
    """The model code must fit the body (D75); it never decides the features by itself.

    - FB, FD, FS: reefer bodies; FS has side doors.
    - CS: curtainsider; MEGA: mega body; COIL: a non-reefer body (the coil well is its own flag).
    - No code (None) is always allowed.
    """
    if model_code is None:
        return
    if model_code in THERMO_MODEL_CODES:
        if not is_thermo(body_type):
            raise ValueError(f"{model_code.value} is a thermo model: the body must be a reefer")
        if model_code is ModelCode.FS and not side_doors:
            raise ValueError("FS (Thermo Side) has side doors")
        return
    if is_thermo(body_type):
        raise ValueError(f"{model_code.value} is not a thermo model")
    if model_code is ModelCode.CS and body_type is not BodyType.CURTAINSIDER:
        raise ValueError("CS is a curtainsider")
    if model_code is ModelCode.MEGA and body_type is not BodyType.MEGA:
        raise ValueError("MEGA needs a mega body")


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


def validate_truck(
    *,
    truck_type: TruckType,
    length_m: Decimal,
    fifth_wheel_from_front_m: Decimal | None,
    low_fifth_wheel: bool,
    drawbar_hitch: bool,
    max_gross_weight_kg: int,
    max_combination_weight_kg: int | None,
) -> None:
    """Truck features (mirrors the CHECKs): fifth wheel and low fifth wheel belong to tractors,
    a drawbar hitch to rigid trucks."""
    if fifth_wheel_from_front_m is not None:
        if truck_type is not TruckType.TRACTOR:
            raise ValueError("fifth_wheel_from_front_m applies to a tractor only")
        if not 0 < fifth_wheel_from_front_m <= length_m:
            raise ValueError("fifth_wheel_from_front_m must be positive and within length_m")
    if low_fifth_wheel and truck_type is not TruckType.TRACTOR:
        raise ValueError("low_fifth_wheel applies to a tractor only")
    if drawbar_hitch and truck_type is not TruckType.RIGID_TRUCK:
        raise ValueError("drawbar_hitch applies to a rigid truck only")
    if max_combination_weight_kg is not None and max_combination_weight_kg < max_gross_weight_kg:
        raise ValueError("max_combination_weight_kg must not be below max_gross_weight_kg")


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
    coupling_type: CouplingType | None,
    kingpin_from_front_m: Decimal | None = None,
    tail_lift: bool = False,
    rail_craneable: bool = False,
) -> None:
    """The single-row rules of a load unit (D60); the database has the same CHECKs.

    - trailer: no truck; coupling type, outer length, kerb weight, gross weight and axles are
      required.
    - fixed_body: a truck is required; those vehicle-level fields and the coupling type must be
      empty (the truck holds them); it is not rail-craneable.
    - kingpin_from_front_m: semi-trailers only, inside the outer length.
    - D25: a semi-trailer has no tail lift.
    - leased / rented: lease_valid_from is required (the end may be open); the other ownerships:
      no lease dates.
    """
    if tail_lift and coupling_type is CouplingType.SEMI_TRAILER:
        raise ValueError("a semi-trailer cannot have a tail lift (D25)")
    if kingpin_from_front_m is not None:
        if coupling_type is not CouplingType.SEMI_TRAILER:
            raise ValueError("kingpin_from_front_m applies to a semi-trailer only")
        if kingpin_from_front_m <= 0 or (
            external_length_m is not None and kingpin_from_front_m >= external_length_m
        ):
            raise ValueError("kingpin_from_front_m must be positive and inside external_length_m")
    vehicle_fields = (external_length_m, kerb_weight_kg, max_gross_weight_kg, axles)
    if unit_type is LoadUnitType.TRAILER:
        if truck_id is not None:
            raise ValueError("a trailer must not reference a truck")
        if coupling_type is None:
            raise ValueError("a trailer needs a coupling_type")
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
        if any(v is not None for v in vehicle_fields) or coupling_type is not None:
            raise ValueError(
                "a fixed body takes length, weights, axles and coupling from its truck: "
                "leave them empty"
            )
        if rail_craneable:
            raise ValueError("a fixed body is not rail-craneable")
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


def validate_compartment_pallet_places(
    load_unit_pallet_places: int | None, places: Sequence[int | None]
) -> None:
    """Pallet places are optional per compartment; their sum must fit the load unit's places.

    With a movable partition the figures are nominal (the partition moves), so only the sum is
    compared. Places per pallet type belong to pallet_types (2B-3), not here.
    """
    if any(p is not None and p < 0 for p in places):
        raise ValueError("pallet_places must not be negative")
    known = [p for p in places if p is not None]
    if load_unit_pallet_places is not None and sum(known) > load_unit_pallet_places:
        raise ValueError("compartment pallet places exceed the load unit's pallet places")


def validate_compartment_set(body_type: BodyType, numbers: Sequence[int]) -> None:
    """Compartments belong to a thermo body only; numbers run 1..n without gaps or repeats."""
    if numbers and not is_thermo(body_type):
        raise ValueError("only a reefer body has compartments")
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        raise ValueError("compartment numbers must be 1..n without gaps or repeats")


def validate_reefer_units(
    body_type: BodyType,
    positions: Sequence[ReeferPosition],
    model_code: ModelCode | None = None,
) -> None:
    """A load unit has 0-2 reefer units, each in its own position (D76). The database has the
    unique (load_unit_id, position); the rest is checked here.

    - Reefer units belong to reefer bodies only.
    - At most 2, in different positions.
    - Model code FB has exactly one reefer unit and FD exactly two (when the units are listed);
      FS has one or two.
    """
    if positions and not is_thermo(body_type):
        raise ValueError("only a reefer body has a reefer unit")
    if len(positions) > MAX_REEFER_UNITS:
        raise ValueError(f"at most {MAX_REEFER_UNITS} reefer units per load unit")
    if len(set(positions)) != len(positions):
        raise ValueError("each reefer unit position (front, rear) can be used once")
    if model_code is ModelCode.FB and len(positions) != 1:
        raise ValueError("FB (Thermo Box) has exactly one reefer unit")
    if model_code is ModelCode.FD and len(positions) != 2:
        raise ValueError("FD (Thermo Double) has exactly two reefer units")


def validate_reefer_unit_allowed(body_type: BodyType) -> None:
    validate_reefer_units(body_type, [ReeferPosition.FRONT])


def validate_zones(compartment_count: int, independently_controlled: Sequence[bool]) -> None:
    """Temperature zones (compartments) are not tied to the number of reefer units (D76).

    Two reefer units do not mean two zones: an FD trailer with one compartment is valid (both
    machines serve the one zone). `independently_controlled` (one flag per compartment) says the
    compartment's set point is controlled on its own; it only makes sense when there are at least
    two compartments to be independent of.
    """
    if len(independently_controlled) > compartment_count:
        raise ValueError("more control flags than compartments")
    if any(independently_controlled) and compartment_count < 2:
        raise ValueError("independently_controlled needs at least two compartments")


@dataclass(frozen=True)
class PartitionSpec:
    """The partition (bulkhead) of a load unit (D76): from the roof, about 50 mm thick, moves in
    steps of one pallet row; the values are per load unit."""

    internal_length_m: Decimal
    partition: bool = False
    thickness_mm: int = 50
    step_pallet_rows: int = 1
    min_pallets_front: int = 4
    min_pallets_rear: int = 4


def validate_partition(spec: PartitionSpec) -> None:
    if spec.thickness_mm <= 0:
        raise ValueError("partition thickness must be positive")
    if spec.step_pallet_rows < 1:
        raise ValueError("partition step must be at least one pallet row")
    if spec.min_pallets_front < 0 or spec.min_pallets_rear < 0:
        raise ValueError("minimum pallets must not be negative")


@dataclass(frozen=True)
class PartitionPosition:
    """One allowed partition position: pallet rows (and EUR pallets) in front of the partition."""

    front_rows: int
    front_pallets: int
    rear_pallets: int


def partition_positions(
    spec: PartitionSpec,
    eur_pallet_places: int,
    row_depth_m: Decimal = EUR_PALLET_ROW_DEPTH_M,
) -> list[PartitionPosition]:
    """The allowed partition positions and the pallet places of the two compartments.

    The partition consumes length: its thickness is taken off the internal length before the rows
    are counted, so the rows are min(places // 2, floor((internal length - thickness) / row depth)).
    The partition moves in steps of `step_pallet_rows` rows (1 row = 2 EUR pallets), and each
    compartment keeps at least its minimum number of pallets. Without a partition there is no
    position. `eur_pallet_places` is the load unit's EUR pallet places without a partition.
    """
    validate_partition(spec)
    if not spec.partition:
        return []
    if eur_pallet_places < 0 or row_depth_m <= 0:
        raise ValueError("pallet places must not be negative and the row depth must be positive")
    usable_m = spec.internal_length_m - Decimal(spec.thickness_mm) / 1000
    rows_by_length = int(usable_m // row_depth_m) if usable_m > 0 else 0
    rows = min(eur_pallet_places // EUR_PALLETS_PER_ROW, rows_by_length)
    positions: list[PartitionPosition] = []
    for front_rows in range(spec.step_pallet_rows, rows, spec.step_pallet_rows):
        front = front_rows * EUR_PALLETS_PER_ROW
        rear = (rows - front_rows) * EUR_PALLETS_PER_ROW
        if front >= spec.min_pallets_front and rear >= spec.min_pallets_rear:
            positions.append(PartitionPosition(front_rows, front, rear))
    return positions


@dataclass(frozen=True)
class EquipmentSubject:
    """What a qualification is about, with the facts that decide which types apply."""

    kind: Literal["truck", "dolly", "load_unit", "reefer_unit"]
    body_type: BodyType | None = None  # load units
    tail_lift: bool = False  # load units


def validate_equipment_qualification(
    subject: EquipmentSubject, qtype: EquipmentQualificationType
) -> None:
    """Which qualification type may be recorded for which subject.

    - ATP and GDP temperature mapping: reefer load units only.
    - Tail lift inspection: load units that have a tail lift.
    - Reefer service: reefer units only (D76), and reefer units take nothing else.
    - Inspection and ADR vehicle approval: any truck, dolly or load unit.
    The database only knows the subject kind (CHECK); body type and tail lift are on another
    table, so services and the seed call this.
    """
    if (qtype in REEFER_UNIT_ONLY_QUALIFICATIONS) != (subject.kind == "reefer_unit"):
        raise ValueError("reefer_service applies to a reefer unit, and a reefer unit takes only it")
    if subject.kind == "reefer_unit":
        return
    if qtype in LOAD_UNIT_ONLY_QUALIFICATIONS and subject.kind != "load_unit":
        raise ValueError(f"{qtype.value} applies to a load unit only")
    if qtype in (
        EquipmentQualificationType.ATP,
        EquipmentQualificationType.GDP_TEMPERATURE_MAPPING,
    ) and not (subject.body_type is not None and is_thermo(subject.body_type)):
        raise ValueError(f"{qtype.value} applies to a reefer load unit only")
    if qtype is EquipmentQualificationType.TAIL_LIFT_INSPECTION and not subject.tail_lift:
        raise ValueError("tail_lift_inspection applies to a load unit with a tail lift only")


def validate_equipment_subject(
    *,
    truck_id: uuid.UUID | None,
    dolly_id: uuid.UUID | None,
    load_unit_id: uuid.UUID | None,
    qtype: EquipmentQualificationType,
    reefer_unit_id: uuid.UUID | None = None,
) -> None:
    """Exactly one subject, and a type that applies to it (mirrors the CHECKs)."""
    ids = (truck_id, dolly_id, load_unit_id, reefer_unit_id)
    if sum(x is not None for x in ids) != 1:
        raise ValueError(
            "exactly one of truck_id, dolly_id, load_unit_id and reefer_unit_id is required"
        )
    if (qtype in REEFER_UNIT_ONLY_QUALIFICATIONS) != (reefer_unit_id is not None):
        raise ValueError("reefer_service applies to a reefer unit only, and vice versa")
    if qtype in LOAD_UNIT_ONLY_QUALIFICATIONS and load_unit_id is None:
        raise ValueError(f"{qtype.value} applies to a load unit only")
