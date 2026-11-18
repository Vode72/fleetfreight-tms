"""Constraints of the 2B-1 register tables, checked against the migrated PostgreSQL schema."""

import uuid
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from domain.locations import LocationType
from domain.parties import CarrierType, CustomerType, DriverEmployment
from domain.qualifications import DriverQualificationType

pytestmark = pytest.mark.usefixtures("clean_registers")


def _insert(engine: Engine, table: str, **values: Any) -> uuid.UUID:
    columns = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    with engine.begin() as conn:
        return uuid.UUID(
            str(
                conn.execute(
                    text(f"INSERT INTO {table} ({columns}) VALUES ({params}) RETURNING id"), values
                ).scalar()
            )
        )


def _customer(engine: Engine, name: str = "Demo A Oy", **kw: Any) -> uuid.UUID:
    return _insert(engine, "customers", **{"name": name, "country": "FI", **kw})


def _location(engine: Engine, name: str = "Demo Place", **kw: Any) -> uuid.UUID:
    values = {"type": "depot", "name": name, "country": "FI", "timezone": "Europe/Helsinki", **kw}
    return _insert(engine, "locations", **values)


def _carrier(engine: Engine, name: str = "Demo Carrier Oy", **kw: Any) -> uuid.UUID:
    return _insert(engine, "carriers", **{"name": name, "type": "own", "country": "FI", **kw})


def _driver(
    engine: Engine, carrier_id: uuid.UUID, name: str = "Demo Driver A", **kw: Any
) -> uuid.UUID:
    return _insert(
        engine, "drivers", **{"carrier_id": carrier_id, "name": name, "employment": "own", **kw}
    )


def _rejected(fn: Any, *args: Any, **kw: Any) -> None:
    with pytest.raises(IntegrityError):
        fn(*args, **kw)


# --- customers


def test_customer_defaults(test_engine: Engine) -> None:
    _customer(test_engine)
    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT type, pallet_exchange_agreed, created_at, updated_at FROM customers")
        ).one()
    assert row.type == "customer"
    assert row.pallet_exchange_agreed is False  # D59: off by default
    assert row.created_at.tzinfo is not None and row.updated_at.tzinfo is not None


@pytest.mark.parametrize("value", [v.value for v in CustomerType])
def test_customer_type_accepts_domain_values(test_engine: Engine, value: str) -> None:
    _customer(test_engine, type=value)


def test_customer_rejects_unknown_type_bad_country_and_blank_name(test_engine: Engine) -> None:
    _rejected(_customer, test_engine, type="supplier")
    _rejected(_customer, test_engine, "Demo B Oy", country="fi")
    _rejected(_customer, test_engine, "Demo C Oy", country="F1")
    _rejected(_customer, test_engine, "   ")


def test_customer_name_is_unique(test_engine: Engine) -> None:
    _customer(test_engine)
    _rejected(_customer, test_engine)


def test_only_one_own_company(test_engine: Engine) -> None:
    _customer(test_engine, "Demo Own Oy", type="own_company")
    _rejected(_customer, test_engine, "Demo Other Own Oy", type="own_company")
    _customer(test_engine, "Demo Customer Oy")  # ordinary customers are not limited
    _customer(test_engine, "Demo Customer 2 Oy")


def test_own_company_slot_is_freed_when_the_row_is_deleted(test_engine: Engine) -> None:
    first = _customer(test_engine, "Demo Own Oy", type="own_company")
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM customers WHERE id = :i"), {"i": first})
    _customer(test_engine, "Demo Own 2 Oy", type="own_company")


# --- locations


@pytest.mark.parametrize("value", [t.value for t in LocationType if t.value != "terminal"])
def test_location_type_accepts_domain_values(test_engine: Engine, value: str) -> None:
    kw: dict[str, Any] = {}
    if value == "customer_site":
        kw["customer_id"] = _customer(test_engine)
    _location(test_engine, type=value, **kw)


def test_terminal_accepted_with_terminal_fields(test_engine: Engine) -> None:
    _location(test_engine, type="terminal", loading_docks=4, cold_storage=False)


def test_location_rejects_unknown_type_country_and_blank_name(test_engine: Engine) -> None:
    _rejected(_location, test_engine, type="warehouse")
    _rejected(_location, test_engine, country="f1")
    _rejected(_location, test_engine, name=" ")


def test_customer_site_requires_customer(test_engine: Engine) -> None:
    _rejected(_location, test_engine, type="customer_site")


