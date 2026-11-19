"""allow unrecorded toll system on country rules

NULL means "not recorded yet", like the other country rule values (D84): a toll system is only
recorded when an official source for it has been checked. Downgrade deletes the rows that have no
toll system recorded, since a value cannot be invented; they are reference data that the loader
(scripts/seed_reference_data.py) can load again.

Revision ID: c3888037643f
Revises: 9bb6eb8d032e
Create Date: 2026-11-19 16:43:28.697223
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'c3888037643f'
down_revision: str | None = '9bb6eb8d032e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('country_rules', 'toll_system', existing_type=sa.String(length=20), nullable=True)


def downgrade() -> None:
    op.execute('DELETE FROM country_rules WHERE toll_system IS NULL')
    op.alter_column('country_rules', 'toll_system', existing_type=sa.String(length=20), nullable=False)
