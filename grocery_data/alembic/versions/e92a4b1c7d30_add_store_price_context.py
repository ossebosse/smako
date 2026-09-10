"""add explicit store price context provenance

Revision ID: e92a4b1c7d30
Revises: d7f1a2c4e9b0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e92a4b1c7d30"
down_revision: str | None = "d7f1a2c4e9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column("price_context_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "stores",
        sa.Column("physical_store_external_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stores", "physical_store_external_id")
    op.drop_column("stores", "price_context_type")
