"""add persistent ICA product registry

Revision ID: c58e2d9e11a0
Revises: b4320fa4d1e7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c58e2d9e11a0"
down_revision: str | None = "b4320fa4d1e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ica_product_registry",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("external_product_id", sa.String(255), nullable=False, unique=True),
        sa.Column("gtin", sa.String(32)),
        sa.Column("name", sa.String(1000)),
        sa.Column("brand", sa.String(500)),
        sa.Column("package_text", sa.String(500)),
        sa.Column("category_path", sa.JSON(), nullable=False),
        sa.Column("canonical_food", sa.String(255)),
        sa.Column("metadata_level", sa.String(32), nullable=False),
        sa.Column("metadata_confidence", sa.String(32), nullable=False),
        sa.Column("active_state", sa.String(32), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_full_metadata_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ica_registry_last_seen", "ica_product_registry", ["last_seen_at"])
    op.create_table(
        "ica_discovery_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "registry_product_id",
            sa.String(32),
            sa.ForeignKey("ica_product_registry.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            sa.String(32),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_page", sa.Text(), nullable=False),
        sa.Column(
            "raw_snapshot_id", sa.String(32), sa.ForeignKey("raw_snapshots.id", ondelete="SET NULL")
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_fingerprint", sa.String(64), nullable=False, unique=True),
    )
    op.create_index(
        "ix_ica_discovery_product_time",
        "ica_discovery_events",
        ["registry_product_id", "observed_at"],
    )
    op.create_table(
        "ica_store_product_observations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "registry_product_id",
            sa.String(32),
            sa.ForeignKey("ica_product_registry.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            sa.String(32),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "raw_snapshot_id", sa.String(32), sa.ForeignKey("raw_snapshots.id", ondelete="SET NULL")
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sale_price", sa.Numeric(18, 6)),
        sa.Column("comparison_price", sa.Numeric(18, 6)),
        sa.Column("comparison_unit", sa.String(32)),
        sa.Column("availability", sa.String(255)),
        sa.Column("promotion", sa.JSON()),
        sa.Column("sale_model", sa.String(64)),
        sa.Column("semantic_confidence", sa.String(32)),
        sa.Column("quantity_confidence", sa.String(32)),
        sa.Column("metadata_level", sa.String(32), nullable=False),
    )
    op.create_index(
        "ix_ica_observation_product_store_time",
        "ica_store_product_observations",
        ["registry_product_id", "store_id", "observed_at"],
    )
    op.create_table(
        "ica_category_registry",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "store_id",
            sa.String(32),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_category_id", sa.String(255), nullable=False),
        sa.Column("parent_external_id", sa.String(255)),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("declared_product_count", sa.Integer()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("store_id", "external_category_id", name="uq_ica_category_store_id"),
    )


def downgrade() -> None:
    op.drop_table("ica_category_registry")
    op.drop_index(
        "ix_ica_observation_product_store_time", table_name="ica_store_product_observations"
    )
    op.drop_table("ica_store_product_observations")
    op.drop_index("ix_ica_discovery_product_time", table_name="ica_discovery_events")
    op.drop_table("ica_discovery_events")
    op.drop_index("ix_ica_registry_last_seen", table_name="ica_product_registry")
    op.drop_table("ica_product_registry")
