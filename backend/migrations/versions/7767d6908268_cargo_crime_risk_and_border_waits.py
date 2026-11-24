"""cargo crime risk and border waits

2B-3e, D95 (approved by Toni 24.11.2026). Does not edit earlier revisions.

Schema:
- cargo_crime_reports: published monthly incident reports that were read (source, month, which
  countries the report names); cargo_crime_counts: reported incidents per country in a report.
  A missing count means "not named", not zero.
- risk_areas: country, ISO 3166-2 region or road with a level 1-5 for a validity period (D67).
  Data rows link to their source; expert estimates state their basis. No overlapping periods
  for the same country, region and road.
- border_wait_observations: heavy-traffic waiting time at a border crossing (D92) by direction
  and moment; demo rows carry a fixed "invented" note.

Downgrade drops the tables WITH their rows (reference and demo data, re-entered by the seeds).

Revision ID: 7767d6908268
Revises: 8df1bdeac8a3
Create Date: 2026-11-24 08:43:40.233786
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7767d6908268"
down_revision: str | None = "8df1bdeac8a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cargo_crime_reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("report_month", sa.Date(), nullable=False),
        sa.Column("coverage_note", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(source_name) <> ''", name="ck_cargo_crime_reports_source_name"),
        sa.CheckConstraint(
            "checked_on >= DATE '2026-01-01'", name="ck_cargo_crime_reports_checked_on"
        ),
        sa.CheckConstraint("source_url ~ '^https://'", name="ck_cargo_crime_reports_source_url"),
        sa.CheckConstraint(
            "extract(day FROM report_month) = 1", name="ck_cargo_crime_reports_month"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", "report_month", name="uq_cargo_crime_reports_month"),
    )
    op.create_table(
        "risk_areas",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("region", sa.String(length=6), nullable=True),
        sa.Column("road_ref", sa.String(length=40), nullable=True),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        postgresql.ExcludeConstraint(
            (sa.column("country"), "="),
            (sa.text("coalesce(region, '')"), "="),
            (sa.text("coalesce(road_ref, '')"), "="),
            (sa.text("daterange(valid_from, valid_until, '[]')"), "&&"),
            using="gist",
            name="ex_risk_areas_no_overlap",
        ),
        sa.CheckConstraint("btrim(basis) <> ''", name="ck_risk_areas_basis"),
        sa.CheckConstraint("checked_on >= DATE '2026-01-01'", name="ck_risk_areas_checked_on"),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_risk_areas_country"),
        sa.CheckConstraint(
            "region IS NULL OR (region ~ '^[A-Z]{2}-[A-Z0-9]{1,3}$' AND left(region, 2) = country)",
            name="ck_risk_areas_region",
        ),
        sa.CheckConstraint(
            "road_ref IS NULL OR btrim(road_ref) <> ''", name="ck_risk_areas_road_ref"
        ),
        sa.CheckConstraint(
            "source_type <> 'data' OR source_url IS NOT NULL", name="ck_risk_areas_data_source"
        ),
        sa.CheckConstraint(
            "source_type IN ('data', 'expert_estimate')", name="ck_risk_areas_source_type"
        ),
        sa.CheckConstraint(
            "source_url IS NULL OR source_url ~ '^https://'", name="ck_risk_areas_source_url"
        ),
        sa.CheckConstraint("level IN (1, 2, 3, 4, 5)", name="ck_risk_areas_level"),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from <= valid_until", name="ck_risk_areas_period"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cargo_crime_counts",
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("incident_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_cargo_crime_counts_country"),
        sa.CheckConstraint("incident_count >= 0", name="ck_cargo_crime_counts_incident_count"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["cargo_crime_reports.id"],
            name="fk_cargo_crime_counts_report_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "country"),
    )
    op.create_table(
        "border_wait_observations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wait_minutes", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "direction IN ('entry', 'exit')", name="ck_border_wait_observations_direction"
        ),
        sa.CheckConstraint(
            "source_type <> 'demo'"
            " OR coalesce(note, '') = 'Invented demo value, not a measurement.'",
            name="ck_border_wait_observations_demo_note",
        ),
        sa.CheckConstraint(
            "source_type IN ('demo', 'historical_avg', 'manual', 'official_feed')",
            name="ck_border_wait_observations_source_type",
        ),
        sa.CheckConstraint(
            "source_type NOT IN ('historical_avg', 'official_feed') OR source_url IS NOT NULL",
            name="ck_border_wait_observations_published_source",
        ),
        sa.CheckConstraint(
            "source_url IS NULL OR source_url ~ '^https://'",
            name="ck_border_wait_observations_source_url",
        ),
        sa.CheckConstraint("wait_minutes >= 0", name="ck_border_wait_observations_wait_minutes"),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["border_crossing_details.location_id"],
            name="fk_border_wait_observations_location_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "location_id",
            "direction",
            "observed_at",
            "source_type",
            name="uq_border_wait_observations_observation",
        ),
    )
    op.create_index(
        "ix_border_wait_observations_location_observed",
        "border_wait_observations",
        ["location_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_border_wait_observations_location_observed", table_name="border_wait_observations"
    )
    op.drop_table("border_wait_observations")
    op.drop_table("cargo_crime_counts")
    op.drop_table("risk_areas")
    op.drop_table("cargo_crime_reports")
