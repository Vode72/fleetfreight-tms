"""Create fictional demo master data (2B-1). Not part of any migration.

Usage (from the backend directory):
    ENVIRONMENT=development uv run python -m scripts.seed_demo_data

Contents: the own company, the terminal network (D31-D33), ports, demo customers with sites,
carriers, drivers and driver qualifications. All names contain "Demo"; addresses, identifiers and
coordinates (a general city centre) are invented or generic. No real companies or contact data.

Idempotent: every row is identified by its natural key (customers, carriers, locations by name,
drivers by carrier and name, qualifications by driver and type). Existing rows are left as they
are (never overwritten, so manual edits survive); only missing rows are created. Qualification
dates are relative to the day of the first run. Refuses to run unless ENVIRONMENT=development.
"""

import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from db.models import Carrier, Customer, Driver, DriverQualification, Location
from db.session import get_engine
from domain.locations import (
    LocationType,
    validate_opening_hours,
    validate_terminal_fields,
    validate_timezone,
)
from domain.parties import CarrierType, CustomerType, DriverEmployment, employment_matches_carrier
from domain.qualifications import DriverQualificationType as Q

OWN_COMPANY = "Demo Freight Oy"
_TERMINAL_HOURS = {day: [["06:00", "22:00"]] for day in ("mon", "tue", "wed", "thu", "fri")}
_SITE_HOURS = {day: [["07:00", "16:00"]] for day in ("mon", "tue", "wed", "thu", "fri")}


@dataclass(frozen=True)
class _Place:
    name: str
    type: LocationType
    country: str
    latitude: str
    longitude: str
    timezone: str
    customer: str | None = None
    docks: int | None = None
    cold: bool | None = None
    temp_min: str | None = None
    temp_max: str | None = None
    plugs: int | None = None
    hours: dict[str, list[list[str]]] | None = None
    booking_required: bool = False
    parent: str | None = None


def _terminal(
    city: str, lat: str, lon: str, docks: int, *, cold: bool = False, plugs: int | None = None
) -> _Place:
    return _Place(
        name=f"Demo Terminal {city}",
        type=LocationType.TERMINAL,
        country="FI",
        latitude=lat,
        longitude=lon,
        timezone="Europe/Helsinki",
        docks=docks,
        cold=cold,
        temp_min="-25.0" if cold else None,
        temp_max="8.0" if cold else None,
        plugs=plugs if cold else None,
        hours=_TERMINAL_HOURS,
    )


def _port(city: str, country: str, lat: str, lon: str, tz: str) -> _Place:
    return _Place(
        name=f"Demo Port {city}",
        type=LocationType.PORT,
        country=country,
        latitude=lat,
        longitude=lon,
        timezone=tz,
    )


# Terminal network (D31): all have loading docks (D32); cold storage and reefer plugs only in
# Central, Tampere and Oulu (D33). Coordinates: general city centre.
PLACES: tuple[_Place, ...] = (
    _terminal("Central", "60.169900", "24.938400", 12, cold=True, plugs=6),
    _terminal("Turku", "60.451800", "22.266600", 6),
    _terminal("Tampere", "61.497800", "23.761000", 8, cold=True, plugs=4),
    _terminal("Kuopio", "62.892400", "27.677000", 5),
    _terminal("Oulu", "65.012100", "25.465100", 6, cold=True, plugs=4),
    _port("Kotka", "FI", "60.466400", "26.945800", "Europe/Helsinki"),
    _port("Vuosaari", "FI", "60.169900", "24.938400", "Europe/Helsinki"),
    _port("Hanko", "FI", "59.823100", "22.950000", "Europe/Helsinki"),
    _port("Oulu", "FI", "65.012100", "25.465100", "Europe/Helsinki"),
    _port("Travemünde", "DE", "53.961700", "10.870000", "Europe/Berlin"),
    _port("Lübeck", "DE", "53.865500", "10.686600", "Europe/Berlin"),
    _Place(
        "Demo Port Lübeck \u2013 Lehmannkai",
        LocationType.PORT,
        "DE",
        "53.870000",
        "10.690000",
        "Europe/Berlin",
        parent="Demo Port Lübeck",
    ),
    _Place(
        "Demo Port Lübeck \u2013 Seelandkai",
        LocationType.PORT,
        "DE",
        "53.875000",
        "10.700000",
        "Europe/Berlin",
        parent="Demo Port Lübeck",
    ),
    _port("Rostock", "DE", "54.092400", "12.099100", "Europe/Berlin"),
    _port("Gdynia", "PL", "54.518900", "18.530500", "Europe/Warsaw"),
    _port("Tallinn", "EE", "59.437000", "24.753600", "Europe/Tallinn"),
    _port("Antwerpen", "BE", "51.219400", "4.402500", "Europe/Brussels"),
    _Place(
        "Demo Paper Mill Site",
        LocationType.CUSTOMER_SITE,
        "FI",
        "62.892400",
        "27.677000",
        "Europe/Helsinki",
        customer="Demo Paper Oy",
        hours=_SITE_HOURS,
        booking_required=True,
    ),
    _Place(
        "Demo Dairy Plant Site",
        LocationType.CUSTOMER_SITE,
        "FI",
        "61.497800",
        "23.761000",
        "Europe/Helsinki",
        customer="Demo Meijeri Oy",
        hours=_SITE_HOURS,
    ),
    _Place(
        "Demo Pharma Warehouse Site",
        LocationType.CUSTOMER_SITE,
        "FI",
        "60.451800",
        "22.266600",
        "Europe/Helsinki",
        customer="Demo Pharma Oy",
        hours=_SITE_HOURS,
        booking_required=True,
    ),
    _Place(
        "Demo Papier Lager Site",
        LocationType.CUSTOMER_SITE,
        "DE",
        "53.551100",
        "9.993700",
        "Europe/Berlin",
        customer="Demo Papier GmbH",
        hours=_SITE_HOURS,
    ),
    _Place(
        "Demo Timber Yard Site",
        LocationType.CUSTOMER_SITE,
        "FI",
        "65.012100",
        "25.465100",
        "Europe/Helsinki",
        customer="Demo Puutavara Oy",
        hours=_SITE_HOURS,
    ),
)

