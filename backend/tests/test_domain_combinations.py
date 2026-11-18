from decimal import Decimal

import pytest

from domain.combinations import (
    VehiclePart,
    combination_totals,
    validate_combination_structure,
)
from domain.equipment import TruckType

TRACTOR = VehiclePart(Decimal("6.20"), 7800, 3)
SEMI = VehiclePart(Decimal("13.60"), 6800, 3)
DOLLY = VehiclePart(Decimal("4.20"), 2000, 2)
RIGID = VehiclePart(Decimal("9.80"), 9800, 3)


def test_truck_alone() -> None:
    totals = combination_totals(TRACTOR)
    assert (totals.part_count, totals.length_m, totals.kerb_weight_kg, totals.axles) == (
        1,
        Decimal("6.20"),
        7800,
        3,
    )


def test_tractor_and_semi_trailer() -> None:
    totals = combination_totals(TRACTOR, trailers=[SEMI])
    assert totals.length_m == Decimal("19.80")
    assert totals.kerb_weight_kg == 14600
    assert totals.axles == 6


def test_hct_tractor_semi_dolly_semi() -> None:
    totals = combination_totals(TRACTOR, dolly=DOLLY, trailers=[SEMI, SEMI])
    assert totals.part_count == 4
    assert totals.length_m == Decimal("6.20") + Decimal("4.20") + 2 * Decimal("13.60")
    assert totals.kerb_weight_kg == 7800 + 2000 + 2 * 6800
    assert totals.axles == 3 + 2 + 6


def test_rigid_truck_dolly_semi_trailer() -> None:
    totals = combination_totals(RIGID, dolly=DOLLY, trailers=[SEMI])
    assert totals.length_m == Decimal("27.60")
    assert totals.kerb_weight_kg == 18600


def test_coupling_gap_is_added_per_joint_and_comes_from_the_caller() -> None:
    totals = combination_totals(
        TRACTOR, dolly=DOLLY, trailers=[SEMI, SEMI], coupling_gap_m=Decimal("0.50")
    )
    assert totals.length_m == Decimal("37.60") + Decimal("1.50")  # four parts, three joints
    assert combination_totals(TRACTOR, coupling_gap_m=Decimal("0.50")).length_m == Decimal("6.20")


def test_decimal_arithmetic_has_no_float_error() -> None:
    parts = [VehiclePart(Decimal("0.1"), 1, 1), VehiclePart(Decimal("0.2"), 1, 1)]
    assert combination_totals(parts[0], trailers=[parts[1]]).length_m == Decimal("0.3")


def test_gross_weight_is_kerb_plus_cargo() -> None:
    totals = combination_totals(TRACTOR, trailers=[SEMI])
    assert totals.gross_weight_kg(24000) == 38600
    assert totals.gross_weight_kg(0) == 14600
    with pytest.raises(ValueError):
        totals.gross_weight_kg(-1)


def test_negative_gap_is_rejected() -> None:
    with pytest.raises(ValueError):
        combination_totals(TRACTOR, coupling_gap_m=Decimal("-0.1"))


def test_no_legal_limits_in_the_module() -> None:
    """D61: limits come from road_restrictions later; the module only computes totals."""
    from pathlib import Path

    import domain.combinations as module

    code = Path(module.__file__).read_text(encoding="utf-8")
    for limit in ("25.25", "34.5", "76000", "40000", "16.5"):
        assert limit not in code


def test_structure_rules() -> None:
    validate_combination_structure(TruckType.TRACTOR, has_dolly=False, trailer_count=1)
    validate_combination_structure(TruckType.TRACTOR, has_dolly=True, trailer_count=2)
    validate_combination_structure(TruckType.RIGID_TRUCK, has_dolly=True, trailer_count=1)
    validate_combination_structure(TruckType.RIGID_TRUCK, has_dolly=False, trailer_count=0)
    with pytest.raises(ValueError):
        validate_combination_structure(TruckType.TRACTOR, has_dolly=True, trailer_count=1)
    with pytest.raises(ValueError):
        validate_combination_structure(TruckType.RIGID_TRUCK, has_dolly=True, trailer_count=0)
    with pytest.raises(ValueError):
        validate_combination_structure(TruckType.TRACTOR, has_dolly=False, trailer_count=-1)
