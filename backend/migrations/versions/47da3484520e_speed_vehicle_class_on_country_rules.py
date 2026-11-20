"""speed vehicle class on country rules

D87: the vehicle class the recorded speed limits apply to, as a gross weight threshold and its
basis (vehicle or combination). Required once a speed limit is recorded.

Revision ID: 47da3484520e
Revises: c3888037643f
Create Date: 2026-11-20 19:23:12.832463
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '47da3484520e'
down_revision: str | None = 'c3888037643f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CHECK = (
    "(speed_over_gross_weight_kg IS NULL) = (speed_weight_basis IS NULL)"
    " AND (speed_over_gross_weight_kg IS NULL OR speed_over_gross_weight_kg > 0)"
    " AND (speed_weight_basis IS NULL OR speed_weight_basis IN ('combination', 'vehicle'))"
    " AND ((truck_speed_motorway_kmh IS NULL AND truck_speed_other_kmh IS NULL)"
    " OR speed_over_gross_weight_kg IS NOT NULL)"
)


def upgrade() -> None:
    op.add_column('country_rules', sa.Column('speed_over_gross_weight_kg', sa.Integer(), nullable=True))
    op.add_column('country_rules', sa.Column('speed_weight_basis', sa.String(length=15), nullable=True))
    # Rows loaded before D87 have speeds but no class: the class is unknown, so their speeds
    # become unrecorded and the reference data loader fills speeds and class in again.
    op.execute(
        'UPDATE country_rules SET truck_speed_motorway_kmh = NULL, truck_speed_other_kmh = NULL'
    )
    op.create_check_constraint('ck_country_rules_speed_class', 'country_rules', _CHECK)


def downgrade() -> None:
    op.drop_constraint('ck_country_rules_speed_class', 'country_rules', type_='check')
    op.drop_column('country_rules', 'speed_weight_basis')
    op.drop_column('country_rules', 'speed_over_gross_weight_kg')
