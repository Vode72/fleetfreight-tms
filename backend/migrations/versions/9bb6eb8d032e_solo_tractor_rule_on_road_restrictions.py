"""solo tractor rule on road restrictions

Revision ID: 9bb6eb8d032e
Revises: 2cb43f9f78c1
Create Date: 2026-11-19

D85: whether a tractor unit driving without a trailer falls under a driving ban: exempt,
conditional or not exempt; NULL = not recorded. Only driving bans carry it. New nullable column,
so existing rows stay valid; the reference data loader fills it for the existing bans.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9bb6eb8d032e"
down_revision: str | None = "2cb43f9f78c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("road_restrictions", sa.Column("solo_tractor", sa.String(length=15), nullable=True))
    op.create_check_constraint(
        "ck_road_restrictions_solo_tractor",
        "road_restrictions",
        "solo_tractor IS NULL OR (restriction_type = 'driving_ban'"
        " AND solo_tractor IN ('conditional', 'exempt', 'not_exempt'))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_road_restrictions_solo_tractor", "road_restrictions", type_="check")
    op.drop_column("road_restrictions", "solo_tractor")
