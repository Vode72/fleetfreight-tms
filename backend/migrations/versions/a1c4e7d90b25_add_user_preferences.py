"""add user theme and language preferences

Revision ID: a1c4e7d90b25
Revises: f73b3971a12f
Create Date: 2026-11-16

D49: the chosen theme and language are stored on the user. NULL means "use the default".
VARCHAR with CHECK constraints (same approach as users.role).
"""

import sqlalchemy as sa
from alembic import op

revision = "a1c4e7d90b25"
down_revision = "f73b3971a12f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("theme", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("language", sa.String(length=5), nullable=True))
    op.create_check_constraint(
        "ck_users_theme", "users", "theme IN ('business-light', 'control-dark')"
    )
    op.create_check_constraint("ck_users_language", "users", "language IN ('en', 'fi')")


def downgrade() -> None:
    op.drop_constraint("ck_users_language", "users", type_="check")
    op.drop_constraint("ck_users_theme", "users", type_="check")
    op.drop_column("users", "language")
    op.drop_column("users", "theme")