# name, type, country, business_id (invented), pallet_exchange_agreed
CUSTOMERS: tuple[tuple[str, CustomerType, str, str | None, bool], ...] = (
    (OWN_COMPANY, CustomerType.OWN_COMPANY, "FI", "DEMO-FI-0001", False),
    ("Demo Paper Oy", CustomerType.CUSTOMER, "FI", "DEMO-FI-0101", False),
    ("Demo Meijeri Oy", CustomerType.CUSTOMER, "FI", "DEMO-FI-0102", True),
    ("Demo Pharma Oy", CustomerType.CUSTOMER, "FI", "DEMO-FI-0103", False),
    ("Demo Papier GmbH", CustomerType.CUSTOMER, "DE", "DEMO-DE-0201", False),
    ("Demo Puutavara Oy", CustomerType.CUSTOMER, "FI", "DEMO-FI-0104", False),
)

# name, type, country, business_id, licence years valid, insurance years valid
CARRIERS: tuple[tuple[str, CarrierType, str, str, int, int], ...] = (
    (OWN_COMPANY, CarrierType.OWN, "FI", "DEMO-FI-0001", 3, 1),
    ("Demo Trans GmbH", CarrierType.SUBCONTRACTOR, "DE", "DEMO-DE-0301", 2, 1),
    ("Demo Kuljetus Oy", CarrierType.SUBCONTRACTOR, "FI", "DEMO-FI-0302", 2, 1),
)

# carrier, name, home terminal (own drivers), employment, qualifications (type, days valid)
_BASE = ((Q.DRIVING_LICENCE_CE, 1500), (Q.PROFESSIONAL_COMPETENCE, 1200), (Q.TACHOGRAPH_CARD, 900))
DRIVERS: tuple[tuple[str, str, str | None, DriverEmployment, tuple[tuple[Q, int], ...]], ...] = (
    (OWN_COMPANY, "Demo Driver Aalto", "Demo Terminal Central", DriverEmployment.OWN, _BASE),
    (
        OWN_COMPANY,
        "Demo Driver Berg",
        "Demo Terminal Central",
        DriverEmployment.OWN,
        (*_BASE, (Q.ADR_BASIC, 700), (Q.ADR_TANK, 700)),
    ),
    (
        OWN_COMPANY,
        "Demo Driver Koski",
        "Demo Terminal Tampere",
        DriverEmployment.OWN,
        (*_BASE, (Q.GDP, 365)),
    ),
    (
        OWN_COMPANY,
        "Demo Driver Laine",
        "Demo Terminal Kuopio",
        DriverEmployment.OWN,
        (*_BASE, (Q.ADR_BASIC, 21), (Q.ADR_CLASS1, 21)),  # expiring soon
    ),
    (
        OWN_COMPANY,
        "Demo Driver Niemi",
        "Demo Terminal Oulu",
        DriverEmployment.OWN,
        (*_BASE, (Q.ADR_BASIC, 900), (Q.ADR_CLASS7, 900)),
    ),
    ("Demo Trans GmbH", "Demo Driver Becker", None, DriverEmployment.SUBCONTRACTOR_NAMED, _BASE),
    (
        "Demo Trans GmbH",
        "Demo Driver Vogel",
        None,
        DriverEmployment.SUBCONTRACTOR_NAMED,
        (*_BASE, (Q.ADR_BASIC, 500)),
    ),
    ("Demo Kuljetus Oy", "Demo Driver Salo", None, DriverEmployment.SUBCONTRACTOR_NAMED, _BASE),
)


