"""ferry and rail lines

2B-3c part 1, D94 (approved by Toni 22.11.2026). Does not edit earlier revisions.

Schema:
- line_operators (ferry or rail, demo names), vessels (ferry operators only: type, lane metres,
  deck height, reefer plugs, accompanied / unaccompanied units, driver cabins) and
  vessel_adr_classes (allowed, forbidden or pre-approval per dangerous goods class).
- line_routes: one direction of a line with check-in, cut-off and dangerous goods declaration
  defaults; line_route_stops: ports (ferry) or rail terminals (rail) in order, loading/unloading.
- line_schedules: weekly pattern (first departure's ISO weekday, vessel, validity) and
  line_schedule_calls: local arrival and departure at every stop as day offsets.
- line_departures ("lähtö"): one dated trip, generated from a schedule or entered by hand, with
  status and overrides; line_departure_calls: planned, cut-off and estimated times per stop.
Composite foreign keys keep the mode consistent (operator, route, stops, schedules) and calls on
the stops of their own route.

Downgrade drops the tables WITH their rows (timetables and departures are demo or re-entered
data; bookings referring to departures come in 2C).

Revision ID: f1f1b6c62fc0
Revises: 4523ff2f5448
Create Date: 2026-11-22 20:44:52.675594
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'f1f1b6c62fc0'
down_revision: str | None = '4523ff2f5448'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('line_operators',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(name) <> ''", name='ck_line_operators_name_not_blank'),
    sa.CheckConstraint("mode IN ('ferry', 'rail')", name='ck_line_operators_mode'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'mode', name='uq_line_operators_id_mode'),
    sa.UniqueConstraint('name', name='uq_line_operators_name')
    )
    op.create_table('line_routes',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('operator_id', sa.UUID(), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('accompanied', sa.Boolean(), nullable=False),
    sa.Column('unaccompanied', sa.Boolean(), nullable=False),
    sa.Column('checkin_minutes', sa.Integer(), nullable=True),
    sa.Column('cutoff_minutes', sa.Integer(), nullable=True),
    sa.Column('dg_declaration_hours', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(accompanied OR unaccompanied) AND (mode = 'ferry' OR NOT accompanied) AND (checkin_minutes IS NULL OR (accompanied AND checkin_minutes >= 0)) AND (cutoff_minutes IS NULL OR (unaccompanied AND cutoff_minutes >= 0)) AND (dg_declaration_hours IS NULL OR dg_declaration_hours >= 0)", name='ck_line_routes_units_and_defaults'),
    sa.CheckConstraint("btrim(name) <> ''", name='ck_line_routes_name_not_blank'),
    sa.CheckConstraint("mode IN ('ferry', 'rail')", name='ck_line_routes_mode'),
    sa.ForeignKeyConstraint(['operator_id', 'mode'], ['line_operators.id', 'line_operators.mode'], name='fk_line_routes_operator_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'mode', name='uq_line_routes_id_mode'),
    sa.UniqueConstraint('name', name='uq_line_routes_name')
    )
    op.create_index('ix_line_routes_operator_id', 'line_routes', ['operator_id'], unique=False)
    op.create_table('vessels',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('operator_id', sa.UUID(), nullable=False),
    sa.Column('operator_mode', sa.String(length=10), server_default=sa.text("'ferry'"), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('vessel_type', sa.String(length=10), nullable=False),
    sa.Column('lane_metres', sa.Integer(), nullable=True),
    sa.Column('deck_height_mm', sa.Integer(), nullable=True),
    sa.Column('reefer_plug_count', sa.Integer(), nullable=True),
    sa.Column('accompanied', sa.Boolean(), nullable=False),
    sa.Column('unaccompanied', sa.Boolean(), nullable=False),
    sa.Column('driver_cabins', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(name) <> ''", name='ck_vessels_name_not_blank'),
    sa.CheckConstraint("operator_mode = 'ferry'", name='ck_vessels_operator_mode'),
    sa.CheckConstraint("vessel_type IN ('ropax', 'roro')", name='ck_vessels_vessel_type'),
    sa.CheckConstraint('(accompanied OR unaccompanied) AND (NOT accompanied OR driver_cabins)', name='ck_vessels_units'),
    sa.CheckConstraint('(lane_metres IS NULL OR lane_metres > 0) AND (deck_height_mm IS NULL OR deck_height_mm > 0) AND (reefer_plug_count IS NULL OR reefer_plug_count >= 0)', name='ck_vessels_capacities'),
    sa.ForeignKeyConstraint(['operator_id', 'operator_mode'], ['line_operators.id', 'line_operators.mode'], name='fk_vessels_operator_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'operator_id', name='uq_vessels_id_operator_id'),
    sa.UniqueConstraint('name', name='uq_vessels_name')
    )
    op.create_index('ix_vessels_operator_id', 'vessels', ['operator_id'], unique=False)
    op.create_table('line_route_stops',
    sa.Column('route_id', sa.UUID(), nullable=False),
    sa.Column('sequence', sa.SmallInteger(), nullable=False),
    sa.Column('route_mode', sa.String(length=10), nullable=False),
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('location_type', sa.String(length=20), nullable=False),
    sa.Column('loading', sa.Boolean(), nullable=False),
    sa.Column('unloading', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(route_mode = 'ferry' AND location_type = 'port') OR (route_mode = 'rail' AND location_type = 'rail_terminal')", name='ck_line_route_stops_location_type'),
    sa.CheckConstraint('loading OR unloading', name='ck_line_route_stops_handles_units'),
    sa.CheckConstraint('sequence >= 1', name='ck_line_route_stops_sequence'),
    sa.ForeignKeyConstraint(['location_id', 'location_type'], ['locations.id', 'locations.type'], name='fk_line_route_stops_location_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['route_id', 'route_mode'], ['line_routes.id', 'line_routes.mode'], name='fk_line_route_stops_route_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('route_id', 'sequence')
    )
    op.create_index('ix_line_route_stops_location_id', 'line_route_stops', ['location_id'], unique=False)
    op.create_table('line_schedules',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('route_id', sa.UUID(), nullable=False),
    sa.Column('route_mode', sa.String(length=10), nullable=False),
    sa.Column('weekday', sa.SmallInteger(), nullable=False),
    sa.Column('vessel_id', sa.UUID(), nullable=True),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(route_mode = 'rail') = (vessel_id IS NULL)", name='ck_line_schedules_vessel'),
    sa.CheckConstraint('valid_until IS NULL OR valid_from <= valid_until', name='ck_line_schedules_period'),
    sa.CheckConstraint('weekday BETWEEN 1 AND 7', name='ck_line_schedules_weekday'),
    sa.ForeignKeyConstraint(['route_id', 'route_mode'], ['line_routes.id', 'line_routes.mode'], name='fk_line_schedules_route_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vessel_id'], ['vessels.id'], name='fk_line_schedules_vessel_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'route_id', name='uq_line_schedules_id_route_id')
    )
    op.create_index('ix_line_schedules_route_id', 'line_schedules', ['route_id'], unique=False)
    op.create_table('vessel_adr_classes',
    sa.Column('vessel_id', sa.UUID(), nullable=False),
    sa.Column('adr_class', sa.String(length=4), nullable=False),
    sa.Column('acceptance', sa.String(length=15), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("acceptance IN ('allowed', 'forbidden', 'pre_approval')", name='ck_vessel_adr_classes_acceptance'),
    sa.CheckConstraint("adr_class IN ('1', '2', '3', '4.1', '4.2', '4.3', '5.1', '5.2', '6.1', '6.2', '7', '8', '9')", name='ck_vessel_adr_classes_class'),
    sa.ForeignKeyConstraint(['vessel_id'], ['vessels.id'], name='fk_vessel_adr_classes_vessel_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('vessel_id', 'adr_class')
    )
    op.create_table('line_departures',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('route_id', sa.UUID(), nullable=False),
    sa.Column('route_mode', sa.String(length=10), nullable=False),
    sa.Column('schedule_id', sa.UUID(), nullable=True),
    sa.Column('service_date', sa.Date(), nullable=False),
    sa.Column('vessel_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=10), server_default=sa.text("'planned'"), nullable=False),
    sa.Column('checkin_minutes', sa.Integer(), nullable=True),
    sa.Column('cutoff_minutes', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("route_mode = 'ferry' OR vessel_id IS NULL", name='ck_line_departures_vessel'),
    sa.CheckConstraint("status IN ('cancelled', 'delayed', 'planned')", name='ck_line_departures_status'),
    sa.CheckConstraint('(checkin_minutes IS NULL OR checkin_minutes >= 0) AND (cutoff_minutes IS NULL OR cutoff_minutes >= 0)', name='ck_line_departures_overrides'),
    sa.ForeignKeyConstraint(['route_id', 'route_mode'], ['line_routes.id', 'line_routes.mode'], name='fk_line_departures_route_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['schedule_id', 'route_id'], ['line_schedules.id', 'line_schedules.route_id'], name='fk_line_departures_schedule_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vessel_id'], ['vessels.id'], name='fk_line_departures_vessel_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'route_id', name='uq_line_departures_id_route_id'),
    sa.UniqueConstraint('schedule_id', 'service_date', name='uq_line_departures_schedule_id_service_date')
    )
    op.create_index('ix_line_departures_route_id_service_date', 'line_departures', ['route_id', 'service_date'], unique=False)
    op.create_table('line_schedule_calls',
    sa.Column('schedule_id', sa.UUID(), nullable=False),
    sa.Column('sequence', sa.SmallInteger(), nullable=False),
    sa.Column('route_id', sa.UUID(), nullable=False),
    sa.Column('arrival_day', sa.SmallInteger(), nullable=True),
    sa.Column('arrival_time', sa.Time(), nullable=True),
    sa.Column('departure_day', sa.SmallInteger(), nullable=True),
    sa.Column('departure_time', sa.Time(), nullable=True),
    sa.Column('cutoff_minutes', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(arrival_day IS NULL) = (arrival_time IS NULL) AND (departure_day IS NULL) = (departure_time IS NULL) AND (arrival_day IS NULL OR arrival_day BETWEEN 0 AND 14) AND (departure_day IS NULL OR departure_day BETWEEN 0 AND 14) AND (arrival_day IS NOT NULL OR departure_day IS NOT NULL)', name='ck_line_schedule_calls_times'),
    sa.CheckConstraint('cutoff_minutes IS NULL OR cutoff_minutes >= 0', name='ck_line_schedule_calls_cutoff'),
    sa.ForeignKeyConstraint(['route_id', 'sequence'], ['line_route_stops.route_id', 'line_route_stops.sequence'], name='fk_line_schedule_calls_stop', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['schedule_id', 'route_id'], ['line_schedules.id', 'line_schedules.route_id'], name='fk_line_schedule_calls_schedule_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('schedule_id', 'sequence')
    )
    op.create_table('line_departure_calls',
    sa.Column('departure_id', sa.UUID(), nullable=False),
    sa.Column('sequence', sa.SmallInteger(), nullable=False),
    sa.Column('route_id', sa.UUID(), nullable=False),
    sa.Column('arrives_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('departs_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cutoff_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('estimated_arrives_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('estimated_departs_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('estimate_source', sa.Text(), nullable=True),
    sa.Column('estimated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(arrives_at IS NOT NULL OR departs_at IS NOT NULL) AND (arrives_at IS NULL OR departs_at IS NULL OR arrives_at <= departs_at) AND (cutoff_at IS NULL OR (departs_at IS NOT NULL AND cutoff_at <= departs_at))', name='ck_line_departure_calls_times'),
    sa.CheckConstraint('(estimated_arrives_at IS NULL AND estimated_departs_at IS NULL) = (estimated_at IS NULL)', name='ck_line_departure_calls_estimate'),
    sa.ForeignKeyConstraint(['departure_id', 'route_id'], ['line_departures.id', 'line_departures.route_id'], name='fk_line_departure_calls_departure_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['route_id', 'sequence'], ['line_route_stops.route_id', 'line_route_stops.sequence'], name='fk_line_departure_calls_stop', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('departure_id', 'sequence')
    )


def downgrade() -> None:
    op.drop_table('line_departure_calls')
    op.drop_table('line_schedule_calls')
    op.drop_index('ix_line_departures_route_id_service_date', table_name='line_departures')
    op.drop_table('line_departures')
    op.drop_table('vessel_adr_classes')
    op.drop_index('ix_line_schedules_route_id', table_name='line_schedules')
    op.drop_table('line_schedules')
    op.drop_index('ix_line_route_stops_location_id', table_name='line_route_stops')
    op.drop_table('line_route_stops')
    op.drop_index('ix_vessels_operator_id', table_name='vessels')
    op.drop_table('vessels')
    op.drop_index('ix_line_routes_operator_id', table_name='line_routes')
    op.drop_table('line_routes')
    op.drop_table('line_operators')
