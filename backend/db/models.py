"""ORM models. Schema changes always go through a new Alembic revision."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base
from domain.locations import LocationType
from domain.parties import CarrierType, CustomerType, DriverEmployment
from domain.qualifications import DriverQualificationType


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
        UUID(as_uuid=True), ForeignKey("customers.id", name="fk_locations_customer_id")
    )
    # Optional area this place belongs to, e.g. a port terminal under its port area.
    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", name="fk_locations_parent_location_id")
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
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Carrier(Base):
    __tablename__ = "carriers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_carriers_name"),
        CheckConstraint(in_list("type", CarrierType), name="ck_carriers_type"),
        CheckConstraint(_COUNTRY_CHECK, name="ck_carriers_country"),
        CheckConstraint("btrim(name) <> ''", name="ck_carriers_name_not_blank"),
        # At most one own carrier, like the own company in customers.
        Index(
            "uq_carriers_one_own",
            "type",
            unique=True,
            postgresql_where=text("type = 'own'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2))
    business_id: Mapped[str | None] = mapped_column(String(40))
    # Dates (not timestamps): a licence is valid through the whole last day.
    transport_licence_valid_until: Mapped[date | None] = mapped_column(Date)
    liability_insurance_valid_until: Mapped[date | None] = mapped_column(Date)
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
        UUID(as_uuid=True), ForeignKey("carriers.id", name="fk_drivers_carrier_id")
    )
    name: Mapped[str] = mapped_column(String(200))
    # Where the driver returns to and takes weekly rest (R6).
    home_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", name="fk_drivers_home_location_id")
    )
    employment: Mapped[str] = mapped_column(String(20))
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
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE", name="fk_driver_qualifications_driver_id"),
    )
    type: Mapped[str] = mapped_column(String(30))
    # Validity period, both ends inclusive. A renewal is a new row, so the history is kept.
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    document_ref: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()
