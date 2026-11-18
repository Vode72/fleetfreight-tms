"""Create fictional demo master data (2B-1). Not part of any migration.

Usage (from the backend directory):
    ENVIRONMENT=development uv run python -m scripts.seed_demo_data

Contents: the own company, the terminal network (D31-D33), ports, rail terminals, customs
offices, demo customers with sites, carriers, drivers and driver qualifications. All names
contain "Demo"; addresses and identifiers are invented. Coordinates: terminals at the general
city centre (D31), ports at a general point of the port area, customer sites and customs offices
at invented points (customer sites in Finland lie 10-40 km from the nearest terminal, except the
Jyvaskyla site, which is served from Tampere or Kuopio). No two places share coordinates except
a port area and its quays. No real companies, addresses or contact data.

Opening hours (local time): Central and Tampere terminals 24/7, other terminals Mon-Fri 05-23
and Sat 06-14; customer sites vary. Ports have opening_hours NULL, which means "not checked"
(Plan Check does not test port opening hours); NULL is also "unknown" for any other place.

Idempotent: every row is identified by its natural key (customers, carriers, locations by name,
drivers by carrier and name, qualifications by driver and type). Existing rows are left as they
are (never overwritten, so manual edits survive, and rows created by an older version of this
script are not updated); only missing rows are created. Qualification and licence dates are
relative to the day of the first run (one qualification is already expired, one is expiring soon,
and one driver has no professional competence, for Plan Check scenarios).
Refuses to run unless ENVIRONMENT=development.
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
_Hours = dict[str, list[list[str]]]
_ALL_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_WEEKDAYS = _ALL_DAYS[:5]


def _hours(days: tuple[str, ...], opens: str, closes: str) -> _Hours:
    return {day: [[opens, closes]] for day in days}


HOURS_24_7 = _hours(_ALL_DAYS, "00:00", "24:00")
HOURS_TERMINAL = {**_hours(_WEEKDAYS, "05:00", "23:00"), "sat": [["06:00", "14:00"]]}
HOURS_DAIRY = _hours((*_WEEKDAYS, "sat"), "05:00", "15:00")
HOURS_PHARMA = _hours(_WEEKDAYS, "08:00", "16:00")
HOURS_OFFICE = _hours(_WEEKDAYS, "07:00", "17:00")
HOURS_INDUSTRY = _hours(_WEEKDAYS, "06:00", "18:00")
HOURS_SHOP = {**_hours(_WEEKDAYS, "09:00", "17:00"), "sat": [["10:00", "14:00"]]}


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
    hours: _Hours | None = None
    booking_required: bool = False
    parent: str | None = None
    side_loading: bool = False
    max_vehicle_length_m: str | None = None
    has_loading_dock: bool | None = None


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
        # Central and Tampere run around the clock (they handle thermo cross docking, D33).
        hours=HOURS_24_7 if city in ("Central", "Tampere") else HOURS_TERMINAL,
    )


def _port(
    name: str, country: str, lat: str, lon: str, tz: str, parent: str | None = None
) -> _Place:
    # opening_hours stays NULL: port opening hours are not checked.
    return _Place(f"Demo Port {name}", LocationType.PORT, country, lat, lon, tz, parent=parent)


def _rail(city: str, country: str, lat: str, lon: str, tz: str) -> _Place:
    return _Place(f"Demo Rail Terminal {city}", LocationType.RAIL_TERMINAL, country, lat, lon, tz)


def _site(
    name: str,
    customer: str,
    country: str,
    lat: str,
    lon: str,
    hours: _Hours,
    *,
    tz: str = "Europe/Helsinki",
    booking: bool = False,
    side: bool = False,
    max_length: str | None = None,
    dock: bool | None = True,
) -> _Place:
    return _Place(
        name,
        LocationType.CUSTOMER_SITE,
        country,
        lat,
        lon,
        tz,
        customer=customer,
        hours=hours,
        booking_required=booking,
        side_loading=side,
        max_vehicle_length_m=max_length,
        has_loading_dock=dock,
    )


def _customs(name: str, country: str, lat: str, lon: str, tz: str, hours: _Hours) -> _Place:
    return _Place(name, LocationType.CUSTOMS_OFFICE, country, lat, lon, tz, hours=hours)


_LUBECK = "Demo Port Lübeck"
# Terminal network (D31): all have loading docks (D32); cold storage and reefer plugs only in
# Central, Tampere and Oulu (D33). Terminals sit at the general city centre.
PLACES: tuple[_Place, ...] = (
    _terminal("Central", "60.169900", "24.938400", 12, cold=True, plugs=6),
    _terminal("Turku", "60.451800", "22.266600", 6),
    _terminal("Tampere", "61.497800", "23.761000", 8, cold=True, plugs=4),
    _terminal("Kuopio", "62.892400", "27.677000", 5),
    _terminal("Oulu", "65.012100", "25.465100", 6, cold=True, plugs=4),
    # Ports: a general point of the port area.
    _port("Kotka", "FI", "60.440000", "26.960000", "Europe/Helsinki"),
    _port("Vuosaari", "FI", "60.210000", "25.140000", "Europe/Helsinki"),
    _port("Hanko", "FI", "59.820000", "22.970000", "Europe/Helsinki"),
    _port("Oulu", "FI", "65.000000", "25.390000", "Europe/Helsinki"),
    _port("Travemünde", "DE", "53.950000", "10.870000", "Europe/Berlin"),
    _port("Lübeck", "DE", "53.865000", "10.685000", "Europe/Berlin"),
    _port("Lübeck \u2013 Lehmannkai", "DE", "53.880000", "10.700000", "Europe/Berlin", _LUBECK),
    _port("Lübeck \u2013 Seelandkai", "DE", "53.900000", "10.730000", "Europe/Berlin", _LUBECK),
    _port("Naantali", "FI", "60.450000", "22.020000", "Europe/Helsinki"),
    # Åland (country code AX, outside the EU VAT area) and Sweden.
    _port("Långnäs", "AX", "60.110000", "20.290000", "Europe/Mariehamn"),
    _port("Kapellskär", "SE", "59.720000", "19.060000", "Europe/Stockholm"),
    _port("Rostock", "DE", "54.150000", "12.100000", "Europe/Berlin"),
    _port("Gdynia", "PL", "54.530000", "18.550000", "Europe/Warsaw"),
    _port("Tallinn", "EE", "59.450000", "24.770000", "Europe/Tallinn"),
    _port("Antwerpen", "BE", "51.270000", "4.350000", "Europe/Brussels"),
    # Rail terminals: invented points in the city area, not at the ports.
    _rail("Rostock", "DE", "54.100000", "12.050000", "Europe/Berlin"),
    _rail("Travemünde", "DE", "53.940000", "10.880000", "Europe/Berlin"),
    _rail("Verona", "IT", "45.430000", "10.990000", "Europe/Rome"),
    # Customs offices (D48): invented points; opening hours matter for Plan Check.
    _customs(
        "Demo Customs Office Central",
        "FI",
        "60.240000",
        "25.050000",
        "Europe/Helsinki",
        HOURS_OFFICE,
    ),
    _customs(
        "Demo Customs Office Svinesund",  # border crossing, Norwegian side
        "NO",
        "59.100000",
        "11.250000",
        "Europe/Oslo",
        _hours(_WEEKDAYS, "06:00", "22:00"),
    ),
    _customs(
        "Demo Customs Office Oslo",
        "NO",
        "59.910000",
        "10.750000",
        "Europe/Oslo",
        _hours(_WEEKDAYS, "08:00", "15:30"),
    ),
    # Customer sites: invented points 10-40 km from the nearest terminal (Jyvaskyla excepted).
    _site(
        "Demo Paper Mill Site",
        "Demo Paper Oy",
        "FI",
        "62.750000",
        "27.450000",
        HOURS_24_7,
        booking=True,
        side=True,
    ),
    _site(
        "Demo Paper Oy \u2013 Jyväskylä Site",
        "Demo Paper Oy",
        "FI",
        "62.260000",
        "25.820000",
        HOURS_OFFICE,
        side=True,
    ),  # served from Tampere or Kuopio (D31)
    _site("Demo Dairy Plant Site", "Demo Meijeri Oy", "FI", "61.620000", "23.950000", HOURS_DAIRY),
    _site(
        "Demo Pharma Warehouse Site",
        "Demo Pharma Oy",
        "FI",
        "60.560000",
        "22.400000",
        HOURS_PHARMA,
        booking=True,
        max_length="12.00",
    ),  # city warehouse, short vehicles only
    _site(
        "Demo Papier Lager Site",
        "Demo Papier GmbH",
        "DE",
        "53.500000",
        "10.100000",
        HOURS_OFFICE,
        tz="Europe/Berlin",
    ),
    _site(
        "Demo Timber Yard Site",
        "Demo Puutavara Oy",
        "FI",
        "64.900000",
        "25.600000",
        HOURS_INDUSTRY,
        side=True,
    ),
    # ADR consignor near Tampere.
    _site("Demo Kemia Plant Site", "Demo Kemia Oy", "FI", "61.380000", "23.600000", HOURS_INDUSTRY),
    # Norway (customs scenarios).
    _site(
        "Demo Norge Lager Site",
        "Demo Norge AS",
        "NO",
        "59.950000",
        "10.800000",
        HOURS_OFFICE,
        tz="Europe/Oslo",
    ),
    # Small LTL sites (Kuopio, Turku and Oulu areas); the Kuopio shop has no loading dock.
    _site(
        "Demo Kauppa Oy \u2013 Kuopio Shop Site",
        "Demo Kauppa Oy",
        "FI",
        "62.800000",
        "27.850000",
        HOURS_SHOP,
        dock=False,
    ),
    _site(
        "Demo Kauppa Oy \u2013 Turku Shop Site",
        "Demo Kauppa Oy",
        "FI",
        "60.520000",
        "22.050000",
        HOURS_SHOP,
    ),
    _site(
        "Demo Konepaja Oy \u2013 Kuopio Workshop Site",
        "Demo Konepaja Oy",
        "FI",
        "62.980000",
        "27.500000",
        HOURS_INDUSTRY,
    ),
    _site(
        "Demo Konepaja Oy \u2013 Oulu Workshop Site",
        "Demo Konepaja Oy",
        "FI",
        "65.100000",
        "25.650000",
        HOURS_INDUSTRY,
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
    ("Demo Kemia Oy", CustomerType.CUSTOMER, "FI", "DEMO-FI-0105", False),  # ADR consignor
    ("Demo Kauppa Oy", CustomerType.CUSTOMER, "FI", "DEMO-FI-0106", False),  # small LTL sites
    ("Demo Konepaja Oy", CustomerType.CUSTOMER, "FI", "DEMO-FI-0107", False),
    ("Demo Norge AS", CustomerType.CUSTOMER, "NO", "DEMO-NO-0401", False),
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
    (
        "Demo Trans GmbH",
        "Demo Driver Becker",
        None,
        DriverEmployment.SUBCONTRACTOR_NAMED,
        # tachograph card already expired (negative days: the first-run day minus 15)
        (_BASE[0], _BASE[1], (Q.TACHOGRAPH_CARD, -15)),
    ),
    (
        "Demo Trans GmbH",
        "Demo Driver Vogel",
        None,
        DriverEmployment.SUBCONTRACTOR_NAMED,
        (*_BASE, (Q.ADR_BASIC, 500)),
    ),
    (
        "Demo Kuljetus Oy",
        "Demo Driver Salo",
        None,
        DriverEmployment.SUBCONTRACTOR_NAMED,
        (_BASE[0], _BASE[2]),  # no professional competence
    ),
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
                side_loading_possible=place.side_loading,
                max_vehicle_length_m=(
                    Decimal(place.max_vehicle_length_m) if place.max_vehicle_length_m else None
                ),
                has_loading_dock=place.has_loading_dock,
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
        if carrier_row is None and carrier_type is CarrierType.OWN:
            carrier_row = session.scalar(select(Carrier).where(Carrier.type == carrier_type.value))
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
