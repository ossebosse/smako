"""add actor-free privacy erasure suppression ledger

Revision ID: f7b2c3d4e5a6
Revises: e6a1b2c3d4f5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import grocery_data.app.storage.models

revision: str = "f7b2c3d4e5a6"
down_revision: str | Sequence[str] | None = "e6a1b2c3d4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("privacy_erasure_suppressions"):
        return
    op.create_table(
        "privacy_erasure_suppressions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            grocery_data.app.storage.models.UTCDateTime(),
            nullable=False,
        ),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_record_id", sa.String(length=128), nullable=False),
        sa.Column(
            "action",
            sa.String(length=32),
            nullable=False,
            server_default="SUPPRESS_ON_RESTORE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "target_kind",
            "target_record_id",
            name="uq_privacy_erasure_suppression_target",
        ),
    )
    op.create_index(
        "ix_privacy_erasure_suppressions_created",
        "privacy_erasure_suppressions",
        ["created_at"],
    )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("privacy_erasure_suppressions"):
        op.drop_table("privacy_erasure_suppressions")
