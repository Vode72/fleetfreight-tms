"""Create fictional demo master data (2B-1, 2B-2). Not part of any migration.

Usage (from the backend directory):
    ENVIRONMENT=development uv run python -m scripts.seed_demo_data

Contents: the own company, the terminal network (D31-D33), ports, rail terminals, customs
offices, secure truck parking areas with certificates and border crossings with their status
history (2B-3b, D92), trailer storage terms of ports and rail terminals and wash places (D93),
ferry and rail lines with vessels, weekly schedules and departures for eight weeks (2B-3c, D94),
demo customers with sites, carriers, drivers and driver qualifications,
and the fleet (2B-2): tractors and rigid trucks, a dolly, trailers and fixed bodies with temperature
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
Parking and border crossings (D92): parking areas have invented names, prices and certificates
(Lübeck shows both schemes, Gdańsk an expired TAPA certificate and its renewal). Border crossings
carry public place names; their status periods come from official sources (Vaalimaa: closed,
reopened for one day and closed again in 2023; Svinesund: open on the check day). The typical
wait setting is left empty; Svinesund has invented wait observations instead, each marked
"Invented demo value, not a measurement." (D95 refines D92).
Cargo crime risk (D95): TAPA EMEA monthly counts as published by trans.info (named countries
only), Benelux hotspot roads from TT Club, Lyon area and AP-7 as marked demo estimates.
Lines (D62, D63, D94): demo operators and vessels on the public routes; each direction is its own
route. Timetables follow public frequencies; Vuosaari-Travemünde, Vuosaari-Tallinn and
Naantali-Långnäs-Kapellskär are modelled on published timetables, the freight-only and rail
timetables are invented. None is an official timetable (every schedule's note says so).
Refuses to run unless ENVIRONMENT=development.
"""

