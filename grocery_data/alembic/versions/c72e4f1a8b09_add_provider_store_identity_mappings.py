"""add persistent external-provider store identity mappings

Revision ID: c72e4f1a8b09
Revises: b61f9d2c7e40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c72e4f1a8b09"
down_revision: str | None = "b61f9d2c7e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_store_identity_mappings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("physical_store_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_context_id", sa.String(length=255), nullable=True),
        sa.Column("provider_store_id", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("verified_identity_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("observed_identity_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("candidate_context_id", sa.String(length=255), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("drift_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["physical_store_id"],
            ["physical_stores.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "physical_store_id",
            "provider",
            name="uq_provider_store_identity_mapping_scope",
        ),
    )
    op.create_index(
        "ix_provider_store_identity_mapping_status",
        "provider_store_identity_mappings",
        ["provider", "status", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_provider_store_identity_mapping_context",
        "provider_store_identity_mappings",
        ["provider", "provider_context_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_store_identity_mapping_context",
        table_name="provider_store_identity_mappings",
    )
    op.drop_index(
        "ix_provider_store_identity_mapping_status",
        table_name="provider_store_identity_mappings",
    )
    op.drop_table("provider_store_identity_mappings")
