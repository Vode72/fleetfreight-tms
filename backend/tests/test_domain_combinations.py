from decimal import Decimal
from pathlib import Path

import pytest

import domain.combinations as combinations_module
from domain.combinations import (
    DollyPart,
    TrailerPart,
    TruckPart,
    combination_totals,
    validate_combination_structure,
)
from domain.equipment import CouplingType, TruckType

D = Decimal
TRACTOR = TruckPart(D("6.20"), 7800, 3, fifth_wheel_from_front_m=D("3.70"))
SEMI = TrailerPart(D("13.74"), 6800, 3, CouplingType.SEMI_TRAILER, kingpin_from_front_m=D("1.60"))
DOLLY = DollyPart(D("3.50"), 2000, 2)
RIGID = TruckPart(D("10.40"), 11200, 3)  # combination truck with a drawbar hitch
FULL = TrailerPart(D("7.82"), 5200, 2, CouplingType.FULL_TRAILER)
CENTRE_AXLE = TrailerPart(D("7.50"), 4800, 2, CouplingType.CENTRE_AXLE_TRAILER)
GAP = D("0.50")


def test_truck_alone_counts_its_full_length() -> None:
    totals = combination_totals(TRACTOR)
    assert (totals.part_count, totals.length_m, totals.kerb_weight_kg, totals.axles) == (
        1,
        D("6.20"),
        7800,
        3,
    )


def test_tractor_and_semi_trailer_overlap_at_the_fifth_wheel() -> None:
    """Tractor front to fifth wheel + trailer kingpin to rear, not 6.20 + 13.74."""
    totals = combination_totals(TRACTOR, chain=[SEMI])
    assert totals.length_m == D("3.70") + (D("13.74") - D("1.60")) == D("15.84")
    assert totals.kerb_weight_kg == 14600  # weights and axles still add up
    assert totals.axles == 6
    assert totals.part_count == 2


def test_hct_tractor_semi_dolly_semi() -> None:
    totals = combination_totals(TRACTOR, chain=[SEMI, DOLLY, SEMI], drawbar_gap_m=GAP)
    # tractor to fifth wheel + semi + gap + dolly (eye to fifth wheel) + semi kingpin to rear
    assert totals.length_m == D("3.70") + D("12.14") + GAP + D("3.50") + D("12.14") == D("31.98")
    assert totals.part_count == 4
    assert totals.kerb_weight_kg == 7800 + 6800 + 2000 + 6800
    assert totals.axles == 3 + 3 + 2 + 3


def test_rigid_truck_dolly_semi_trailer() -> None:
    totals = combination_totals(RIGID, chain=[DOLLY, SEMI], drawbar_gap_m=GAP)
    assert totals.length_m == D("10.40") + GAP + D("3.50") + D("12.14") == D("26.54")


@pytest.mark.parametrize("trailer", [FULL, CENTRE_AXLE])
def test_rigid_truck_with_a_drawbar_trailer_adds_lengths_and_a_gap(trailer: TrailerPart) -> None:
    totals = combination_totals(RIGID, chain=[trailer], drawbar_gap_m=GAP)
    assert totals.length_m == D("10.40") + GAP + trailer.length_m


def test_the_gap_applies_to_drawbar_joints_only() -> None:
    no_gap = combination_totals(TRACTOR, chain=[SEMI, DOLLY, SEMI]).length_m
    with_gap = combination_totals(TRACTOR, chain=[SEMI, DOLLY, SEMI], drawbar_gap_m=GAP).length_m
    assert with_gap - no_gap == GAP  # one drawbar joint (semi to dolly); the fifth wheels have none
    assert combination_totals(TRACTOR, chain=[SEMI], drawbar_gap_m=GAP).length_m == D("15.84")
    assert (
        combination_totals(RIGID, chain=[FULL], drawbar_gap_m=GAP).length_m
        - combination_totals(RIGID, chain=[FULL]).length_m
        == GAP
    )


def test_decimal_arithmetic_has_no_float_error() -> None:
    a = TruckPart(D("0.1"), 1, 1)
    b = DollyPart(D("0.2"), 1, 1)
    assert combination_totals(a, chain=[b]).length_m == D("0.3")  # 0.1 + 0.2, exactly


