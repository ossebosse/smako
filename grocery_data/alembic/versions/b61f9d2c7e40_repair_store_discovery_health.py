"""repair missing physical-store discovery health table

Revision ID: b61f9d2c7e40
Revises: a8d3e5f7b901

The discovery-health table was added to the a8 revision after an operator
working database had already been stamped at a8.  This additive repair makes
that historical schema drift explicit without rewriting or restamping the
operator database.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b61f9d2c7e40"
down_revision: str | None = "a8d3e5f7b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh databases already receive this logical a8 table from the current
    # a8 migration. Databases stamped before that addition do not. Inspecting
    # the real schema lets one repair revision safely support both histories.
    if sa.inspect(op.get_bind()).has_table("physical_store_discovery_health"):
        return

    op.create_table(
        "physical_store_discovery_health",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("normalized_city", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("discovered_count", sa.Integer(), nullable=False),
        sa.Column("previous_count", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chain",
            "normalized_city",
            name="uq_physical_store_discovery_health_scope",
        ),
    )
    op.create_index(
        "ix_physical_store_discovery_health_status_observed",
        "physical_store_discovery_health",
        ["status", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    # This is a repair for a table that logically belongs to a8, not a new
    # feature introduced after a8. Downgrading to a8 must therefore retain it;
    # a subsequent downgrade of a8 remains responsible for removing it.
    pass
