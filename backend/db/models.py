"""ORM models. Schema changes always go through a new Alembic revision."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base
from domain.equipment import (
    LOAD_UNIT_ONLY_QUALIFICATIONS,
    BodyType,
    CouplingType,
    EquipmentQualificationType,
    EvaporatorPosition,
    LoadUnitType,
    ModelCode,
    Ownership,
    PowerSource,
    TruckType,
)
from domain.locations import LocationType
from domain.parties import CarrierType, CustomerType, DriverEmployment
from domain.qualifications import DriverQualificationType
from domain.restrictions import (
    ADR_TUNNEL_CATEGORIES,
    UNIT_BY_TYPE,
    Exemption,
    LimitUnit,
    LoadState,
    RestrictionType,
    SoloTractor,
    TollSystem,
    WeightBasis,
    WindowKind,
)


def in_list(column: str, values: type[StrEnum]) -> str:
    """CHECK expression listing a domain enum's values, sorted like the migrations."""
    return f"{column} IN ({', '.join(f"'{v.value}'" for v in sorted(values, key=str))})"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def _archived_at() -> Mapped[datetime | None]:
    """D72: NULL = active; rows are archived, not deleted."""
    return mapped_column(DateTime(timezone=True))


def _fk(column: str, name: str) -> ForeignKey:
    """Register foreign keys never cascade (D72): deleting a referenced row is refused."""
    return ForeignKey(column, ondelete="RESTRICT", name=name)


_COUNTRY_CHECK = "country ~ '^[A-Z]{2}$'"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint("role IN ('admin', 'planner', 'viewer')", name="ck_users_role"),
        CheckConstraint("theme IN ('business-light', 'control-dark')", name="ck_users_theme"),
        CheckConstraint("language IN ('en', 'fi')", name="ck_users_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # UI preferences (D49); NULL = default. Allowed values: domain/preferences.py.
    theme: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str | None] = mapped_column(String(5))


class AuthSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE", name="fk_sessions_user_id")
    )
    # SHA-256 hex digest of the cookie token. The token itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Absolute maximum lifetime; the sliding idle timeout is checked against last_seen_at.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(200))
    ip: Mapped[str | None] = mapped_column(String(45))