def test_gross_weight_is_kerb_plus_cargo() -> None:
    totals = combination_totals(TRACTOR, chain=[SEMI])
    assert totals.gross_weight_kg(24000) == 38600
    assert totals.gross_weight_kg(0) == 14600
    with pytest.raises(ValueError):
        totals.gross_weight_kg(-1)


def test_negative_gap_is_rejected() -> None:
    with pytest.raises(ValueError):
        combination_totals(TRACTOR, drawbar_gap_m=D("-0.1"))


def test_a_semi_trailer_needs_something_to_sit_on() -> None:
    with pytest.raises(ValueError, match="no fifth wheel position"):
        combination_totals(TruckPart(D("6.2"), 7800, 3), chain=[SEMI])  # tractor without data
    with pytest.raises(ValueError, match="fifth wheel"):
        combination_totals(RIGID, chain=[SEMI])  # rigid truck, no dolly
    with pytest.raises(ValueError, match="fifth wheel"):
        combination_totals(RIGID, chain=[FULL, SEMI])  # behind a drawbar trailer
    with pytest.raises(ValueError, match="fifth wheel"):
        combination_totals(TRACTOR, chain=[SEMI, SEMI])  # behind a semi-trailer
    with pytest.raises(ValueError, match="kingpin"):
        combination_totals(TRACTOR, chain=[TrailerPart(D("13.74"), 6800, 3)])


def test_no_legal_limits_in_the_module() -> None:
    """D61: limits come from road_restrictions later; the module only computes totals."""
    code = Path(combinations_module.__file__).read_text(encoding="utf-8")
    for limit in ("25.25", "34.5", "76000", "40000", "16.5", "18.75"):
        assert limit not in code


TRACTOR_T, RIGID_T = TruckType.TRACTOR, TruckType.RIGID_TRUCK


@pytest.mark.parametrize(
    ("truck", "counts"),
    [
        (TRACTOR_T, {}),  # solo
        (TRACTOR_T, {"semi_trailers": 1}),
        (TRACTOR_T, {"semi_trailers": 2, "dollies": 1}),  # HCT
        (TRACTOR_T, {"semi_trailers": 3, "dollies": 2}),
        (RIGID_T, {}),
        (RIGID_T, {"semi_trailers": 1, "dollies": 1, "drawbar_hitch": True}),
        (RIGID_T, {"full_trailers": 1, "drawbar_hitch": True}),
        (RIGID_T, {"centre_axle_trailers": 1, "drawbar_hitch": True}),
    ],
)
def test_valid_structures(truck: TruckType, counts: dict[str, int | bool]) -> None:
    validate_combination_structure(truck, **counts)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("truck", "counts", "message"),
    [
        (TRACTOR_T, {"semi_trailers": 2}, "1 \\+ dollies"),  # two semis without a dolly
        (TRACTOR_T, {"semi_trailers": 1, "dollies": 1}, "1 \\+ dollies"),
        (TRACTOR_T, {"dollies": 1}, "1 \\+ dollies"),
        (TRACTOR_T, {"full_trailers": 1}, "does not pull"),
        (TRACTOR_T, {"centre_axle_trailers": 1}, "does not pull"),
        (RIGID_T, {"semi_trailers": 1, "drawbar_hitch": True}, "semi-trailers = dollies"),
        (RIGID_T, {"dollies": 1, "drawbar_hitch": True}, "semi-trailers = dollies"),
        (RIGID_T, {"full_trailers": 2, "drawbar_hitch": True}, "at most one"),
        (
            RIGID_T,
            {"full_trailers": 1, "centre_axle_trailers": 1, "drawbar_hitch": True},
            "at most",
        ),
        (
            RIGID_T,
            {"full_trailers": 1, "dollies": 1, "semi_trailers": 1, "drawbar_hitch": True},
            "at most",
        ),
        (RIGID_T, {"semi_trailers": 2, "dollies": 2, "drawbar_hitch": True}, "one dolly"),
        (RIGID_T, {"semi_trailers": 1, "dollies": 1}, "drawbar hitch"),
        (RIGID_T, {"full_trailers": 1}, "drawbar hitch"),
        (RIGID_T, {"dollies": -1}, "negative"),
    ],
)
def test_invalid_structures(truck: TruckType, counts: dict[str, int | bool], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_combination_structure(truck, **counts)  # type: ignore[arg-type]
