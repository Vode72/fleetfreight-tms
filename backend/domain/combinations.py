"""Basis for the length and mass of a vehicle combination (D55, D61). Pure domain module.

Computes totals from the given values only. It holds NO legal limits: maximum length, maximum
gross mass and permitted routes (HCT) come later from the road_restrictions table (phase 2B-3) and
are checked by Plan Check (phase 5), after the limits have been verified from the sources (D61).

Modelling simplifications, to be reviewed before Plan Check:
- The combination length is the sum of the part lengths plus a coupling gap per joint. The real
  figure depends on kingpin and drawbar geometry, so `coupling_gap_m` is a caller-supplied value
  (a setting later), not a constant here.
- Kerb weights and axles add up. The gross weight is the kerb weight plus the cargo weight. The
  parts' own maximum gross weights do not add up to a combination limit, so none is computed.
- A fixed body is not a separate part: its truck already carries its length, weight and axles.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from domain.equipment import TruckType


@dataclass(frozen=True)
class VehiclePart:
    """One physical part of a combination: truck, dolly or trailer."""

    length_m: Decimal
    kerb_weight_kg: int
    axles: int


@dataclass(frozen=True)
class CombinationTotals:
    part_count: int
    length_m: Decimal
    kerb_weight_kg: int
    axles: int

    def gross_weight_kg(self, cargo_weight_kg: int) -> int:
        """Kerb weight plus cargo."""
        if cargo_weight_kg < 0:
            raise ValueError("cargo_weight_kg must not be negative")
        return self.kerb_weight_kg + cargo_weight_kg


def validate_combination_structure(
    truck_type: TruckType, *, has_dolly: bool, trailer_count: int
) -> None:
    """Structural sanity only: a dolly sits between two towed units behind a tractor, or between a
    rigid truck and one trailer. A fixed body is not counted as a trailer."""
    if trailer_count < 0:
        raise ValueError("trailer_count must not be negative")
    if has_dolly:
        needed = 2 if truck_type is TruckType.TRACTOR else 1
        if trailer_count < needed:
            raise ValueError(
                f"a dolly behind a {truck_type.value} needs at least {needed} trailer(s)"
            )


def combination_totals(
    truck: VehiclePart,
    *,
    dolly: VehiclePart | None = None,
    trailers: Sequence[VehiclePart] = (),
    coupling_gap_m: Decimal = Decimal(0),
) -> CombinationTotals:
    """Length, kerb weight and axles of truck + optional dolly + trailers (in this order)."""
    if coupling_gap_m < 0:
        raise ValueError("coupling_gap_m must not be negative")
    parts = [truck, *([dolly] if dolly else []), *trailers]
    gaps = coupling_gap_m * (len(parts) - 1)
    return CombinationTotals(
        part_count=len(parts),
        length_m=sum((p.length_m for p in parts), Decimal(0)) + gaps,
        kerb_weight_kg=sum(p.kerb_weight_kg for p in parts),
        axles=sum(p.axles for p in parts),
    )