class Customer(Base):
    """Customers and the own company (2B-1).

    At most one row (database); exactly one is ensured by the seed and later the service layer.
    """

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_customers_name"),
        CheckConstraint(in_list("type", CustomerType), name="ck_customers_type"),
        CheckConstraint(_COUNTRY_CHECK, name="ck_customers_country"),
        CheckConstraint("btrim(name) <> ''", name="ck_customers_name_not_blank"),
        # At most one own company: a unique index over the rows of that type only.
        Index(
            "uq_customers_one_own_company",
            "type",
            unique=True,
            postgresql_where=text("type = 'own_company'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), server_default=CustomerType.CUSTOMER.value)
    # Invented identifier in demo data (never a real business ID).
    business_id: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str] = mapped_column(String(2))
    # D59: pallet exchange agreed per customer, off by default.
    pallet_exchange_agreed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    archived_at: Mapped[datetime | None] = _archived_at()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Location(Base):
    """Physical places (D13): customer sites, terminals, ports, depots, workshops and so on."""

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("name", name="uq_locations_name"),
        CheckConstraint(in_list("type", LocationType), name="ck_locations_type"),
        CheckConstraint(_COUNTRY_CHECK, name="ck_locations_country"),
        CheckConstraint("btrim(name) <> ''", name="ck_locations_name_not_blank"),
        CheckConstraint(
            "type <> 'customer_site' OR customer_id IS NOT NULL",
            name="ck_locations_customer_site_has_customer",
        ),
        CheckConstraint(
            "country <> 'FI' OR postal_code IS NULL OR postal_code ~ '^[0-9]{5}$'",
            name="ck_locations_postal_code_fi",
        ),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="ck_locations_coordinates_pair"
        ),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",
            name="ck_locations_coordinates_range",
        ),
        CheckConstraint(
            "max_vehicle_length_m IS NULL OR max_vehicle_length_m > 0",
            name="ck_locations_max_vehicle_length",
        ),
        CheckConstraint(
            "opening_hours IS NULL OR jsonb_typeof(opening_hours) = 'object'",
            name="ck_locations_opening_hours_object",
        ),
        # Terminal fields: required for terminals (D32, D33), forbidden for every other type.
        CheckConstraint(
            "(type = 'terminal' AND loading_docks IS NOT NULL AND loading_docks >= 1"
            " AND cold_storage IS NOT NULL"
            " AND (reefer_plug_count IS NULL OR reefer_plug_count >= 0)"
            " AND (cold_storage OR (temperature_min IS NULL AND temperature_max IS NULL))"
            " AND (temperature_min IS NULL OR temperature_max IS NULL"
            " OR temperature_min <= temperature_max))"
            " OR (type <> 'terminal' AND loading_docks IS NULL AND cold_storage IS NULL"
            " AND temperature_min IS NULL AND temperature_max IS NULL"
            " AND reefer_plug_count IS NULL)",
            name="ck_locations_terminal_fields",
        ),
        CheckConstraint(
            "parent_location_id IS NULL OR parent_location_id <> id",
            name="ck_locations_parent_not_self",
        ),
        CheckConstraint(
            "type = 'customer_site' OR has_loading_dock IS NULL",
            name="ck_locations_loading_dock_customer_site_only",
        ),
        Index("ix_locations_type", "type"),
        Index("ix_locations_parent_location_id", "parent_location_id"),
        Index("ix_locations_customer_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    type: Mapped[str] = mapped_column(String(20))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("customers.id", "fk_locations_customer_id")
    )
    # Optional area this place belongs to, e.g. a port terminal under its port area.
    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("locations.id", "fk_locations_parent_location_id")
    )
    name: Mapped[str] = mapped_column(String(200))
    # Free text; demo data uses invented addresses only.
    address: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    # IANA name; validated in domain.locations.validate_timezone (not expressible as a CHECK).
    timezone: Mapped[str] = mapped_column(String(64))
    # Weekly opening hours in local time; shape in domain.locations.validate_opening_hours.
    opening_hours: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    booking_required: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    max_vehicle_length_m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    side_loading_possible: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Terminal fields (type = 'terminal' only).
    loading_docks: Mapped[int | None] = mapped_column(Integer)
    cold_storage: Mapped[bool | None] = mapped_column(Boolean)
    temperature_min: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    temperature_max: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    reefer_plug_count: Mapped[int | None] = mapped_column(Integer)
    # Customer sites only: does the site have a loading dock? NULL = unknown.
    has_loading_dock: Mapped[bool | None] = mapped_column(Boolean)
    archived_at: Mapped[datetime | None] = _archived_at()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Carrier(Base):
    """A carrier: the own one or a subcontractor.

    D73: the own carrier (type 'own') links to the own company's customer row and has no name,
    business ID or country of its own; they are read from that row (one source of truth, see
    domain.parties.carrier_display_name). A subcontractor has them here and no link.
    """

    __tablename__ = "carriers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_carriers_name"),
        CheckConstraint(in_list("type", CarrierType), name="ck_carriers_type"),
        CheckConstraint(_COUNTRY_CHECK, name="ck_carriers_country"),
        CheckConstraint("btrim(name) <> ''", name="ck_carriers_name_not_blank"),
        # D73: type 'own' <=> linked to a customer row. That the row is the own company is checked
        # in domain.parties.validate_carrier_customer_link (spans two tables).
        CheckConstraint("(type = 'own') = (customer_id IS NOT NULL)", name="ck_carriers_own_link"),
        CheckConstraint(
            "(type = 'own' AND name IS NULL AND business_id IS NULL AND country IS NULL)"
            " OR (type <> 'own' AND name IS NOT NULL AND country IS NOT NULL)",
            name="ck_carriers_identity_source",
        ),
        Index("ix_carriers_customer_id", "customer_id"),
        # At most one own carrier, like the own company in customers.
        Index(
            "uq_carriers_one_own",
            "type",
            unique=True,
            postgresql_where=text("type = 'own'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("customers.id", "fk_carriers_customer_id")
    )
    # name, country and business_id: subcontractors only (own carrier: from the customer row).
    name: Mapped[str | None] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(2))
    business_id: Mapped[str | None] = mapped_column(String(40))
    # Dates (not timestamps): a licence is valid through the whole last day.
    transport_licence_valid_until: Mapped[date | None] = mapped_column(Date)
    liability_insurance_valid_until: Mapped[date | None] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = _archived_at()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Driver(Base):
    """A driver (R6). Unnamed subcontractor work has no driver row (D20)."""

    __tablename__ = "drivers"
    __table_args__ = (
        UniqueConstraint("carrier_id", "name", name="uq_drivers_carrier_id_name"),
        CheckConstraint(in_list("employment", DriverEmployment), name="ck_drivers_employment"),
        CheckConstraint("btrim(name) <> ''", name="ck_drivers_name_not_blank"),
        Index("ix_drivers_home_location_id", "home_location_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    carrier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _fk("carriers.id", "fk_drivers_carrier_id")
    )
    name: Mapped[str] = mapped_column(String(200))
    # Where the driver returns to and takes weekly rest (R6).
    home_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("locations.id", "fk_drivers_home_location_id")
    )
    employment: Mapped[str] = mapped_column(String(20))
    archived_at: Mapped[datetime | None] = _archived_at()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class DriverQualification(Base):
    """Driver qualification period (D67). Vehicle eligibility: own table in 2B-2."""

    __tablename__ = "driver_qualifications"
    __table_args__ = (
        CheckConstraint("valid_from <= valid_until", name="ck_driver_qualifications_period"),
        # History (D67): periods of one driver and type never overlap (both ends inclusive).
        # Needs the btree_gist extension for = on uuid and varchar inside a gist index.
        ExcludeConstraint(
            ("driver_id", "="),
            ("type", "="),
            (text("daterange(valid_from, valid_until, '[]')"), "&&"),
            using="gist",
            name="ex_driver_qualifications_no_overlap",
        ),
        Index("ix_driver_qualifications_driver_id", "driver_id"),
        CheckConstraint(
            in_list("type", DriverQualificationType), name="ck_driver_qualifications_type"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _fk("drivers.id", "fk_driver_qualifications_driver_id")
    )
    type: Mapped[str] = mapped_column(String(30))
    # Validity period, both ends inclusive. A renewal is a new row, so the history is kept.
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    document_ref: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


# --- Fleet (2B-2). Every foreign key is RESTRICT (D72); registrations are invented in demo data.

_VEHICLE_CHECKS = (
    "length_m > 0 AND kerb_weight_kg > 0 AND max_gross_weight_kg >= kerb_weight_kg AND axles >= 1"
)
LOAD_UNIT_ONLY_TYPES_SQL = ", ".join(f"'{t.value}'" for t in sorted(LOAD_UNIT_ONLY_QUALIFICATIONS))


class Truck(Base):
    """Tractor unit or rigid truck (D39). A rigid truck's body is a `load_units` row (D60)."""

    __tablename__ = "trucks"
    __table_args__ = (
        UniqueConstraint("registration", name="uq_trucks_registration"),
        CheckConstraint(in_list("type", TruckType), name="ck_trucks_type"),
        CheckConstraint("btrim(registration) <> ''", name="ck_trucks_registration_not_blank"),
        CheckConstraint(_VEHICLE_CHECKS, name="ck_trucks_dimensions"),
        # The fifth wheel (and a low one) belong to tractors, the drawbar hitch to rigid trucks.
        CheckConstraint(
            "fifth_wheel_from_front_m IS NULL OR (type = 'tractor' AND fifth_wheel_from_front_m > 0"
            " AND fifth_wheel_from_front_m <= length_m)",
            name="ck_trucks_fifth_wheel",
        ),
        CheckConstraint(
            "NOT low_fifth_wheel OR type = 'tractor'", name="ck_trucks_low_fifth_wheel_tractor"
        ),
        CheckConstraint(
            "NOT drawbar_hitch OR type = 'rigid_truck'", name="ck_trucks_drawbar_hitch_rigid"
        ),
        CheckConstraint(
            "max_combination_weight_kg IS NULL OR max_combination_weight_kg >= max_gross_weight_kg",
            name="ck_trucks_max_combination_weight",
        ),
        Index("ix_trucks_carrier_id", "carrier_id"),
        Index("ix_trucks_home_location_id", "home_location_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    carrier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _fk("carriers.id", "fk_trucks_carrier_id")
    )
    registration: Mapped[str] = mapped_column(String(30))
    type: Mapped[str] = mapped_column(String(20))
    length_m: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    kerb_weight_kg: Mapped[int] = mapped_column(Integer)
    max_gross_weight_kg: Mapped[int] = mapped_column(Integer)
    axles: Mapped[int] = mapped_column(Integer)
    # Distance from the front of the truck to the fifth wheel (tractors); used for combination
    # length (a semi-trailer's front part lies over the tractor).
    fifth_wheel_from_front_m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    # Low fifth wheel: needed to pull a mega trailer (compatibility).
    low_fifth_wheel: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Rigid trucks: towing device for a dolly or a full / centre-axle trailer.
    drawbar_hitch: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # The truck's own limit for a whole combination; NULL = not recorded.
    max_combination_weight_kg: Mapped[int | None] = mapped_column(Integer)
    # Base location (where the truck normally starts and returns); NULL = none.
    home_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("locations.id", "fk_trucks_home_location_id")
    )
    archived_at: Mapped[datetime | None] = _archived_at()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Dolly(Base):
    """Converter dolly (D61): equipment without a load unit, coupled to a leg.

    `length_m` runs from the drawbar eye to the dolly's fifth wheel (see domain.combinations).
    """

    __tablename__ = "dollies"
    __table_args__ = (
        UniqueConstraint("registration", name="uq_dollies_registration"),
        CheckConstraint("btrim(registration) <> ''", name="ck_dollies_registration_not_blank"),
        CheckConstraint(_VEHICLE_CHECKS, name="ck_dollies_dimensions"),
        Index("ix_dollies_carrier_id", "carrier_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    carrier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _fk("carriers.id", "fk_dollies_carrier_id")
    )
    registration: Mapped[str] = mapped_column(String(30))
    length_m: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    kerb_weight_kg: Mapped[int] = mapped_column(Integer)
    max_gross_weight_kg: Mapped[int] = mapped_column(Integer)
    axles: Mapped[int] = mapped_column(Integer)
    archived_at: Mapped[datetime | None] = _archived_at()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class LoadUnit(Base):
    """Load unit (D60): a trailer or the fixed body of a rigid truck. Trips follow load units.

    A fixed body takes length, weights and axles from its truck (stored only there); a trailer
    has them here. ATP class and inspections are periods in equipment_qualifications (D67).
    """

    __tablename__ = "load_units"
    __table_args__ = (
        UniqueConstraint("registration", name="uq_load_units_registration"),
        # One fixed body per truck (NULL for trailers does not collide).
        UniqueConstraint("truck_id", name="uq_load_units_truck_id"),
        CheckConstraint(in_list("type", LoadUnitType), name="ck_load_units_type"),
        CheckConstraint(in_list("body_type", BodyType), name="ck_load_units_body_type"),
        CheckConstraint(in_list("ownership", Ownership), name="ck_load_units_ownership"),
        CheckConstraint(in_list("coupling_type", CouplingType), name="ck_load_units_coupling_type"),
        CheckConstraint(in_list("model_code", ModelCode), name="ck_load_units_model_code"),
        # D75: the thermo codes FB, FD, FS go with reefer bodies and the others do not. The code
        # does not decide any feature, except that FS (Thermo Side) has side doors.
        CheckConstraint(
            "model_code IS NULL OR ((model_code IN ('FB', 'FD', 'FS')) = (body_type = 'reefer'))",
            name="ck_load_units_model_code_body",
        ),
        CheckConstraint(
            "model_code IS DISTINCT FROM 'FS' OR side_doors", name="ck_load_units_fs_side_doors"
        ),
        # D76: only FD has a partition, and every FD has one.
        CheckConstraint(
            "partition = coalesce(model_code = 'FD', false)", name="ck_load_units_partition_fd"
        ),
        # D76: partition values (only used when partition is true).
        CheckConstraint(
            "partition_thickness_mm > 0 AND partition_step_pallet_rows >= 1"
            " AND min_pallets_front >= 0 AND min_pallets_rear >= 0"
            " AND (partition_max_rear_share IS NULL"
            " OR (partition AND partition_max_rear_share > 0 AND partition_max_rear_share <= 1))",
            name="ck_load_units_partition_values",
        ),
        # A trailer has a coupling type; a fixed body has none (it is part of its truck).
        CheckConstraint(
            "(type = 'fixed_body') = (coupling_type IS NULL)", name="ck_load_units_coupling_link"
        ),
        # D25: a semi-trailer has no tail lift.
        CheckConstraint(
            "coupling_type IS DISTINCT FROM 'semi_trailer' OR NOT tail_lift",
            name="ck_load_units_semi_trailer_no_tail_lift",
        ),
        # Kingpin position: semi-trailers only, inside the outer length.
        CheckConstraint(
            "kingpin_from_front_m IS NULL OR (coupling_type IS NOT DISTINCT FROM 'semi_trailer'"
            " AND kingpin_from_front_m > 0 AND kingpin_from_front_m < external_length_m)",
            name="ck_load_units_kingpin",
        ),
        CheckConstraint(
            "(external_height_m IS NULL OR external_height_m > 0)"
            " AND (external_width_m IS NULL OR external_width_m > 0)",
            name="ck_load_units_external_size",
        ),
        # The body of a rigid truck is not lifted onto a train on its own (D63).
        CheckConstraint(
            "type <> 'fixed_body' OR NOT rail_craneable", name="ck_load_units_fixed_body_no_rail"
        ),
        CheckConstraint("btrim(registration) <> ''", name="ck_load_units_registration_not_blank"),
        CheckConstraint(
            "(type = 'fixed_body') = (truck_id IS NOT NULL)", name="ck_load_units_truck_link"
        ),
        # Trailer: the vehicle-level fields are required; fixed body: they live on the truck.
        CheckConstraint(
            "(type = 'trailer' AND external_length_m IS NOT NULL AND kerb_weight_kg IS NOT NULL"
            " AND max_gross_weight_kg IS NOT NULL AND axles IS NOT NULL)"
            " OR (type = 'fixed_body' AND external_length_m IS NULL AND kerb_weight_kg IS NULL"
            " AND max_gross_weight_kg IS NULL AND axles IS NULL)",
            name="ck_load_units_vehicle_fields",
        ),
        CheckConstraint(
            "external_length_m IS NULL OR (external_length_m > 0 AND kerb_weight_kg > 0"
            " AND max_gross_weight_kg >= kerb_weight_kg AND axles >= 1)",
            name="ck_load_units_vehicle_values",
        ),
        CheckConstraint(
            "internal_length_m > 0 AND internal_width_m > 0 AND internal_height_m > 0"
            " AND (door_height_m IS NULL OR door_height_m > 0)"
            " AND (ldm IS NULL OR ldm > 0) AND (pallet_places IS NULL OR pallet_places >= 0)",
            name="ck_load_units_cargo_space",
        ),
        CheckConstraint(
            "lease_valid_from IS NULL OR lease_valid_until IS NULL"
            " OR lease_valid_from <= lease_valid_until",
            name="ck_load_units_lease_period",
        ),
        # Leased / rented: the lease start is required (the end may be open); otherwise no dates.
        CheckConstraint(
            "(ownership IN ('leased', 'rented') AND lease_valid_from IS NOT NULL)"
            " OR (ownership NOT IN ('leased', 'rented') AND lease_valid_from IS NULL"
            " AND lease_valid_until IS NULL)",
            name="ck_load_units_lease_by_ownership",
        ),
        Index("ix_load_units_carrier_id", "carrier_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    type: Mapped[str] = mapped_column(String(20))
    truck_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("trucks.id", "fk_load_units_truck_id")
    )
    # Owner or holder.
    carrier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _fk("carriers.id", "fk_load_units_carrier_id")
    )
    # Registration plate, or an invented identifier for a body that has no plate of its own.
    registration: Mapped[str] = mapped_column(String(30))
    body_type: Mapped[str] = mapped_column(String(20))
    # D55: how a trailer is coupled; NULL for a fixed body.
    coupling_type: Mapped[str | None] = mapped_column(String(20))
    # D75: model code (FB, FD, FS, CS, MEGA, COIL; invented thermo codes). NULL = no code.
    model_code: Mapped[str | None] = mapped_column(String(10))
    internal_length_m: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    internal_width_m: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    internal_height_m: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    door_height_m: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    external_length_m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    # Semi-trailers: distance from the front of the trailer to the kingpin.
    kingpin_from_front_m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    external_height_m: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    external_width_m: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    ldm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pallet_places: Mapped[int | None] = mapped_column(Integer)
    kerb_weight_kg: Mapped[int | None] = mapped_column(Integer)
    max_gross_weight_kg: Mapped[int | None] = mapped_column(Integer)
    axles: Mapped[int | None] = mapped_column(Integer)
    # D36 special features (simple choices on the load unit).
    xl_certified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    coil_well: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    tir_cable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    top_loading: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    tail_lift: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Side doors (side loading on a body that has no curtains, e.g. a thermo FS, D75).
    side_doors: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # D76: partition (bulkhead) from the roof; values are per load unit and used when partition
    # is true. Thickness in mm, step in pallet rows (1 row = 2 EUR pallets), minimum pallets per
    # compartment (EUR pallets).
    partition: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    partition_thickness_mm: Mapped[int] = mapped_column(Integer, server_default=text("50"))
    partition_step_pallet_rows: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    min_pallets_front: Mapped[int] = mapped_column(Integer, server_default=text("4"))
    min_pallets_rear: Mapped[int] = mapped_column(Integer, server_default=text("4"))
    # Largest share of the rear compartment (e.g. 0.333 = 1/3), when the machine limits it;
    # NULL = no limit.
    partition_max_rear_share: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    # D63: physically suitable for rail (craneable); Plan Check tests it.
    rail_craneable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Relative to the holder `carrier_id`; see domain.equipment.Ownership.
    ownership: Mapped[str] = mapped_column(String(20), server_default=Ownership.OWN.value)
    # Dates, both ends inclusive. NULL end of a lease = open-ended.
    lease_valid_from: Mapped[date | None] = mapped_column(Date)
    lease_valid_until: Mapped[date | None] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = _archived_at()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class ReeferUnit(Base):
    """Refrigeration unit (the machine, at the front) of a reefer load unit (D47, D76): at most
    one per load unit. Power source and reefer service belong to the machine; the zones are
    served by its evaporators. Which body types may have one is checked in the domain."""

    __tablename__ = "reefer_units"
    __table_args__ = (
        UniqueConstraint("load_unit_id", name="uq_reefer_units_load_unit_id"),
        # Target of the composite foreign key of evaporators (an evaporator's machine must belong
        # to the same load unit).
        UniqueConstraint("id", "load_unit_id", name="uq_reefer_units_id_load_unit_id"),
        CheckConstraint(in_list("power_source", PowerSource), name="ck_reefer_units_power_source"),
        CheckConstraint("btrim(unit_name) <> ''", name="ck_reefer_units_unit_name_not_blank"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # The unique constraint above also serves lookups by load_unit_id.
    load_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _fk("load_units.id", "fk_reefer_units_load_unit_id")
    )
    # Invented make and model in demo data.
    unit_name: Mapped[str] = mapped_column(String(100))
    power_source: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class ReeferEvaporator(Base):
    """Evaporator (indoor unit) of a reefer unit (D76): FB and FS have one, FD two (front and
    rear of the partition). The counts are domain checks; the position is unique per machine."""

    __tablename__ = "reefer_evaporators"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reefer_unit_id", "load_unit_id"],
            ["reefer_units.id", "reefer_units.load_unit_id"],
            ondelete="RESTRICT",
            name="fk_reefer_evaporators_reefer_unit_id",
        ),
        UniqueConstraint(
            "reefer_unit_id", "position", name="uq_reefer_evaporators_reefer_unit_id_position"
        ),
        # Target of the composite foreign key of compartments.
        UniqueConstraint("id", "load_unit_id", name="uq_reefer_evaporators_id_load_unit_id"),
        CheckConstraint(
            in_list("position", EvaporatorPosition), name="ck_reefer_evaporators_position"
        ),
        Index("ix_reefer_evaporators_load_unit_id", "load_unit_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    reefer_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Denormalised from the machine so that compartments can check the same load unit.
    load_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    position: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Compartment(Base):
    """Temperature compartment (zone) of a reefer load unit (D47, D76).

    The model code fixes the zones (FB, FS one; FD two). `evaporator_id` is the evaporator
    serving this compartment (NULL = not recorded); an evaporator serves at most one compartment.
    """

    __tablename__ = "compartments"
    __table_args__ = (
        UniqueConstraint("load_unit_id", "number", name="uq_compartments_load_unit_id_number"),
        # The serving evaporator must belong to the same load unit (MATCH SIMPLE: skipped when
        # NULL).
        ForeignKeyConstraint(
            ["evaporator_id", "load_unit_id"],
            ["reefer_evaporators.id", "reefer_evaporators.load_unit_id"],
            ondelete="RESTRICT",
            name="fk_compartments_evaporator_id",
        ),
        UniqueConstraint("evaporator_id", name="uq_compartments_evaporator_id"),
        CheckConstraint("number >= 1", name="ck_compartments_number"),
        CheckConstraint(
            "pallet_places IS NULL OR pallet_places >= 0", name="ck_compartments_pallet_places"
        ),
        CheckConstraint("temperature_min <= temperature_max", name="ck_compartments_temperature"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # The unique constraint above also serves lookups by load_unit_id.
    load_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _fk("load_units.id", "fk_compartments_load_unit_id")
    )
    evaporator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    number: Mapped[int] = mapped_column(Integer)
    # Degrees Celsius, the range the compartment can hold.
    temperature_min: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    temperature_max: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    # Nominal EUR pallet places of this compartment (optional); with a partition they come from
    # the partition position (domain.equipment.partition_positions). Per pallet type: pallet_types.
    pallet_places: Mapped[int | None] = mapped_column(Integer)
    # The set point of this compartment is controlled independently of the others (D76).
    independently_controlled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class EquipmentQualification(Base):
    """Equipment eligibility period (D70, D67): ATP, inspection, tail lift, GDP mapping, ADR."""

    __tablename__ = "equipment_qualifications"
    __table_args__ = (
        CheckConstraint(
            in_list("type", EquipmentQualificationType), name="ck_equipment_qualifications_type"
        ),
        CheckConstraint("valid_from <= valid_until", name="ck_equipment_qualifications_period"),
        # Exactly one subject.
        CheckConstraint(
            "num_nonnulls(truck_id, dolly_id, load_unit_id, reefer_unit_id) = 1",
            name="ck_equipment_qualifications_one_subject",
        ),
        # D76: reefer service belongs to a reefer unit, and a reefer unit takes nothing else.
        CheckConstraint(
            "(type = 'reefer_service') = (reefer_unit_id IS NOT NULL)",
            name="ck_equipment_qualifications_reefer_service",
        ),
        CheckConstraint(
            f"type NOT IN ({LOAD_UNIT_ONLY_TYPES_SQL}) OR load_unit_id IS NOT NULL",
            name="ck_equipment_qualifications_load_unit_only_types",
        ),
        CheckConstraint(
            "class_code IS NULL OR btrim(class_code) <> ''",
            name="ck_equipment_qualifications_class_code_not_blank",
        ),
        # History (D67): periods of one subject and type never overlap (both ends inclusive).
        # The subject is spread over four columns; the CHECK above makes exactly one non-null, so
        # coalesce() yields a single key. (Needs btree_gist, created in c52d8e3f1a47.)
        ExcludeConstraint(
            (text("coalesce(truck_id, dolly_id, load_unit_id, reefer_unit_id)"), "="),
            ("type", "="),
            (text("daterange(valid_from, valid_until, '[]')"), "&&"),
            using="gist",
            name="ex_equipment_qualifications_no_overlap",
        ),
        Index("ix_equipment_qualifications_truck_id", "truck_id"),
        Index("ix_equipment_qualifications_dolly_id", "dolly_id"),
        Index("ix_equipment_qualifications_load_unit_id", "load_unit_id"),
        Index("ix_equipment_qualifications_reefer_unit_id", "reefer_unit_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    truck_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("trucks.id", "fk_equipment_qualifications_truck_id")
    )
    dolly_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("dollies.id", "fk_equipment_qualifications_dolly_id")
    )
    load_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("load_units.id", "fk_equipment_qualifications_load_unit_id")
    )
    reefer_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _fk("reefer_units.id", "fk_equipment_qualifications_reefer_unit_id")
    )
    type: Mapped[str] = mapped_column(String(30))
    # Optional classification, e.g. the ATP class of a thermo body.
    class_code: Mapped[str | None] = mapped_column(String(10))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    document_ref: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


# --- Countries and road restrictions (2B-3a, D84). Reference data with a source per row; the
# legal values are never written from memory. Plan Check uses them in phase 5.

_SOURCE_CHECKS = (
    "source_url ~ '^https://'",
    "checked_on >= DATE '2026-01-01'",
)
_REGION_CHECK = (
    "region IS NULL OR (region ~ '^[A-Z]{2}-[A-Z0-9]{1,3}$' AND left(region, 2) = country)"
)
# Month 1-12 and day 1-31 (the exact day per month is checked by domain.restrictions.month_day).
_SEASON_CHECK = (
    "(season_start IS NULL) = (season_end IS NULL)"
    " AND (season_start IS NULL OR (season_start / 100 BETWEEN 1 AND 12"
    " AND season_start % 100 BETWEEN 1 AND 31 AND season_end / 100 BETWEEN 1 AND 12"
    " AND season_end % 100 BETWEEN 1 AND 31))"
)


def _source_checks(table: str) -> tuple[CheckConstraint, CheckConstraint]:
    return (
        CheckConstraint(_SOURCE_CHECKS[0], name=f"ck_{table}_source_url"),
        CheckConstraint(_SOURCE_CHECKS[1], name=f"ck_{table}_checked_on"),
    )


def _sql_list(values: list[str] | tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in sorted(values))


_KG_TYPES = _sql_list([t.value for t, u in UNIT_BY_TYPE.items() if u is LimitUnit.KG])
_TUNNEL_CATEGORIES = _sql_list(ADR_TUNNEL_CATEGORIES)
_MM_TYPES = _sql_list([t.value for t, u in UNIT_BY_TYPE.items() if u is LimitUnit.MM])


class Country(Base):
    """A country that matters for road rules (D84). Key: ISO 3166-1 alpha-2 code."""

    __tablename__ = "countries"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z]{2}$'", name="ck_countries_code"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_countries_currency"),
        CheckConstraint(
            "btrim(name_en) <> '' AND btrim(name_fi) <> ''", name="ck_countries_names_not_blank"
        ),
    )

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(100))
    name_fi: Mapped[str] = mapped_column(String(100))
    time_zone: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3))
    eu_member: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class CountryRule(Base):
    """General road rules of a country for one validity period (D67, D84). NULL = not recorded."""

    __tablename__ = "country_rules"
    __table_args__ = (
        CheckConstraint(
            "valid_until IS NULL OR valid_from <= valid_until", name="ck_country_rules_period"
        ),
        ExcludeConstraint(
            ("country", "="),
            (text("daterange(valid_from, valid_until, '[]')"), "&&"),
            using="gist",
            name="ex_country_rules_no_overlap",
        ),
        CheckConstraint(in_list("toll_system", TollSystem), name="ck_country_rules_toll_system"),
        CheckConstraint(
            "(truck_speed_motorway_kmh IS NULL OR truck_speed_motorway_kmh BETWEEN 1 AND 200)"
            " AND (truck_speed_other_kmh IS NULL OR truck_speed_other_kmh BETWEEN 1 AND 200)",
            name="ck_country_rules_speeds",
        ),
        CheckConstraint(
            "(speed_over_gross_weight_kg IS NULL) = (speed_weight_basis IS NULL)"
            " AND (speed_over_gross_weight_kg IS NULL OR speed_over_gross_weight_kg > 0)"
            " AND (speed_weight_basis IS NULL OR "
            + in_list("speed_weight_basis", WeightBasis)
            + ") AND ((truck_speed_motorway_kmh IS NULL AND truck_speed_other_kmh IS NULL)"
            " OR speed_over_gross_weight_kg IS NOT NULL)",
            name="ck_country_rules_speed_class",
        ),
        CheckConstraint(
            "(max_gross_weight_kg IS NULL OR max_gross_weight_kg > 0)"
            " AND (max_length_mm IS NULL OR max_length_mm > 0)",
            name="ck_country_rules_limits",
        ),
        CheckConstraint(
            _SEASON_CHECK.replace("season_", "winter_equipment_"),
            name="ck_country_rules_winter_season",
        ),
        *_source_checks("country_rules"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    country: Mapped[str] = mapped_column(
        String(2), _fk("countries.code", "fk_country_rules_country")
    )
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)  # NULL = until further notice
    # Speed limits for heavy goods vehicles: motorways, and other roads outside built-up areas.
    truck_speed_motorway_kmh: Mapped[int | None] = mapped_column(SmallInteger)
    truck_speed_other_kmh: Mapped[int | None] = mapped_column(SmallInteger)
    # D87: the vehicle class the speeds apply to (over this gross weight, of the vehicle or the
    # combination). Required once a speed is recorded.
    speed_over_gross_weight_kg: Mapped[int | None] = mapped_column(Integer)
    speed_weight_basis: Mapped[str | None] = mapped_column(String(15))
    # D89: maximum gross weight and length of a semi-trailer combination (tractor and
    # semi-trailer, five axles) in national traffic on the general road network. Other axle
    # counts and full-trailer combinations are in the note. The EU limit for international
    # traffic is domain.eu_limits; Plan Check uses the strictest value along the route.
    max_gross_weight_kg: Mapped[int | None] = mapped_column(Integer)
    max_length_mm: Mapped[int | None] = mapped_column(Integer)
    # D89: only whether HCT/EMS combinations are allowed in the country at all; their limits
    # and networks are road_restrictions rows of type hct_route.
    hct_allowed: Mapped[bool | None] = mapped_column(Boolean)
    # Season of winter equipment requirements, MMDD (may run over the new year).
    winter_equipment_start: Mapped[int | None] = mapped_column(SmallInteger)
    winter_equipment_end: Mapped[int | None] = mapped_column(SmallInteger)
    toll_system: Mapped[str | None] = mapped_column(String(20))
    posted_worker_declaration: Mapped[bool | None] = mapped_column(Boolean)
    cabotage_note: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    checked_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class PublicHoliday(Base):
    """A holiday that a country's road rules refer to, nationwide or in one region (ISO 3166-2,
    e.g. DE-BY) (D84). Only the holidays the rules name: e.g. Germany's driving ban lists its own
    days (§ 30(4) StVO), so a regional holiday outside that list is not a row here."""

    __tablename__ = "public_holidays"
    __table_args__ = (
        UniqueConstraint(
            "country",
            "region",
            "holiday_date",
            name="uq_public_holidays_country_region_date",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(_REGION_CHECK, name="ck_public_holidays_region"),
        CheckConstraint("btrim(name_local) <> ''", name="ck_public_holidays_name_not_blank"),
        Index("ix_public_holidays_date", "holiday_date"),
        *_source_checks("public_holidays"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    country: Mapped[str] = mapped_column(
        String(2), _fk("countries.code", "fk_public_holidays_country")
    )
    region: Mapped[str | None] = mapped_column(String(6))
    holiday_date: Mapped[date] = mapped_column(Date)
    name_local: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(Text)
    checked_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class RoadRestriction(Base):
    """A driving ban, a weight or dimension limit, an HCT route, an ADR tunnel or an environmental
    zone in a country, a region or on a road section (D84). Rules: domain/restrictions.py."""

    __tablename__ = "road_restrictions"
    __table_args__ = (
        CheckConstraint(
            in_list("restriction_type", RestrictionType), name="ck_road_restrictions_type"
        ),
        CheckConstraint(
            f"limit_unit IS NULL OR {in_list('limit_unit', LimitUnit)}",
            name="ck_road_restrictions_limit_unit",
        ),
        CheckConstraint(in_list("load_state", LoadState), name="ck_road_restrictions_load_state"),
        CheckConstraint(
            in_list("weight_basis", WeightBasis), name="ck_road_restrictions_weight_basis"
        ),
        CheckConstraint(
            f"solo_tractor IS NULL OR (restriction_type = 'driving_ban'"
            f" AND {in_list('solo_tractor', SoloTractor)})",
            name="ck_road_restrictions_solo_tractor",
        ),
        # A limit has a positive value in its unit; other types have none (validate_restriction).
        # coalesce(): a NULL would make the expression unknown, and CHECK lets unknown pass.
        CheckConstraint(
            f"(restriction_type IN ({_KG_TYPES}) AND coalesce(limit_value, 0) > 0"
            " AND coalesce(limit_unit, '') = 'kg')"
            f" OR (restriction_type IN ({_MM_TYPES}) AND coalesce(limit_value, 0) > 0"
            " AND coalesce(limit_unit, '') = 'mm')"
            f" OR (restriction_type NOT IN ({_KG_TYPES}, {_MM_TYPES})"
            " AND limit_value IS NULL AND limit_unit IS NULL)",
            name="ck_road_restrictions_limit",
        ),
        CheckConstraint(
            "(restriction_type = 'adr_tunnel') = (tunnel_category IS NOT NULL)"
            f" AND (tunnel_category IS NULL OR tunnel_category IN ({_TUNNEL_CATEGORIES}))",
            name="ck_road_restrictions_tunnel_category",
        ),
        CheckConstraint(
            f"exemptions <@ ARRAY[{_sql_list([e.value for e in Exemption])}]::varchar[]",
            name="ck_road_restrictions_exemptions",
        ),
        CheckConstraint(
            "over_gross_weight_kg IS NULL OR over_gross_weight_kg > 0",
            name="ck_road_restrictions_over_gross_weight",
        ),
        UniqueConstraint("code", name="uq_road_restrictions_code"),
        CheckConstraint("code ~ '^[A-Z]{2}-[A-Z0-9-]+$'", name="ck_road_restrictions_code"),
        CheckConstraint(_REGION_CHECK, name="ck_road_restrictions_region"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from <= valid_until", name="ck_road_restrictions_period"
        ),
        CheckConstraint(
            "road_ref IS NULL OR btrim(road_ref) <> ''", name="ck_road_restrictions_road_ref"
        ),
        # Target of the windows' composite key: only driving bans have windows.
        UniqueConstraint("id", "restriction_type", name="uq_road_restrictions_id_type"),
        Index("ix_road_restrictions_country_type", "country", "restriction_type"),
        *_source_checks("road_restrictions"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Stable key of a reference row, e.g. DE-SUNDAY-HOLIDAY-BAN; the loader matches on it.
    code: Mapped[str] = mapped_column(String(60))
    country: Mapped[str] = mapped_column(
        String(2), _fk("countries.code", "fk_road_restrictions_country")
    )
    region: Mapped[str | None] = mapped_column(String(6))
    road_ref: Mapped[str | None] = mapped_column(String(40))  # e.g. a road number
    section: Mapped[str | None] = mapped_column(Text)  # where on the road, in words
    restriction_type: Mapped[str] = mapped_column(String(30))
    limit_value: Mapped[int | None] = mapped_column(Integer)
    limit_unit: Mapped[str | None] = mapped_column(String(2))
    tunnel_category: Mapped[str | None] = mapped_column(String(1))
    # Who it applies to: vehicles over this permissible gross weight (NULL = all), ADR only,
    # load state.
    over_gross_weight_kg: Mapped[int | None] = mapped_column(Integer)
    weight_basis: Mapped[str] = mapped_column(
        String(15), server_default=text("'vehicle'"), default=WeightBasis.VEHICLE.value
    )
    # Also any truck towing a trailer, whatever its weight (e.g. § 30(3) StVO).
    with_trailer_any_weight: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False
    )
    # Driving bans: a tractor unit without a trailer (D85). NULL = not recorded.
    solo_tractor: Mapped[str | None] = mapped_column(String(15))
    adr_only: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), default=False)
    load_state: Mapped[str] = mapped_column(
        String(10), server_default=text("'any'"), default=LoadState.ANY.value
    )
    exemptions: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), server_default=text("'{}'::varchar[]"), default=list
    )
    note: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)  # NULL = until further notice
    source_url: Mapped[str] = mapped_column(Text)
    checked_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class RoadRestrictionWindow(Base):
    """When a driving ban applies (D84): weekdays, public holidays, the day before one, or one
    calendar date; a local time within one day, optionally only in a yearly season (MMDD).
    Rules: BanWindow."""

    __tablename__ = "road_restriction_windows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["restriction_id", "restriction_type"],
            ["road_restrictions.id", "road_restrictions.restriction_type"],
            ondelete="RESTRICT",
            name="fk_road_restriction_windows_restriction",
        ),
        CheckConstraint(
            "restriction_type = 'driving_ban'", name="ck_road_restriction_windows_driving_ban"
        ),
        CheckConstraint(in_list("kind", WindowKind), name="ck_road_restriction_windows_kind"),
        CheckConstraint(
            "end_time IS NULL OR end_time > start_time", name="ck_road_restriction_windows_times"
        ),
        # Distinct weekdays: checked by BanWindow (a CHECK cannot hold a subquery).
        CheckConstraint(
            "(kind = 'weekdays') = (cardinality(weekdays) > 0)"
            " AND weekdays <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]",
            name="ck_road_restriction_windows_weekdays",
        ),
        CheckConstraint(_SEASON_CHECK, name="ck_road_restriction_windows_season"),
        CheckConstraint(
            "(kind = 'date') = (on_date IS NOT NULL) AND (kind <> 'date' OR season_start IS NULL)",
            name="ck_road_restriction_windows_date",
        ),
        Index("ix_road_restriction_windows_restriction_id", "restriction_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    restriction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    restriction_type: Mapped[str] = mapped_column(
        String(30), server_default=text("'driving_ban'"), default=RestrictionType.DRIVING_BAN.value
    )
    kind: Mapped[str] = mapped_column(String(20))
    weekdays: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), server_default=text("'{}'::smallint[]"), default=list
    )
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)  # NULL = until midnight
    season_start: Mapped[int | None] = mapped_column(SmallInteger)  # MMDD
    season_end: Mapped[int | None] = mapped_column(SmallInteger)
    on_date: Mapped[date | None] = mapped_column(Date)  # kind 'date' only
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()
