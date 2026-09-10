"""add credential-free external price-candidate cache

Revision ID: a8d3e5f7b901
Revises: f4a8c2d91e73
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8d3e5f7b901"
down_revision: str | None = "f4a8c2d91e73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Some official locators expose more than one stable ID for one physical
    # site (for example ICA accountNumber + storeId). Persist only the closed
    # public identity list; it contains no transport or credential material.
    op.add_column(
        "physical_stores",
        sa.Column(
            "external_store_aliases",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )

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

    op.create_table(
        "external_price_candidates",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("physical_store_id", sa.String(length=64), nullable=False),
        sa.Column("grocery_context_id", sa.String(length=255), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.String(length=255), nullable=False),
        sa.Column("product_name", sa.String(length=1000), nullable=False),
        sa.Column("normalized_product_name", sa.String(length=1000), nullable=False),
        sa.Column("gtin", sa.String(length=32), nullable=True),
        sa.Column("current_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("regular_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("member_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("comparison_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("comparison_unit", sa.String(length=32), nullable=True),
        sa.Column("promotion_type", sa.String(length=32), nullable=True),
        sa.Column("member_only", sa.Boolean(), nullable=False),
        sa.Column("multibuy_quantity", sa.Integer(), nullable=True),
        sa.Column("multibuy_total_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("sale_model", sa.String(length=64), nullable=False),
        sa.Column("common_product_score", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["physical_store_id"],
            ["physical_stores.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "physical_store_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
            "product_id",
            name="uq_external_price_candidate_identity",
        ),
    )
    op.create_index(
        "ix_external_price_candidate_active_context",
        "external_price_candidates",
        ["physical_store_id", "source_provider", "grocery_context_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_external_price_candidate_store_gtin_time",
        "external_price_candidates",
        ["physical_store_id", "gtin", "observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_external_price_candidate_store_name_time",
        "external_price_candidates",
        ["physical_store_id", "normalized_product_name", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_price_candidate_store_name_time",
        table_name="external_price_candidates",
    )
    op.drop_index(
        "ix_external_price_candidate_store_gtin_time",
        table_name="external_price_candidates",
    )
    op.drop_index(
        "ix_external_price_candidate_active_context",
        table_name="external_price_candidates",
    )
    op.drop_table("external_price_candidates")
    op.drop_index(
        "ix_physical_store_discovery_health_status_observed",
        table_name="physical_store_discovery_health",
    )
    op.drop_table("physical_store_discovery_health")
    op.drop_column("physical_stores", "external_store_aliases")
