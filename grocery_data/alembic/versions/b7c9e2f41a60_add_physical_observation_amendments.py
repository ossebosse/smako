"""add append-only physical observation amendments

Revision ID: b7c9e2f41a60
Revises: fc93a7d5b214
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "b7c9e2f41a60"
down_revision: str | Sequence[str] | None = "fc93a7d5b214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "physical_observation_amendments"
_COLUMNS = {
    "id",
    "validation_session_id",
    "validation_session_item_id",
    "kind",
    "payload_json",
    "payload_schema_version",
    "payload_sha256",
    "base_observation_id",
    "supersedes_amendment_id",
    "observed_at",
    "observed_at_precision",
    "reason",
    "source",
    "reference",
    "client_request_id",
    "created_at",
}


def _require_existing_shape(inspector: Inspector) -> None:
    actual_columns = {row["name"] for row in inspector.get_columns(_TABLE)}
    actual_unique = {
        frozenset(row["column_names"])
        for row in inspector.get_unique_constraints(_TABLE)
    }
    required_unique = {
        frozenset(
            {
                "validation_session_id",
                "validation_session_item_id",
                "client_request_id",
            }
        ),
        frozenset({"supersedes_amendment_id"}),
    }
    if actual_columns != _COLUMNS or not required_unique.issubset(actual_unique):
        raise RuntimeError(
            f"existing {_TABLE} does not match the required additive amendment schema"
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Local startup may run metadata.create_all() before the explicit Alembic
    # migration. Accept only the exact additive shape in that case.
    if not inspector.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("validation_session_id", sa.String(length=64), nullable=False),
            sa.Column(
                "validation_session_item_id",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("payload_schema_version", sa.Integer(), nullable=False),
            sa.Column("payload_sha256", sa.String(length=64), nullable=False),
            sa.Column("base_observation_id", sa.String(length=64), nullable=True),
            sa.Column("supersedes_amendment_id", sa.String(length=64), nullable=True),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("observed_at_precision", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("reference", sa.Text(), nullable=False),
            sa.Column("client_request_id", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "kind IN ('late_capture', 'correction')",
                name="ck_physical_observation_amendment_kind",
            ),
            sa.CheckConstraint(
                "observed_at_precision IN "
                "('exact', 'minute', 'hour', 'day', 'visit_window', 'unknown')",
                name="ck_physical_observation_amendment_time_precision",
            ),
            sa.CheckConstraint(
                "payload_schema_version = 1",
                name="ck_physical_observation_amendment_schema_version",
            ),
            sa.CheckConstraint(
                "(kind = 'late_capture' AND base_observation_id IS NULL "
                "AND supersedes_amendment_id IS NULL) OR "
                "(kind = 'correction' AND (base_observation_id IS NOT NULL "
                "OR supersedes_amendment_id IS NOT NULL))",
                name="ck_physical_observation_amendment_chain",
            ),
            sa.ForeignKeyConstraint(
                ["validation_session_id"],
                ["physical_validation_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["validation_session_item_id"],
                ["physical_validation_session_items.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["base_observation_id"],
                ["physical_price_observations.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["supersedes_amendment_id"],
                [f"{_TABLE}.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "validation_session_id",
                "validation_session_item_id",
                "client_request_id",
                name="uq_physical_observation_amendment_request",
            ),
            sa.UniqueConstraint(
                "supersedes_amendment_id",
                name="uq_physical_observation_amendment_supersedes",
            ),
        )

    inspector = sa.inspect(bind)
    _require_existing_shape(inspector)
    indexes = {row["name"] for row in inspector.get_indexes(_TABLE)}
    if "ix_physical_observation_amendments_session_created" not in indexes:
        op.create_index(
            "ix_physical_observation_amendments_session_created",
            _TABLE,
            ["validation_session_id", "created_at"],
            unique=False,
        )
    if "ix_physical_observation_amendments_item_created" not in indexes:
        op.create_index(
            "ix_physical_observation_amendments_item_created",
            _TABLE,
            ["validation_session_item_id", "created_at"],
            unique=False,
        )
    if "ux_physical_observation_amendments_item_root" not in indexes:
        op.create_index(
            "ux_physical_observation_amendments_item_root",
            _TABLE,
            ["validation_session_item_id"],
            unique=True,
            sqlite_where=sa.text("supersedes_amendment_id IS NULL"),
            postgresql_where=sa.text("supersedes_amendment_id IS NULL"),
        )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table(_TABLE):
        op.drop_table(_TABLE)
