"""add structured pickup-point identity to store-context links

Revision ID: f83c4d2a9b71
Revises: c72e4f1a8b09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f83c4d2a9b71"
down_revision: str | None = "c72e4f1a8b09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_context_links",
        sa.Column("pickup_point_external_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_store_context_links_pickup_point",
        "store_context_links",
        ["source_provider", "pickup_point_external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_store_context_links_pickup_point",
        table_name="store_context_links",
    )
    op.drop_column("store_context_links", "pickup_point_external_id")
