"""Create fictional demo master data (2B-1, 2B-2). Not part of any migration.

Usage (from the backend directory):
    ENVIRONMENT=development uv run python -m scripts.seed_demo_data

Contents: the own company, the terminal network (D31-D33), ports, rail terminals, customs
offices, demo customers with sites, carriers, drivers and driver qualifications, and the fleet
(2B-2): tractors and rigid trucks, a dolly, trailers and fixed bodies with temperature
compartments and reefer units, and equipment qualification periods. All names contain "Demo";
addresses and identifiers are invented; registrations look like DEMO-TRK-001 (never real plates).
The own carrier is linked to the own company's customer row and has no name of its own (D73).
Coordinates: terminals at the general
city centre (D31), ports at a general point of the port area, customer sites and customs offices
at invented points (customer sites in Finland lie 10-40 km from the nearest terminal, except the
Jyvaskyla site, which is served from Tampere or Kuopio). No two places share coordinates except
a port area and its quays. No real companies, addresses or contact data.

Opening hours (local time): Central and Tampere terminals 24/7, other terminals Mon-Fri 05-23
and Sat 06-14; customer sites vary. Ports have opening_hours NULL, which means "not checked"
(Plan Check does not test port opening hours); NULL is also "unknown" for any other place.

Idempotent: every row is identified by its natural key (customers, subcontractor carriers,
locations by name, the own carrier by its type, drivers by carrier and name, qualification periods
by driver, type and document reference, trucks, dollies and load units by registration,
compartments by load unit and number, equipment periods by subject, type and document reference).
Existing rows are left as they are (never overwritten, so manual edits survive, and rows created
by an older version of this script are not updated); only missing rows are created.
Qualification dates are relative to the day of the first run. For Plan Check scenarios one
qualification is already expired, one is expiring soon, one driver has no professional
competence, and one driver shows the history (an expired period and its renewal). The GDP end
date follows the setting GDP_TRAINING_DEFAULT_VALIDITY_MONTHS (a company practice, not a
regulation).
Fleet scenarios: the own carrier has 5 tractors, 2 rigid trucks with a fixed body (one box with a
tail lift, one thermo) and a dolly, so a tractor + semi-trailer + dolly + semi-trailer (HCT, D61)
and a rigid truck + dolly + semi-trailer can be formed; 10 trailers (curtainsider, mega,
side-opening, XL with coil well, TIR cable, top loading, a two-compartment thermo with a reefer
unit, one leased, one rented, one a partner's), some rail-craneable (D63). Equipment periods: ATP
for both thermo load units (one expiring soon, the trailer's renewed so history shows), one
expired inspection, a GDP temperature mapping and a tail lift inspection.
Refuses to run unless ENVIRONMENT=development.
"""

