"""add bounded physical validation sessions

Revision ID: d19f6a3c8b52
Revises: f83c4d2a9b71
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d19f6a3c8b52"
down_revision: str | None = "f83c4d2a9b71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "physical_validation_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("physical_store_id", sa.String(length=64), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("store_name", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blind_capture", sa.Boolean(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("sampling_strategy", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("suggestion_set_sha256", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["physical_store_id"],
            ["physical_stores.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_physical_validation_sessions_store_started",
        "physical_validation_sessions",
        ["physical_store_id", "started_at"],
        unique=False,
    )
    op.create_table(
        "physical_validation_session_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("stratum", sa.String(length=32), nullable=False),
        sa.Column("target_gtin", sa.String(length=32), nullable=True),
        sa.Column("target_product_name", sa.String(length=1000), nullable=False),
        sa.Column("target_brand", sa.String(length=500), nullable=True),
        sa.Column("target_category", sa.String(length=500), nullable=True),
        sa.Column("target_package_description", sa.String(length=128), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("candidate_set_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["physical_validation_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "ordinal",
            name="uq_physical_validation_session_item_ordinal",
        ),
    )
    op.create_index(
        "ix_physical_validation_session_items_session_stratum",
        "physical_validation_session_items",
        ["session_id", "stratum"],
        unique=False,
    )
    op.create_table(
        "physical_validation_session_candidates",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_item_id", sa.String(length=64), nullable=False),
        sa.Column("physical_store_id", sa.String(length=64), nullable=False),
        sa.Column("grocery_context_id", sa.String(length=255), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.String(length=255), nullable=False),
        sa.Column("product_name", sa.String(length=1000), nullable=False),
        sa.Column("brand", sa.String(length=500), nullable=True),
        sa.Column("category", sa.String(length=500), nullable=True),
        sa.Column("package_description", sa.String(length=128), nullable=True),
        sa.Column("gtin", sa.String(length=32), nullable=True),
        sa.Column("current_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("regular_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("member_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("comparison_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("comparison_unit", sa.String(length=32), nullable=True),
        sa.Column("promotion_type", sa.String(length=32), nullable=True),
        sa.Column("member_only", sa.Boolean(), nullable=False),
        sa.Column("multibuy_quantity", sa.Integer(), nullable=True),
        sa.Column("multibuy_total_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("sale_model", sa.String(length=64), nullable=False),
        sa.Column("common_product_score", sa.Numeric(18, 6), nullable=False),
        sa.Column("recent_price_change", sa.Numeric(18, 6), nullable=True),
        sa.Column("candidate_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_item_id"],
            ["physical_validation_session_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_item_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
            "product_id",
            name="uq_physical_validation_session_candidate_identity",
        ),
    )
    op.create_index(
        "ix_physical_validation_session_candidates_item_provider",
        "physical_validation_session_candidates",
        ["session_item_id", "source_provider"],
        unique=False,
    )
    with op.batch_alter_table("physical_price_observations") as batch_op:
        batch_op.add_column(
            sa.Column("validation_session_id", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("validation_session_item_id", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("price_semantics", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("identity_status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("promotion_text", sa.String(length=1000), nullable=True))
        batch_op.add_column(
            sa.Column("immutable_candidate_set_sha256", sa.String(length=64), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_physical_observation_validation_session",
            "physical_validation_sessions",
            ["validation_session_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_physical_observation_validation_session_item",
            "physical_validation_session_items",
            ["validation_session_item_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "uq_physical_price_observation_session_item",
            ["validation_session_item_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("physical_price_observations") as batch_op:
        batch_op.drop_index("uq_physical_price_observation_session_item")
        batch_op.drop_constraint(
            "fk_physical_observation_validation_session_item",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_physical_observation_validation_session",
            type_="foreignkey",
        )
        batch_op.drop_column("immutable_candidate_set_sha256")
        batch_op.drop_column("identity_status")
        batch_op.drop_column("promotion_text")
        batch_op.drop_column("price_semantics")
        batch_op.drop_column("validation_session_item_id")
        batch_op.drop_column("validation_session_id")
    op.drop_index(
        "ix_physical_validation_session_candidates_item_provider",
        table_name="physical_validation_session_candidates",
    )
    op.drop_table("physical_validation_session_candidates")
    op.drop_index(
        "ix_physical_validation_session_items_session_stratum",
        table_name="physical_validation_session_items",
    )
    op.drop_table("physical_validation_session_items")
    op.drop_index(
        "ix_physical_validation_sessions_store_started",
        table_name="physical_validation_sessions",
    )
    op.drop_table("physical_validation_sessions")
