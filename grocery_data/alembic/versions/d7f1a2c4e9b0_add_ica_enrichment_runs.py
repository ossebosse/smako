"""add ICA enrichment run diagnostics

Revision ID: d7f1a2c4e9b0
Revises: c58e2d9e11a0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7f1a2c4e9b0"
down_revision: str | None = "c58e2d9e11a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ica_enrichment_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("challenge_encountered", sa.Boolean(), nullable=False),
        sa.Column("pages_visited", sa.Integer(), nullable=False),
        sa.Column("product_ids_seen", sa.Integer(), nullable=False),
        sa.Column("price_observations", sa.Integer(), nullable=False),
        sa.Column("route_metrics", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ica_enrichment_store_finished",
        "ica_enrichment_runs",
        ["store_id", "finished_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ica_enrichment_store_finished", table_name="ica_enrichment_runs")
    op.drop_table("ica_enrichment_runs")
