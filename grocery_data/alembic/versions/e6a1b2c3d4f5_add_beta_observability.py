"""add public-beta feedback, telemetry and request metrics

Revision ID: e6a1b2c3d4f5
Revises: d8f2a6c41b90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import grocery_data.app.storage.models

revision: str = "e6a1b2c3d4f5"
down_revision: str | Sequence[str] | None = "d8f2a6c41b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_feedback() -> None:
    if sa.inspect(op.get_bind()).has_table("beta_feedback"):
        return
    op.create_table(
        "beta_feedback",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            grocery_data.app.storage.models.UTCDateTime(),
            nullable=False,
        ),
        sa.Column("actor_hash", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page_context", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=False),
        sa.Column("build_id", sa.String(length=128), nullable=False),
        sa.Column("price_universe_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_beta_feedback_created_category",
        "beta_feedback",
        ["created_at", "category"],
    )
    op.create_index(
        "ix_beta_feedback_plan", "beta_feedback", ["plan_id", "created_at"]
    )


def _create_analytics() -> None:
    if sa.inspect(op.get_bind()).has_table("product_analytics_events"):
        return
    op.create_table(
        "product_analytics_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            grocery_data.app.storage.models.UTCDateTime(),
            nullable=False,
        ),
        sa.Column("actor_hash", sa.String(length=64), nullable=True),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("page_context", sa.String(length=128), nullable=True),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("app_version", sa.String(length=64), nullable=False),
        sa.Column("build_id", sa.String(length=128), nullable=False),
        sa.Column("price_universe_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_analytics_created_event",
        "product_analytics_events",
        ["created_at", "event_name"],
    )
    op.create_index(
        "ix_product_analytics_actor_created",
        "product_analytics_events",
        ["actor_hash", "created_at"],
    )


def _create_frontend_errors() -> None:
    if sa.inspect(op.get_bind()).has_table("frontend_errors"):
        return
    op.create_table(
        "frontend_errors",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            grocery_data.app.storage.models.UTCDateTime(),
            nullable=False,
        ),
        sa.Column("actor_hash", sa.String(length=64), nullable=True),
        sa.Column("route", sa.String(length=256), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=False),
        sa.Column("build_id", sa.String(length=128), nullable=False),
        sa.Column("price_universe_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_frontend_errors_created_code",
        "frontend_errors",
        ["created_at", "error_code"],
    )


def _create_request_metrics() -> None:
    if sa.inspect(op.get_bind()).has_table("beta_request_metrics"):
        return
    op.create_table(
        "beta_request_metrics",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            grocery_data.app.storage.models.UTCDateTime(),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=256), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("price_universe_id", sa.String(length=255), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=False),
        sa.Column("build_id", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_beta_request_metrics_request_id"),
    )
    op.create_index(
        "ix_beta_request_metrics_created_endpoint",
        "beta_request_metrics",
        ["created_at", "endpoint"],
    )
    op.create_index(
        "ix_beta_request_metrics_status_created",
        "beta_request_metrics",
        ["status_code", "created_at"],
    )


def upgrade() -> None:
    _create_feedback()
    _create_analytics()
    _create_frontend_errors()
    _create_request_metrics()


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in (
        "beta_request_metrics",
        "frontend_errors",
        "product_analytics_events",
        "beta_feedback",
    ):
        if inspector.has_table(table):
            op.drop_table(table)
