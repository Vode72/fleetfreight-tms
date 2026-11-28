"""routing preferences and ltl linehauls

2B-3c part 2, D64 and D96 (approved by Toni 26.11.2026). Does not edit earlier revisions.

Schema:
- routing_preferences: suggested routing per country pair (origin NULL = any; postal prefix
  reserved for later): gateway port or rail terminal on the foreign side, optional ferry route,
  onward road or rail (rail route), optional road border crossing, priority (equal =
  alternatives) and validity (D67). Composite foreign keys keep the location types and route
  modes right.
- ltl_linehauls: LTL trunk run between two terminals: ISO departure weekdays, local departure,
  cut-off and arrival (day offset), delivery promise in working days, thermo flag, validity.

Downgrade drops the tables WITH their rows (settings and demo data, re-entered if needed).

Revision ID: 6b0acbaf3f8c
Revises: 7767d6908268
Create Date: 2026-11-26 21:18:14.190133
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '6b0acbaf3f8c'
down_revision: str | None = '7767d6908268'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ltl_linehauls',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('origin_terminal_id', sa.UUID(), nullable=False),
    sa.Column('origin_terminal_type', sa.String(length=20), server_default=sa.text("'terminal'"), nullable=False),
    sa.Column('destination_terminal_id', sa.UUID(), nullable=False),
    sa.Column('destination_terminal_type', sa.String(length=20), server_default=sa.text("'terminal'"), nullable=False),
    sa.Column('weekdays', postgresql.ARRAY(sa.SmallInteger()), nullable=False),
    sa.Column('departure_time', sa.Time(), nullable=False),
    sa.Column('cutoff_time', sa.Time(), nullable=False),
    sa.Column('arrival_day', sa.SmallInteger(), nullable=False),
    sa.Column('arrival_time', sa.Time(), nullable=False),
    sa.Column('delivery_days', sa.SmallInteger(), nullable=False),
    sa.Column('temperature_controlled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("origin_terminal_type = 'terminal' AND destination_terminal_type = 'terminal' AND origin_terminal_id <> destination_terminal_id", name='ck_ltl_linehauls_terminals'),
    sa.CheckConstraint('cardinality(weekdays) >= 1 AND weekdays <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]', name='ck_ltl_linehauls_weekdays'),
    sa.CheckConstraint('cutoff_time <= departure_time AND arrival_day BETWEEN 0 AND 14 AND (arrival_day > 0 OR arrival_time > departure_time)', name='ck_ltl_linehauls_times'),
    sa.CheckConstraint('delivery_days >= 0', name='ck_ltl_linehauls_delivery_days'),
    sa.CheckConstraint('valid_until IS NULL OR valid_from <= valid_until', name='ck_ltl_linehauls_period'),
    sa.ForeignKeyConstraint(['destination_terminal_id', 'destination_terminal_type'], ['locations.id', 'locations.type'], name='fk_ltl_linehauls_destination_terminal', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['origin_terminal_id', 'origin_terminal_type'], ['locations.id', 'locations.type'], name='fk_ltl_linehauls_origin_terminal', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ltl_linehauls_destination_terminal_id', 'ltl_linehauls', ['destination_terminal_id'], unique=False)
    op.create_index('ix_ltl_linehauls_origin_terminal_id', 'ltl_linehauls', ['origin_terminal_id'], unique=False)
    op.create_table('routing_preferences',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('origin_country', sa.String(length=2), nullable=True),
    sa.Column('destination_country', sa.String(length=2), nullable=False),
    sa.Column('postal_prefix', sa.String(length=10), nullable=True),
    sa.Column('priority', sa.SmallInteger(), nullable=False),
    sa.Column('gateway_location_id', sa.UUID(), nullable=True),
    sa.Column('gateway_location_type', sa.String(length=20), nullable=True),
    sa.Column('line_route_id', sa.UUID(), nullable=True),
    sa.Column('line_route_mode', sa.String(length=10), nullable=True),
    sa.Column('onward_mode', sa.String(length=10), server_default=sa.text("'road'"), nullable=False),
    sa.Column('onward_route_id', sa.UUID(), nullable=True),
    sa.Column('onward_route_mode', sa.String(length=10), nullable=True),
    sa.Column('via_location_id', sa.UUID(), nullable=True),
    sa.Column('via_location_type', sa.String(length=20), nullable=True),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(gateway_location_id IS NULL) = (gateway_location_type IS NULL) AND (line_route_id IS NULL) = (line_route_mode IS NULL) AND (onward_route_id IS NULL) = (onward_route_mode IS NULL) AND (via_location_id IS NULL) = (via_location_type IS NULL) AND (gateway_location_id IS NULL OR gateway_location_type IN ('port', 'rail_terminal')) AND (line_route_id IS NULL OR line_route_mode = 'ferry') AND (onward_route_id IS NULL OR onward_route_mode = 'rail') AND (via_location_id IS NULL OR via_location_type = 'border_crossing') AND (gateway_location_id IS NOT NULL OR via_location_id IS NOT NULL) AND (line_route_id IS NULL OR gateway_location_id IS NOT NULL) AND ((onward_mode = 'rail') = (onward_route_id IS NOT NULL)) AND (onward_route_id IS NULL OR gateway_location_id IS NOT NULL)", name='ck_routing_preferences_legs'),
    sa.CheckConstraint("destination_country ~ '^[A-Z]{2}$' AND (origin_country IS NULL OR origin_country ~ '^[A-Z]{2}$') AND (origin_country IS NULL OR origin_country <> destination_country)", name='ck_routing_preferences_countries'),
    sa.CheckConstraint("onward_mode IN ('rail', 'road')", name='ck_routing_preferences_onward_mode'),
    sa.CheckConstraint("postal_prefix IS NULL OR postal_prefix ~ '^[0-9A-Z]{1,10}$'", name='ck_routing_preferences_postal_prefix'),
    sa.CheckConstraint('priority >= 1', name='ck_routing_preferences_priority'),
    sa.CheckConstraint('valid_until IS NULL OR valid_from <= valid_until', name='ck_routing_preferences_period'),
    sa.ForeignKeyConstraint(['gateway_location_id', 'gateway_location_type'], ['locations.id', 'locations.type'], name='fk_routing_preferences_gateway', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['line_route_id', 'line_route_mode'], ['line_routes.id', 'line_routes.mode'], name='fk_routing_preferences_line_route', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['onward_route_id', 'onward_route_mode'], ['line_routes.id', 'line_routes.mode'], name='fk_routing_preferences_onward_route', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['via_location_id', 'via_location_type'], ['locations.id', 'locations.type'], name='fk_routing_preferences_via', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_routing_preferences_destination', 'routing_preferences', ['destination_country', 'origin_country'], unique=False)
    op.create_index('ix_routing_preferences_gateway_location_id', 'routing_preferences', ['gateway_location_id'], unique=False)
    op.create_index('ix_routing_preferences_line_route_id', 'routing_preferences', ['line_route_id'], unique=False)
    op.create_index('ix_routing_preferences_onward_route_id', 'routing_preferences', ['onward_route_id'], unique=False)
    op.create_index('ix_routing_preferences_via_location_id', 'routing_preferences', ['via_location_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_routing_preferences_via_location_id', table_name='routing_preferences')
    op.drop_index('ix_routing_preferences_onward_route_id', table_name='routing_preferences')
    op.drop_index('ix_routing_preferences_line_route_id', table_name='routing_preferences')
    op.drop_index('ix_routing_preferences_gateway_location_id', table_name='routing_preferences')
    op.drop_index('ix_routing_preferences_destination', table_name='routing_preferences')
    op.drop_table('routing_preferences')
    op.drop_index('ix_ltl_linehauls_origin_terminal_id', table_name='ltl_linehauls')
    op.drop_index('ix_ltl_linehauls_destination_terminal_id', table_name='ltl_linehauls')
    op.drop_table('ltl_linehauls')
