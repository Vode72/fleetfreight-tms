"""archiving, RESTRICT foreign keys and the own carrier's link to the own company

Revision ID: f0c09cb23c9d
Revises: c52d8e3f1a47
Create Date: 2026-11-18

Phase 2B-2, revision A (D72, D73). Does not edit c52d8e3f1a47.

D72 (archive instead of delete):
- archived_at (timestamptz, NULL = active) on customers, locations, carriers and drivers.
- Every register foreign key becomes ON DELETE RESTRICT. Only driver_qualifications.driver_id
  was CASCADE; the others were the default (NO ACTION), recreated as RESTRICT so the rule is
  explicit and uniform. (sessions.user_id stays CASCADE: users are not a register.)

D73 (the own company is stored once):
- carriers.customer_id references customers. CHECK: type = 'own' exactly when customer_id is set.
- The own carrier has no name, business ID or country of its own; they are read from the
  customer row. So carriers.name and carriers.country become nullable, with a CHECK that an own
  carrier leaves name, business_id and country empty and any other carrier has name and country.
- That the referenced customer is the own company spans two tables; it is checked in
  domain.parties.validate_carrier_customer_link (service layer, seed, tests).
- Existing data: an own carrier is linked to the own company's customer row and its duplicated
  name, business ID and country are cleared. If an own carrier exists but no own company, the
  upgrade stops with an error instead of guessing.
The downgrade copies name, business ID and country back from the customer row before it restores
NOT NULL, and recreates the old foreign keys (driver_qualifications CASCADE again).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f0c09cb23c9d"
down_revision: str | None = "c52d8e3f1a47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, constraint name, referenced table, ondelete before this revision)
_FOREIGN_KEYS: tuple[tuple[str, str, str, str, str | None], ...] = (
    ("locations", "customer_id", "fk_locations_customer_id", "customers", None),
    ("locations", "parent_location_id", "fk_locations_parent_location_id", "locations", None),
    ("drivers", "carrier_id", "fk_drivers_carrier_id", "carriers", None),
    ("drivers", "home_location_id", "fk_drivers_home_location_id", "locations", None),
    (
        "driver_qualifications",
        "driver_id",
        "fk_driver_qualifications_driver_id",
        "drivers",
        "CASCADE",
    ),
)


def _recreate_foreign_keys(*, restrict: bool) -> None:
    """Drop and recreate the register FKs as RESTRICT, or (downgrade) with their old behaviour."""
    for table, column, name, target, old in _FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            target,
            [column],
            ["id"],
            ondelete="RESTRICT" if restrict else old,
        )


def upgrade() -> None:
    for table in ("customers", "locations", "carriers", "drivers"):
        op.add_column(table, sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    _recreate_foreign_keys(restrict=True)

    op.add_column("carriers", sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_carriers_customer_id",
        "carriers",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_carriers_customer_id", "carriers", ["customer_id"])

    bind = op.get_bind()
    has_own_carrier = bind.execute(sa.text("SELECT 1 FROM carriers WHERE type = 'own'")).scalar()
    has_own_company = bind.execute(
        sa.text("SELECT 1 FROM customers WHERE type = 'own_company'")
    ).scalar()
    if has_own_carrier and not has_own_company:
        raise RuntimeError(
            "carriers has an own carrier but customers has no own_company row (D73): "
            "create the own company's customer row first"
        )
    op.alter_column("carriers", "name", existing_type=sa.String(length=200), nullable=True)
    op.alter_column("carriers", "country", existing_type=sa.String(length=2), nullable=True)
    op.execute(
        "UPDATE carriers SET customer_id = (SELECT id FROM customers WHERE type = 'own_company'),"
        " name = NULL, business_id = NULL, country = NULL WHERE type = 'own'"
    )
    op.create_check_constraint(
        "ck_carriers_own_link", "carriers", "(type = 'own') = (customer_id IS NOT NULL)"
    )
    op.create_check_constraint(
        "ck_carriers_identity_source",
        "carriers",
        "(type = 'own' AND name IS NULL AND business_id IS NULL AND country IS NULL)"
        " OR (type <> 'own' AND name IS NOT NULL AND country IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_carriers_identity_source", "carriers", type_="check")
    op.drop_constraint("ck_carriers_own_link", "carriers", type_="check")
    op.execute(
        "UPDATE carriers SET name = c.name, business_id = c.business_id, country = c.country"
        " FROM customers c WHERE carriers.customer_id = c.id"
    )
    op.alter_column("carriers", "country", existing_type=sa.String(length=2), nullable=False)
    op.alter_column("carriers", "name", existing_type=sa.String(length=200), nullable=False)
    op.drop_index("ix_carriers_customer_id", table_name="carriers")
    op.drop_constraint("fk_carriers_customer_id", "carriers", type_="foreignkey")
    op.drop_column("carriers", "customer_id")

    _recreate_foreign_keys(restrict=False)

    for table in ("drivers", "carriers", "locations", "customers"):
        op.drop_column(table, "archived_at")
