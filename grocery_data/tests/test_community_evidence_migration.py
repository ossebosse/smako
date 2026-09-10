from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from grocery_data.app.storage import create_database_engine, create_schema

HEAD = "f7b2c3d4e5a6"


def _config(database: Path, monkeypatch) -> Config:  # type: ignore[no-untyped-def]
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        f"sqlite+pysqlite:///{database.resolve().as_posix()}",
    )
    return Config(str(root / "alembic.ini"))


def test_upgrade_adds_append_only_community_tables(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "community.sqlite"
    command.upgrade(_config(database, monkeypatch), "head")
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    )
    try:
        inspector = sa.inspect(engine)
        assert {
            "community_evidence_observations",
            "community_evidence_moderation_events",
            "community_receipt_ingestions",
            "beta_feedback",
            "product_analytics_events",
            "frontend_errors",
            "beta_request_metrics",
            "privacy_erasure_suppressions",
        }.issubset(inspector.get_table_names())
        columns = {
            row["name"]
            for row in inspector.get_columns("community_evidence_observations")
        }
        assert {
            "source_provider_store_id",
            "store_identity_verified",
            "payload_sha256",
            "promotion_eligibility",
            "promotion_mechanism",
            "receipt_ingestion_id",
        }.issubset(columns)
        receipt_unique_columns = {
            frozenset(constraint.get("column_names") or ())
            for constraint in inspector.get_unique_constraints(
                "community_receipt_ingestions"
            )
        } | {
            frozenset(index.get("column_names") or ())
            for index in inspector.get_indexes("community_receipt_ingestions")
            if index.get("unique")
        }
        assert frozenset({"actor_hash", "raw_sha256"}) in receipt_unique_columns
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == HEAD
    finally:
        engine.dispose()


def test_upgrade_accepts_tables_precreated_by_local_startup(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "community-precreated.sqlite"
    config = _config(database, monkeypatch)
    command.upgrade(config, "b7c9e2f41a60")
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    )
    try:
        create_schema(engine)
    finally:
        engine.dispose()
    command.upgrade(config, "head")
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    )
    try:
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == HEAD
    finally:
        engine.dispose()