import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from db.models import (
    Carrier,
    Compartment,
    Customer,
    Dolly,
    Driver,
    DriverQualification,
    EquipmentQualification,
    LoadUnit,
    Location,
    ReeferUnit,
    Truck,
)
from db.session import get_engine
from domain.equipment import (
    BodyType,
    CouplingType,
    EquipmentQualificationType,
    EquipmentSubject,
    LoadUnitType,
    ModelCode,
    Ownership,
    PartitionSpec,
    PowerSource,
    ReeferPosition,
    TruckType,
    validate_compartment,
    validate_compartment_pallet_places,
    validate_compartment_set,
    validate_equipment_qualification,
    validate_equipment_subject,
    validate_fixed_body_host,
    validate_load_unit,
    validate_model_code,
    validate_partition,
    validate_partition_allowed,
    validate_reefer_units,
    validate_truck,
    validate_vehicle,
    validate_zones,
)
from domain.locations import (
    LocationType,
    validate_opening_hours,
    validate_postal_code,
    validate_terminal_fields,
    validate_timezone,
)
from domain.parties import (
    CarrierType,
    CustomerType,
    DriverEmployment,
    employment_matches_carrier,
    validate_carrier_customer_link,
)
from domain.qualifications import DriverQualificationType as Q
from domain.qualifications import suggest_gdp_valid_until

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
    postal_code: str | None = None
    city: str | None = None
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
_PLACES_WITHOUT_LOCALITY: tuple[_Place, ...] = (
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

# Postal code and city (D68). Real codes of the general city-centre area only; where a code is not
# certain it stays None and only the city is given. Street addresses are invented ("Demo Street N").
_LOCALITY: dict[str, tuple[str | None, str]] = {
    "Demo Terminal Central": ("01510", "Vantaa"),
    "Demo Terminal Turku": ("20100", "Turku"),
    "Demo Terminal Tampere": ("33100", "Tampere"),
    "Demo Terminal Kuopio": ("70100", "Kuopio"),
    "Demo Terminal Oulu": ("90100", "Oulu"),
    "Demo Port Kotka": ("48100", "Kotka"),
    "Demo Port Vuosaari": ("00980", "Helsinki"),
    "Demo Port Hanko": ("10900", "Hanko"),
    "Demo Port Oulu": ("90100", "Oulu"),
    "Demo Port Naantali": ("21100", "Naantali"),
    "Demo Port Långnäs": (None, "Lumparland"),
    "Demo Port Kapellskär": (None, "Kapellskär"),
    "Demo Port Travemünde": ("23570", "Lübeck"),
    "Demo Port Lübeck": (None, "Lübeck"),
    "Demo Port Lübeck \u2013 Lehmannkai": (None, "Lübeck"),
    "Demo Port Lübeck \u2013 Seelandkai": (None, "Lübeck"),
    "Demo Port Rostock": ("18055", "Rostock"),
    "Demo Port Gdynia": (None, "Gdynia"),
    "Demo Port Tallinn": (None, "Tallinn"),
    "Demo Port Antwerpen": ("2000", "Antwerpen"),
    "Demo Rail Terminal Rostock": ("18055", "Rostock"),
    "Demo Rail Terminal Travemünde": ("23570", "Lübeck"),
    "Demo Rail Terminal Verona": ("37121", "Verona"),
    "Demo Customs Office Central": ("01510", "Vantaa"),
    "Demo Customs Office Svinesund": (None, "Svinesund"),
    "Demo Customs Office Oslo": (None, "Oslo"),
    "Demo Paper Mill Site": ("70100", "Kuopio"),
    "Demo Paper Oy \u2013 Jyväskylä Site": ("40100", "Jyväskylä"),
    "Demo Dairy Plant Site": ("33100", "Tampere"),
    "Demo Pharma Warehouse Site": ("20100", "Turku"),
    "Demo Papier Lager Site": ("20095", "Hamburg"),
    "Demo Timber Yard Site": ("90100", "Oulu"),
    "Demo Kemia Plant Site": ("33100", "Tampere"),
    "Demo Norge Lager Site": (None, "Oslo"),
    "Demo Kauppa Oy \u2013 Kuopio Shop Site": ("70100", "Kuopio"),
    "Demo Kauppa Oy \u2013 Turku Shop Site": ("20100", "Turku"),
    "Demo Konepaja Oy \u2013 Kuopio Workshop Site": ("70100", "Kuopio"),
    "Demo Konepaja Oy \u2013 Oulu Workshop Site": ("90100", "Oulu"),
}
PLACES: tuple[_Place, ...] = tuple(
    replace(p, postal_code=_LOCALITY[p.name][0], city=_LOCALITY[p.name][1])
    for p in _PLACES_WITHOUT_LOCALITY
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

# name, type, country, business_id, licence years valid, insurance years valid.
# The own carrier row is created without name, country and business ID (D73: read from the own
# company's customer row); the name here only identifies it in this script.
CARRIERS: tuple[tuple[str, CarrierType, str, str, int, int], ...] = (
    (OWN_COMPANY, CarrierType.OWN, "FI", "DEMO-FI-0001", 3, 1),
    ("Demo Trans GmbH", CarrierType.SUBCONTRACTOR, "DE", "DEMO-DE-0301", 2, 1),
    ("Demo Kuljetus Oy", CarrierType.SUBCONTRACTOR, "FI", "DEMO-FI-0302", 2, 1),
)

# A qualification period: (type, days from the first-run day to valid_until, years of validity).
# GDP is the exception (see Koski below).
# valid_from = valid_until - years * 365 days + 1 day, so a renewal can start the day after.
_Spec = tuple[Q, int, int]
_BASE: tuple[_Spec, ...] = (
    (Q.DRIVING_LICENCE_CE, 1500, 10),
    (Q.PROFESSIONAL_COMPETENCE, 1200, 5),
    (Q.TACHOGRAPH_CARD, 900, 5),
)
_CE, _PC, _TACHO = _BASE

# carrier, name, home terminal (own drivers), employment, qualification periods
DRIVERS: tuple[tuple[str, str, str | None, DriverEmployment, tuple[_Spec, ...]], ...] = (
    (
        OWN_COMPANY,
        "Demo Driver Aalto",
        "Demo Terminal Central",
        DriverEmployment.OWN,
        # History demo: the tachograph card expired 40 days ago and was renewed the next day.
        (_CE, _PC, (Q.TACHOGRAPH_CARD, -40, 5), (Q.TACHOGRAPH_CARD, 1785, 5)),
    ),
    (
        OWN_COMPANY,
        "Demo Driver Berg",
        "Demo Terminal Central",
        DriverEmployment.OWN,
        (*_BASE, (Q.ADR_BASIC, 700, 5), (Q.ADR_TANK, 700, 5)),
    ),
    (
        OWN_COMPANY,
        "Demo Driver Koski",
        "Demo Terminal Tampere",
        DriverEmployment.OWN,
        # GDP: the first number is the offset of valid_from; the end date is suggested from the
        # GDP_TRAINING_DEFAULT_VALIDITY_MONTHS setting (D69).
        (*_BASE, (Q.GDP, -100, 0)),
    ),
    (
        OWN_COMPANY,
        "Demo Driver Laine",
        "Demo Terminal Kuopio",
        DriverEmployment.OWN,
        (*_BASE, (Q.ADR_BASIC, 21, 5), (Q.ADR_CLASS1, 21, 5)),  # expiring soon
    ),
    (
        OWN_COMPANY,
        "Demo Driver Niemi",
        "Demo Terminal Oulu",
        DriverEmployment.OWN,
        (*_BASE, (Q.ADR_BASIC, 900, 5), (Q.ADR_CLASS7, 900, 5)),
    ),
    (
        "Demo Trans GmbH",
        "Demo Driver Becker",
        None,
        DriverEmployment.SUBCONTRACTOR_NAMED,
        (_CE, _PC, (Q.TACHOGRAPH_CARD, -15, 5)),  # tachograph card already expired, not renewed
    ),
    (
        "Demo Trans GmbH",
        "Demo Driver Vogel",
        None,
        DriverEmployment.SUBCONTRACTOR_NAMED,
        (*_BASE, (Q.ADR_BASIC, 500, 5)),
    ),
    (
        "Demo Kuljetus Oy",
        "Demo Driver Salo",
        None,
        DriverEmployment.SUBCONTRACTOR_NAMED,
        (_CE, _TACHO),  # no professional competence
    ),
)


@dataclass(frozen=True)
class _TruckSpec:
    registration: str
    carrier: str
    type: TruckType
    length_m: str
    kerb_weight_kg: int
    max_gross_weight_kg: int
    axles: int
    fifth_wheel_from_front_m: str | None = None
    low_fifth_wheel: bool = False
    drawbar_hitch: bool = False
    max_combination_weight_kg: int | None = None
    home: str | None = None  # name of the base location


def _tractor(registration: str, carrier: str, home: str | None = None, **kw: object) -> _TruckSpec:
    """A three-axle tractor unit with the fifth wheel 3.70 m from the front."""
    fields: dict[str, object] = {
        "length_m": "6.20",
        "kerb_weight_kg": 7800,
        "max_gross_weight_kg": 26000,
        "axles": 3,
        "fifth_wheel_from_front_m": "3.70",
    }
    fields.update(kw)
    return _TruckSpec(
        registration,
        carrier,
        TruckType.TRACTOR,
        home=home,
        **fields,  # type: ignore[arg-type]
    )


def _rigid(
    registration: str, length_m: str, kerb_weight_kg: int, home: str, **kw: object
) -> _TruckSpec:
    """A three-axle rigid truck of the own carrier (its body is a fixed-body load unit)."""
    return _TruckSpec(
        registration,
        OWN_COMPANY,
        TruckType.RIGID_TRUCK,
        length_m,
        kerb_weight_kg,
        26000,
        3,
        home=home,
        **kw,  # type: ignore[arg-type]
    )


TRUCKS: tuple[_TruckSpec, ...] = (
    # Own carrier: five tractors (001 is HCT-capable, 002 has a low fifth wheel for the mega
    # trailers, 004 has two axles) and three rigid trucks whose bodies are load units.
    _tractor("DEMO-TRK-001", OWN_COMPANY, "Demo Terminal Central", max_combination_weight_kg=76000),
    _tractor(
        "DEMO-TRK-002",
        OWN_COMPANY,
        "Demo Terminal Central",
        low_fifth_wheel=True,
        max_combination_weight_kg=60000,
    ),
    _tractor("DEMO-TRK-003", OWN_COMPANY, "Demo Terminal Tampere", max_combination_weight_kg=60000),
    _tractor(
        "DEMO-TRK-004",
        OWN_COMPANY,
        "Demo Terminal Kuopio",
        length_m="6.00",
        kerb_weight_kg=7200,
        max_gross_weight_kg=18000,
        axles=2,
        fifth_wheel_from_front_m="3.40",
        max_combination_weight_kg=44000,
    ),
    _tractor("DEMO-TRK-005", OWN_COMPANY, "Demo Terminal Oulu", max_combination_weight_kg=60000),
    _rigid("DEMO-TRK-006", "9.80", 9800, "Demo Terminal Central"),
    _rigid("DEMO-TRK-007", "9.50", 10400, "Demo Terminal Tampere"),
    # Combination truck (D55): longer, with a drawbar hitch for a full trailer or a dolly.
    _rigid(
        "DEMO-TRK-011",
        "10.40",
        11200,
        "Demo Terminal Central",
        drawbar_hitch=True,
        max_combination_weight_kg=60000,
    ),
    # Subcontractors: one or two tractors each (no base location recorded).
    _tractor("DEMO-TRK-008", "Demo Trans GmbH"),
    _tractor("DEMO-TRK-009", "Demo Trans GmbH"),
    _tractor("DEMO-TRK-010", "Demo Kuljetus Oy"),
)

# registration, carrier, length_m (drawbar eye to fifth wheel), kerb_weight_kg,
# max_gross_weight_kg, axles
DOLLIES: tuple[tuple[str, str, str, int, int, int], ...] = (
    ("DEMO-DOL-001", OWN_COMPANY, "3.50", 2000, 18000, 2),
)


@dataclass(frozen=True)
class _LoadUnitSpec:
    registration: str
    carrier: str
    body_type: BodyType
    internal_length_m: str
    internal_width_m: str
    internal_height_m: str
    door_height_m: str | None
    ldm: str
    pallet_places: int
    type: LoadUnitType = LoadUnitType.TRAILER
    coupling: CouplingType | None = CouplingType.SEMI_TRAILER
    model_code: ModelCode | None = None
    truck: str | None = None  # registration of the truck (fixed body)
    external_length_m: str | None = "13.74"
    kingpin_from_front_m: str | None = "1.60"
    external_height_m: str | None = "3.95"
    external_width_m: str | None = "2.55"
    kerb_weight_kg: int | None = 6800
    max_gross_weight_kg: int | None = 39000
    axles: int | None = 3
    xl_certified: bool = False
    coil_well: bool = False
    tir_cable: bool = False
    top_loading: bool = False
    tail_lift: bool = False
    side_doors: bool = False
    partition: bool = False  # D76; thickness, step and minimum pallets keep the defaults
    rail_craneable: bool = False
    ownership: Ownership = Ownership.OWN
    lease_from_days: int | None = None  # offsets from the first-run day
    lease_until_days: int | None = None


def _semi(
    registration: str, body: BodyType, carrier: str = OWN_COMPANY, **kw: object
) -> _LoadUnitSpec:
    """A standard semi-trailer: internal 13.60 m and 13.6 LDM, external a little longer."""
    fields: dict[str, object] = {
        "internal_length_m": "13.60",
        "internal_width_m": "2.48",
        "internal_height_m": "2.75",
        "door_height_m": "2.65",
        "ldm": "13.60",
        "pallet_places": 33,
    }
    fields.update(kw)
    return _LoadUnitSpec(registration, carrier, body, **fields)  # type: ignore[arg-type]


def _fixed_body(
    registration: str,
    truck: str,
    body: BodyType,
    internal: tuple[str, str, str],
    door_height_m: str,
    pallet_places: int,
    **kw: object,
) -> _LoadUnitSpec:
    """A fixed body: length, weights, axles and coupling are on the truck (single source)."""
    return _LoadUnitSpec(
        registration,
        OWN_COMPANY,
        body,
        *internal,
        door_height_m,
        internal[0],  # LDM = internal length
        pallet_places,
        type=LoadUnitType.FIXED_BODY,
        coupling=None,
        truck=truck,
        external_length_m=None,
        kingpin_from_front_m=None,
        kerb_weight_kg=None,
        max_gross_weight_kg=None,
        axles=None,
        **kw,  # type: ignore[arg-type]
    )


LOAD_UNITS: tuple[_LoadUnitSpec, ...] = (
    _semi("DEMO-TRL-001", BodyType.CURTAINSIDER, model_code=ModelCode.CS),
    _semi(
        "DEMO-TRL-002",
        BodyType.MEGA,
        model_code=ModelCode.MEGA,
        internal_height_m="3.00",
        door_height_m="2.90",
        external_height_m="4.00",
        rail_craneable=True,
    ),
    _semi("DEMO-TRL-003", BodyType.SIDE_OPENING, rail_craneable=True),
    # XL certified (EN 12642 XL) with a coil well (D36).
    _semi(
        "DEMO-TRL-004",
        BodyType.CURTAINSIDER,
        model_code=ModelCode.COIL,
        xl_certified=True,
        coil_well=True,
        pallet_places=30,
        kerb_weight_kg=7100,
        rail_craneable=True,
    ),
    _semi("DEMO-TRL-005", BodyType.CURTAINSIDER, model_code=ModelCode.CS, tir_cable=True),
    _semi(
        "DEMO-TRL-006",
        BodyType.CURTAINSIDER,
        model_code=ModelCode.CS,
        top_loading=True,
        kerb_weight_kg=7000,
    ),
    # Two-compartment thermo (freezer and chilled), reefer unit and compartments seeded below.
    _semi(
        "DEMO-TRL-007",
        BodyType.REEFER,
        model_code=ModelCode.FD,
        partition=True,
        internal_length_m="13.10",
        internal_width_m="2.46",
        internal_height_m="2.50",
        door_height_m="2.45",
        ldm="13.10",
        pallet_places=32,
        kerb_weight_kg=8600,
        external_width_m="2.60",
        rail_craneable=True,
    ),
    _semi(
        "DEMO-TRL-008",
        BodyType.CURTAINSIDER,
        model_code=ModelCode.CS,
        ownership=Ownership.LEASED,
        lease_from_days=-400,
        lease_until_days=330,
    ),
    _semi(
        "DEMO-TRL-009",
        BodyType.MEGA,
        model_code=ModelCode.MEGA,
        internal_height_m="3.00",
        door_height_m="2.90",
        external_height_m="4.00",
        ownership=Ownership.RENTED,
        lease_from_days=-20,
        lease_until_days=40,
    ),
    _semi(
        "DEMO-TRL-010",
        BodyType.CURTAINSIDER,
        model_code=ModelCode.CS,
        carrier="Demo Trans GmbH",
        ownership=Ownership.PARTNER,
    ),
    # Full trailer (drawbar, own front axle) for the combination truck (D55).
    _semi(
        "DEMO-TRL-011",
        BodyType.CURTAINSIDER,
        model_code=ModelCode.CS,
        coupling=CouplingType.FULL_TRAILER,
        internal_length_m="7.70",
        ldm="7.70",
        pallet_places=18,
        external_length_m="7.82",
        kingpin_from_front_m=None,
        kerb_weight_kg=5200,
        max_gross_weight_kg=18000,
        axles=2,
    ),
    # Thermo Double, two diesel units, the partition in the middle (16 + 16 places).
    _semi(
        "DEMO-TRL-012",
        BodyType.REEFER,
        model_code=ModelCode.FD,
        partition=True,
        internal_length_m="13.10",
        internal_width_m="2.46",
        internal_height_m="2.50",
        door_height_m="2.45",
        ldm="13.10",
        pallet_places=32,
        kerb_weight_kg=8700,
        external_width_m="2.60",
    ),
    # Thermo Side: side doors, one reefer unit, one zone.
    _semi(
        "DEMO-TRL-013",
        BodyType.REEFER,
        model_code=ModelCode.FS,
        side_doors=True,
        internal_length_m="13.10",
        internal_width_m="2.46",
        internal_height_m="2.50",
        door_height_m="2.45",
        ldm="13.10",
        pallet_places=32,
        kerb_weight_kg=8800,
        external_width_m="2.60",
    ),
    _fixed_body(
        "DEMO-BOD-001",
        "DEMO-TRK-006",
        BodyType.BOX,
        ("6.20", "2.45", "2.40"),
        "2.30",
        14,
        external_height_m="3.60",
        external_width_m="2.55",
        tail_lift=True,
    ),
    _fixed_body(
        "DEMO-BOD-002",
        "DEMO-TRK-007",
        BodyType.REEFER,
        ("6.00", "2.40", "2.20"),
        "2.10",
        12,
        model_code=ModelCode.FB,
        external_height_m="3.50",
        external_width_m="2.55",
    ),
    # Body of the combination truck: curtainsider, side loading.
    _fixed_body(
        "DEMO-BOD-003",
        "DEMO-TRK-011",
        BodyType.CURTAINSIDER,
        ("7.40", "2.48", "2.75"),
        "2.65",
        18,
        model_code=ModelCode.CS,
        external_height_m="3.95",
        external_width_m="2.55",
    ),
)

# registration -> compartments: (number, temperature_min, temperature_max, pallet_places,
# independently_controlled, position of the serving reefer unit or None). The temperatures are the
# range each compartment can hold. With a partition the places follow an allowed partition
# position (partition_positions).
_Comp = tuple[int, str, str, int | None, bool, ReeferPosition | None]
COMPARTMENTS: dict[str, tuple[_Comp, ...]] = {
    # FD with two zones behind a partition (12 + 20 places), one machine each
    "DEMO-TRL-007": (
        (1, "-25.0", "-18.0", 12, True, ReeferPosition.FRONT),
        (2, "2.0", "8.0", 20, True, ReeferPosition.REAR),
    ),
    # FD, both zones with the full range, partition in the middle (16 + 16 places)
    "DEMO-TRL-012": (
        (1, "-25.0", "8.0", 16, True, ReeferPosition.FRONT),
        (2, "-25.0", "8.0", 16, True, ReeferPosition.REAR),
    ),
    "DEMO-TRL-013": ((1, "-25.0", "8.0", None, False, ReeferPosition.FRONT),),
    "DEMO-BOD-002": ((1, "-25.0", "8.0", None, False, ReeferPosition.FRONT),),
}
# registration -> reefer units: (position, unit name, power source); invented make and model.
# TRL-007's rear unit is a hybrid: it can run on electricity in a port (D27).
REEFER_UNITS: dict[str, tuple[tuple[ReeferPosition, str, PowerSource], ...]] = {
    "DEMO-TRL-007": (
        (ReeferPosition.FRONT, "Demo Chill Duo 300 F", PowerSource.DIESEL),
        (ReeferPosition.REAR, "Demo Chill Duo 300 R", PowerSource.HYBRID),
    ),
    "DEMO-TRL-012": (
        (ReeferPosition.FRONT, "Demo Chill Duo 200 F", PowerSource.DIESEL),
        (ReeferPosition.REAR, "Demo Chill Duo 200 R", PowerSource.DIESEL),
    ),
    "DEMO-TRL-013": ((ReeferPosition.FRONT, "Demo Chill Side 150", PowerSource.DIESEL),),
    "DEMO-BOD-002": ((ReeferPosition.FRONT, "Demo Chill Mono 100", PowerSource.ELECTRIC),),
}

_ET = EquipmentQualificationType
# subject kind, registration, type, class code, days from the first-run day to valid_from and
# valid_until. Inspections are generated below for every truck, dolly and trailer.
_EquipSpec = tuple[str, str, EquipmentQualificationType, str | None, int, int]
_THREE_YEARS = 3 * 365
EQUIPMENT_QUALIFICATIONS: tuple[_EquipSpec, ...] = (
    # ATP of the thermo trailer: first period ended 61 days ago and was renewed the next day.
    ("load_unit", "DEMO-TRL-007", _ET.ATP, "FRC", -61 - _THREE_YEARS + 1, -61),
    ("load_unit", "DEMO-TRL-007", _ET.ATP, "FRC", -60, -60 + _THREE_YEARS - 1),
    # ATP of the thermo body: expires in 25 days.
    ("load_unit", "DEMO-BOD-002", _ET.ATP, "FRC", 25 - _THREE_YEARS + 1, 25),
    ("load_unit", "DEMO-TRL-012", _ET.ATP, "FRC", -400, -400 + _THREE_YEARS - 1),
    ("load_unit", "DEMO-TRL-013", _ET.ATP, "FRC", -300, -300 + _THREE_YEARS - 1),
    # Reefer unit service (D76), per machine; "reefer_unit" subjects are named "<unit>:<position>".
    ("reefer_unit", "DEMO-TRL-007:front", _ET.REEFER_SERVICE, None, -165, 200),
    ("reefer_unit", "DEMO-TRL-007:rear", _ET.REEFER_SERVICE, None, -345, 20),  # expiring soon
    ("reefer_unit", "DEMO-TRL-012:front", _ET.REEFER_SERVICE, None, -245, 120),
    ("reefer_unit", "DEMO-TRL-012:rear", _ET.REEFER_SERVICE, None, -105, 260),
    ("reefer_unit", "DEMO-TRL-013:front", _ET.REEFER_SERVICE, None, -275, 90),
    ("reefer_unit", "DEMO-BOD-002:front", _ET.REEFER_SERVICE, None, -215, 150),
    ("load_unit", "DEMO-TRL-007", _ET.GDP_TEMPERATURE_MAPPING, None, -64, 300),
    ("load_unit", "DEMO-BOD-001", _ET.TAIL_LIFT_INSPECTION, None, -214, 150),
)
EXPIRED_INSPECTION = "DEMO-TRL-001"  # inspection ended 12 days ago and is not renewed


def _inspection_specs() -> tuple[_EquipSpec, ...]:
    """One-year inspections with staggered end dates; one of them already expired."""
    specs: list[_EquipSpec] = []
    registrations = (
        [("truck", t.registration) for t in TRUCKS]
        + [("dolly", d[0]) for d in DOLLIES]
        + [("load_unit", u.registration) for u in LOAD_UNITS if u.type is LoadUnitType.TRAILER]
    )
    for index, (kind, registration) in enumerate(registrations):
        until = -12 if registration == EXPIRED_INSPECTION else 90 + (index * 41) % 270
        specs.append((kind, registration, _ET.INSPECTION, None, until - 364, until))
    return tuple(specs)


def _seed_fleet(
    session: Session,
    carriers: dict[str, Carrier],
    locations: dict[str, Location],
    today: date,
    created: Counter[str],
) -> None:
    trucks: dict[str, Truck] = {}
    for spec in TRUCKS:
        length = Decimal(spec.length_m)
        validate_vehicle(
            length_m=length,
            kerb_weight_kg=spec.kerb_weight_kg,
            max_gross_weight_kg=spec.max_gross_weight_kg,
            axles=spec.axles,
        )
        fifth_wheel = (
            Decimal(spec.fifth_wheel_from_front_m) if spec.fifth_wheel_from_front_m else None
        )
        validate_truck(
            truck_type=spec.type,
            length_m=length,
            fifth_wheel_from_front_m=fifth_wheel,
            low_fifth_wheel=spec.low_fifth_wheel,
            drawbar_hitch=spec.drawbar_hitch,
            max_gross_weight_kg=spec.max_gross_weight_kg,
            max_combination_weight_kg=spec.max_combination_weight_kg,
        )
        truck = session.scalar(select(Truck).where(Truck.registration == spec.registration))
        if truck is None:
            truck = Truck(
                carrier_id=carriers[spec.carrier].id,
                registration=spec.registration,
                type=spec.type.value,
                length_m=length,
                kerb_weight_kg=spec.kerb_weight_kg,
                max_gross_weight_kg=spec.max_gross_weight_kg,
                axles=spec.axles,
                fifth_wheel_from_front_m=fifth_wheel,
                low_fifth_wheel=spec.low_fifth_wheel,
                drawbar_hitch=spec.drawbar_hitch,
                max_combination_weight_kg=spec.max_combination_weight_kg,
                home_location_id=locations[spec.home].id if spec.home else None,
            )
            session.add(truck)
            created["trucks"] += 1
        trucks[spec.registration] = truck
    session.flush()

    dollies: dict[str, Dolly] = {}
    for registration, carrier, length_m, kerb, gross, axles in DOLLIES:
        validate_vehicle(
            length_m=Decimal(length_m), kerb_weight_kg=kerb, max_gross_weight_kg=gross, axles=axles
        )
        dolly = session.scalar(select(Dolly).where(Dolly.registration == registration))
        if dolly is None:
            dolly = Dolly(
                carrier_id=carriers[carrier].id,
                registration=registration,
                length_m=Decimal(length_m),
                kerb_weight_kg=kerb,
                max_gross_weight_kg=gross,
                axles=axles,
            )
            session.add(dolly)
            created["dollies"] += 1
        dollies[registration] = dolly
    session.flush()

    load_units: dict[str, LoadUnit] = {}
    for u in LOAD_UNITS:
        host = trucks[u.truck] if u.truck else None
        ext = Decimal(u.external_length_m) if u.external_length_m else None
        lease_from = (
            today + timedelta(days=u.lease_from_days) if u.lease_from_days is not None else None
        )
        lease_until = (
            today + timedelta(days=u.lease_until_days) if u.lease_until_days is not None else None
        )
        kingpin = Decimal(u.kingpin_from_front_m) if u.kingpin_from_front_m else None
        validate_load_unit(
            unit_type=u.type,
            truck_id=host.id if host else None,
            external_length_m=ext,
            kerb_weight_kg=u.kerb_weight_kg,
            max_gross_weight_kg=u.max_gross_weight_kg,
            axles=u.axles,
            ownership=u.ownership,
            lease_valid_from=lease_from,
            lease_valid_until=lease_until,
            coupling_type=u.coupling,
            kingpin_from_front_m=kingpin,
            tail_lift=u.tail_lift,
            rail_craneable=u.rail_craneable,
        )
        validate_model_code(u.model_code, u.body_type, u.side_doors)
        validate_partition(PartitionSpec(Decimal(u.internal_length_m), partition=u.partition))
        validate_partition_allowed(u.model_code, u.partition)
        if host is not None:
            validate_fixed_body_host(
                truck_type=TruckType(host.type),
                truck_carrier_id=host.carrier_id,
                load_unit_carrier_id=carriers[u.carrier].id,
            )
        unit = session.scalar(select(LoadUnit).where(LoadUnit.registration == u.registration))
        if unit is None:
            unit = LoadUnit(
                type=u.type.value,
                truck_id=host.id if host else None,
                carrier_id=carriers[u.carrier].id,
                registration=u.registration,
                body_type=u.body_type.value,
                coupling_type=u.coupling.value if u.coupling else None,
                model_code=u.model_code.value if u.model_code else None,
                internal_length_m=Decimal(u.internal_length_m),
                internal_width_m=Decimal(u.internal_width_m),
                internal_height_m=Decimal(u.internal_height_m),
                door_height_m=Decimal(u.door_height_m) if u.door_height_m else None,
                external_length_m=ext,
                kingpin_from_front_m=kingpin,
                external_height_m=(Decimal(u.external_height_m) if u.external_height_m else None),
                external_width_m=Decimal(u.external_width_m) if u.external_width_m else None,
                ldm=Decimal(u.ldm),
                pallet_places=u.pallet_places,
                kerb_weight_kg=u.kerb_weight_kg,
                max_gross_weight_kg=u.max_gross_weight_kg,
                axles=u.axles,
                xl_certified=u.xl_certified,
                coil_well=u.coil_well,
                tir_cable=u.tir_cable,
                top_loading=u.top_loading,
                tail_lift=u.tail_lift,
                side_doors=u.side_doors,
                partition=u.partition,
                rail_craneable=u.rail_craneable,
                ownership=u.ownership.value,
                lease_valid_from=lease_from,
                lease_valid_until=lease_until,
            )
            session.add(unit)
            created["load_units"] += 1
        load_units[u.registration] = unit
    session.flush()

    unit_specs = {u.registration: u for u in LOAD_UNITS}
    body_types = {u.registration: u.body_type for u in LOAD_UNITS}

    # Reefer units (D76) before the compartments that name them.
    reefer_units: dict[str, ReeferUnit] = {}  # key "<registration>:<position>"
    for registration, machines in REEFER_UNITS.items():
        unit = load_units[registration]
        validate_reefer_units(
            body_types[registration],
            [m[0] for m in machines],
            unit_specs[registration].model_code,
        )
        for position, unit_name, power in machines:
            machine = session.scalar(
                select(ReeferUnit).where(
                    ReeferUnit.load_unit_id == unit.id, ReeferUnit.position == position.value
                )
            )
            if machine is None:
                machine = ReeferUnit(
                    load_unit_id=unit.id,
                    position=position.value,
                    unit_name=unit_name,
                    power_source=power.value,
                )
                session.add(machine)
                created["reefer_units"] += 1
            reefer_units[f"{registration}:{position.value}"] = machine
    session.flush()

    for registration, rows in COMPARTMENTS.items():
        comp_unit = unit_specs[registration]
        validate_compartment_set(comp_unit.body_type, [row[0] for row in rows])
        validate_compartment_pallet_places(comp_unit.pallet_places, [row[3] for row in rows])
        validate_zones(len(rows), [row[4] for row in rows], comp_unit.model_code)
        for number, t_min, t_max, places, independent, serving in rows:
            validate_compartment(number, Decimal(t_min), Decimal(t_max))
            unit = load_units[registration]
            serving_unit = reefer_units[f"{registration}:{serving.value}"] if serving else None
            if (
                session.scalar(
                    select(Compartment.id).where(
                        Compartment.load_unit_id == unit.id, Compartment.number == number
                    )
                )
                is None
            ):
                session.add(
                    Compartment(
                        load_unit_id=unit.id,
                        reefer_unit_id=serving_unit.id if serving_unit else None,
                        number=number,
                        temperature_min=Decimal(t_min),
                        temperature_max=Decimal(t_max),
                        pallet_places=places,
                        independently_controlled=independent,
                    )
                )
                created["compartments"] += 1
    session.flush()

    subjects: dict[str, dict[str, Truck | Dolly | LoadUnit | ReeferUnit]] = {
        "truck": dict(trucks),
        "dolly": dict(dollies),
        "load_unit": dict(load_units),
        "reefer_unit": dict(reefer_units),
    }
    seen: Counter[tuple[str, EquipmentQualificationType]] = Counter()
    for kind, registration, qtype, class_code, from_days, until_days in (
        *EQUIPMENT_QUALIFICATIONS,
        *_inspection_specs(),
    ):
        subject = subjects[kind][registration]
        ids = {f"{kind}_id": subject.id}
        unit_spec = unit_specs.get(registration) if kind == "load_unit" else None
        validate_equipment_qualification(
            EquipmentSubject(
                kind=kind,  # type: ignore[arg-type]
                body_type=unit_spec.body_type if unit_spec else None,
                tail_lift=unit_spec.tail_lift if unit_spec else False,
            ),
            qtype,
        )
        validate_equipment_subject(
            truck_id=ids.get("truck_id"),
            dolly_id=ids.get("dolly_id"),
            load_unit_id=ids.get("load_unit_id"),
            reefer_unit_id=ids.get("reefer_unit_id"),
            qtype=qtype,
        )
        seen[(registration, qtype)] += 1
        ref = f"DEMO-{qtype.value.upper()}-{registration[5:]}-{seen[(registration, qtype)]}"
        subject_column = getattr(EquipmentQualification, f"{kind}_id")
        if (
            session.scalar(
                select(EquipmentQualification.id).where(
                    subject_column == subject.id,
                    EquipmentQualification.type == qtype.value,
                    EquipmentQualification.document_ref == ref,
                )
            )
            is None
        ):
            session.add(
                EquipmentQualification(
                    **ids,
                    type=qtype.value,
                    class_code=class_code,
                    valid_from=today + timedelta(days=from_days),
                    valid_until=today + timedelta(days=until_days),
                    document_ref=ref,
                )
            )
            created["equipment_qualifications"] += 1


def _document_ref(qtype: Q, driver_name: str, nth: int) -> str:
    """Natural key of a seeded period within a driver: type, surname and the period's number."""
    return f"DEMO-{qtype.value.upper()}-{driver_name.rsplit(' ', 1)[-1].upper()}-{nth}"


def seed_demo_data(
    session: Session, today: date | None = None, gdp_validity_months: int | None = None
) -> Counter[str]:
    """Create the missing demo rows. Returns the number of rows created per table.

    `gdp_validity_months` defaults to the setting GDP_TRAINING_DEFAULT_VALIDITY_MONTHS.
    """
    today = today or date.today()
    if gdp_validity_months is None:
        gdp_validity_months = get_settings().gdp_training_default_validity_months
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
    for number, place in enumerate(PLACES, start=1):
        location = session.scalar(select(Location).where(Location.name == place.name))
        if location is None:
            temp_min = Decimal(place.temp_min) if place.temp_min is not None else None
            temp_max = Decimal(place.temp_max) if place.temp_max is not None else None
            validate_timezone(place.timezone)
            if place.postal_code is not None:
                validate_postal_code(place.country, place.postal_code)
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
                address=f"Demo Street {number}",
                postal_code=place.postal_code,
                city=place.city,
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

    # --- carriers (the own carrier links to the own company's customer row, D73)
    carriers: dict[str, Carrier] = {}
    for name, carrier_type, country, business_id, licence_years, insurance_years in CARRIERS:
        is_own = carrier_type is CarrierType.OWN
        carrier_row = None
        if is_own:
            carrier_row = session.scalar(select(Carrier).where(Carrier.type == carrier_type.value))
        else:
            carrier_row = session.scalar(select(Carrier).where(Carrier.name == name))
        if carrier_row is None:
            own_customer = customers[OWN_COMPANY] if is_own else None
            validate_carrier_customer_link(
                carrier_type, CustomerType(own_customer.type) if own_customer else None
            )
            carrier_row = Carrier(
                customer_id=own_customer.id if own_customer else None,
                name=None if is_own else name,
                type=carrier_type.value,
                country=None if is_own else country,
                business_id=None if is_own else business_id,
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
        seen: Counter[Q] = Counter()
        for qtype, days, years in quals:
            seen[qtype] += 1
            ref = _document_ref(qtype, name, seen[qtype])
            exists = session.scalar(
                select(DriverQualification.id).where(
                    DriverQualification.driver_id == driver.id,
                    DriverQualification.type == qtype.value,
                    DriverQualification.document_ref == ref,
                )
            )
            if exists is None:
                if qtype is Q.GDP:
                    valid_from = today + timedelta(days=days)
                    valid_until = suggest_gdp_valid_until(valid_from, gdp_validity_months)
                else:
                    valid_until = today + timedelta(days=days)
                    valid_from = valid_until - timedelta(days=365 * years - 1)
                session.add(
                    DriverQualification(
                        driver_id=driver.id,
                        type=qtype.value,
                        valid_from=valid_from,
                        valid_until=valid_until,
                        document_ref=ref,
                    )
                )
                created["driver_qualifications"] += 1
    session.flush()

    _seed_fleet(session, carriers, locations, today, created)
    session.commit()
    return created


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo data unless ENVIRONMENT=development.", file=sys.stderr)
        return 2
    with sessionmaker(bind=get_engine())() as session:
        created = seed_demo_data(session)
    for table in (
        "customers",
        "locations",
        "carriers",
        "drivers",
        "driver_qualifications",
        "trucks",
        "dollies",
        "load_units",
        "compartments",
        "reefer_units",
        "equipment_qualifications",
    ):
        print(f"{table}: {created[table]} created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
