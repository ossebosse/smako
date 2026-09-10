"""add physical validation V3 snapshot locks and comparison versions

Revision ID: fc93a7d5b214
Revises: fb82c6e194d0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "fc93a7d5b214"
down_revision: str | Sequence[str] | None = "fb82c6e194d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_existing_shape(
    inspector: Inspector,
    table_name: str,
    *,
    columns: set[str],
    unique_columns: set[str],
) -> None:
    actual_columns = {row["name"] for row in inspector.get_columns(table_name)}
    actual_unique = {
        frozenset(row["column_names"])
        for row in inspector.get_unique_constraints(table_name)
    }
    if actual_columns != columns or frozenset(unique_columns) not in actual_unique:
        raise RuntimeError(
            f"existing {table_name} does not match the required additive V3 schema"
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    locks_table = "physical_validation_snapshot_locks"
    versions_table = "physical_validation_comparison_versions"

    # Local deployments historically call metadata.create_all() at startup.
    # A process started after the model was added can therefore have the exact
    # new tables before Alembic advances.  Accept that safe, additive state
    # instead of failing the operator's first explicit migration.
    if not inspector.has_table(locks_table):
        op.create_table(
            locks_table,
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("validation_session_id", sa.String(length=64), nullable=False),
            sa.Column("source_provider", sa.String(length=32), nullable=False),
            sa.Column("grocery_context_id", sa.String(length=255), nullable=False),
            sa.Column("source_snapshot_id", sa.String(length=255), nullable=False),
            sa.Column("candidate_count", sa.Integer(), nullable=False),
            sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
            sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["validation_session_id"],
                ["physical_validation_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "validation_session_id",
                "source_provider",
                "grocery_context_id",
                "source_snapshot_id",
                name="uq_physical_validation_snapshot_lock_identity",
            ),
        )
    inspector = sa.inspect(bind)
    _require_existing_shape(
        inspector,
        locks_table,
        columns={
            "id",
            "validation_session_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
            "candidate_count",
            "evidence_sha256",
            "locked_at",
            "created_at",
        },
        unique_columns={
            "validation_session_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
        },
    )
    lock_indexes = {row["name"] for row in inspector.get_indexes(locks_table)}
    if "ix_physical_validation_snapshot_locks_session" not in lock_indexes:
        op.create_index(
            "ix_physical_validation_snapshot_locks_session",
            locks_table,
            ["validation_session_id"],
            unique=False,
        )

    if not inspector.has_table(versions_table):
        op.create_table(
            versions_table,
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("validation_session_id", sa.String(length=64), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("version_kind", sa.String(length=32), nullable=False),
            sa.Column("source_snapshot_ids", sa.JSON(), nullable=False),
            sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
            sa.Column("freshness_threshold_hours", sa.Numeric(10, 4), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["validation_session_id"],
                ["physical_validation_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "validation_session_id",
                "version_number",
                name="uq_physical_validation_comparison_version_number",
            ),
        )
    inspector = sa.inspect(bind)
    _require_existing_shape(
        inspector,
        versions_table,
        columns={
            "id",
            "validation_session_id",
            "version_number",
            "version_kind",
            "source_snapshot_ids",
            "evidence_sha256",
            "freshness_threshold_hours",
            "reason",
            "created_at",
        },
        unique_columns={"validation_session_id", "version_number"},
    )
    version_indexes = {row["name"] for row in inspector.get_indexes(versions_table)}
    if "ix_physical_validation_comparison_versions_session_kind" not in version_indexes:
        op.create_index(
            "ix_physical_validation_comparison_versions_session_kind",
            versions_table,
            ["validation_session_id", "version_kind"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    versions_table = "physical_validation_comparison_versions"
    locks_table = "physical_validation_snapshot_locks"
    if inspector.has_table(versions_table):
        op.drop_table(versions_table)
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(locks_table):
        op.drop_table(locks_table)
