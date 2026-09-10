"""add physical product identifier evidence v2

Revision ID: f95c3d7a102e
Revises: e4b7a1d29c60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from grocery_data.app.storage.models import UTCDateTime

revision: str = "f95c3d7a102e"
down_revision: str | None = "e4b7a1d29c60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_if_missing(name: str, *columns: sa.Column, constraints=()) -> bool:  # type: ignore[type-arg]
    if sa.inspect(op.get_bind()).has_table(name):
        return False
    op.create_table(name, *columns, *constraints)
    return True


def upgrade() -> None:
    created_product = _create_if_missing(
        "product_identifier_evidence",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("source_product_id", sa.String(length=255), nullable=True),
        sa.Column("external_product_id", sa.String(length=255), nullable=False),
        sa.Column("identifier_type", sa.String(length=32), nullable=False),
        sa.Column("identifier_value", sa.String(length=255), nullable=False),
        sa.Column("evidence_source", sa.String(length=64), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("evidence_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("observed_at", UTCDateTime(), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        constraints=(
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "chain",
                "source_provider",
                "scope_key",
                "external_product_id",
                "identifier_type",
                "identifier_value",
                name="uq_product_identifier_evidence_fact",
            ),
        ),
    )
    if created_product:
        op.create_index(
            "ix_product_identifier_evidence_chain_identifier",
            "product_identifier_evidence",
            ["chain", "identifier_type", "identifier_value", "is_active"],
        )
        op.create_index(
            "ix_product_identifier_evidence_product",
            "product_identifier_evidence",
            ["chain", "source_provider", "scope_key", "external_product_id", "is_active"],
        )

    _create_if_missing(
        "physical_validation_session_item_identifiers",
        sa.Column("session_item_id", sa.String(length=64), nullable=False),
        sa.Column("target_product_id", sa.String(length=255), nullable=True),
        sa.Column("target_source_provider", sa.String(length=32), nullable=True),
        sa.Column("target_grocery_context_id", sa.String(length=255), nullable=True),
        sa.Column("target_external_product_id", sa.String(length=255), nullable=True),
        sa.Column("target_store_external_id", sa.String(length=255), nullable=True),
        sa.Column("target_sale_model", sa.String(length=64), nullable=False),
        sa.Column("identifier_status", sa.String(length=64), nullable=False),
        sa.Column("identifier_evidence_id", sa.String(length=64), nullable=True),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        constraints=(
            sa.ForeignKeyConstraint(
                ["session_item_id"],
                ["physical_validation_session_items.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["identifier_evidence_id"],
                ["product_identifier_evidence.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("session_item_id"),
        ),
    )
    inspector = sa.inspect(op.get_bind())
    indexes = {
        index["name"]
        for index in inspector.get_indexes("physical_validation_session_item_identifiers")
    }
    if "ix_physical_session_item_identifier_status" not in indexes:
        op.create_index(
            "ix_physical_session_item_identifier_status",
            "physical_validation_session_item_identifiers",
            ["identifier_status"],
        )

    _create_if_missing(
        "physical_identifier_preparations",
        sa.Column("validation_session_id", sa.String(length=64), nullable=False),
        sa.Column("target_products", sa.Integer(), nullable=False),
        sa.Column("known_gtin_before", sa.Integer(), nullable=False),
        sa.Column("enriched_gtin", sa.Integer(), nullable=False),
        sa.Column("gtin_unavailable", sa.Integer(), nullable=False),
        sa.Column("weight_no_gtin_required", sa.Integer(), nullable=False),
        sa.Column("true_unresolved", sa.Integer(), nullable=False),
        sa.Column("detail_requests", sa.Integer(), nullable=False),
        sa.Column("cache_hits", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("request_limit", sa.Integer(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        constraints=(
            sa.ForeignKeyConstraint(
                ["validation_session_id"],
                ["physical_validation_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("validation_session_id"),
        ),
    )
    _create_if_missing(
        "physical_observation_v2_evidence",
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("identification_evidence", sa.String(length=64), nullable=False),
        sa.Column("regular_shelf_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("weight_price_type", sa.String(length=32), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        constraints=(
            sa.ForeignKeyConstraint(
                ["observation_id"],
                ["physical_price_observations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("observation_id"),
        ),
    )
    created_shelf = _create_if_missing(
        "shelf_identifier_evidence",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("physical_store_id", sa.String(length=64), nullable=False),
        sa.Column("validation_session_id", sa.String(length=64), nullable=True),
        sa.Column("validation_session_item_id", sa.String(length=64), nullable=True),
        sa.Column("selected_source_product_id", sa.String(length=255), nullable=True),
        sa.Column("raw_value", sa.String(length=255), nullable=False),
        sa.Column("barcode_format", sa.String(length=64), nullable=False),
        sa.Column("observed_at", UTCDateTime(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        constraints=(
            sa.ForeignKeyConstraint(
                ["physical_store_id"], ["physical_stores.id"], ondelete="CASCADE"
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
            sa.PrimaryKeyConstraint("id"),
        ),
    )
    if created_shelf:
        op.create_index(
            "ix_shelf_identifier_evidence_store_observed",
            "shelf_identifier_evidence",
            ["physical_store_id", "observed_at"],
        )


def downgrade() -> None:
    op.drop_table("shelf_identifier_evidence")
    op.drop_table("physical_observation_v2_evidence")
    op.drop_table("physical_identifier_preparations")
    op.drop_table("physical_validation_session_item_identifiers")
    op.drop_table("product_identifier_evidence")
