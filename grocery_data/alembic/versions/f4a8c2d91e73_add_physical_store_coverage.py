"""add physical-store coverage and optional ground-truth samples

Revision ID: f4a8c2d91e73
Revises: e92a4b1c7d30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4a8c2d91e73"
down_revision: str | None = "e92a4b1c7d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "physical_stores",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("external_store_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("official_source", sa.Text(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("not_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chain",
            "external_store_id",
            name="uq_physical_stores_chain_external_id",
        ),
    )
    op.create_index(
        "ix_physical_stores_city_chain_active",
        "physical_stores",
        ["city", "chain", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_physical_stores_lifecycle",
        "physical_stores",
        ["lifecycle_state", "not_seen_at"],
        unique=False,
    )

    op.create_table(
        "store_context_links",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("physical_store_id", sa.String(length=64), nullable=False),
        sa.Column("grocery_context_id", sa.String(length=255), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("source_channel", sa.String(length=32), nullable=False),
        sa.Column("local_store_id", sa.String(length=32), nullable=True),
        sa.Column("grocery_context_name", sa.String(length=500), nullable=True),
        sa.Column("price_context_type", sa.String(length=32), nullable=True),
        sa.Column("coverage", sa.String(length=32), nullable=True),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("basket_eligible", sa.Boolean(), nullable=False),
        sa.Column("offers_only", sa.Boolean(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=255), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["local_store_id"],
            ["stores.id"],
            ondelete="SET NULL",
        ),
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
            name="uq_store_context_links_identity",
        ),
    )
    op.create_index(
        "ix_store_context_links_context",
        "store_context_links",
        ["source_provider", "grocery_context_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_context_links_local_store",
        "store_context_links",
        ["local_store_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_context_links_physical_active",
        "store_context_links",
        ["physical_store_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "physical_price_observations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("physical_store_id", sa.String(length=64), nullable=False),
        sa.Column("gtin", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.String(length=1000), nullable=True),
        sa.Column("shelf_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("comparison_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("comparison_unit", sa.String(length=32), nullable=True),
        sa.Column("promotion_type", sa.String(length=32), nullable=True),
        sa.Column("member_only", sa.Boolean(), nullable=True),
        sa.Column("multibuy_quantity", sa.Integer(), nullable=True),
        sa.Column("multibuy_total_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photo_reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["physical_store_id"],
            ["physical_stores.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_physical_price_observations_gtin",
        "physical_price_observations",
        ["gtin"],
        unique=False,
    )
    op.create_index(
        "ix_physical_price_observations_store_gtin_observed",
        "physical_price_observations",
        ["physical_store_id", "gtin", "observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_physical_price_observations_store_observed",
        "physical_price_observations",
        ["physical_store_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_physical_price_observations_store_observed",
        table_name="physical_price_observations",
    )
    op.drop_index(
        "ix_physical_price_observations_store_gtin_observed",
        table_name="physical_price_observations",
    )
    op.drop_index(
        "ix_physical_price_observations_gtin",
        table_name="physical_price_observations",
    )
    op.drop_table("physical_price_observations")

    op.drop_index(
        "ix_store_context_links_physical_active",
        table_name="store_context_links",
    )
    op.drop_index("ix_store_context_links_local_store", table_name="store_context_links")
    op.drop_index("ix_store_context_links_context", table_name="store_context_links")
    op.drop_table("store_context_links")

    op.drop_index("ix_physical_stores_lifecycle", table_name="physical_stores")
    op.drop_index("ix_physical_stores_city_chain_active", table_name="physical_stores")
    op.drop_table("physical_stores")
