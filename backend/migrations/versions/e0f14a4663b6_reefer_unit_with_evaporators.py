"""one reefer unit per load unit with evaporators; maximum rear share of the partition

Revision ID: e0f14a4663b6
Revises: d3ad319be9a8
Create Date: 2026-11-18

D76 refined 18.11.2026 (Toni): every thermo load unit has ONE reefer unit (the machine, at the
front). Its evaporators (indoor units) serve the zones: FB and FS one, FD two (front and rear of
the partition). Does not edit d3ad319be9a8.

Schema:
- reefer_evaporators (new): reefer_unit_id + load_unit_id (composite foreign key to the machine,
  so both are on the same load unit), position front | rear, unique (reefer_unit_id, position).
- compartments.reefer_unit_id is replaced by evaporator_id (composite foreign key to the
  evaporator on the same load unit; unique: one compartment per evaporator).
- reefer_units loses position; unique load_unit_id (one machine per load unit).
- load_units.partition_max_rear_share (NUMERIC(4,3), NULL = no limit): the largest share of the
  pallet rows for the rear compartment; only with a partition.

Existing data:
- Per load unit the front machine (or, without one, the rear one) is kept. Every old machine
  becomes an evaporator at its old position under the kept machine, and each compartment moves
  from its old machine to that evaporator. A compartment without a machine (NULL: "not recorded
  or served by both" in the old model) stays without an evaporator.
- The result follows the model code (D76): FB and FS get their one evaporator at the front (an
  old rear-only machine moves to the front); an FD with one old machine gets the missing
  evaporator. An FB or FS with two old machines stops the upgrade (it cannot be one zone without
  guessing which compartment goes).
- The removed machine's reefer service periods move to the kept machine. If they overlap the kept
  machine's periods, the exclusion constraint stops the upgrade (nothing is lost silently).
- If one old machine served several compartments, the upgrade stops with an error (an
  evaporator serves one compartment).
- The removed machine's name and power source are dropped: the kept machine's values stand.

The downgrade restores a rear machine for every rear evaporator (copying the kept machine's name
and power source), points the compartments back to the machines and drops the new table and
column. Service periods stay on the front machine. A load unit that had only a rear machine comes
back with a front machine and a rear one (both with the kept values).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e0f14a4663b6"
down_revision: str | None = "d3ad319be9a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PARTITION_VALUES_OLD = (
    "partition_thickness_mm > 0 AND partition_step_pallet_rows >= 1"
    " AND min_pallets_front >= 0 AND min_pallets_rear >= 0"
)
_PARTITION_VALUES_NEW = (
    _PARTITION_VALUES_OLD + " AND (partition_max_rear_share IS NULL"
    " OR (partition AND partition_max_rear_share > 0 AND partition_max_rear_share <= 1))"
)

# The machine kept per load unit: front first, otherwise the rear one.
_KEEPERS = (
    "SELECT DISTINCT ON (load_unit_id) load_unit_id, id FROM reefer_units"
    " ORDER BY load_unit_id, (position = 'front') DESC"
)


def upgrade() -> None:
    # load_units: maximum rear share of the partition
    op.add_column(
        "load_units", sa.Column("partition_max_rear_share", sa.Numeric(4, 3), nullable=True)
    )
    op.drop_constraint("ck_load_units_partition_values", "load_units", type_="check")
    op.create_check_constraint(
        "ck_load_units_partition_values", "load_units", _PARTITION_VALUES_NEW
    )

    op.create_table(
        "reefer_evaporators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("reefer_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("load_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["reefer_unit_id", "load_unit_id"],
            ["reefer_units.id", "reefer_units.load_unit_id"],
            name="fk_reefer_evaporators_reefer_unit_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "reefer_unit_id", "position", name="uq_reefer_evaporators_reefer_unit_id_position"
        ),
        sa.UniqueConstraint("id", "load_unit_id", name="uq_reefer_evaporators_id_load_unit_id"),
        sa.CheckConstraint("position IN ('front', 'rear')", name="ck_reefer_evaporators_position"),
    )
    op.create_index("ix_reefer_evaporators_load_unit_id", "reefer_evaporators", ["load_unit_id"])

    # Data: stop before changing anything if one machine served several compartments.
    shared = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM (SELECT reefer_unit_id FROM compartments"
                " WHERE reefer_unit_id IS NOT NULL GROUP BY reefer_unit_id"
                " HAVING count(*) > 1) s"
            )
        )
        .scalar()
    )
    if shared:
        raise RuntimeError(
            f"{shared} reefer unit(s) serve several compartments; an evaporator serves one (D76):"
            " point the compartments to one machine each first (SELECT reefer_unit_id FROM"
            " compartments GROUP BY reefer_unit_id HAVING count(*) > 1)"
        )
    single_zone_twins = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT string_agg(l.registration, ', ') FROM load_units l WHERE l.model_code IN"
                " ('FB', 'FS') AND (SELECT count(*) FROM reefer_units r"
                " WHERE r.load_unit_id = l.id) > 1"
            )
        )
        .scalar()
    )
    if single_zone_twins:
        raise RuntimeError(
            f"FB / FS load units with two reefer units ({single_zone_twins}): FB and FS have one"
            " evaporator and one zone (D76); remove the extra machine first"
        )
    # Every old machine becomes an evaporator at its position under the kept machine.
    # FB and FS: the one evaporator is at the front.
    op.execute(
        "UPDATE reefer_units r SET position = 'front' FROM load_units l"
        " WHERE l.id = r.load_unit_id AND l.model_code IN ('FB', 'FS')"
    )
    op.execute(
        "INSERT INTO reefer_evaporators (reefer_unit_id, load_unit_id, position)"
        f" SELECT k.id, r.load_unit_id, r.position FROM reefer_units r JOIN ({_KEEPERS}) k"
        " ON k.load_unit_id = r.load_unit_id"
    )
    # FD: front and rear; a missing one is added (no compartment yet).
    op.execute(
        "INSERT INTO reefer_evaporators (reefer_unit_id, load_unit_id, position)"
        f" SELECT k.id, k.load_unit_id, p.position FROM ({_KEEPERS}) k"
        " JOIN load_units l ON l.id = k.load_unit_id AND l.model_code = 'FD'"
        " CROSS JOIN (VALUES ('front'), ('rear')) AS p(position)"
        " WHERE NOT EXISTS (SELECT 1 FROM reefer_evaporators e"
        " WHERE e.reefer_unit_id = k.id AND e.position = p.position)"
    )
    op.add_column(
        "compartments",
        sa.Column("evaporator_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "UPDATE compartments c SET evaporator_id = e.id FROM reefer_units r"
        " JOIN reefer_evaporators e ON e.load_unit_id = r.load_unit_id"
        " AND e.position = r.position WHERE c.reefer_unit_id = r.id"
    )
    # Service periods of the removed machines move to the kept machine (overlap -> error).
    op.execute(
        f"UPDATE equipment_qualifications q SET reefer_unit_id = k.id FROM reefer_units r"
        f" JOIN ({_KEEPERS}) k ON k.load_unit_id = r.load_unit_id"
        " WHERE q.reefer_unit_id = r.id AND r.id <> k.id"
    )

    # compartments: from the machine to the evaporator
    op.drop_constraint("fk_compartments_reefer_unit_id", "compartments", type_="foreignkey")
    op.drop_index("ix_compartments_reefer_unit_id", table_name="compartments")
    op.drop_column("compartments", "reefer_unit_id")
    op.create_foreign_key(
        "fk_compartments_evaporator_id",
        "compartments",
        "reefer_evaporators",
        ["evaporator_id", "load_unit_id"],
        ["id", "load_unit_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_compartments_evaporator_id", "compartments", ["evaporator_id"])

    # reefer_units: the extra machines go, then the position
    op.execute(
        f"DELETE FROM reefer_units WHERE id NOT IN (SELECT id FROM ({_KEEPERS}) k)"
    )
    op.drop_constraint("ck_reefer_units_position", "reefer_units", type_="check")
    op.drop_constraint("uq_reefer_units_load_unit_id_position", "reefer_units", type_="unique")
    op.drop_column("reefer_units", "position")
    op.create_unique_constraint("uq_reefer_units_load_unit_id", "reefer_units", ["load_unit_id"])


def downgrade() -> None:
    # reefer_units: position back; the kept machine sits at the front
    op.drop_constraint("uq_reefer_units_load_unit_id", "reefer_units", type_="unique")
    op.add_column(
        "reefer_units",
        sa.Column("position", sa.String(length=10), server_default="front", nullable=False),
    )
    op.alter_column("reefer_units", "position", server_default=None)
    op.create_unique_constraint(
        "uq_reefer_units_load_unit_id_position", "reefer_units", ["load_unit_id", "position"]
    )
    op.create_check_constraint(
        "ck_reefer_units_position", "reefer_units", "position IN ('front', 'rear')"
    )
    # A rear evaporator becomes a rear machine again (name and power source copied).
    op.execute(
        "INSERT INTO reefer_units (load_unit_id, position, unit_name, power_source)"
        " SELECT r.load_unit_id, 'rear', r.unit_name, r.power_source FROM reefer_evaporators e"
        " JOIN reefer_units r ON r.id = e.reefer_unit_id WHERE e.position = 'rear'"
    )

    # compartments: from the evaporator back to the machine at the same position
    op.add_column(
        "compartments",
        sa.Column("reefer_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "UPDATE compartments c SET reefer_unit_id = r.id FROM reefer_evaporators e"
        " JOIN reefer_units r ON r.load_unit_id = e.load_unit_id AND r.position = e.position"
        " WHERE c.evaporator_id = e.id"
    )
    op.drop_constraint("uq_compartments_evaporator_id", "compartments", type_="unique")
    op.drop_constraint("fk_compartments_evaporator_id", "compartments", type_="foreignkey")
    op.drop_column("compartments", "evaporator_id")
    op.create_foreign_key(
        "fk_compartments_reefer_unit_id",
        "compartments",
        "reefer_units",
        ["reefer_unit_id", "load_unit_id"],
        ["id", "load_unit_id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_compartments_reefer_unit_id", "compartments", ["reefer_unit_id"])

    op.drop_table("reefer_evaporators")

    op.drop_constraint("ck_load_units_partition_values", "load_units", type_="check")
    op.create_check_constraint(
        "ck_load_units_partition_values", "load_units", _PARTITION_VALUES_OLD
    )
    op.drop_column("load_units", "partition_max_rear_share")
