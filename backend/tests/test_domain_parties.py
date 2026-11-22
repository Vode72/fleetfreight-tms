import re
from enum import StrEnum
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint

from db.models import Carrier, Customer, Driver, DriverQualification, Location, in_list
from domain.countries import validate_country
from domain.locations import LocationType
from domain.parties import (
    CarrierType,
    CustomerType,
    DriverEmployment,
    carrier_display_name,
    employment_matches_carrier,
    validate_carrier_customer_link,
    validate_name,
)
from domain.qualifications import DriverQualificationType

_VERSIONS = Path(__file__).parents[1] / "migrations/versions"
MIGRATION = _VERSIONS / "c52d8e3f1a47_create_parties_and_locations.py"
# CHECK lists redefined by a later revision: the latest one must match the domain.
LATEST_MIGRATION = {
    "ck_locations_type": _VERSIONS / "988966e62624_parking_and_border_crossing_details.py",
}

# (model, constraint name, column, domain enum)
ENUM_CHECKS = [
    (Customer, "ck_customers_type", "type", CustomerType),
    (Location, "ck_locations_type", "type", LocationType),
    (Carrier, "ck_carriers_type", "type", CarrierType),
    (Driver, "ck_drivers_employment", "employment", DriverEmployment),
    (DriverQualification, "ck_driver_qualifications_type", "type", DriverQualificationType),
]


def test_allowed_values() -> None:
    assert [v.value for v in CustomerType] == ["customer", "own_company"]
    assert [v.value for v in CarrierType] == ["own", "subcontractor"]
    assert [v.value for v in DriverEmployment] == ["own", "subcontractor_named"]
    assert {v.value for v in LocationType} == {
        "customer_site",
        "terminal",
        "port",
        "depot",
        "workshop",
        "wash",
        "inspection",
        "parking",
        "rail_terminal",
        "fuel",
        "customs_office",
        "border_crossing",
    }
    assert {v.value for v in DriverQualificationType} == {
        "adr_basic",
        "adr_tank",
        "adr_class1",
        "adr_class7",
        "driving_licence_c",
        "driving_licence_ce",
        "professional_competence",
        "tachograph_card",
        "gdp",
    }


@pytest.mark.parametrize(("model", "name", "column", "enum"), ENUM_CHECKS)
def test_model_and_migration_check_lists_match_domain(
    model: type, name: str, column: str, enum: type[StrEnum]
) -> None:
    """Model and migration CHECK lists must list exactly the domain values."""
    checks = {
        c.name: str(c.sqltext)
        for c in model.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }
    expected = in_list(column, enum)
    assert checks[name] == expected
    # The migration splits long strings over several lines; join them before comparing.
    path = LATEST_MIGRATION.get(name, MIGRATION)
    migration = re.sub(r'"\s*"', "", path.read_text(encoding="utf-8"))
    assert f'"{expected}"' in migration
    # Independent of in_list: every domain value appears in the CHECK as a quoted literal.
    for value in enum:
        assert f"'{value.value}'" in checks[name]


@pytest.mark.parametrize("value", ["FI", "DE", "EE", "AX", "IT", "SE"])
def test_valid_country(value: str) -> None:
    assert validate_country(value) == value


@pytest.mark.parametrize("value", ["", "fi", "FIN", "F", "F1", "FI ", "FI\n"])
def test_invalid_country(value: str) -> None:
    with pytest.raises(ValueError):
        validate_country(value)


def test_validate_name_trims_and_rejects_blank() -> None:
    assert validate_name("  Demo Freight Oy ") == "Demo Freight Oy"
    for blank in ("", "   "):
        with pytest.raises(ValueError):
            validate_name(blank)


def test_employment_matches_carrier() -> None:
    assert employment_matches_carrier(DriverEmployment.OWN, CarrierType.OWN)
    assert employment_matches_carrier(
        DriverEmployment.SUBCONTRACTOR_NAMED, CarrierType.SUBCONTRACTOR
    )
    assert not employment_matches_carrier(DriverEmployment.OWN, CarrierType.SUBCONTRACTOR)
    assert not employment_matches_carrier(DriverEmployment.SUBCONTRACTOR_NAMED, CarrierType.OWN)


def test_carrier_customer_link_rules_d73() -> None:
    validate_carrier_customer_link(CarrierType.OWN, CustomerType.OWN_COMPANY)
    validate_carrier_customer_link(CarrierType.SUBCONTRACTOR, None)
    with pytest.raises(ValueError):
        validate_carrier_customer_link(
            CarrierType.OWN, CustomerType.CUSTOMER
        )  # not the own company
    with pytest.raises(ValueError):
        validate_carrier_customer_link(CarrierType.OWN, None)
    with pytest.raises(ValueError):
        validate_carrier_customer_link(CarrierType.SUBCONTRACTOR, CustomerType.OWN_COMPANY)
    with pytest.raises(ValueError):
        validate_carrier_customer_link(CarrierType.SUBCONTRACTOR, CustomerType.CUSTOMER)


def test_carrier_display_name_reads_the_customer_for_the_own_carrier() -> None:
    assert carrier_display_name("Demo Sub Oy", None) == "Demo Sub Oy"
    assert carrier_display_name(None, "Demo Freight Oy") == "Demo Freight Oy"
    with pytest.raises(ValueError):
        carrier_display_name(None, None)
