"""repair additive physical observation v2 evidence columns

Revision ID: fa71c2d8e4b3
Revises: f95c3d7a102e

Some local PoC databases received ``physical_observation_v2_evidence`` from
``metadata.create_all()`` while the V2 model was still being extended.  The
f95 revision deliberately leaves an already existing table alone, so those
databases can otherwise be stamped at f95 while still lacking a nullable V2
column.  This repair is additive, data preserving and safe for both histories.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fa71c2d8e4b3"
down_revision: str | None = "f95c3d7a102e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "physical_observation_v2_evidence"
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        raise RuntimeError(
            f"{table_name} is missing after the physical identifier V2 revision"
        )
    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    with op.batch_alter_table(table_name) as batch_op:
        if "regular_shelf_price" not in existing_columns:
            batch_op.add_column(
                sa.Column("regular_shelf_price", sa.Numeric(18, 6), nullable=True)
            )
        if "weight_price_type" not in existing_columns:
            batch_op.add_column(
                sa.Column("weight_price_type", sa.String(length=32), nullable=True)
            )


def downgrade() -> None:
    # These columns logically belong to f95.  Keeping them while downgrading
    # only this repair mirrors the historical f95 schema; downgrading f95 then
    # removes the complete evidence table.
    pass
