"""secure community receipt idempotency

Revision ID: d8f2a6c41b90
Revises: c1d4e7f90a22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f2a6c41b90"
down_revision: str | Sequence[str] | None = "c1d4e7f90a22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "community_receipt_ingestions"
_INDEX = "uq_community_receipts_actor_fingerprint"
_COLUMNS = {"actor_hash", "raw_sha256"}


def _already_unique(inspector: sa.Inspector) -> bool:
    for constraint in inspector.get_unique_constraints(_TABLE):
        if set(constraint.get("column_names") or ()) == _COLUMNS:
            return True
    return any(
        bool(index.get("unique"))
        and set(index.get("column_names") or ()) == _COLUMNS
        for index in inspector.get_indexes(_TABLE)
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(_TABLE):
        raise RuntimeError(f"required table {_TABLE} does not exist")
    if not _already_unique(inspector):
        op.create_index(
            _INDEX,
            _TABLE,
            ["actor_hash", "raw_sha256"],
            unique=True,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(_TABLE):
        return
    if any(index.get("name") == _INDEX for index in inspector.get_indexes(_TABLE)):
        op.drop_index(_INDEX, table_name=_TABLE)

