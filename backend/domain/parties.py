"""Customers, carriers and drivers (R6, D20, D54, D59). Pure domain module.

The allowed values are stored in the database (see the CHECK constraints in db/models.py and the
migration); tests/test_domain_parties.py keeps both in step.
"""

from enum import StrEnum


class CustomerType(StrEnum):
    CUSTOMER = "customer"
    # The operating company itself; payer of internal orders (D54). At most one row (database);
    # exactly one is ensured by the seed and later the service layer.
    OWN_COMPANY = "own_company"


class CarrierType(StrEnum):
    OWN = "own"
    SUBCONTRACTOR = "subcontractor"


class DriverEmployment(StrEnum):
    OWN = "own"
    # A named driver of a subcontractor. Unnamed subcontractor work has no driver at all (D20).
    SUBCONTRACTOR_NAMED = "subcontractor_named"


def validate_name(value: str) -> str:
    """Names are stored trimmed and must not be empty."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("name must not be empty")
    return stripped


def employment_matches_carrier(employment: DriverEmployment, carrier_type: CarrierType) -> bool:
    """An own driver belongs to the own carrier, a named subcontractor driver to a subcontractor.

    Spans two tables, so the database cannot check it with a CHECK constraint; services that
    create drivers must call this.
    """
    expected = CarrierType.OWN if employment is DriverEmployment.OWN else CarrierType.SUBCONTRACTOR
    return carrier_type is expected


def validate_carrier_customer_link(
    carrier_type: CarrierType, customer_type: CustomerType | None
) -> None:
    """D73: the own carrier points to the own company's customer row, a subcontractor to none.

    `customer_type` is the type of the referenced customer row, or None when there is no link.
    The database checks the link's presence (CHECK on carriers) but not the referenced row's
    type, because that spans two tables; services and the seed must call this.
    """
    if carrier_type is CarrierType.OWN:
        if customer_type is not CustomerType.OWN_COMPANY:
            raise ValueError("the own carrier must reference the own company's customer row")
    elif customer_type is not None:
        raise ValueError("a subcontractor must not reference a customer row")


def carrier_display_name(carrier_name: str | None, customer_name: str | None) -> str:
    """The own carrier has no name or business ID of its own (D73): read them from the customer.

    A subcontractor carries its own name. Exactly one of the two sources is expected.
    """
    name = carrier_name if carrier_name is not None else customer_name
    if name is None:
        raise ValueError("carrier has neither a name nor a linked customer")
    return name