import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from db.models import (
    BorderCrossingDetails,
    BorderCrossingStatusPeriod,
    BorderWaitObservation,
    CargoCrimeCount,
    CargoCrimeReport,
    Carrier,
    Compartment,
    Customer,
    Dolly,
    Driver,
    DriverQualification,
    EquipmentQualification,
    LineDeparture,
    LineDepartureCall,
    LineOperator,
    LineRoute,
    LineRouteStop,
    LineSchedule,
    LineScheduleCall,
    LoadUnit,
    Location,
    ParkingCertification,
    ParkingDetails,
    ReeferEvaporator,
    ReeferUnit,
    RiskArea,
    TrailerStorageRule,
    Truck,
    Vessel,
    VesselAdrClass,
    WashDetails,
)
from db.session import get_engine
from domain.equipment import (
    BodyType,
    CouplingType,
    EquipmentQualificationType,
    EquipmentSubject,
    EvaporatorPosition,
    LoadUnitType,
    ModelCode,
    Ownership,
    PartitionSpec,
    PowerSource,
    TruckType,
    validate_compartment,
    validate_compartment_pallet_places,
    validate_compartment_set,
    validate_equipment_qualification,
    validate_equipment_subject,
    validate_evaporators,
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
from domain.lines import (
    AdrAcceptance,
    Call,
    LineMode,
    Stop,
    VesselType,
    departures_to_add,
    plan_departure,
    service_dates,
    validate_calls,
    validate_route,
    validate_schedule_periods,
    validate_stops,
    validate_vessel,
)
from domain.locations import (
    BorderCrossingStatus,
    LocationType,
    ParkingCertificationLevel,
    ParkingCertificationScheme,
    ParkingService,
    WashGrade,
    WashScope,
    validate_border_crossing,
    validate_customs_office_pair,
    validate_opening_hours,
    validate_parking_certification,
    validate_parking_details,
    validate_postal_code,
    validate_site_features,
    validate_status_periods,
    validate_terminal_fields,
    validate_timezone,
    validate_trailer_storage_rule,
    validate_wash_details,
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
from domain.risks import (
    DEMO_WAIT_NOTE,
    RiskSourceType,
    WaitDirection,
    WaitSourceType,
    validate_incident_count,
    validate_report_month,
    validate_risk_area,
    validate_wait_observation,
)

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
    forklift_available: bool | None = None
    tail_lift_required: bool | None = None


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


def _wash(name: str, lat: str, lon: str) -> _Place:
    return _Place(
        f"Demo {name}", LocationType.WASH, "FI", lat, lon, "Europe/Helsinki", hours=HOURS_INDUSTRY
    )


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


def _parking(city: str, country: str, lat: str, lon: str, tz: str, **kw: object) -> _Place:
    return _Place(f"Demo Truck Parking {city}", LocationType.PARKING, country, lat, lon, tz, **kw)  # type: ignore[arg-type]


def _border(name: str, country: str, lat: str, lon: str, tz: str) -> _Place:
    # Public place name (rule 5); open around the clock unless a status period says otherwise.
    return _Place(
        f"Demo Border Crossing {name}",
        LocationType.BORDER_CROSSING,
        country,
        lat,
        lon,
        tz,
        hours=HOURS_24_7,
    )


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
        # Border crossing, Swedish side; open 24/7 like the real clearance office (Tullverket,
        # Svinesund Customs Clearance Office, checked 22.11.2026).
        "Demo Customs Office Svinesund SE",
        "SE",
        "59.080000",
        "11.260000",
        "Europe/Stockholm",
        HOURS_24_7,
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
    # Secure truck parking (D92): invented points near the ports and on main routes.
    _parking(
        "Lübeck",
        "DE",
        "53.920000",
        "10.800000",
        "Europe/Berlin",
        hours=HOURS_24_7,
        booking_required=False,
    ),
    _parking("Rostock", "DE", "54.120000", "12.150000", "Europe/Berlin", hours=HOURS_24_7),
    _parking("Gdańsk", "PL", "54.340000", "18.600000", "Europe/Warsaw", hours=HOURS_24_7),
    _parking(
        "Jönköping",
        "SE",
        "57.760000",
        "14.180000",
        "Europe/Stockholm",
        hours=HOURS_24_7,
        booking_required=True,
    ),
    # Border crossings (D92): general points at the public crossings.
    _border("Tornio\u2013Haaparanta", "FI", "65.844000", "24.150000", "Europe/Helsinki"),
    _border("Vaalimaa", "FI", "60.580000", "27.830000", "Europe/Helsinki"),
    _border("Svinesund", "SE", "59.090000", "11.270000", "Europe/Stockholm"),
    # Wash places (D56, D93): invented points.
    _wash("Truck Wash Tampere", "61.470000", "23.850000"),
    _wash("Tank Cleaning Kotka", "60.500000", "26.900000"),
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
    "Demo Customs Office Svinesund SE": (None, "Strömstad"),
    "Demo Customs Office Oslo": (None, "Oslo"),
    "Demo Truck Parking Lübeck": (None, "Lübeck"),
    "Demo Truck Parking Rostock": (None, "Rostock"),
    "Demo Truck Parking Gdańsk": (None, "Gdańsk"),
    "Demo Truck Parking Jönköping": (None, "Jönköping"),
    "Demo Border Crossing Tornio\u2013Haaparanta": ("95400", "Tornio"),
    "Demo Border Crossing Vaalimaa": ("49930", "Virolahti"),
    "Demo Border Crossing Svinesund": (None, "Strömstad"),
    "Demo Truck Wash Tampere": ("33100", "Tampere"),
    "Demo Tank Cleaning Kotka": ("48100", "Kotka"),
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
# Customer site features (D93): forklift on site, unloading needs a tail lift; others unknown.
SITE_FEATURES: dict[str, tuple[bool | None, bool | None]] = {
    "Demo Paper Mill Site": (True, False),
    "Demo Timber Yard Site": (True, False),
    "Demo Kemia Plant Site": (True, False),
    "Demo Dairy Plant Site": (True, False),
    # Small shop without a loading dock: no forklift, unloading with a tail lift. Intended Plan
    # Check scenario: the only tail lift body is based at the Central terminal, so the delivery
    # goes through a terminal (D25).
    "Demo Kauppa Oy \u2013 Kuopio Shop Site": (False, True),
    "Demo Kauppa Oy \u2013 Turku Shop Site": (False, None),
}
PLACES: tuple[_Place, ...] = tuple(
    replace(
        p,
        postal_code=_LOCALITY[p.name][0],
        city=_LOCALITY[p.name][1],
        forklift_available=SITE_FEATURES.get(p.name, (None, None))[0],
        tail_lift_required=SITE_FEATURES.get(p.name, (None, None))[1],
    )
    for p in _PLACES_WITHOUT_LOCALITY
)

_S = ParkingService


@dataclass(frozen=True)
class _ParkingSpec:
    spaces: int | None
    night_price_cents: int | None
    price_currency: str | None
    reefer_plugs: int | None
    booking_possible: bool
    adr_allowed: bool | None
    services: tuple[ParkingService, ...]
    trailer_drop: bool | None = None


# Invented parking details (prices are demo values, D28 cents in the local currency).
PARKING: dict[str, _ParkingSpec] = {
    "Demo Truck Parking Lübeck": _ParkingSpec(
        120,
        2500,
        "EUR",
        20,
        True,
        False,
        (_S.SHOWER, _S.TOILET, _S.RESTAURANT, _S.SECURITY_STAFF),
        trailer_drop=True,
    ),
    "Demo Truck Parking Rostock": _ParkingSpec(
        40, None, None, None, False, None, (_S.TOILET,), trailer_drop=True
    ),
    "Demo Truck Parking Gdańsk": _ParkingSpec(
        80, 6000, "PLN", 8, True, True, (_S.SHOWER, _S.TOILET, _S.FUEL, _S.SECURITY_STAFF)
    ),
    "Demo Truck Parking Jönköping": _ParkingSpec(
        60,
        25000,
        "SEK",
        12,
        True,
        False,
        (_S.SHOWER, _S.TOILET, _S.RESTAURANT, _S.ACCOMMODATION, _S.SECURITY_STAFF),
    ),
}
_CS = ParkingCertificationScheme
_CL = ParkingCertificationLevel
# Invented certificates: parking, scheme, level, start and end in days from the seed day,
# document reference. Lübeck holds both schemes; Gdańsk shows an expired period and its renewal.
PARKING_CERTIFICATIONS: tuple[
    tuple[str, ParkingCertificationScheme, ParkingCertificationLevel, int, int, str], ...
] = (
    ("Demo Truck Parking Lübeck", _CS.EU_SSPA, _CL.GOLD, -200, 900, "DEMO-SSPA-001"),
    ("Demo Truck Parking Lübeck", _CS.TAPA_PSR, _CL.LEVEL_2, -400, 700, "DEMO-PSR-001"),
    ("Demo Truck Parking Gdańsk", _CS.TAPA_PSR, _CL.LEVEL_3, -1200, -105, "DEMO-PSR-002"),
    ("Demo Truck Parking Gdańsk", _CS.TAPA_PSR, _CL.LEVEL_3, -100, 995, "DEMO-PSR-003"),
    ("Demo Truck Parking Jönköping", _CS.EU_SSPA, _CL.BRONZE, -30, 1065, "DEMO-SSPA-002"),
)


@dataclass(frozen=True)
class _BorderSpec:
    other_country: str
    customs_office: str | None
    other_customs_office: str | None
    note: str | None


BORDER_CROSSINGS: dict[str, _BorderSpec] = {
    "Demo Border Crossing Tornio\u2013Haaparanta": _BorderSpec(
        "SE", None, None, "Internal EU border; no customs formalities."
    ),
    "Demo Border Crossing Vaalimaa": _BorderSpec(
        "RU", None, None, "No customs offices recorded while the crossing is closed."
    ),
    "Demo Border Crossing Svinesund": _BorderSpec(
        "NO",
        "Demo Customs Office Svinesund SE",
        "Demo Customs Office Svinesund",
        "Exports from Norway by road are declared on the Swedish side.",
    ),
}

_HEL = ZoneInfo("Europe/Helsinki")
_STO = ZoneInfo("Europe/Stockholm")
_TULLI_CLOSED = "https://tulli.fi/en/-/border-crossing-points-on-the-eastern-border-remain-closed"
_TULLI_OPEN = (
    "https://tulli.fi/en/-/the-temporary-traffic-restrictions-at-the-eastern-border-to-continue"
    "-vaalimaa-and-niirala-will-open-on-14-december-2023"
)
_TULLI_REOPEN_CLOSED = (
    "https://tulli.fi/en/-/all-border-crossing-points-for-road-traffic-at-the-eastern-border"
    "-closed-again-as-of-20.00-on-15-december"
)
_VN_STILL_CLOSED = (
    "https://valtioneuvosto.fi/en/-/1410869/finland-s-eastern-border-to-remain-closed-until"
    "-further-notice-2"
)
_TOLL_SVINESUND = (
    "https://toll.no/en/about-norwegian-customs/contact-us/all-customs-offices/"
    "svinesund-customs-office-e6"
)
_CHECKED = date(2026, 11, 22)
_NO_TIME = "The source gives the day only; the period starts at 00:00 local time."
# Official status history: crossing, status, starts_at, ends_at, note, source.
BORDER_STATUS: tuple[
    tuple[str, BorderCrossingStatus, datetime, datetime | None, str | None, str], ...
] = (
    (
        "Demo Border Crossing Vaalimaa",
        BorderCrossingStatus.CLOSED,
        datetime(2023, 11, 18, tzinfo=_HEL),
        datetime(2023, 12, 14, tzinfo=_HEL),
        f"Government decision 16.11.2023. {_NO_TIME}",
        _TULLI_CLOSED,
    ),
    (
        "Demo Border Crossing Vaalimaa",
        BorderCrossingStatus.OPEN,
        datetime(2023, 12, 14, tzinfo=_HEL),
        datetime(2023, 12, 15, 20, 0, tzinfo=_HEL),
        f"Government decision 12.12.2023. {_NO_TIME}",
        _TULLI_OPEN,
    ),
    (
        "Demo Border Crossing Vaalimaa",
        BorderCrossingStatus.CLOSED,
        datetime(2023, 12, 15, 20, 0, tzinfo=_HEL),
        None,
        "Closed again from 20.00; still closed until further notice by the Government decision"
        f" of 4.6.2026 ({_VN_STILL_CLOSED}).",
        _TULLI_REOPEN_CLOSED,
    ),
    (
        "Demo Border Crossing Svinesund",
        BorderCrossingStatus.OPEN,
        datetime(2026, 11, 22, tzinfo=_STO),
        None,
        "Open on the check day: Norwegian Customs keeps the crossing open 24/7 for cross-border"
        " road traffic. Earlier history not recorded.",
        _TOLL_SVINESUND,
    ),
)


# Trailer storage terms (D83, D93): invented demo fees from 1.1.2026, not any port's tariff (every
# row's note says so). Free days 3 unless noted.
# place, free days, daily fee cents, currency, reefer plugs, reefer plug fee cents per day, note
STORAGE_FROM = date(2026, 1, 1)
_DEMO_TARIFF = "Demo value, not a tariff."
STORAGE_RULES: tuple[tuple[str, int, int, str, bool, int | None, str | None], ...] = (
    ("Demo Port Vuosaari", 3, 3500, "EUR", True, 2500, None),
    ("Demo Port Kotka", 3, 3000, "EUR", True, 2500, None),
    ("Demo Port Hanko", 3, 3000, "EUR", True, 2500, None),
    ("Demo Port Oulu", 3, 2500, "EUR", False, None, None),
    ("Demo Port Naantali", 3, 3000, "EUR", True, 2500, None),
    ("Demo Port Långnäs", 2, 2000, "EUR", False, None, "Small port: two free days."),
    ("Demo Port Kapellskär", 3, 35000, "SEK", True, 25000, None),
    ("Demo Port Travemünde", 3, 4000, "EUR", True, 3000, None),
    ("Demo Port Lübeck", 3, 3500, "EUR", True, 3000, "Applies to the quays without a rule."),
    # the quay's own terms override the port area's (D93)
    ("Demo Port Lübeck \u2013 Lehmannkai", 2, 4500, "EUR", True, 3000, "Quay's own terms."),
    ("Demo Port Rostock", 3, 3500, "EUR", True, 3000, None),
    ("Demo Port Gdynia", 3, 15000, "PLN", True, 12000, None),
    ("Demo Port Tallinn", 3, 3000, "EUR", True, 2500, None),
    ("Demo Port Antwerpen", 3, 5000, "EUR", True, 3500, None),
    ("Demo Rail Terminal Rostock", 3, 3000, "EUR", True, 3000, None),
    ("Demo Rail Terminal Travemünde", 3, 3000, "EUR", True, 3000, None),
    ("Demo Rail Terminal Verona", 2, 4000, "EUR", True, 3500, None),
)
_SC, _GR = WashScope, WashGrade
# Wash places: scopes, grades, cleaning document, ECD (tank and bulk).
WASHES: dict[str, tuple[tuple[WashScope, ...], tuple[WashGrade, ...], bool, bool]] = {
    "Demo Truck Wash Tampere": (
        (_SC.INTERIOR, _SC.EXTERIOR),
        (_GR.GENERAL, _GR.FOOD_GRADE),
        True,
        False,
    ),
    "Demo Tank Cleaning Kotka": ((_SC.INTERIOR,), (_GR.CHEMICAL, _GR.TANK), True, True),
}


# --- Lines (D62, D63, D94) ----------------------------------------------------------------------

DEPARTURE_WEEKS = 8
_TIMETABLE_NOTE = (
    "Demo timetable based on public route frequencies (D62); not an official timetable."
)
_PUBLISHED_NOTE = "Demo timetable modelled on a published timetable; not an official timetable."

# operator name, mode
LINE_OPERATORS: tuple[tuple[str, LineMode], ...] = (
    ("Demo Baltic Line", LineMode.FERRY),
    ("Demo Gulf Ferries", LineMode.FERRY),
    ("Demo Shortsea", LineMode.FERRY),
    ("Demo Polska Line", LineMode.FERRY),
    ("Demo Rail", LineMode.RAIL),
)


@dataclass(frozen=True)
class _VesselSpec:
    operator: str
    type: VesselType
    lane_metres: int
    deck_height_mm: int | None
    reefer_plugs: int
    accompanied: bool
    unaccompanied: bool
    cabins: bool
    adr: tuple[tuple[str, AdrAcceptance, str | None], ...]


_RP, _RR = VesselType.ROPAX, VesselType.RORO
_ALLOW, _FORBID, _PRE = AdrAcceptance.ALLOWED, AdrAcceptance.FORBIDDEN, AdrAcceptance.PRE_APPROVAL
# Invented vessels; ro-pax ships refuse class 1 and need approval for class 7, ro-ro ships take
# more classes (demo values, not any real ship's rules).
_ROPAX_ADR = (
    ("1", _FORBID, None),
    ("2", _ALLOW, "Open deck only."),
    ("3", _ALLOW, None),
    ("7", _PRE, None),
    ("8", _ALLOW, None),
    ("9", _ALLOW, None),
)
_RORO_ADR = (
    ("1", _PRE, None),
    ("2", _ALLOW, None),
    ("3", _ALLOW, None),
    ("6.1", _ALLOW, None),
    ("7", _PRE, None),
    ("8", _ALLOW, None),
    ("9", _ALLOW, None),
)
VESSELS: dict[str, _VesselSpec] = {
    "Demo Star": _VesselSpec(
        "Demo Baltic Line", _RP, 4200, 4800, 120, True, True, True, _ROPAX_ADR
    ),
    "Demo Comet": _VesselSpec(
        "Demo Baltic Line", _RP, 4200, 4800, 120, True, True, True, _ROPAX_ADR
    ),
    "Demo Aurora": _VesselSpec(
        "Demo Baltic Line", _RP, 2800, 4600, 60, True, True, True, _ROPAX_ADR
    ),
    "Demo Borealis": _VesselSpec(
        "Demo Baltic Line", _RP, 2800, 4600, 60, True, True, True, _ROPAX_ADR
    ),
    "Demo Gulf": _VesselSpec(
        "Demo Gulf Ferries", _RP, 1900, None, 40, True, True, True, _ROPAX_ADR
    ),
    "Demo Carrier One": _VesselSpec(
        "Demo Shortsea", _RR, 3000, 5000, 80, False, True, False, _RORO_ADR
    ),
    "Demo Carrier Two": _VesselSpec(
        "Demo Shortsea", _RR, 3000, 5000, 80, False, True, False, _RORO_ADR
    ),
    "Demo Carrier Three": _VesselSpec(
        "Demo Shortsea", _RR, 3000, 5000, 80, False, True, False, _RORO_ADR
    ),
    "Demo Amber": _VesselSpec(
        "Demo Polska Line", _RP, 3200, 4700, 90, True, True, True, _ROPAX_ADR
    ),
}

_P = "Demo Port "
_R = "Demo Rail Terminal "
# stop: (place, loading, unloading); call: (arrival day, arrival, departure day, departure)
_Stop = tuple[str, bool, bool]
_CallSpec = tuple[int | None, str | None, int | None, str | None]


@dataclass(frozen=True)
class _ScheduleSpec:
    weekdays: tuple[int, ...]
    vessel: str | None
    calls: tuple[_CallSpec, ...]
    note: str = _TIMETABLE_NOTE


@dataclass(frozen=True)
class _RouteSpec:
    operator: str
    mode: LineMode
    accompanied: bool
    unaccompanied: bool
    checkin: int | None
    cutoff: int | None
    dg_hours: int | None
    stops: tuple[_Stop, ...]
    schedules: tuple[_ScheduleSpec, ...]
    note: str | None = None


_DAILY = (1, 2, 3, 4, 5, 6, 7)
_ODD, _EVEN = (1, 3, 5, 7), (2, 4, 6)


def _two(origin: str, destination: str) -> tuple[_Stop, _Stop]:
    return ((origin, True, False), (destination, False, True))


_DEMO_DEFAULTS = "Check-in, cut-off and declaration deadline are demo values."
# Vessels are set on a schedule only where one ship can sail it without overlapping its other
# departures; elsewhere the vessel is assigned per departure (NULL in the demo).


def _ferry(
    operator: str,
    stops: tuple[_Stop, ...],
    schedules: tuple[_ScheduleSpec, ...],
    *,
    accompanied: bool = True,
    checkin: int = 120,
    cutoff: int = 180,
    dg_hours: int = 24,
    note: str | None = None,
) -> _RouteSpec:
    return _RouteSpec(
        operator,
        LineMode.FERRY,
        accompanied,
        True,
        checkin if accompanied else None,
        cutoff,
        dg_hours,
        stops,
        schedules,
        note=f"{_DEMO_DEFAULTS} {note}" if note else _DEMO_DEFAULTS,
    )


def _rail_route(stops: tuple[_Stop, ...], schedules: tuple[_ScheduleSpec, ...]) -> _RouteSpec:
    return _RouteSpec(
        "Demo Rail",
        LineMode.RAIL,
        False,
        True,
        None,
        240,
        48,
        stops,
        schedules,
        note=(
            "Cut-off and declaration deadline are demo values. Loading gauge (profile) checked"
            " with Plan Check in phase 5; rail units need RID."
        ),
    )


LINE_ROUTES: dict[str, _RouteSpec] = {
    "Demo Vuosaari\u2013Travemünde": _ferry(
        "Demo Baltic Line",
        _two(_P + "Vuosaari", _P + "Travemünde"),
        (
            _ScheduleSpec(
                _ODD,
                None,
                ((None, None, 0, "17:00"), (1, "23:00", None, None)),
                _PUBLISHED_NOTE,
            ),
            _ScheduleSpec(
                _EVEN,
                None,
                ((None, None, 0, "17:00"), (1, "23:00", None, None)),
                _PUBLISHED_NOTE,
            ),
        ),
    ),
    "Demo Travemünde\u2013Vuosaari": _ferry(
        "Demo Baltic Line",
        _two(_P + "Travemünde", _P + "Vuosaari"),
        (
            _ScheduleSpec(
                _ODD,
                None,
                ((None, None, 0, "02:00"), (1, "10:00", None, None)),
                _PUBLISHED_NOTE,
            ),
            _ScheduleSpec(
                _EVEN,
                None,
                ((None, None, 0, "02:00"), (1, "10:00", None, None)),
                _PUBLISHED_NOTE,
            ),
        ),
    ),
    "Demo Vuosaari\u2013Tallinn": _ferry(
        "Demo Gulf Ferries",
        _two(_P + "Vuosaari", _P + "Tallinn"),
        (
            _ScheduleSpec(
                _DAILY,
                "Demo Gulf",
                ((None, None, 0, "06:00"), (0, "08:45", None, None)),
                _PUBLISHED_NOTE,
            ),
            _ScheduleSpec(
                _DAILY,
                "Demo Gulf",
                ((None, None, 0, "20:00"), (0, "22:45", None, None)),
                _PUBLISHED_NOTE,
            ),
        ),
        checkin=60,
        cutoff=90,
    ),
    "Demo Tallinn\u2013Vuosaari": _ferry(
        "Demo Gulf Ferries",
        _two(_P + "Tallinn", _P + "Vuosaari"),
        (
            _ScheduleSpec(
                _DAILY,
                "Demo Gulf",
                ((None, None, 0, "09:30"), (0, "12:15", None, None)),
                _PUBLISHED_NOTE,
            ),
            _ScheduleSpec(
                _DAILY,
                "Demo Gulf",
                ((None, None, 0, "23:30"), (1, "02:15", None, None)),
                _PUBLISHED_NOTE,
            ),
        ),
        checkin=60,
        cutoff=90,
    ),
    "Demo Kotka\u2013Lübeck": _ferry(
        "Demo Shortsea",
        _two(_P + "Kotka", _P + "Lübeck"),
        (_ScheduleSpec((1, 3, 5), None, ((None, None, 0, "20:00"), (2, "08:00", None, None))),),
        accompanied=False,
    ),
    "Demo Lübeck\u2013Kotka": _ferry(
        "Demo Shortsea",
        _two(_P + "Lübeck", _P + "Kotka"),
        (_ScheduleSpec((2, 4, 6), None, ((None, None, 0, "22:00"), (2, "08:00", None, None))),),
        accompanied=False,
    ),
    "Demo Kotka\u2013Hanko\u2013Antwerpen": _ferry(
        "Demo Shortsea",
        ((_P + "Kotka", True, False), (_P + "Hanko", True, True), (_P + "Antwerpen", False, True)),
        (
            _ScheduleSpec(
                (2,),
                "Demo Carrier Two",
                ((None, None, 0, "18:00"), (1, "06:00", 1, "14:00"), (3, "10:00", None, None)),
            ),
        ),
        accompanied=False,
    ),
    "Demo Antwerpen\u2013Hanko\u2013Kotka": _ferry(
        "Demo Shortsea",
        ((_P + "Antwerpen", True, False), (_P + "Hanko", True, True), (_P + "Kotka", False, True)),
        (
            _ScheduleSpec(
                (5,),
                "Demo Carrier Two",
                ((None, None, 0, "20:00"), (2, "18:00", 3, "02:00"), (3, "12:00", None, None)),
            ),
        ),
        accompanied=False,
    ),
    "Demo Kotka\u2013Antwerpen": _ferry(
        "Demo Shortsea",
        _two(_P + "Kotka", _P + "Antwerpen"),
        (
            _ScheduleSpec(
                (4,), "Demo Carrier One", ((None, None, 0, "20:00"), (3, "06:00", None, None))
            ),
        ),
        accompanied=False,
    ),
    "Demo Antwerpen\u2013Kotka": _ferry(
        "Demo Shortsea",
        _two(_P + "Antwerpen", _P + "Kotka"),
        (
            _ScheduleSpec(
                (7,), "Demo Carrier One", ((None, None, 0, "20:00"), (3, "06:00", None, None))
            ),
        ),
        accompanied=False,
    ),
    "Demo Hanko\u2013Gdynia": _ferry(
        "Demo Polska Line",
        _two(_P + "Hanko", _P + "Gdynia"),
        (
            _ScheduleSpec(
                (1, 2, 3, 4, 5, 6),
                None,
                ((None, None, 0, "21:00"), (1, "19:00", None, None)),
            ),
        ),
    ),
    "Demo Gdynia\u2013Hanko": _ferry(
        "Demo Polska Line",
        _two(_P + "Gdynia", _P + "Hanko"),
        (
            _ScheduleSpec(
                (1, 2, 3, 4, 5, 6),
                None,
                ((None, None, 0, "20:00"), (1, "20:00", None, None)),
            ),
        ),
    ),
    "Demo Hanko\u2013Rostock": _ferry(
        "Demo Polska Line",
        _two(_P + "Hanko", _P + "Rostock"),
        (_ScheduleSpec((1, 2, 4, 6), None, ((None, None, 0, "22:00"), (1, "21:00", None, None))),),
    ),
    "Demo Rostock\u2013Hanko": _ferry(
        "Demo Polska Line",
        _two(_P + "Rostock", _P + "Hanko"),
        (_ScheduleSpec((2, 3, 5, 7), None, ((None, None, 0, "23:00"), (2, "00:00", None, None))),),
    ),
    "Demo Oulu\u2013Travemünde\u2013Antwerpen": _ferry(
        "Demo Shortsea",
        (
            (_P + "Oulu", True, False),
            (_P + "Travemünde", True, True),
            (_P + "Antwerpen", False, True),
        ),
        (
            _ScheduleSpec(
                (6,),
                "Demo Carrier Three",
                ((None, None, 0, "18:00"), (2, "06:00", 2, "18:00"), (4, "06:00", None, None)),
            ),
        ),
        accompanied=False,
    ),
    "Demo Antwerpen\u2013Travemünde\u2013Oulu": _ferry(
        "Demo Shortsea",
        (
            (_P + "Antwerpen", True, False),
            (_P + "Travemünde", True, True),
            (_P + "Oulu", False, True),
        ),
        (
            _ScheduleSpec(
                (3,),
                "Demo Carrier Three",
                ((None, None, 0, "20:00"), (1, "20:00", 2, "06:00"), (3, "10:00", None, None)),
            ),
        ),
        accompanied=False,
    ),
    "Demo Naantali\u2013Långnäs\u2013Kapellskär": _ferry(
        "Demo Baltic Line",
        (
            (_P + "Naantali", True, False),
            (_P + "Långnäs", True, True),
            (_P + "Kapellskär", False, True),
        ),
        (
            _ScheduleSpec(
                _DAILY,
                "Demo Aurora",
                ((None, None, 0, "10:00"), (0, "14:45", 0, "15:00"), (0, "17:45", None, None)),
                _PUBLISHED_NOTE,
            ),
            _ScheduleSpec(
                _DAILY,
                "Demo Borealis",
                ((None, None, 0, "22:45"), (1, "03:45", 1, "03:55"), (1, "06:15", None, None)),
                _PUBLISHED_NOTE,
            ),
        ),
    ),
    "Demo Kapellskär\u2013Långnäs\u2013Naantali": _ferry(
        "Demo Baltic Line",
        (
            (_P + "Kapellskär", True, False),
            (_P + "Långnäs", True, True),
            (_P + "Naantali", False, True),
        ),
        (
            _ScheduleSpec(
                _DAILY,
                "Demo Borealis",
                ((None, None, 0, "10:30"), (0, "15:00", 0, "15:15"), (0, "19:55", None, None)),
                _PUBLISHED_NOTE,
            ),
            _ScheduleSpec(
                _DAILY,
                "Demo Aurora",
                ((None, None, 0, "21:45"), (1, "02:00", 1, "02:10"), (1, "07:15", None, None)),
                _PUBLISHED_NOTE,
            ),
        ),
    ),
    "Demo Rail Rostock\u2013Verona": _rail_route(
        _two(_R + "Rostock", _R + "Verona"),
        (_ScheduleSpec((1, 3, 5), None, ((None, None, 0, "18:00"), (2, "06:00", None, None))),),
    ),
    "Demo Rail Verona\u2013Rostock": _rail_route(
        _two(_R + "Verona", _R + "Rostock"),
        (_ScheduleSpec((2, 4, 6), None, ((None, None, 0, "20:00"), (2, "08:00", None, None))),),
    ),
    "Demo Rail Travemünde\u2013Verona": _rail_route(
        _two(_R + "Travemünde", _R + "Verona"),
        (_ScheduleSpec((2, 4, 6), None, ((None, None, 0, "17:00"), (2, "05:00", None, None))),),
    ),
    "Demo Rail Verona\u2013Travemünde": _rail_route(
        _two(_R + "Verona", _R + "Travemünde"),
        (_ScheduleSpec((1, 3, 5), None, ((None, None, 0, "21:00"), (2, "09:00", None, None))),),
    ),
}


def _hhmm(value: str | None) -> time | None:
    return time.fromisoformat(value) if value is not None else None


def schedule_calls(spec: _ScheduleSpec) -> list[Call]:
    return [
        Call(number, a_day, _hhmm(a_time), d_day, _hhmm(d_time))
        for number, (a_day, a_time, d_day, d_time) in enumerate(spec.calls, start=1)
    ]


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
    # Thermo Double, two diesel units; the partition position is chosen for the load (D76).
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
# independently_controlled, position of the serving evaporator or None). The temperatures are the
# range each compartment can hold.
_Comp = tuple[int, str, str, int | None, bool, EvaporatorPosition | None]
COMPARTMENTS: dict[str, tuple[_Comp, ...]] = {
    # FD: two zones, one machine each. No pallet places: the partition moves one EUR row at a
    # time (4 + 28 ... 28 + 4) and its position is chosen for the load (D76).
    "DEMO-TRL-007": (
        (1, "-25.0", "-18.0", None, True, EvaporatorPosition.FRONT),
        (2, "2.0", "8.0", None, True, EvaporatorPosition.REAR),
    ),
    "DEMO-TRL-012": (
        (1, "-25.0", "8.0", None, True, EvaporatorPosition.FRONT),
        (2, "-25.0", "8.0", None, True, EvaporatorPosition.REAR),
    ),
    "DEMO-TRL-013": ((1, "-25.0", "8.0", None, False, EvaporatorPosition.FRONT),),
    "DEMO-BOD-002": ((1, "-25.0", "8.0", None, False, EvaporatorPosition.FRONT),),
}
# registration -> the reefer unit (machine, at the front): (unit name, power source); invented
# make and model. TRL-007's machine is a hybrid: it can run on electricity in a port (D27).
REEFER_UNITS: dict[str, tuple[str, PowerSource]] = {
    "DEMO-TRL-007": ("Demo Chill Duo 300", PowerSource.HYBRID),
    "DEMO-TRL-012": ("Demo Chill Duo 200", PowerSource.DIESEL),
    "DEMO-TRL-013": ("Demo Chill Side 150", PowerSource.DIESEL),
    "DEMO-BOD-002": ("Demo Chill Mono 100", PowerSource.ELECTRIC),
}
# registration -> evaporators (indoor units) of the machine (D76): FD front and rear, FB and FS
# one at the front.
EVAPORATORS: dict[str, tuple[EvaporatorPosition, ...]] = {
    "DEMO-TRL-007": (EvaporatorPosition.FRONT, EvaporatorPosition.REAR),
    "DEMO-TRL-012": (EvaporatorPosition.FRONT, EvaporatorPosition.REAR),
    "DEMO-TRL-013": (EvaporatorPosition.FRONT,),
    "DEMO-BOD-002": (EvaporatorPosition.FRONT,),
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
    # Reefer unit service (D76), one machine per load unit; "reefer_unit" subjects are named by
    # the load unit's registration.
    ("reefer_unit", "DEMO-TRL-007", _ET.REEFER_SERVICE, None, -345, 20),  # expiring soon
    ("reefer_unit", "DEMO-TRL-012", _ET.REEFER_SERVICE, None, -245, 120),
    ("reefer_unit", "DEMO-TRL-013", _ET.REEFER_SERVICE, None, -275, 90),
    ("reefer_unit", "DEMO-BOD-002", _ET.REEFER_SERVICE, None, -215, 150),
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

    # Reefer units and their evaporators (D76) before the compartments that name them.
    reefer_units: dict[str, ReeferUnit] = {}  # by registration
    evaporators: dict[str, ReeferEvaporator] = {}  # key "<registration>:<position>"
    for registration, (unit_name, power) in REEFER_UNITS.items():
        unit = load_units[registration]
        model_code = unit_specs[registration].model_code
        validate_reefer_units(body_types[registration], 1, model_code)
        validate_evaporators(EVAPORATORS[registration], model_code)
        machine = session.scalar(select(ReeferUnit).where(ReeferUnit.load_unit_id == unit.id))
        if machine is None:
            machine = ReeferUnit(
                load_unit_id=unit.id, unit_name=unit_name, power_source=power.value
            )
            session.add(machine)
            session.flush()
            created["reefer_units"] += 1
        reefer_units[registration] = machine
        for position in EVAPORATORS[registration]:
            evaporator = session.scalar(
                select(ReeferEvaporator).where(
                    ReeferEvaporator.reefer_unit_id == machine.id,
                    ReeferEvaporator.position == position.value,
                )
            )
            if evaporator is None:
                evaporator = ReeferEvaporator(
                    reefer_unit_id=machine.id, load_unit_id=unit.id, position=position.value
                )
                session.add(evaporator)
                created["reefer_evaporators"] += 1
            evaporators[f"{registration}:{position.value}"] = evaporator
    session.flush()

    for registration, rows in COMPARTMENTS.items():
        comp_unit = unit_specs[registration]
        validate_compartment_set(comp_unit.body_type, [row[0] for row in rows])
        validate_compartment_pallet_places(
            comp_unit.pallet_places, [row[3] for row in rows], comp_unit.model_code
        )
        validate_zones(len(rows), [row[4] for row in rows], comp_unit.model_code)
        for number, t_min, t_max, places, independent, serving in rows:
            validate_compartment(number, Decimal(t_min), Decimal(t_max))
            unit = load_units[registration]
            serving_evaporator = evaporators[f"{registration}:{serving.value}"] if serving else None
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
                        evaporator_id=serving_evaporator.id if serving_evaporator else None,
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


def _seed_places(
    session: Session, locations: dict[str, Location], today: date, created: Counter[str]
) -> None:
    """Parking details, certificates, border crossings and status periods (2B-3b, D92)."""
    for name, spec in PARKING.items():
        location = locations[name]
        if session.get(ParkingDetails, location.id) is None:
            services = validate_parking_details(
                spaces=spec.spaces,
                night_price_cents=spec.night_price_cents,
                price_currency=spec.price_currency,
                reefer_plug_count=spec.reefer_plugs,
                booking_possible=spec.booking_possible,
                booking_required=location.booking_required,
                services=[s.value for s in spec.services],
            )
            session.add(
                ParkingDetails(
                    location_id=location.id,
                    spaces=spec.spaces,
                    night_price_cents=spec.night_price_cents,
                    price_currency=spec.price_currency,
                    reefer_plug_count=spec.reefer_plugs,
                    booking_possible=spec.booking_possible,
                    adr_vehicles_allowed=spec.adr_allowed,
                    trailer_drop_allowed=spec.trailer_drop,
                    services=services,
                )
            )
            created["parking_details"] += 1
    session.flush()
    for name, scheme, level, start, end, ref in PARKING_CERTIFICATIONS:
        location = locations[name]
        exists = session.scalar(
            select(ParkingCertification.id).where(
                ParkingCertification.location_id == location.id,
                ParkingCertification.document_ref == ref,
            )
        )
        if exists is None:
            valid_from, valid_until = today + timedelta(days=start), today + timedelta(days=end)
            validate_parking_certification(scheme, level, valid_from, valid_until)
            session.add(
                ParkingCertification(
                    location_id=location.id,
                    scheme=scheme.value,
                    level=level.value,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    document_ref=ref,
                )
            )
            created["parking_certifications"] += 1

    for name, border in BORDER_CROSSINGS.items():
        location = locations[name]
        if session.get(BorderCrossingDetails, location.id) is None:
            office = locations[border.customs_office] if border.customs_office else None
            other = locations[border.other_customs_office] if border.other_customs_office else None
            validate_customs_office_pair(office.id if office else None, other.id if other else None)
            validate_border_crossing(
                location.country,
                border.other_country,
                typical_wait_minutes=None,
                customs_office_country=office.country if office else None,
                other_customs_office_country=other.country if other else None,
            )
            session.add(
                BorderCrossingDetails(
                    location_id=location.id,
                    other_country=border.other_country,
                    customs_office_id=office.id if office else None,
                    customs_office_type=office.type if office else None,
                    other_customs_office_id=other.id if other else None,
                    other_customs_office_type=other.type if other else None,
                    note=border.note,
                )
            )
            created["border_crossing_details"] += 1
    session.flush()
    for name in BORDER_CROSSINGS:
        validate_status_periods([(st, a, b) for n, st, a, b, _, _ in BORDER_STATUS if n == name])
    for name, status, starts_at, ends_at, note, source in BORDER_STATUS:
        location = locations[name]
        exists = session.scalar(
            select(BorderCrossingStatusPeriod.id).where(
                BorderCrossingStatusPeriod.location_id == location.id,
                BorderCrossingStatusPeriod.starts_at == starts_at,
            )
        )
        if exists is None:
            session.add(
                BorderCrossingStatusPeriod(
                    location_id=location.id,
                    status=status.value,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    note=note,
                    source_url=source,
                    checked_on=_CHECKED,
                )
            )
            created["border_crossing_status_periods"] += 1
    session.flush()

    for name, free, fee, currency, plugs, plug_fee, note in STORAGE_RULES:
        location = locations[name]
        exists = session.scalar(
            select(TrailerStorageRule.id).where(
                TrailerStorageRule.location_id == location.id,
                TrailerStorageRule.valid_from == STORAGE_FROM,
            )
        )
        if exists is None:
            validate_trailer_storage_rule(
                location.type,
                free_days=free,
                daily_fee_cents=fee,
                currency=currency,
                reefer_plug_available=plugs,
                reefer_plug_daily_fee_cents=plug_fee,
                valid_from=STORAGE_FROM,
                valid_until=None,
            )
            session.add(
                TrailerStorageRule(
                    location_id=location.id,
                    location_type=location.type,
                    valid_from=STORAGE_FROM,
                    free_days=free,
                    daily_fee_cents=fee,
                    currency=currency,
                    reefer_plug_available=plugs,
                    reefer_plug_daily_fee_cents=plug_fee,
                    note=f"{_DEMO_TARIFF} {note}" if note else _DEMO_TARIFF,
                )
            )
            created["trailer_storage_rules"] += 1

    for name, (scopes, grades, document, ecd) in WASHES.items():
        location = locations[name]
        if session.get(WashDetails, location.id) is None:
            scope_values, grade_values = validate_wash_details(
                [v.value for v in scopes],
                [v.value for v in grades],
                issues_cleaning_document=document,
                issues_ecd=ecd,
            )
            session.add(
                WashDetails(
                    location_id=location.id,
                    scopes=scope_values,
                    grades=grade_values,
                    issues_cleaning_document=document,
                    issues_ecd=ecd,
                )
            )
            created["wash_details"] += 1
    session.flush()


def _seed_lines(
    session: Session, locations: dict[str, Location], today: date, created: Counter[str]
) -> None:
    """Operators, vessels, routes with stops, weekly schedules and departures (D94).

    Departures are generated for DEPARTURE_WEEKS from the seed day; only missing ones are added
    (domain.lines.departures_to_add), so a departure changed or added by hand stays as it is.
    """
    operators: dict[str, LineOperator] = {}
    for name, mode in LINE_OPERATORS:
        operator = session.scalar(select(LineOperator).where(LineOperator.name == name))
        if operator is None:
            operator = LineOperator(name=name, mode=mode.value)
            session.add(operator)
            created["line_operators"] += 1
        operators[name] = operator
    session.flush()

    vessels: dict[str, Vessel] = {}
    for name, v in VESSELS.items():
        vessel = session.scalar(select(Vessel).where(Vessel.name == name))
        if vessel is None:
            validate_vessel(
                lane_metres=v.lane_metres,
                deck_height_mm=v.deck_height_mm,
                reefer_plug_count=v.reefer_plugs,
                accompanied=v.accompanied,
                unaccompanied=v.unaccompanied,
                driver_cabins=v.cabins,
            )
            vessel = Vessel(
                operator_id=operators[v.operator].id,
                name=name,
                vessel_type=v.type.value,
                lane_metres=v.lane_metres,
                deck_height_mm=v.deck_height_mm,
                reefer_plug_count=v.reefer_plugs,
                accompanied=v.accompanied,
                unaccompanied=v.unaccompanied,
                driver_cabins=v.cabins,
            )
            session.add(vessel)
            session.flush()
            created["vessels"] += 1
            for adr_class, acceptance, note in v.adr:
                session.add(
                    VesselAdrClass(
                        vessel_id=vessel.id,
                        adr_class=adr_class,
                        acceptance=acceptance.value,
                        note=note,
                    )
                )
                created["vessel_adr_classes"] += 1
        vessels[name] = vessel
    session.flush()

    end = today + timedelta(days=7 * DEPARTURE_WEEKS - 1)
    for route_name, spec in LINE_ROUTES.items():
        route = session.scalar(select(LineRoute).where(LineRoute.name == route_name))
        stops = [Stop(n, load, unload) for n, (_, load, unload) in enumerate(spec.stops, 1)]
        if route is None:
            validate_route(
                spec.mode,
                accompanied=spec.accompanied,
                unaccompanied=spec.unaccompanied,
                checkin_minutes=spec.checkin,
                cutoff_minutes=spec.cutoff,
                dg_declaration_hours=spec.dg_hours,
            )
            validate_stops(stops)
            route = LineRoute(
                operator_id=operators[spec.operator].id,
                mode=spec.mode.value,
                name=route_name,
                accompanied=spec.accompanied,
                unaccompanied=spec.unaccompanied,
                checkin_minutes=spec.checkin,
                cutoff_minutes=spec.cutoff,
                dg_declaration_hours=spec.dg_hours,
                note=spec.note,
            )
            session.add(route)
            session.flush()
            created["line_routes"] += 1
            for stop, (place, _, _) in zip(stops, spec.stops, strict=True):
                location = locations[place]
                session.add(
                    LineRouteStop(
                        route_id=route.id,
                        sequence=stop.sequence,
                        route_mode=spec.mode.value,
                        location_id=location.id,
                        location_type=location.type,
                        loading=stop.loading,
                        unloading=stop.unloading,
                    )
                )
                created["line_route_stops"] += 1
            session.flush()
        zones = [locations[place].timezone for place, _, _ in spec.stops]
        validate_schedule_periods(
            [
                (
                    weekday,
                    schedule_calls(sched)[0].departure_time or time(0),
                    date(2026, 1, 1),
                    None,
                )
                for sched in spec.schedules
                for weekday in sched.weekdays
            ]
        )
        for sched in spec.schedules:
            calls = schedule_calls(sched)
            validate_calls(calls)
            for weekday in sched.weekdays:
                first_departure = calls[0].departure_time
                schedule = session.scalar(
                    select(LineSchedule)
                    .join(
                        LineScheduleCall,
                        (LineScheduleCall.schedule_id == LineSchedule.id)
                        & (LineScheduleCall.sequence == 1),
                    )
                    .where(
                        LineSchedule.route_id == route.id,
                        LineSchedule.weekday == weekday,
                        LineScheduleCall.departure_time == first_departure,
                    )
                )
                if schedule is None:
                    schedule = LineSchedule(
                        route_id=route.id,
                        route_mode=spec.mode.value,
                        operator_id=route.operator_id,
                        weekday=weekday,
                        vessel_id=vessels[sched.vessel].id if sched.vessel else None,
                        valid_from=date(2026, 1, 1),
                        note=sched.note,
                    )
                    session.add(schedule)
                    session.flush()
                    created["line_schedules"] += 1
                    for call in calls:
                        session.add(
                            LineScheduleCall(
                                schedule_id=schedule.id,
                                sequence=call.sequence,
                                route_id=route.id,
                                arrival_day=call.arrival_day,
                                arrival_time=call.arrival_time,
                                departure_day=call.departure_day,
                                departure_time=call.departure_time,
                            )
                        )
                        created["line_schedule_calls"] += 1
                    session.flush()
                existing = session.scalars(
                    select(LineDeparture.service_date).where(
                        LineDeparture.schedule_id == schedule.id
                    )
                ).all()
                planned = service_dates(
                    weekday, schedule.valid_from, schedule.valid_until, today, end
                )
                plans = {
                    day: plan_departure(day, calls, zones, stops, route_cutoff_minutes=spec.cutoff)
                    for day in planned
                }
                route_firsts = session.scalars(
                    select(LineDepartureCall.departs_at).where(
                        LineDepartureCall.route_id == route.id,
                        LineDepartureCall.sequence == 1,
                    )
                ).all()
                to_add = departures_to_add(
                    planned,
                    existing,
                    [moment for moment in route_firsts if moment is not None],
                    {day: plan[0].departs_at for day, plan in plans.items() if plan[0].departs_at},
                )
                for service_date in to_add:
                    departure = LineDeparture(
                        route_id=route.id,
                        route_mode=spec.mode.value,
                        operator_id=route.operator_id,
                        schedule_id=schedule.id,
                        service_date=service_date,
                        vessel_id=schedule.vessel_id,
                    )
                    session.add(departure)
                    session.flush()
                    created["line_departures"] += 1
                    for planned_call in plans[service_date]:
                        session.add(
                            LineDepartureCall(
                                departure_id=departure.id,
                                sequence=planned_call.sequence,
                                route_id=route.id,
                                arrives_at=planned_call.arrives_at,
                                departs_at=planned_call.departs_at,
                                cutoff_at=planned_call.cutoff_at,
                            )
                        )
                        created["line_departure_calls"] += 1
                    session.flush()
    session.flush()


# --- Cargo crime risk and border waiting times (2B-3e, D95) -----------------------------------
# Reported incidents per country from the TAPA EMEA monthly figures as published by trans.info.
# Only the countries an article names get a count; a missing country is unknown, not zero.
_TAPA = "TAPA EMEA Cargo Crime Monitor, as reported by trans.info"
# Every source was read on the same day for this demo; a real update sets its own day per row.
_RISK_CHECKED = date(2026, 11, 24)
_TOP5 = "The article names the five countries with the most reports only."
CARGO_CRIME_REPORTS: tuple[tuple[date, str, str, dict[str, int]], ...] = (
    (
        date(2025, 12, 1),
        "https://trans.info/en/cargo-crime-reports-454902",
        _TOP5,
        {"DE": 115, "IT": 64, "GB": 54, "ES": 41, "FR": 41},
    ),
    (
        date(2026, 2, 1),
        "https://trans.info/en/cargo-theft-europe-471019",
        _TOP5,
        {"DE": 223, "IT": 105, "ES": 96, "FR": 79, "GB": 64},
    ),
    (
        date(2026, 3, 1),
        "https://trans.info/en/tapa-march-2026-477316",
        "The article names nine of the 51 reporting countries. The counts are for March only but"
        " about five times those of other months; the level uses the median.",
        {
            "DE": 1295,
            "IT": 867,
            "FR": 850,
            "GB": 761,
            "ES": 682,
            "PL": 338,
            "CZ": 207,
            "SK": 94,
            "NL": 45,
        },
    ),
    (
        date(2026, 5, 1),
        "https://trans.info/en/cargo-theft-june-493590",
        "Previous-month figures in the June article; Germany is not given as a number.",
        {"IT": 176, "ES": 111, "FR": 139, "GB": 169, "BE": 63, "GR": 26, "NL": 92, "PL": 23},
    ),
    (
        date(2026, 6, 1),
        "https://trans.info/en/cargo-theft-june-493590",
        "The article names thirteen countries.",
        {
            "DE": 440,
            "IT": 320,
            "ES": 280,
            "FR": 262,
            "GB": 224,
            "BE": 80,
            "GR": 57,
            "NL": 53,
            "AT": 29,
            "SE": 28,
            "PL": 25,
            "CZ": 24,
            "RO": 23,
        },
    ),
    (
        date(2026, 7, 1),
        "https://trans.info/en/fewer-cargo-thefts-but-bigger-losses-and-more-violence-in-july"
        "-499745",
        _TOP5,
        {"DE": 200, "IT": 159, "ES": 106, "FR": 81, "GB": 48},
    ),
    (
        date(2026, 9, 1),
        "https://trans.info/en/losses-of-24-8-million-euros-despite-only-0-5-per-cent-of"
        "-reports-assessed-tapa-shows-the-scale-of-cargo-theft-512114",
        "The article names nine European countries.",
        {
            "DE": 202,
            "IT": 103,
            "FR": 84,
            "ES": 75,
            "GB": 49,
            "SE": 40,
            "CH": 24,
            "AT": 15,
            "PL": 4,
        },
    ),
)

_TT_CLUB_BENELUX = (
    "https://www.ttclub.com/news-and-resources/news/article/tt-club-warns-of-sophisticated"
    "-criminal-networks-targeting-benelux-logistics-hub/"
)
_HOTSPOT_BASIS = (
    "Demo classification: a named hotspot road = level 4. Named in the TT Club, BSI Consulting"
    " and TVM 2026 Benelux report as a highway with elevated theft rates, particularly at"
    " unsecured rest areas."
)
# The report names the roads for Belgium and the Netherlands together; E19 runs through both.
_BENELUX_HOTSPOTS = (("BE", "E19"), ("NL", "E19"), ("BE", "E17"), ("NL", "A67"), ("NL", "A2"))
_DEMO_ESTIMATE = "Demo estimate for the portfolio demo, not a security assessment: "


@dataclass(frozen=True)
class _RiskAreaSpec:
    country: str
    region: str | None
    road_ref: str | None
    section: str | None
    level: int
    source_type: RiskSourceType
    basis: str
    source_url: str | None
    valid_from: date


RISK_AREAS: tuple[_RiskAreaSpec, ...] = (
    *(
        _RiskAreaSpec(
            country,
            None,
            road,
            None,
            4,
            RiskSourceType.DATA,
            _HOTSPOT_BASIS,
            _TT_CLUB_BENELUX,
            date(2026, 3, 31),
        )
        for country, road in _BENELUX_HOTSPOTS
    ),
    _RiskAreaSpec(
        "FR",
        "FR-ARA",
        None,
        "Lyon area motorways and rest areas",
        4,
        RiskSourceType.EXPERT_ESTIMATE,
        _DEMO_ESTIMATE + "few secure parking places after Lyon on the way south; plan the rest"
        " before the area.",
        None,
        date(2026, 11, 24),
    ),
    _RiskAreaSpec(
        "ES",
        "ES-CT",
        "AP-7",
        "French border to Barcelona",
        4,
        RiskSourceType.EXPERT_ESTIMATE,
        _DEMO_ESTIMATE + "avoid unplanned stops between the border and Barcelona.",
        None,
        date(2026, 11, 24),
    ),
)

_CET = ZoneInfo("Europe/Stockholm")
# Invented heavy-traffic waits at Svinesund (location in SE): direction, local time, minutes.
BORDER_WAITS: tuple[tuple[str, WaitDirection, datetime, int], ...] = tuple(
    ("Demo Border Crossing Svinesund", direction, datetime(2026, 11, day, hour, 0, tzinfo=_CET), m)
    for direction, day, hour, m in (
        (WaitDirection.EXIT, 2, 7, 45),
        (WaitDirection.EXIT, 9, 7, 60),
        (WaitDirection.EXIT, 16, 7, 35),
        (WaitDirection.EXIT, 2, 14, 20),
        (WaitDirection.EXIT, 9, 14, 15),
        (WaitDirection.ENTRY, 6, 16, 30),
        (WaitDirection.ENTRY, 13, 16, 40),
        (WaitDirection.ENTRY, 20, 16, 25),
    )
)


def _seed_risks(session: Session, locations: dict[str, Location], created: Counter[str]) -> None:
    """Monthly reports, risk areas and demo border waits (D95). Idempotent."""
    for month, url, coverage, counts in CARGO_CRIME_REPORTS:
        validate_report_month(month)
        report = session.scalar(
            select(CargoCrimeReport).where(
                CargoCrimeReport.source_name == _TAPA, CargoCrimeReport.report_month == month
            )
        )
        if report is None:
            report = CargoCrimeReport(
                source_name=_TAPA,
                report_month=month,
                coverage_note=coverage,
                source_url=url,
                checked_on=_RISK_CHECKED,
            )
            session.add(report)
            session.flush()
            created["cargo_crime_reports"] += 1
        for country, count in counts.items():
            if session.get(CargoCrimeCount, (report.id, country)) is None:
                session.add(
                    CargoCrimeCount(
                        report_id=report.id,
                        country=country,
                        incident_count=validate_incident_count(count),
                    )
                )
                created["cargo_crime_counts"] += 1
    session.flush()

    for area in RISK_AREAS:
        validate_risk_area(
            country=area.country,
            region=area.region,
            road_ref=area.road_ref,
            level=area.level,
            source_type=area.source_type,
            basis=area.basis,
            source_url=area.source_url,
            valid_from=area.valid_from,
            valid_until=None,
        )
        exists = session.scalar(
            select(RiskArea.id).where(
                RiskArea.country == area.country,
                RiskArea.region.is_not_distinct_from(area.region),
                RiskArea.road_ref.is_not_distinct_from(area.road_ref),
                RiskArea.valid_from == area.valid_from,
            )
        )
        if exists is None:
            session.add(
                RiskArea(
                    country=area.country,
                    region=area.region,
                    road_ref=area.road_ref,
                    section=area.section,
                    level=area.level,
                    source_type=area.source_type.value,
                    basis=area.basis,
                    source_url=area.source_url,
                    checked_on=_RISK_CHECKED,
                    valid_from=area.valid_from,
                )
            )
            created["risk_areas"] += 1
    session.flush()

    for name, direction, observed_at, minutes in BORDER_WAITS:
        validate_wait_observation(
            observed_at=observed_at,
            wait_minutes=minutes,
            source_type=WaitSourceType.DEMO,
            source_url=None,
            note=DEMO_WAIT_NOTE,
        )
        location = locations[name]
        exists = session.scalar(
            select(BorderWaitObservation.id).where(
                BorderWaitObservation.location_id == location.id,
                BorderWaitObservation.direction == direction.value,
                BorderWaitObservation.observed_at == observed_at,
                BorderWaitObservation.source_type == WaitSourceType.DEMO.value,
            )
        )
        if exists is None:
            session.add(
                BorderWaitObservation(
                    location_id=location.id,
                    direction=direction.value,
                    observed_at=observed_at,
                    wait_minutes=minutes,
                    source_type=WaitSourceType.DEMO.value,
                    note=DEMO_WAIT_NOTE,
                )
            )
            created["border_wait_observations"] += 1
    session.flush()


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
            validate_site_features(
                place.type,
                forklift_available=place.forklift_available,
                tail_lift_required=place.tail_lift_required,
                has_loading_dock=place.has_loading_dock,
            )
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
                forklift_available=place.forklift_available,
                tail_lift_required=place.tail_lift_required,
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

    _seed_places(session, locations, today, created)
    _seed_lines(session, locations, today, created)
    _seed_risks(session, locations, created)
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
        "parking_details",
        "parking_certifications",
        "border_crossing_details",
        "border_crossing_status_periods",
        "border_wait_observations",
        "cargo_crime_reports",
        "cargo_crime_counts",
        "risk_areas",
        "trailer_storage_rules",
        "wash_details",
        "line_operators",
        "vessels",
        "vessel_adr_classes",
        "line_routes",
        "line_route_stops",
        "line_schedules",
        "line_schedule_calls",
        "line_departures",
        "line_departure_calls",
        "drivers",
        "driver_qualifications",
        "trucks",
        "dollies",
        "load_units",
        "reefer_units",
        "reefer_evaporators",
        "compartments",
        "equipment_qualifications",
    ):
        print(f"{table}: {created[table]} created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
