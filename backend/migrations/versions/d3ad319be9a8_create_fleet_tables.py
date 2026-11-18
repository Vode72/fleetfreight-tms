"""create trucks, dollies, load_units, compartments, reefer_units and equipment_qualifications

Revision ID: d3ad319be9a8
Revises: f0c09cb23c9d
Create Date: 2026-11-18

Phase 2B-2 (data model v1, fleet), revision B. Allowed values are VARCHAR + CHECK; the lists must
match domain/equipment.py (tests/test_domain_equipment.py compares them). Every foreign key is
ON DELETE RESTRICT (D72) and every foreign key column has an index (a unique constraint that
starts with the column counts). Lengths are metres, weights kilograms, temperatures degrees
Celsius (NUMERIC, never float); validity dates are DATE, both ends inclusive.

- load_units (D60): type trailer | fixed_body. A fixed body references its truck (unique: one body
  per truck) and has no own length, weights or axles (the truck holds them); a trailer has them.
- equipment_qualifications (D70, D67): exactly one subject (truck, dolly or load unit); ATP,
  tail lift and GDP mapping apply to load units only. One exclusion constraint forbids
  overlapping periods per subject and type: the subject spans three columns, and because the
  CHECK makes exactly one of them non-null, coalesce(truck_id, dolly_id, load_unit_id) is a
  single key (simpler than three partial exclusion constraints). ATP class and inspections are
  periods here, not columns on load_units (D67).
- trucks: tractor features (fifth wheel position, low fifth wheel), rigid truck drawbar hitch,
  own combination weight limit and base location (D55, D61). load_units: coupling type (semi,
  full or centre-axle trailer; NULL for a fixed body), kingpin position, external height and
  width, D25 (a semi-trailer has no tail lift), a fixed body is not rail-craneable (D63).
  compartments: optional pallet places.
- D75: load_units.model_code (FB, FD, FS, CS, MEGA, COIL; the thermo codes go with reefer bodies,
  FS has side doors) and the separate feature column side_doors.
- D76: up to two reefer units per load unit, one per position (unique (load_unit_id, position));
  compartments may name the unit serving them (composite foreign key, so the unit belongs to
  the same load unit) and say whether they are controlled independently; load_units carry the
  partition values; equipment_qualifications has a fourth subject, the reefer unit (type
  reefer_service, reefer units take only that type). Because compartments reference reefer_units,
  reefer_units is created before compartments (a deviation from the table order of chapter 3).
- Needs the btree_gist extension, created in c52d8e3f1a47.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3ad319be9a8"
down_revision: str | None = "f0c09cb23c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _uuid(name: str, *, nullable: bool = False) -> sa.Column[Any]:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _flag(name: str) -> sa.Column[Any]:
    return sa.Column(name, sa.Boolean(), server_default=sa.text("false"), nullable=False)


def _fk(column: str, target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [f"{target}.id"], name=name, ondelete="RESTRICT")


_VEHICLE_CHECKS = (
    "length_m > 0 AND kerb_weight_kg > 0 AND max_gross_weight_kg >= kerb_weight_kg AND axles >= 1"
)


def upgrade() -> None:
    op.create_table(
        "trucks",
        _id(),
        _uuid("carrier_id"),
        sa.Column("registration", sa.String(length=30), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("length_m", sa.Numeric(5, 2), nullable=False),
        sa.Column("kerb_weight_kg", sa.Integer(), nullable=False),
        sa.Column("max_gross_weight_kg", sa.Integer(), nullable=False),
        sa.Column("axles", sa.Integer(), nullable=False),
        sa.Column("fifth_wheel_from_front_m", sa.Numeric(5, 2), nullable=True),
        _flag("low_fifth_wheel"),
        _flag("drawbar_hitch"),
        sa.Column("max_combination_weight_kg", sa.Integer(), nullable=True),
        _uuid("home_location_id", nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _fk("carrier_id", "carriers", "fk_trucks_carrier_id"),
        _fk("home_location_id", "locations", "fk_trucks_home_location_id"),
        sa.UniqueConstraint("registration", name="uq_trucks_registration"),
        sa.CheckConstraint("type IN ('rigid_truck', 'tractor')", name="ck_trucks_type"),
        sa.CheckConstraint("btrim(registration) <> ''", name="ck_trucks_registration_not_blank"),
        sa.CheckConstraint(_VEHICLE_CHECKS, name="ck_trucks_dimensions"),
        sa.CheckConstraint(
            "fifth_wheel_from_front_m IS NULL OR (type = 'tractor' AND fifth_wheel_from_front_m > 0"
            " AND fifth_wheel_from_front_m <= length_m)",
            name="ck_trucks_fifth_wheel",
        ),
        sa.CheckConstraint(
            "NOT low_fifth_wheel OR type = 'tractor'", name="ck_trucks_low_fifth_wheel_tractor"
        ),
        sa.CheckConstraint(
            "NOT drawbar_hitch OR type = 'rigid_truck'", name="ck_trucks_drawbar_hitch_rigid"
        ),
        sa.CheckConstraint(
            "max_combination_weight_kg IS NULL OR max_combination_weight_kg >= max_gross_weight_kg",
            name="ck_trucks_max_combination_weight",
        ),
    )
    op.create_index("ix_trucks_carrier_id", "trucks", ["carrier_id"])
    op.create_index("ix_trucks_home_location_id", "trucks", ["home_location_id"])

    op.create_table(
        "dollies",
        _id(),
        _uuid("carrier_id"),
        sa.Column("registration", sa.String(length=30), nullable=False),
        sa.Column("length_m", sa.Numeric(5, 2), nullable=False),
        sa.Column("kerb_weight_kg", sa.Integer(), nullable=False),
        sa.Column("max_gross_weight_kg", sa.Integer(), nullable=False),
        sa.Column("axles", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _fk("carrier_id", "carriers", "fk_dollies_carrier_id"),
        sa.UniqueConstraint("registration", name="uq_dollies_registration"),
        sa.CheckConstraint("btrim(registration) <> ''", name="ck_dollies_registration_not_blank"),
        sa.CheckConstraint(_VEHICLE_CHECKS, name="ck_dollies_dimensions"),
    )
    op.create_index("ix_dollies_carrier_id", "dollies", ["carrier_id"])

    op.create_table(
        "load_units",
        _id(),
        sa.Column("type", sa.String(length=20), nullable=False),
        _uuid("truck_id", nullable=True),
        _uuid("carrier_id"),
        sa.Column("registration", sa.String(length=30), nullable=False),
        sa.Column("body_type", sa.String(length=20), nullable=False),
        sa.Column("coupling_type", sa.String(length=20), nullable=True),
        sa.Column("model_code", sa.String(length=10), nullable=True),
        sa.Column("internal_length_m", sa.Numeric(5, 2), nullable=False),
        sa.Column("internal_width_m", sa.Numeric(4, 2), nullable=False),
        sa.Column("internal_height_m", sa.Numeric(4, 2), nullable=False),
        sa.Column("door_height_m", sa.Numeric(4, 2), nullable=True),
        sa.Column("external_length_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("kingpin_from_front_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("external_height_m", sa.Numeric(4, 2), nullable=True),
        sa.Column("external_width_m", sa.Numeric(4, 2), nullable=True),
        sa.Column("ldm", sa.Numeric(5, 2), nullable=True),
        sa.Column("pallet_places", sa.Integer(), nullable=True),
        sa.Column("kerb_weight_kg", sa.Integer(), nullable=True),
        sa.Column("max_gross_weight_kg", sa.Integer(), nullable=True),
        sa.Column("axles", sa.Integer(), nullable=True),
        _flag("xl_certified"),
        _flag("coil_well"),
        _flag("tir_cable"),
        _flag("top_loading"),
        _flag("tail_lift"),
        _flag("side_doors"),
        _flag("partition"),
        sa.Column("partition_thickness_mm", sa.Integer(), server_default="50", nullable=False),
        sa.Column("partition_step_pallet_rows", sa.Integer(), server_default="1", nullable=False),
        sa.Column("min_pallets_front", sa.Integer(), server_default="4", nullable=False),
        sa.Column("min_pallets_rear", sa.Integer(), server_default="4", nullable=False),
        _flag("rail_craneable"),
        sa.Column("ownership", sa.String(length=20), server_default="own", nullable=False),
        sa.Column("lease_valid_from", sa.Date(), nullable=True),
        sa.Column("lease_valid_until", sa.Date(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _fk("truck_id", "trucks", "fk_load_units_truck_id"),
        _fk("carrier_id", "carriers", "fk_load_units_carrier_id"),
        sa.UniqueConstraint("registration", name="uq_load_units_registration"),
        sa.UniqueConstraint("truck_id", name="uq_load_units_truck_id"),
        sa.CheckConstraint("type IN ('fixed_body', 'trailer')", name="ck_load_units_type"),
        sa.CheckConstraint(
            "body_type IN ('box', 'curtainsider', 'mega', 'reefer', 'side_opening')",
            name="ck_load_units_body_type",
        ),
        sa.CheckConstraint(
            "ownership IN ('customer_owned', 'leased', 'own', 'partner', 'rented')",
            name="ck_load_units_ownership",
        ),
        sa.CheckConstraint(
            "coupling_type IN ('centre_axle_trailer', 'full_trailer', 'semi_trailer')",
            name="ck_load_units_coupling_type",
        ),
        sa.CheckConstraint(
            "model_code IN ('COIL', 'CS', 'FB', 'FD', 'FS', 'MEGA')",
            name="ck_load_units_model_code",
        ),
        sa.CheckConstraint(
            "model_code IS NULL OR ((model_code IN ('FB', 'FD', 'FS')) = (body_type = 'reefer'))",
            name="ck_load_units_model_code_body",
        ),
        sa.CheckConstraint(
            "model_code IS DISTINCT FROM 'FS' OR side_doors", name="ck_load_units_fs_side_doors"
        ),
        sa.CheckConstraint(
            "partition_thickness_mm > 0 AND partition_step_pallet_rows >= 1"
            " AND min_pallets_front >= 0 AND min_pallets_rear >= 0",
            name="ck_load_units_partition_values",
        ),
        sa.CheckConstraint(
            "(type = 'fixed_body') = (coupling_type IS NULL)", name="ck_load_units_coupling_link"
        ),
        sa.CheckConstraint(
            "coupling_type IS DISTINCT FROM 'semi_trailer' OR NOT tail_lift",
            name="ck_load_units_semi_trailer_no_tail_lift",
        ),
        sa.CheckConstraint(
            "kingpin_from_front_m IS NULL OR (coupling_type IS NOT DISTINCT FROM 'semi_trailer'"
            " AND kingpin_from_front_m > 0 AND kingpin_from_front_m < external_length_m)",
            name="ck_load_units_kingpin",
        ),
        sa.CheckConstraint(
            "(external_height_m IS NULL OR external_height_m > 0)"
            " AND (external_width_m IS NULL OR external_width_m > 0)",
            name="ck_load_units_external_size",
        ),
        sa.CheckConstraint(
            "type <> 'fixed_body' OR NOT rail_craneable", name="ck_load_units_fixed_body_no_rail"
        ),
        sa.CheckConstraint(
            "btrim(registration) <> ''", name="ck_load_units_registration_not_blank"
        ),
        sa.CheckConstraint(
            "(type = 'fixed_body') = (truck_id IS NOT NULL)", name="ck_load_units_truck_link"
        ),
        sa.CheckConstraint(
            "(type = 'trailer' AND external_length_m IS NOT NULL AND kerb_weight_kg IS NOT NULL"
            " AND max_gross_weight_kg IS NOT NULL AND axles IS NOT NULL)"
            " OR (type = 'fixed_body' AND external_length_m IS NULL AND kerb_weight_kg IS NULL"
            " AND max_gross_weight_kg IS NULL AND axles IS NULL)",
            name="ck_load_units_vehicle_fields",
        ),
        sa.CheckConstraint(
            "external_length_m IS NULL OR (external_length_m > 0 AND kerb_weight_kg > 0"
            " AND max_gross_weight_kg >= kerb_weight_kg AND axles >= 1)",
            name="ck_load_units_vehicle_values",
        ),
        sa.CheckConstraint(
            "internal_length_m > 0 AND internal_width_m > 0 AND internal_height_m > 0"
            " AND (door_height_m IS NULL OR door_height_m > 0)"
            " AND (ldm IS NULL OR ldm > 0) AND (pallet_places IS NULL OR pallet_places >= 0)",
            name="ck_load_units_cargo_space",
        ),
        sa.CheckConstraint(
            "lease_valid_from IS NULL OR lease_valid_until IS NULL"
            " OR lease_valid_from <= lease_valid_until",
            name="ck_load_units_lease_period",
        ),
        sa.CheckConstraint(
            "(ownership IN ('leased', 'rented') AND lease_valid_from IS NOT NULL)"
            " OR (ownership NOT IN ('leased', 'rented') AND lease_valid_from IS NULL"
            " AND lease_valid_until IS NULL)",
            name="ck_load_units_lease_by_ownership",
        ),
    )
    op.create_index("ix_load_units_carrier_id", "load_units", ["carrier_id"])

    op.create_table(
        "reefer_units",
        _id(),
        _uuid("load_unit_id"),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("unit_name", sa.String(length=100), nullable=False),
        sa.Column("power_source", sa.String(length=10), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _fk("load_unit_id", "load_units", "fk_reefer_units_load_unit_id"),
        sa.UniqueConstraint(
            "load_unit_id", "position", name="uq_reefer_units_load_unit_id_position"
        ),
        sa.UniqueConstraint("id", "load_unit_id", name="uq_reefer_units_id_load_unit_id"),
        sa.CheckConstraint("position IN ('front', 'rear')", name="ck_reefer_units_position"),
        sa.CheckConstraint(
            "power_source IN ('diesel', 'electric', 'hybrid')", name="ck_reefer_units_power_source"
        ),
        sa.CheckConstraint("btrim(unit_name) <> ''", name="ck_reefer_units_unit_name_not_blank"),
    )

    op.create_table(
        "compartments",
        _id(),
        _uuid("load_unit_id"),
        _uuid("reefer_unit_id", nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("temperature_min", sa.Numeric(4, 1), nullable=False),
        sa.Column("temperature_max", sa.Numeric(4, 1), nullable=False),
        sa.Column("pallet_places", sa.Integer(), nullable=True),
        _flag("independently_controlled"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _fk("load_unit_id", "load_units", "fk_compartments_load_unit_id"),
        sa.ForeignKeyConstraint(
            ["reefer_unit_id", "load_unit_id"],
            ["reefer_units.id", "reefer_units.load_unit_id"],
            name="fk_compartments_reefer_unit_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("load_unit_id", "number", name="uq_compartments_load_unit_id_number"),
        sa.CheckConstraint("number >= 1", name="ck_compartments_number"),
        sa.CheckConstraint(
            "pallet_places IS NULL OR pallet_places >= 0", name="ck_compartments_pallet_places"
        ),
        sa.CheckConstraint("temperature_min <= temperature_max", name="ck_compartments_temperature"),
    )
    op.create_index("ix_compartments_reefer_unit_id", "compartments", ["reefer_unit_id"])

    op.create_table(
        "equipment_qualifications",
        _id(),
        _uuid("truck_id", nullable=True),
        _uuid("dolly_id", nullable=True),
        _uuid("load_unit_id", nullable=True),
        _uuid("reefer_unit_id", nullable=True),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("class_code", sa.String(length=10), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("document_ref", sa.String(length=100), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _fk("truck_id", "trucks", "fk_equipment_qualifications_truck_id"),
        _fk("dolly_id", "dollies", "fk_equipment_qualifications_dolly_id"),
        _fk("load_unit_id", "load_units", "fk_equipment_qualifications_load_unit_id"),
        _fk("reefer_unit_id", "reefer_units", "fk_equipment_qualifications_reefer_unit_id"),
        sa.CheckConstraint(
            "type IN ('adr_vehicle_approval', 'atp', 'gdp_temperature_mapping', 'inspection', "
            "'reefer_service', 'tail_lift_inspection')",
            name="ck_equipment_qualifications_type",
        ),
        sa.CheckConstraint("valid_from <= valid_until", name="ck_equipment_qualifications_period"),
        sa.CheckConstraint(
            "num_nonnulls(truck_id, dolly_id, load_unit_id, reefer_unit_id) = 1",
            name="ck_equipment_qualifications_one_subject",
        ),
        sa.CheckConstraint(
            "(type = 'reefer_service') = (reefer_unit_id IS NOT NULL)",
            name="ck_equipment_qualifications_reefer_service",
        ),
        sa.CheckConstraint(
            "type NOT IN ('atp', 'gdp_temperature_mapping', 'tail_lift_inspection')"
            " OR load_unit_id IS NOT NULL",
            name="ck_equipment_qualifications_load_unit_only_types",
        ),
        sa.CheckConstraint(
            "class_code IS NULL OR btrim(class_code) <> ''",
            name="ck_equipment_qualifications_class_code_not_blank",
        ),
        postgresql.ExcludeConstraint(
            (sa.text("coalesce(truck_id, dolly_id, load_unit_id, reefer_unit_id)"), "="),
            ("type", "="),
            (sa.text("daterange(valid_from, valid_until, '[]')"), "&&"),
            using="gist",
            name="ex_equipment_qualifications_no_overlap",
        ),
    )
    op.create_index("ix_equipment_qualifications_truck_id", "equipment_qualifications", ["truck_id"])
    op.create_index("ix_equipment_qualifications_dolly_id", "equipment_qualifications", ["dolly_id"])
    op.create_index(
        "ix_equipment_qualifications_load_unit_id", "equipment_qualifications", ["load_unit_id"]
    )
    op.create_index(
        "ix_equipment_qualifications_reefer_unit_id",
        "equipment_qualifications",
        ["reefer_unit_id"],
    )


def downgrade() -> None:
    # Reverse order of creation. The btree_gist extension stays (created by an earlier revision).
    op.drop_table("equipment_qualifications")
    op.drop_table("compartments")
    op.drop_table("reefer_units")
    op.drop_table("load_units")
    op.drop_table("dollies")
    op.drop_table("trucks")
