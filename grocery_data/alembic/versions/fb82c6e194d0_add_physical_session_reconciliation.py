"""add explicit physical-session snapshot reconciliation

Revision ID: fb82c6e194d0
Revises: fa71c2d8e4b3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fb82c6e194d0"
down_revision: str | Sequence[str] | None = "fa71c2d8e4b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "physical_validation_session_reconciliations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("validation_session_id", sa.String(length=64), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("grocery_context_id", sa.String(length=255), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["catalog_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_session_id"],
            ["physical_validation_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "validation_session_id",
            name="uq_physical_validation_session_reconciliation_session",
        ),
    )
    op.create_index(
        "ix_physical_validation_reconciliation_snapshot",
        "physical_validation_session_reconciliations",
        ["source_snapshot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_physical_validation_reconciliation_snapshot",
        table_name="physical_validation_session_reconciliations",
    )
    op.drop_table("physical_validation_session_reconciliations")
