"""create customers, locations, carriers, drivers and driver_qualifications

Revision ID: c52d8e3f1a47
Revises: a1c4e7d90b25
Create Date: 2026-11-18

Phase 2B-1 (data model v1, base registers). Allowed values are VARCHAR + CHECK (same approach as
users.role); the lists must match the domain modules (tests/test_domain_*.py compare them).
Opening hours are JSONB (weekly intervals, validated in domain.locations). Validity dates are
DATE. The unique partial indexes uq_customers_one_own_company and uq_carriers_one_own allow at most one
own company and one own carrier.
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c52d8e3f1a47"
down_revision = "a1c4e7d90b25"
branch_labels = None
depends_on = None


def _id() -> sa.Column[Any]:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "customers",
        _id(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=20), server_default="customer", nullable=False),
        sa.Column("business_id", sa.String(length=40), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column(
            "pallet_exchange_agreed", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_customers_name"),
        sa.CheckConstraint("type IN ('customer', 'own_company')", name="ck_customers_type"),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_customers_country"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_customers_name_not_blank"),
    )
    op.create_index(
        "uq_customers_one_own_company",
        "customers",
        ["type"],
        unique=True,
        postgresql_where=sa.text("type = 'own_company'"),
    )

    op.create_table(
        "locations",
        _id(),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("opening_hours", postgresql.JSONB(), nullable=True),
        sa.Column("booking_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("max_vehicle_length_m", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "side_loading_possible", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("loading_docks", sa.Integer(), nullable=True),
        sa.Column("cold_storage", sa.Boolean(), nullable=True),
        sa.Column("temperature_min", sa.Numeric(4, 1), nullable=True),
        sa.Column("temperature_max", sa.Numeric(4, 1), nullable=True),
        sa.Column("reefer_plug_count", sa.Integer(), nullable=True),
        sa.Column("has_loading_dock", sa.Boolean(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_locations_customer_id"),
        sa.ForeignKeyConstraint(
            ["parent_location_id"], ["locations.id"], name="fk_locations_parent_location_id"
        ),
        sa.UniqueConstraint("name", name="uq_locations_name"),
        sa.CheckConstraint(
            "type IN ('customer_site', 'customs_office', 'depot', 'fuel', 'inspection', "
            "'parking', 'port', 'rail_terminal', 'terminal', 'wash', 'workshop')",
            name="ck_locations_type",
        ),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_locations_country"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_locations_name_not_blank"),
        sa.CheckConstraint(
            "type <> 'customer_site' OR customer_id IS NOT NULL",
            name="ck_locations_customer_site_has_customer",
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="ck_locations_coordinates_pair"
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",
            name="ck_locations_coordinates_range",
        ),
        sa.CheckConstraint(
            "max_vehicle_length_m IS NULL OR max_vehicle_length_m > 0",
            name="ck_locations_max_vehicle_length",
        ),
        sa.CheckConstraint(
            "parent_location_id IS NULL OR parent_location_id <> id",
            name="ck_locations_parent_not_self",
        ),
        sa.CheckConstraint(
            "type = 'customer_site' OR has_loading_dock IS NULL",
            name="ck_locations_loading_dock_customer_site_only",
        ),
        sa.CheckConstraint(
            "opening_hours IS NULL OR jsonb_typeof(opening_hours) = 'object'",
            name="ck_locations_opening_hours_object",
        ),
        sa.CheckConstraint(
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
    )
    op.create_index("ix_locations_type", "locations", ["type"])
    op.create_index("ix_locations_parent_location_id", "locations", ["parent_location_id"])
    op.create_index("ix_locations_customer_id", "locations", ["customer_id"])

    op.create_table(
        "carriers",
        _id(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("business_id", sa.String(length=40), nullable=True),
        sa.Column("transport_licence_valid_until", sa.Date(), nullable=True),
        sa.Column("liability_insurance_valid_until", sa.Date(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_carriers_name"),
        sa.CheckConstraint("type IN ('own', 'subcontractor')", name="ck_carriers_type"),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_carriers_country"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_carriers_name_not_blank"),
    )
    op.create_index(
        "uq_carriers_one_own",
        "carriers",
        ["type"],
        unique=True,
        postgresql_where=sa.text("type = 'own'"),
    )

    op.create_table(
        "drivers",
        _id(),
        sa.Column("carrier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("home_location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employment", sa.String(length=20), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["carrier_id"], ["carriers.id"], name="fk_drivers_carrier_id"),
        sa.ForeignKeyConstraint(
            ["home_location_id"], ["locations.id"], name="fk_drivers_home_location_id"
        ),
        sa.UniqueConstraint("carrier_id", "name", name="uq_drivers_carrier_id_name"),
        sa.CheckConstraint(
            "employment IN ('own', 'subcontractor_named')", name="ck_drivers_employment"
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_drivers_name_not_blank"),
    )
    op.create_index("ix_drivers_home_location_id", "drivers", ["home_location_id"])

    op.create_table(
        "driver_qualifications",
        _id(),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("document_ref", sa.String(length=100), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["drivers.id"],
            name="fk_driver_qualifications_driver_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("driver_id", "type", name="uq_driver_qualifications_driver_id_type"),
        sa.CheckConstraint(
            "type IN ('adr_basic', 'adr_class1', 'adr_class7', 'adr_tank', "
            "'driving_licence_c', 'driving_licence_ce', 'gdp', 'professional_competence', 'tachograph_card')",
            name="ck_driver_qualifications_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("driver_qualifications")
    op.drop_index("ix_drivers_home_location_id", table_name="drivers")
    op.drop_table("drivers")
    op.drop_index("uq_carriers_one_own", table_name="carriers")
    op.drop_table("carriers")
    op.drop_index("ix_locations_parent_location_id", table_name="locations")
    op.drop_index("ix_locations_customer_id", table_name="locations")
    op.drop_index("ix_locations_type", table_name="locations")
    op.drop_table("locations")
    op.drop_index("uq_customers_one_own_company", table_name="customers")
    op.drop_table("customers")
