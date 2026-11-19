"""countries, public holidays and road restrictions

Revision ID: 2cb43f9f78c1
Revises: e0f14a4663b6
Create Date: 2026-11-19

Phase 2B-3a (D84). New tables only; no existing table changes:
- countries: ISO code, names, time zone, currency, EU membership.
- country_rules: general road rules per validity period (D67, no overlaps per country).
- public_holidays: holidays the road rules refer to, per country, optionally per region.
- road_restrictions: driving bans, weight and dimension limits, seasonal limits, bridges, HCT
  routes, ADR tunnels and environmental zones; scope, exemptions, validity.
- road_restriction_windows: driving ban windows (weekdays, holidays, day before a holiday, or a
  single date for yearly published ban lists); a composite key to (id, restriction_type)
  keeps windows on driving bans only.
Every reference row carries a source URL (https) and a check date. The rows themselves are
reference data loaded by scripts.seed_reference_data, not by this migration (rule 2).
Existing country columns (customers, locations, carriers) get no foreign key yet (later revision).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '2cb43f9f78c1'
down_revision: str | None = 'e0f14a4663b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('countries',
    sa.Column('code', sa.String(length=2), nullable=False),
    sa.Column('name_en', sa.String(length=100), nullable=False),
    sa.Column('name_fi', sa.String(length=100), nullable=False),
    sa.Column('time_zone', sa.String(length=64), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('eu_member', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(name_en) <> '' AND btrim(name_fi) <> ''", name='ck_countries_names_not_blank'),
    sa.CheckConstraint("code ~ '^[A-Z]{2}$'", name='ck_countries_code'),
    sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='ck_countries_currency'),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('country_rules',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('truck_speed_motorway_kmh', sa.SmallInteger(), nullable=True),
    sa.Column('truck_speed_other_kmh', sa.SmallInteger(), nullable=True),
    sa.Column('max_gross_weight_kg', sa.Integer(), nullable=True),
    sa.Column('max_length_mm', sa.Integer(), nullable=True),
    sa.Column('hct_allowed', sa.Boolean(), nullable=True),
    sa.Column('winter_equipment_start', sa.SmallInteger(), nullable=True),
    sa.Column('winter_equipment_end', sa.SmallInteger(), nullable=True),
    sa.Column('toll_system', sa.String(length=20), nullable=False),
    sa.Column('posted_worker_declaration', sa.Boolean(), nullable=True),
    sa.Column('cabotage_note', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('checked_on', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('country'), '='), (sa.text("daterange(valid_from, valid_until, '[]')"), '&&'), using='gist', name='ex_country_rules_no_overlap'),
    sa.CheckConstraint("checked_on >= DATE '2026-01-01'", name='ck_country_rules_checked_on'),
    sa.CheckConstraint("source_url ~ '^https://'", name='ck_country_rules_source_url'),
    sa.CheckConstraint("toll_system IN ('distance_based', 'none', 'time_based')", name='ck_country_rules_toll_system'),
    sa.CheckConstraint('(max_gross_weight_kg IS NULL OR max_gross_weight_kg > 0) AND (max_length_mm IS NULL OR max_length_mm > 0)', name='ck_country_rules_limits'),
    sa.CheckConstraint('(truck_speed_motorway_kmh IS NULL OR truck_speed_motorway_kmh BETWEEN 1 AND 200) AND (truck_speed_other_kmh IS NULL OR truck_speed_other_kmh BETWEEN 1 AND 200)', name='ck_country_rules_speeds'),
    sa.CheckConstraint('(winter_equipment_start IS NULL) = (winter_equipment_end IS NULL) AND (winter_equipment_start IS NULL OR (winter_equipment_start BETWEEN 101 AND 1231 AND winter_equipment_end BETWEEN 101 AND 1231))', name='ck_country_rules_winter_season'),
    sa.CheckConstraint('valid_until IS NULL OR valid_from <= valid_until', name='ck_country_rules_period'),
    sa.ForeignKeyConstraint(['country'], ['countries.code'], name='fk_country_rules_country', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('public_holidays',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('region', sa.String(length=6), nullable=True),
    sa.Column('holiday_date', sa.Date(), nullable=False),
    sa.Column('name_local', sa.String(length=120), nullable=False),
    sa.Column('name_en', sa.String(length=120), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('checked_on', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(name_local) <> ''", name='ck_public_holidays_name_not_blank'),
    sa.CheckConstraint("checked_on >= DATE '2026-01-01'", name='ck_public_holidays_checked_on'),
    sa.CheckConstraint("region IS NULL OR (region ~ '^[A-Z]{2}-[A-Z0-9]{1,3}$' AND left(region, 2) = country)", name='ck_public_holidays_region'),
    sa.CheckConstraint("source_url ~ '^https://'", name='ck_public_holidays_source_url'),
    sa.ForeignKeyConstraint(['country'], ['countries.code'], name='fk_public_holidays_country', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('country', 'region', 'holiday_date', name='uq_public_holidays_country_region_date', postgresql_nulls_not_distinct=True)
    )
    op.create_index('ix_public_holidays_date', 'public_holidays', ['holiday_date'], unique=False)
    op.create_table('road_restrictions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('region', sa.String(length=6), nullable=True),
    sa.Column('road_ref', sa.String(length=40), nullable=True),
    sa.Column('section', sa.Text(), nullable=True),
    sa.Column('restriction_type', sa.String(length=30), nullable=False),
    sa.Column('limit_value', sa.Integer(), nullable=True),
    sa.Column('limit_unit', sa.String(length=2), nullable=True),
    sa.Column('tunnel_category', sa.String(length=1), nullable=True),
    sa.Column('over_gross_weight_kg', sa.Integer(), nullable=True),
    sa.Column('adr_only', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('load_state', sa.String(length=10), server_default=sa.text("'any'"), nullable=False),
    sa.Column('exemptions', postgresql.ARRAY(sa.String(length=30)), server_default=sa.text("'{}'::varchar[]"), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('checked_on', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(restriction_type = 'adr_tunnel') = (tunnel_category IS NOT NULL) AND (tunnel_category IS NULL OR tunnel_category IN ('B', 'C', 'D', 'E'))", name='ck_road_restrictions_tunnel_category'),
    sa.CheckConstraint("(restriction_type IN ('axle_weight', 'bogie_weight', 'bridge', 'gross_weight', 'seasonal_weight') AND coalesce(limit_value, 0) > 0 AND coalesce(limit_unit, '') = 'kg') OR (restriction_type IN ('height', 'length') AND coalesce(limit_value, 0) > 0 AND coalesce(limit_unit, '') = 'mm') OR (restriction_type NOT IN ('axle_weight', 'bogie_weight', 'bridge', 'gross_weight', 'seasonal_weight', 'height', 'length') AND limit_value IS NULL AND limit_unit IS NULL)", name='ck_road_restrictions_limit'),
    sa.CheckConstraint("checked_on >= DATE '2026-01-01'", name='ck_road_restrictions_checked_on'),
    sa.CheckConstraint("exemptions <@ ARRAY['combined_transport', 'empty_run', 'live_animals', 'other', 'perishable_goods']::varchar[]", name='ck_road_restrictions_exemptions'),
    sa.CheckConstraint("limit_unit IS NULL OR limit_unit IN ('kg', 'mm')", name='ck_road_restrictions_limit_unit'),
    sa.CheckConstraint("load_state IN ('any', 'empty', 'loaded')", name='ck_road_restrictions_load_state'),
    sa.CheckConstraint("region IS NULL OR (region ~ '^[A-Z]{2}-[A-Z0-9]{1,3}$' AND left(region, 2) = country)", name='ck_road_restrictions_region'),
    sa.CheckConstraint("restriction_type IN ('adr_tunnel', 'axle_weight', 'bogie_weight', 'bridge', 'driving_ban', 'environmental_zone', 'gross_weight', 'hct_route', 'height', 'length', 'seasonal_weight')", name='ck_road_restrictions_type'),
    sa.CheckConstraint("road_ref IS NULL OR btrim(road_ref) <> ''", name='ck_road_restrictions_road_ref'),
    sa.CheckConstraint("source_url ~ '^https://'", name='ck_road_restrictions_source_url'),
    sa.CheckConstraint('over_gross_weight_kg IS NULL OR over_gross_weight_kg > 0', name='ck_road_restrictions_over_gross_weight'),
    sa.CheckConstraint("code ~ '^[A-Z]{2}-[A-Z0-9-]+$'", name='ck_road_restrictions_code'),
    sa.CheckConstraint('valid_until IS NULL OR valid_from <= valid_until', name='ck_road_restrictions_period'),
    sa.ForeignKeyConstraint(['country'], ['countries.code'], name='fk_road_restrictions_country', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_road_restrictions_code'),
    sa.UniqueConstraint('id', 'restriction_type', name='uq_road_restrictions_id_type')
    )
    op.create_index('ix_road_restrictions_country_type', 'road_restrictions', ['country', 'restriction_type'], unique=False)
    op.create_table('road_restriction_windows',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('restriction_id', sa.UUID(), nullable=False),
    sa.Column('restriction_type', sa.String(length=30), server_default=sa.text("'driving_ban'"), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('weekdays', postgresql.ARRAY(sa.SmallInteger()), server_default=sa.text("'{}'::smallint[]"), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=True),
    sa.Column('season_start', sa.SmallInteger(), nullable=True),
    sa.Column('season_end', sa.SmallInteger(), nullable=True),
    sa.Column('on_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(kind = 'weekdays') = (cardinality(weekdays) > 0) AND weekdays <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]", name='ck_road_restriction_windows_weekdays'),
    sa.CheckConstraint("kind IN ('date', 'day_before_holiday', 'public_holiday', 'weekdays')", name='ck_road_restriction_windows_kind'),
    sa.CheckConstraint("restriction_type = 'driving_ban'", name='ck_road_restriction_windows_driving_ban'),
    sa.CheckConstraint('(season_start IS NULL) = (season_end IS NULL) AND (season_start IS NULL OR (season_start BETWEEN 101 AND 1231 AND season_end BETWEEN 101 AND 1231))', name='ck_road_restriction_windows_season'),
    sa.CheckConstraint("(kind = 'date') = (on_date IS NOT NULL) AND (kind <> 'date' OR season_start IS NULL)", name='ck_road_restriction_windows_date'),
    sa.CheckConstraint('end_time IS NULL OR end_time > start_time', name='ck_road_restriction_windows_times'),
    sa.ForeignKeyConstraint(['restriction_id', 'restriction_type'], ['road_restrictions.id', 'road_restrictions.restriction_type'], name='fk_road_restriction_windows_restriction', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_road_restriction_windows_restriction_id', 'road_restriction_windows', ['restriction_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_road_restriction_windows_restriction_id', table_name='road_restriction_windows')
    op.drop_table('road_restriction_windows')
    op.drop_index('ix_road_restrictions_country_type', table_name='road_restrictions')
    op.drop_table('road_restrictions')
    op.drop_index('ix_public_holidays_date', table_name='public_holidays')
    op.drop_table('public_holidays')
    op.drop_table('country_rules')
    op.drop_table('countries')