def test_loading_dock_flag_is_for_customer_sites_only(test_engine: Engine) -> None:
    customer = _customer(test_engine)
    for flag in (True, False):
        _location(
            test_engine,
            f"Demo Site {flag}",
            type="customer_site",
            customer_id=customer,
            has_loading_dock=flag,
        )
    _location(test_engine, "Demo Site Unknown", type="customer_site", customer_id=customer)
    _rejected(_location, test_engine, "Demo Depot", type="depot", has_loading_dock=True)
    _rejected(
        _location,
        test_engine,
        "Demo Terminal",
        type="terminal",
        loading_docks=2,
        cold_storage=False,
        has_loading_dock=True,
    )


def test_location_customer_fk(test_engine: Engine) -> None:
    _rejected(_location, test_engine, type="customer_site", customer_id=uuid.uuid4())


def test_parent_location(test_engine: Engine) -> None:
    parent = _location(test_engine, "Demo Port Area", type="port")
    child = _location(
        test_engine, "Demo Port Area - Quay A", type="port", parent_location_id=parent
    )
    _rejected(_location, test_engine, "Demo Orphan", parent_location_id=uuid.uuid4())  # FK
    with pytest.raises(IntegrityError), test_engine.begin() as conn:  # not its own parent
        conn.execute(
            text("UPDATE locations SET parent_location_id = id WHERE id = :i"), {"i": child}
        )
    with pytest.raises(IntegrityError), test_engine.begin() as conn:  # parent in use
        conn.execute(text("DELETE FROM locations WHERE id = :i"), {"i": parent})


def test_location_name_is_unique(test_engine: Engine) -> None:
    _location(test_engine)
    _rejected(_location, test_engine)


def test_coordinates_must_come_as_a_valid_pair(test_engine: Engine) -> None:
    _location(test_engine, "Demo Ok", latitude="60.169900", longitude="24.938400")
    _location(test_engine, "Demo None")
    _rejected(_location, test_engine, "Demo Lat Only", latitude="60.1")
    _rejected(_location, test_engine, "Demo Lon Only", longitude="24.9")
    _rejected(_location, test_engine, "Demo Bad Lat", latitude="91", longitude="24.9")
    _rejected(_location, test_engine, "Demo Bad Lon", latitude="60", longitude="181")


def test_coordinates_keep_decimal_precision(test_engine: Engine) -> None:
    _location(test_engine, latitude="60.169912", longitude="24.938412")
    with test_engine.connect() as conn:
        lat = conn.execute(text("SELECT latitude FROM locations")).scalar()
    assert str(lat) == "60.169912"


def test_opening_hours_must_be_a_json_object(test_engine: Engine) -> None:
    _location(test_engine, "Demo Obj", opening_hours='{"mon": [["08:00", "16:00"]]}')
    _rejected(_location, test_engine, "Demo Arr", opening_hours="[]")
    _rejected(_location, test_engine, "Demo Str", opening_hours='"mon"')


def test_max_vehicle_length_must_be_positive(test_engine: Engine) -> None:
    _location(test_engine, "Demo Ok", max_vehicle_length_m="16.50")
    _rejected(_location, test_engine, "Demo Zero", max_vehicle_length_m="0")


@pytest.mark.parametrize(
    "fields",
    [
        {"loading_docks": 1},
        {"cold_storage": True},
        {"temperature_min": "-20"},
        {"reefer_plug_count": 2},
    ],
)
def test_terminal_fields_rejected_on_other_types(
    test_engine: Engine, fields: dict[str, Any]
) -> None:
    _rejected(_location, test_engine, type="port", **fields)


@pytest.mark.parametrize(
    "fields",
    [
        {},  # docks and cold_storage are mandatory
        {"loading_docks": 4},
        {"cold_storage": False},
        {"loading_docks": 0, "cold_storage": False},
        {"loading_docks": 4, "cold_storage": False, "reefer_plug_count": -1},
        {"loading_docks": 4, "cold_storage": False, "temperature_min": "2"},
        {"loading_docks": 4, "cold_storage": True, "temperature_min": "9", "temperature_max": "8"},
    ],
)
def test_terminal_requires_valid_terminal_fields(
    test_engine: Engine, fields: dict[str, Any]
) -> None:
    _rejected(_location, test_engine, type="terminal", **fields)


def test_cold_terminal_accepted(test_engine: Engine) -> None:
    _location(
        test_engine,
        type="terminal",
        loading_docks=8,
        cold_storage=True,
        temperature_min="-25.0",
        temperature_max="8.0",
        reefer_plug_count=6,
    )


