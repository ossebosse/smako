"""add append-only community evidence and privacy-safe receipt audit

Revision ID: c1d4e7f90a22
Revises: b7c9e2f41a60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d4e7f90a22"
down_revision: str | Sequence[str] | None = "b7c9e2f41a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_columns(table: str, expected: set[str]) -> None:
    actual = {row["name"] for row in sa.inspect(op.get_bind()).get_columns(table)}
    if actual != expected:
        raise RuntimeError(f"existing {table} does not match the required schema")


def _create_receipts() -> None:
    if sa.inspect(op.get_bind()).has_table("community_receipt_ingestions"):
        _require_columns(
            "community_receipt_ingestions",
            {
                "id",
                "actor_hash",
                "retailer",
                "physical_store_id",
                "status",
                "parser_name",
                "raw_sha256",
                "raw_retained",
                "raw_discarded_at",
                "retention_expires_at",
                "purchase_observed_at",
                "parsed_lines",
                "warnings",
                "created_at",
            },
        )
        return
    op.create_table(
        "community_receipt_ingestions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("actor_hash", sa.String(length=64), nullable=False),
        sa.Column("retailer", sa.String(length=64), nullable=True),
        sa.Column("physical_store_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(length=128), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=True),
        sa.Column("raw_retained", sa.Boolean(), nullable=False),
        sa.Column("raw_discarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purchase_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parsed_lines", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "raw_retained IS FALSE",
            name="ck_community_receipts_no_raw_retention",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_community_receipts_created_status",
        "community_receipt_ingestions",
        ["created_at", "status"],
    )


def _create_evidence() -> None:
    if sa.inspect(op.get_bind()).has_table("community_evidence_observations"):
        _require_columns(
            "community_evidence_observations",
            {
                "id",
                "created_at",
                "observed_at",
                "actor_hash",
                "idempotency_key",
                "payload_sha256",
                "evidence_type",
                "evidence_source",
                "initial_status",
                "chain",
                "physical_store_id",
                "source_provider_store_id",
                "store_identity_verified",
                "store_display_name",
                "grocery_context_id",
                "gtin",
                "source_product_id",
                "product_name",
                "brand",
                "package_description",
                "physical_presence",
                "shelf_price",
                "digital_price",
                "unit_price",
                "price_unit",
                "quantity",
                "promotion_eligibility",
                "promotion_mechanism",
                "promotion_regular_price",
                "promotion_active_price",
                "promotion_required_quantity",
                "promotion_total_price",
                "promotion_percent_discount",
                "promotion_max_quantity",
                "promotion_member_program",
                "promotion_valid_from",
                "promotion_valid_to",
                "promotion_description",
                "receipt_ingestion_id",
                "plan_id",
                "price_snapshot_id",
                "note",
                "identity_confidence",
                "evidence_confidence",
            },
        )
        return
    op.create_table(
        "community_evidence_observations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_source", sa.String(length=32), nullable=False),
        sa.Column("initial_status", sa.String(length=32), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=True),
        sa.Column("physical_store_id", sa.String(length=128), nullable=True),
        sa.Column("source_provider_store_id", sa.String(length=255), nullable=True),
        sa.Column("store_identity_verified", sa.Boolean(), nullable=False),
        sa.Column("store_display_name", sa.String(length=500), nullable=True),
        sa.Column("grocery_context_id", sa.String(length=255), nullable=True),
        sa.Column("gtin", sa.String(length=32), nullable=True),
        sa.Column("source_product_id", sa.String(length=500), nullable=True),
        sa.Column("product_name", sa.String(length=1000), nullable=True),
        sa.Column("brand", sa.String(length=500), nullable=True),
        sa.Column("package_description", sa.String(length=500), nullable=True),
        sa.Column("physical_presence", sa.Boolean(), nullable=True),
        sa.Column("shelf_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("digital_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_unit", sa.String(length=32), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("promotion_eligibility", sa.String(length=32), nullable=True),
        sa.Column("promotion_mechanism", sa.String(length=32), nullable=True),
        sa.Column("promotion_regular_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("promotion_active_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("promotion_required_quantity", sa.Integer(), nullable=True),
        sa.Column("promotion_total_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("promotion_percent_discount", sa.Numeric(7, 4), nullable=True),
        sa.Column("promotion_max_quantity", sa.Integer(), nullable=True),
        sa.Column("promotion_member_program", sa.String(length=100), nullable=True),
        sa.Column("promotion_valid_from", sa.Date(), nullable=True),
        sa.Column("promotion_valid_to", sa.Date(), nullable=True),
        sa.Column("promotion_description", sa.Text(), nullable=True),
        sa.Column("receipt_ingestion_id", sa.String(length=64), nullable=True),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("price_snapshot_id", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("identity_confidence", sa.String(length=64), nullable=False),
        sa.Column("evidence_confidence", sa.Numeric(5, 4), nullable=False),
        sa.CheckConstraint(
            "initial_status IN ('USER_REPORTED', 'QUARANTINED')",
            name="ck_community_evidence_initial_status",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_ingestion_id"],
            ["community_receipt_ingestions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_hash",
            "idempotency_key",
            name="uq_community_evidence_actor_request",
        ),
    )
    op.create_index(
        "ix_community_evidence_store_product_time",
        "community_evidence_observations",
        ["physical_store_id", "gtin", "observed_at"],
    )
    op.create_index(
        "ix_community_evidence_type_created",
        "community_evidence_observations",
        ["evidence_type", "created_at"],
    )
    op.create_index(
        "ix_community_evidence_payload_created",
        "community_evidence_observations",
        ["payload_sha256", "created_at"],
    )


def _create_moderation() -> None:
    if sa.inspect(op.get_bind()).has_table("community_evidence_moderation_events"):
        _require_columns(
            "community_evidence_moderation_events",
            {
                "id",
                "evidence_id",
                "status",
                "reason",
                "moderator_hash",
                "idempotency_key",
                "created_at",
            },
        )
        return
    op.create_table(
        "community_evidence_moderation_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("evidence_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("moderator_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["community_evidence_observations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_id",
            "idempotency_key",
            name="uq_community_moderation_request",
        ),
    )
    op.create_index(
        "ix_community_moderation_evidence_created",
        "community_evidence_moderation_events",
        ["evidence_id", "created_at"],
    )


def upgrade() -> None:
    _create_receipts()
    _create_evidence()
    _create_moderation()


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in (
        "community_evidence_moderation_events",
        "community_evidence_observations",
        "community_receipt_ingestions",
    ):
        if inspector.has_table(table):
            op.drop_table(table)
