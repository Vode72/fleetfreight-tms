"""parking and border crossing details

2B-3b, D92 (approved by Toni 22.11.2026). Does not edit earlier revisions.

Schema:
- locations: new type border_crossing; unique (id, type) as the target of composite foreign keys
  that tie a detail row to one location type (the detail table's type column is fixed by a CHECK,
  so a location's type cannot change while its detail row exists).
- parking_details: one row per parking location (spaces, night price with its currency, reefer
  plugs, booking possible, ADR vehicles allowed, services).
- parking_certifications: EU (2022/1012) and TAPA PSR certificates as validity periods (D67).
- border_crossing_details: one row per border crossing (other country, customs office of each
  side, heavy traffic allowed, typical wait as a setting, note).
- border_crossing_status_periods: open / closed / restricted over [starts_at, ends_at) with the
  official source (times, not days: a border may close in the evening).

Downgrade drops the new tables and restores the old type list; it stops if border crossing
locations exist (archive or remove them first, nothing is deleted silently).

Revision ID: 988966e62624
Revises: 47da3484520e
Create Date: 2026-11-22 09:25:56.626247
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '988966e62624'
down_revision: str | None = '47da3484520e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_TYPES = (
    "type IN ('customer_site', 'customs_office', 'depot', 'fuel', 'inspection', 'parking', 'port',"
    " 'rail_terminal', 'terminal', 'wash', 'workshop')"
)
_NEW_TYPES = (
    "type IN ('border_crossing', 'customer_site', 'customs_office', 'depot', 'fuel', 'inspection',"
    " 'parking', 'port', 'rail_terminal', 'terminal', 'wash', 'workshop')"
)


def upgrade() -> None:
    op.drop_constraint('ck_locations_type', 'locations', type_='check')
    op.create_check_constraint('ck_locations_type', 'locations', _NEW_TYPES)
    op.create_unique_constraint('uq_locations_id_type', 'locations', ['id', 'type'])
    op.create_table('border_crossing_details',
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('location_type', sa.String(length=20), server_default=sa.text("'border_crossing'"), nullable=False),
    sa.Column('other_country', sa.String(length=2), nullable=False),
    sa.Column('customs_office_id', sa.UUID(), nullable=True),
    sa.Column('customs_office_type', sa.String(length=20), nullable=True),
    sa.Column('other_customs_office_id', sa.UUID(), nullable=True),
    sa.Column('other_customs_office_type', sa.String(length=20), nullable=True),
    sa.Column('heavy_traffic_allowed', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('typical_wait_minutes', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("customs_office_type = 'customs_office'", name='ck_border_crossing_details_customs_office_type'),
    sa.CheckConstraint("location_type = 'border_crossing'", name='ck_border_crossing_details_location_type'),
    sa.CheckConstraint("other_country ~ '^[A-Z]{2}$'", name='ck_border_crossing_details_other_country'),
    sa.CheckConstraint("other_customs_office_type = 'customs_office'", name='ck_border_crossing_details_other_customs_office_type'),
    sa.CheckConstraint('(customs_office_id IS NULL) = (customs_office_type IS NULL) AND (other_customs_office_id IS NULL) = (other_customs_office_type IS NULL)', name='ck_border_crossing_details_customs_office_pairs'),
    sa.CheckConstraint('typical_wait_minutes IS NULL OR typical_wait_minutes >= 0', name='ck_border_crossing_details_typical_wait'),
    sa.ForeignKeyConstraint(['customs_office_id', 'customs_office_type'], ['locations.id', 'locations.type'], name='fk_border_crossing_details_customs_office_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['location_id', 'location_type'], ['locations.id', 'locations.type'], name='fk_border_crossing_details_location_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['other_customs_office_id', 'other_customs_office_type'], ['locations.id', 'locations.type'], name='fk_border_crossing_details_other_customs_office_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('location_id')
    )
    op.create_index('ix_border_crossing_details_customs_office_id', 'border_crossing_details', ['customs_office_id'], unique=False)
    op.create_index('ix_border_crossing_details_other_customs_office_id', 'border_crossing_details', ['other_customs_office_id'], unique=False)
    op.create_table('parking_details',
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('location_type', sa.String(length=20), server_default=sa.text("'parking'"), nullable=False),
    sa.Column('spaces', sa.Integer(), nullable=True),
    sa.Column('night_price_cents', sa.Integer(), nullable=True),
    sa.Column('price_currency', sa.String(length=3), nullable=True),
    sa.Column('reefer_plug_count', sa.Integer(), nullable=True),
    sa.Column('booking_possible', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('adr_vehicles_allowed', sa.Boolean(), nullable=True),
    sa.Column('services', postgresql.ARRAY(sa.String(length=20)), server_default=sa.text("'{}'::varchar[]"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(night_price_cents IS NULL) = (price_currency IS NULL) AND (night_price_cents IS NULL OR night_price_cents >= 0) AND (price_currency IS NULL OR price_currency ~ '^[A-Z]{3}$')", name='ck_parking_details_night_price'),
    sa.CheckConstraint("location_type = 'parking'", name='ck_parking_details_location_type'),
    sa.CheckConstraint("services <@ ARRAY['accommodation', 'fuel', 'restaurant', 'security_staff', 'shower', 'toilet']::varchar[]", name='ck_parking_details_services'),
    sa.CheckConstraint('reefer_plug_count IS NULL OR reefer_plug_count >= 0', name='ck_parking_details_reefer_plug_count'),
    sa.CheckConstraint('spaces IS NULL OR spaces >= 1', name='ck_parking_details_spaces'),
    sa.ForeignKeyConstraint(['location_id', 'location_type'], ['locations.id', 'locations.type'], name='fk_parking_details_location_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('location_id')
    )
    op.create_table('border_crossing_status_periods',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('checked_on', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('location_id'), '='), (sa.text("tstzrange(starts_at, ends_at, '[)')"), '&&'), using='gist', name='ex_border_crossing_status_periods_no_overlap'),
    sa.CheckConstraint("checked_on >= DATE '2026-01-01'", name='ck_border_crossing_status_periods_checked_on'),
    sa.CheckConstraint("source_url ~ '^https://'", name='ck_border_crossing_status_periods_source_url'),
    sa.CheckConstraint("status IN ('closed', 'open', 'restricted')", name='ck_border_crossing_status_periods_status'),
    sa.CheckConstraint('ends_at IS NULL OR starts_at < ends_at', name='ck_border_crossing_status_periods_period'),
    sa.ForeignKeyConstraint(['location_id'], ['border_crossing_details.location_id'], name='fk_border_crossing_status_periods_location_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('parking_certifications',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('scheme', sa.String(length=20), nullable=False),
    sa.Column('level', sa.String(length=20), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('document_ref', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('location_id'), '='), (sa.column('scheme'), '='), (sa.text("daterange(valid_from, valid_until, '[]')"), '&&'), using='gist', name='ex_parking_certifications_no_overlap'),
    sa.CheckConstraint("(scheme = 'eu_sspa' AND level IN ('bronze', 'gold', 'platinum', 'silver')) OR (scheme = 'tapa_psr' AND level IN ('level_1', 'level_2', 'level_3'))", name='ck_parking_certifications_level'),
    sa.CheckConstraint("scheme IN ('eu_sspa', 'tapa_psr')", name='ck_parking_certifications_scheme'),
    sa.CheckConstraint('valid_until IS NULL OR valid_from <= valid_until', name='ck_parking_certifications_period'),
    sa.ForeignKeyConstraint(['location_id'], ['parking_details.location_id'], name='fk_parking_certifications_location_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('parking_certifications')
    op.drop_table('border_crossing_status_periods')
    op.drop_table('parking_details')
    op.drop_index('ix_border_crossing_details_other_customs_office_id', table_name='border_crossing_details')
    op.drop_index('ix_border_crossing_details_customs_office_id', table_name='border_crossing_details')
    op.drop_table('border_crossing_details')
    op.drop_constraint('uq_locations_id_type', 'locations', type_='unique')
    # Fails while border crossing locations exist (see the module docstring).
    op.drop_constraint('ck_locations_type', 'locations', type_='check')
    op.create_check_constraint('ck_locations_type', 'locations', _OLD_TYPES)
