"""add catalog read indexes

Revision ID: b4320fa4d1e7
Revises: a171e06320cf
Create Date: 2026-08-21 17:20:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4320fa4d1e7"
down_revision: str | Sequence[str] | None = "a171e06320cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_source_products_snapshot_store",
        "source_products",
        ["catalog_snapshot_id", "store_id"],
        unique=False,
    )
    op.create_index(
        "ix_products_snapshot_store_name",
        "products",
        ["catalog_snapshot_id", "store_id", "name"],
        unique=False,
    )
    op.create_index(
        "ix_price_observations_snapshot_source",
        "price_observations",
        ["catalog_snapshot_id", "source_product_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotions_source_product",
        "promotions",
        ["source_product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_promotions_source_product", table_name="promotions")
    op.drop_index(
        "ix_price_observations_snapshot_source",
        table_name="price_observations",
    )
    op.drop_index("ix_products_snapshot_store_name", table_name="products")
    op.drop_index("ix_source_products_snapshot_store", table_name="source_products")
