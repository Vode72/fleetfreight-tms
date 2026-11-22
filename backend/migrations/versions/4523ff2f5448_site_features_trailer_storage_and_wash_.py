"""site features trailer storage and wash details

2B-3b part b, D93 (approved by Toni 22.11.2026). Does not edit earlier revisions.

Schema:
- locations: forklift_available and tail_lift_required (customer sites only, NULL = unknown).
- parking_details: trailer_drop_allowed (trailer left without its tractor, D18, D82).
- trailer_storage_rules (D27, D63, D83): free days, daily fee with currency, reefer plugs and
  their fee, as validity periods (D67) per port or rail terminal; composite foreign key to
  locations (id, type) with the type limited to port and rail_terminal.
- wash_details (D56): scopes (interior, exterior), interior grades (general, food grade,
  chemical, tank), cleaning document and European Cleaning Document (tank and bulk).

Downgrade drops the new tables and columns WITH their values (storage terms, wash details and
the site features); reload them with the demo seed or enter them again.

Revision ID: 4523ff2f5448
Revises: 988966e62624
Create Date: 2026-11-22 09:58:53.877818
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '4523ff2f5448'
down_revision: str | None = '988966e62624'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('trailer_storage_rules',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('location_type', sa.String(length=20), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('free_days', sa.SmallInteger(), server_default=sa.text('3'), nullable=False),
    sa.Column('daily_fee_cents', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('reefer_plug_available', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('reefer_plug_daily_fee_cents', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('location_id'), '='), (sa.text("daterange(valid_from, valid_until, '[]')"), '&&'), using='gist', name='ex_trailer_storage_rules_no_overlap'),
    sa.CheckConstraint("daily_fee_cents >= 0 AND currency ~ '^[A-Z]{3}$'", name='ck_trailer_storage_rules_daily_fee'),
    sa.CheckConstraint("location_type IN ('port', 'rail_terminal')", name='ck_trailer_storage_rules_location_type'),
    sa.CheckConstraint('free_days >= 0', name='ck_trailer_storage_rules_free_days'),
    sa.CheckConstraint('reefer_plug_daily_fee_cents IS NULL OR (reefer_plug_available AND reefer_plug_daily_fee_cents >= 0)', name='ck_trailer_storage_rules_reefer_plug_fee'),
    sa.CheckConstraint('valid_until IS NULL OR valid_from <= valid_until', name='ck_trailer_storage_rules_period'),
    sa.ForeignKeyConstraint(['location_id', 'location_type'], ['locations.id', 'locations.type'], name='fk_trailer_storage_rules_location_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('wash_details',
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('location_type', sa.String(length=20), server_default=sa.text("'wash'"), nullable=False),
    sa.Column('scopes', postgresql.ARRAY(sa.String(length=20)), nullable=False),
    sa.Column('grades', postgresql.ARRAY(sa.String(length=20)), server_default=sa.text("'{}'::varchar[]"), nullable=False),
    sa.Column('issues_cleaning_document', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('issues_ecd', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("('interior' = ANY(scopes)) = (cardinality(grades) >= 1)", name='ck_wash_details_grades_need_interior'),
    sa.CheckConstraint("(NOT issues_cleaning_document OR 'interior' = ANY(scopes)) AND (NOT issues_ecd OR (issues_cleaning_document AND 'tank' = ANY(grades)))", name='ck_wash_details_documents'),
    sa.CheckConstraint("cardinality(scopes) >= 1 AND scopes <@ ARRAY['exterior', 'interior']::varchar[] AND grades <@ ARRAY['chemical', 'food_grade', 'general', 'tank']::varchar[]", name='ck_wash_details_values'),
    sa.CheckConstraint("location_type = 'wash'", name='ck_wash_details_location_type'),
    sa.ForeignKeyConstraint(['location_id', 'location_type'], ['locations.id', 'locations.type'], name='fk_wash_details_location_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('location_id')
    )
    op.add_column('locations', sa.Column('forklift_available', sa.Boolean(), nullable=True))
    op.add_column('locations', sa.Column('tail_lift_required', sa.Boolean(), nullable=True))
    op.create_check_constraint(
        'ck_locations_site_features_customer_site_only',
        'locations',
        "type = 'customer_site' OR (forklift_available IS NULL AND tail_lift_required IS NULL)",
    )
    op.add_column('parking_details', sa.Column('trailer_drop_allowed', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_constraint('ck_locations_site_features_customer_site_only', 'locations', type_='check')
    op.drop_column('parking_details', 'trailer_drop_allowed')
    op.drop_column('locations', 'tail_lift_required')
    op.drop_column('locations', 'forklift_available')
    op.drop_table('wash_details')
    op.drop_table('trailer_storage_rules')