# --- carriers


@pytest.mark.parametrize("value", [t.value for t in CarrierType])
def test_carrier_type_accepts_domain_values(test_engine: Engine, value: str) -> None:
    _carrier(test_engine, type=value)


def test_only_one_own_carrier(test_engine: Engine) -> None:
    _carrier(test_engine, "Demo Own Carrier Oy", type="own")
    _rejected(_carrier, test_engine, "Demo Own Carrier 2 Oy", type="own")
    _carrier(test_engine, "Demo Sub 1 Oy", type="subcontractor")
    _carrier(test_engine, "Demo Sub 2 Oy", type="subcontractor")


def test_carrier_constraints(test_engine: Engine) -> None:
    _carrier(test_engine, transport_licence_valid_until="2028-01-31")
    _rejected(_carrier, test_engine, "Demo X", type="broker")
    _rejected(_carrier, test_engine, "Demo Y", country="de")
    _rejected(_carrier, test_engine)  # duplicate name


# --- drivers


@pytest.mark.parametrize("value", [e.value for e in DriverEmployment])
def test_driver_employment_accepts_domain_values(test_engine: Engine, value: str) -> None:
    _driver(test_engine, _carrier(test_engine), employment=value)


def test_driver_constraints(test_engine: Engine) -> None:
    carrier = _carrier(test_engine)
    _driver(test_engine, carrier)
    _rejected(_driver, test_engine, carrier, "Demo Driver B", employment="freelance")
    _rejected(_driver, test_engine, carrier)  # same name at the same carrier
    _rejected(_driver, test_engine, uuid.uuid4(), "Demo Driver C")  # carrier FK
    _rejected(_driver, test_engine, carrier, "Demo Driver D", home_location_id=uuid.uuid4())
    _rejected(_driver, test_engine, carrier, " ")
    other = _carrier(test_engine, "Demo Other Oy", type="subcontractor")
    _driver(test_engine, other)  # same name is fine at another carrier


def test_driver_home_location(test_engine: Engine) -> None:
    home = _location(test_engine, type="terminal", loading_docks=3, cold_storage=False)
    _driver(test_engine, _carrier(test_engine), home_location_id=home)


def test_carrier_and_location_in_use_cannot_be_deleted(test_engine: Engine) -> None:
    home = _location(test_engine)
    carrier = _carrier(test_engine)
    _driver(test_engine, carrier, home_location_id=home)
    for table, row_id in (("locations", home), ("carriers", carrier)):
        with pytest.raises(IntegrityError), test_engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": row_id})


# --- driver qualifications


def _qualification(engine: Engine, driver_id: uuid.UUID, **kw: Any) -> uuid.UUID:
    values = {"driver_id": driver_id, "type": "gdp", "valid_until": "2027-06-30", **kw}
    return _insert(engine, "driver_qualifications", **values)


@pytest.mark.parametrize("value", [q.value for q in DriverQualificationType])
def test_qualification_type_accepts_domain_values(test_engine: Engine, value: str) -> None:
    driver = _driver(test_engine, _carrier(test_engine))
    _qualification(test_engine, driver, type=value, document_ref="DEMO-REF")


def test_qualification_constraints(test_engine: Engine) -> None:
    driver = _driver(test_engine, _carrier(test_engine))
    _qualification(test_engine, driver)
    _rejected(_qualification, test_engine, driver)  # one record per driver and type
    _rejected(_qualification, test_engine, driver, type="forklift")
    _rejected(_qualification, test_engine, driver, type="adr_tank", valid_until=None)
    _rejected(_qualification, test_engine, uuid.uuid4())  # driver FK


def test_qualifications_are_deleted_with_the_driver(test_engine: Engine) -> None:
    driver = _driver(test_engine, _carrier(test_engine))
    _qualification(test_engine, driver)
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM drivers WHERE id = :i"), {"i": driver})
        assert conn.execute(text("SELECT count(*) FROM driver_qualifications")).scalar() == 0


def test_updated_at_moves_on_orm_update(test_engine: Engine) -> None:
    from sqlalchemy.orm import sessionmaker

    from db.models import Customer

    _customer(test_engine)
    with sessionmaker(bind=test_engine)() as session:
        customer = session.query(Customer).one()
        before = customer.updated_at
        customer.pallet_exchange_agreed = True
        session.commit()
        session.refresh(customer)
        assert customer.updated_at > before
