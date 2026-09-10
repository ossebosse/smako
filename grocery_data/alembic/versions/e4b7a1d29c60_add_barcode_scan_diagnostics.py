"""add privacy-minimal barcode scanner diagnostics

Revision ID: e4b7a1d29c60
Revises: d19f6a3c8b52
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from grocery_data.app.storage.models import UTCDateTime

revision: str = "e4b7a1d29c60"
down_revision: str | None = "d19f6a3c8b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "barcode_scan_diagnostics"
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        op.create_table(
            table_name,
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("scanner_provider", sa.String(length=32), nullable=False),
            sa.Column("barcode_format", sa.String(length=32), nullable=True),
            sa.Column("outcome", sa.String(length=32), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("failure_reason", sa.String(length=64), nullable=True),
            sa.Column("created_at", UTCDateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        existing_indexes: set[str] = set()
    else:
        # The application historically calls metadata.create_all() at startup.
        # A new model can therefore exist before Alembic records its revision.
        # Accept only the exact expected shape; never silently stamp an
        # unrelated or incomplete table.
        expected_columns = {
            "id",
            "scanner_provider",
            "barcode_format",
            "outcome",
            "duration_ms",
            "failure_reason",
            "created_at",
        }
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if actual_columns != expected_columns:
            raise RuntimeError(
                f"existing {table_name} columns do not match the expected schema"
            )
        existing_indexes = {
            index["name"] for index in inspector.get_indexes(table_name)
        }

    if "ix_barcode_scan_diagnostics_created" not in existing_indexes:
        op.create_index(
            "ix_barcode_scan_diagnostics_created",
            table_name,
            ["created_at"],
            unique=False,
        )
    if "ix_barcode_scan_diagnostics_provider_outcome" not in existing_indexes:
        op.create_index(
            "ix_barcode_scan_diagnostics_provider_outcome",
            table_name,
            ["scanner_provider", "outcome"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_barcode_scan_diagnostics_provider_outcome",
        table_name="barcode_scan_diagnostics",
    )
    op.drop_index(
        "ix_barcode_scan_diagnostics_created",
        table_name="barcode_scan_diagnostics",
    )
    op.drop_table("barcode_scan_diagnostics")
