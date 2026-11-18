"""Basis for the length and mass of a vehicle combination (D55, D61). Pure domain module.

Computes totals from the given values only. It holds NO legal limits: maximum length, maximum
gross mass and permitted routes (HCT) come later from the road_restrictions table (phase 2B-3) and
are checked by Plan Check (phase 5).

The combination types accepted below are the general structures of road haulage (tractor with a
semi-trailer; tractor with semi-trailer, dolly and semi-trailer; rigid truck with a drawbar
trailer; rigid truck with dolly and semi-trailer). Which of them are permitted, and the length
and mass figures, are to be checked from the sources before phase 5 (D61).

Length model (simplifications, to be reviewed before Plan Check):
- Fifth-wheel coupling (a semi-trailer on a tractor or on a dolly): the semi-trailer's front part
  (up to its kingpin) lies over the unit in front. So a tractor contributes only the distance from
  its front to the fifth wheel (`fifth_wheel_from_front_m`), and the semi-trailer contributes from
  its kingpin to its rear (`length_m - kingpin_from_front_m`).
- Drawbar coupling (a dolly, a full trailer or a centre-axle trailer behind a truck or trailer):
  the parts' lengths are added with a drawbar gap per joint, a caller-supplied value
  (`drawbar_gap_m`, a setting later, not a constant here). For a dolly, `length_m` is the distance
  from its drawbar eye to its fifth wheel; a semi-trailer on it adds its kingpin-to-rear part.
- Kerb weights and axles add up. The gross weight is the kerb weight plus the cargo weight. The
  parts' own maximum gross weights do not add up to a combination limit, so none is computed.
- A fixed body is not a separate part: its truck already carries its length, weight and axles.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from domain.equipment import CouplingType, TruckType


@dataclass(frozen=True)
class VehiclePart:
    """One physical part of a combination."""

    length_m: Decimal
    kerb_weight_kg: int
    axles: int


@dataclass(frozen=True)
class TruckPart(VehiclePart):
    """The pulling truck. `length_m` is its overall length; a tractor also gives the distance from
    its front to the fifth wheel."""

    fifth_wheel_from_front_m: Decimal | None = None


@dataclass(frozen=True)
class DollyPart(VehiclePart):
    """A dolly: `length_m` runs from the drawbar eye to its fifth wheel."""


@dataclass(frozen=True)
class TrailerPart(VehiclePart):
    """A trailer; `length_m` is its external length."""

    coupling: CouplingType = CouplingType.SEMI_TRAILER
    kingpin_from_front_m: Decimal | None = None


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
    truck_type: TruckType,
    *,
    dollies: int = 0,
    semi_trailers: int = 0,
    full_trailers: int = 0,
    centre_axle_trailers: int = 0,
    drawbar_hitch: bool = False,
) -> None:
    """Which parts a combination may consist of (general structure only, no limits).

    - Tractor: no trailer at all (solo), or semi-trailers = 1 + dollies (tractor, semi-trailer,
      then dolly and semi-trailer pairs). Drawbar trailers are not pulled by a tractor.
    - Rigid truck: semi-trailers = dollies (a semi-trailer needs a dolly under its front), so a
      semi-trailer without a dolly is not allowed. Alternatively exactly one full or centre-axle
      trailer on the drawbar, with no dolly and no semi-trailer. Pulling anything needs a drawbar
      hitch on the truck.
    A fixed body is not a trailer and is not counted.
    """
    counts = (dollies, semi_trailers, full_trailers, centre_axle_trailers)
    if min(counts) < 0:
        raise ValueError("part counts must not be negative")
    drawbar_trailers = full_trailers + centre_axle_trailers
    if truck_type is TruckType.TRACTOR:
        if drawbar_trailers:
            raise ValueError("a tractor does not pull a full or centre-axle trailer")
        if (semi_trailers, dollies) != (0, 0) and semi_trailers != 1 + dollies:
            raise ValueError(
                f"a tractor needs semi-trailers = 1 + dollies, got {semi_trailers} and {dollies}"
            )
        return
    if drawbar_trailers:
        if drawbar_trailers != 1 or dollies or semi_trailers:
            raise ValueError(
                "a rigid truck pulls at most one full or centre-axle trailer, without a dolly"
                " or semi-trailer"
            )
    elif semi_trailers != dollies:
        raise ValueError(
            f"a rigid truck needs semi-trailers = dollies, got {semi_trailers} and {dollies}"
        )
    elif dollies > 1:
        # A dolly couples to the truck's drawbar hitch, not behind a semi-trailer.
        raise ValueError("a rigid truck pulls at most one dolly with one semi-trailer")
    if (dollies or drawbar_trailers) and not drawbar_hitch:
        raise ValueError("a rigid truck needs a drawbar hitch to pull a dolly or trailer")


def _is_semi(part: object) -> bool:
    return isinstance(part, TrailerPart) and part.coupling is CouplingType.SEMI_TRAILER


def combination_totals(
    truck: TruckPart,
    *,
    chain: Sequence[DollyPart | TrailerPart] = (),
    drawbar_gap_m: Decimal = Decimal(0),
) -> CombinationTotals:
    """Length, kerb weight and axles of the truck and the parts behind it, in order.

    Raises ValueError when a semi-trailer has nothing to sit on: it must follow a tractor that has
    a fifth wheel position, or a dolly, and it needs its kingpin position.
    """
    if drawbar_gap_m < 0:
        raise ValueError("drawbar_gap_m must not be negative")
    units: list[VehiclePart] = [truck, *chain]
    length = Decimal(0)
    for index, unit in enumerate(units):
        following = units[index + 1] if index + 1 < len(units) else None
        if isinstance(unit, TrailerPart) and _is_semi(unit):
            if unit.kingpin_from_front_m is None:
                raise ValueError("a semi-trailer needs kingpin_from_front_m")
            behind = units[index - 1]
            if not isinstance(behind, DollyPart) and not (
                isinstance(behind, TruckPart) and behind.fifth_wheel_from_front_m is not None
            ):
                raise ValueError(
                    "a semi-trailer needs a tractor with a fifth wheel position or a dolly in front"
                )
            length += unit.length_m - unit.kingpin_from_front_m
        elif isinstance(unit, TruckPart) and _is_semi(following):
            if unit.fifth_wheel_from_front_m is None:
                raise ValueError("the truck has no fifth wheel position")
            length += unit.fifth_wheel_from_front_m  # the rest of the tractor is under the trailer
        else:
            length += unit.length_m
        # A drawbar joint (dolly, full trailer, centre-axle trailer behind something) has a gap.
        if following is not None and not _is_semi(following):
            length += drawbar_gap_m
    return CombinationTotals(
        part_count=len(units),
        length_m=length,
        kerb_weight_kg=sum(u.kerb_weight_kg for u in units),
        axles=sum(u.axles for u in units),
    )