def _document_ref(qtype: Q, driver_name: str) -> str:
    return f"DEMO-{qtype.value.upper()}-{driver_name.rsplit(' ', 1)[-1].upper()}"


def seed_demo_data(session: Session, today: date | None = None) -> Counter[str]:
    """Create the missing demo rows. Returns the number of rows created per table."""
    today = today or date.today()
    created: Counter[str] = Counter()

    # --- customers (exactly one own company: reuse an existing one under another name)
    customers: dict[str, Customer] = {}
    for name, ctype, country, business_id, pallets in CUSTOMERS:
        customer = session.scalar(select(Customer).where(Customer.name == name))
        if customer is None and ctype is CustomerType.OWN_COMPANY:
            customer = session.scalar(select(Customer).where(Customer.type == ctype.value))
        if customer is None:
            customer = Customer(
                name=name,
                type=ctype.value,
                country=country,
                business_id=business_id,
                pallet_exchange_agreed=pallets,
            )
            session.add(customer)
            created["customers"] += 1
        customers[name] = customer
    session.flush()

    # --- locations
    locations: dict[str, Location] = {}
    for place in PLACES:
        location = session.scalar(select(Location).where(Location.name == place.name))
        if location is None:
            temp_min = Decimal(place.temp_min) if place.temp_min is not None else None
            temp_max = Decimal(place.temp_max) if place.temp_max is not None else None
            validate_timezone(place.timezone)
            validate_terminal_fields(
                place.type,
                loading_docks=place.docks,
                cold_storage=place.cold,
                temperature_min=temp_min,
                temperature_max=temp_max,
                reefer_plug_count=place.plugs,
            )
            location = Location(
                name=place.name,
                type=place.type.value,
                customer_id=customers[place.customer].id if place.customer else None,
                parent_location_id=locations[place.parent].id if place.parent else None,
                address="Demo Address 1 (fictional)",
                country=place.country,
                latitude=Decimal(place.latitude),
                longitude=Decimal(place.longitude),
                timezone=place.timezone,
                opening_hours=validate_opening_hours(place.hours) if place.hours else None,
                booking_required=place.booking_required,
                loading_docks=place.docks,
                cold_storage=place.cold,
                temperature_min=temp_min,
                temperature_max=temp_max,
                reefer_plug_count=place.plugs,
            )
            session.add(location)
            created["locations"] += 1
        locations[place.name] = location
    session.flush()

    # --- carriers
    carriers: dict[str, Carrier] = {}
    for name, carrier_type, country, business_id, licence_years, insurance_years in CARRIERS:
        carrier_row = session.scalar(select(Carrier).where(Carrier.name == name))
        if carrier_row is None:
            carrier_row = Carrier(
                name=name,
                type=carrier_type.value,
                country=country,
                business_id=business_id,
                transport_licence_valid_until=today + timedelta(days=365 * licence_years),
                liability_insurance_valid_until=today + timedelta(days=365 * insurance_years),
            )
            session.add(carrier_row)
            created["carriers"] += 1
        carriers[name] = carrier_row
    session.flush()

    # --- drivers and their qualifications
    for carrier_name, name, home, employment, quals in DRIVERS:
        carrier = carriers[carrier_name]
        if not employment_matches_carrier(employment, CarrierType(carrier.type)):
            raise ValueError(f"{name}: employment {employment} does not fit carrier {carrier_name}")
        driver = session.scalar(
            select(Driver).where(Driver.carrier_id == carrier.id, Driver.name == name)
        )
        if driver is None:
            driver = Driver(
                carrier_id=carrier.id,
                name=name,
                home_location_id=locations[home].id if home else None,
                employment=employment.value,
            )
            session.add(driver)
            session.flush()
            created["drivers"] += 1
        for qtype, days in quals:
            exists = session.scalar(
                select(DriverQualification.id).where(
                    DriverQualification.driver_id == driver.id,
                    DriverQualification.type == qtype.value,
                )
            )
            if exists is None:
                session.add(
                    DriverQualification(
                        driver_id=driver.id,
                        type=qtype.value,
                        valid_until=today + timedelta(days=days),
                        document_ref=_document_ref(qtype, name),
                    )
                )
                created["driver_qualifications"] += 1
    session.commit()
    return created


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo data unless ENVIRONMENT=development.", file=sys.stderr)
        return 2
    with sessionmaker(bind=get_engine())() as session:
        created = seed_demo_data(session)
    for table in ("customers", "locations", "carriers", "drivers", "driver_qualifications"):
        print(f"{table}: {created[table]} created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
