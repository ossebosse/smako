from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from grocery_data.app.storage import create_database_engine, create_schema

_HEAD_REVISION = "f7b2c3d4e5a6"


def test_upgrade_adds_v3_snapshot_lock_and_comparison_version_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "physical-v3.sqlite"
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        f"sqlite+pysqlite:///{database.resolve().as_posix()}",
    )
    command.upgrade(Config(str(root / "alembic.ini")), "head")

    engine = create_database_engine(
        f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    )
    try:
        inspector = sa.inspect(engine)
        assert {
            "physical_observation_amendments",
            "physical_validation_snapshot_locks",
            "physical_validation_comparison_versions",
        }.issubset(inspector.get_table_names())
        assert {
            "validation_session_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
            "candidate_count",
            "evidence_sha256",
            "locked_at",
        }.issubset(
            {
                row["name"]
                for row in inspector.get_columns("physical_validation_snapshot_locks")
            }
        )
        assert {
            "validation_session_id",
            "validation_session_item_id",
            "kind",
            "payload_json",
            "payload_schema_version",
            "payload_sha256",
            "base_observation_id",
            "supersedes_amendment_id",
            "observed_at",
            "observed_at_precision",
            "reason",
            "source",
            "reference",
            "client_request_id",
        }.issubset(
            {
                row["name"]
                for row in inspector.get_columns("physical_observation_amendments")
            }
        )
        assert {
            "validation_session_id",
            "version_number",
            "version_kind",
            "source_snapshot_ids",
            "evidence_sha256",
            "freshness_threshold_hours",
            "reason",
        }.issubset(
            {
                row["name"]
                for row in inspector.get_columns(
                    "physical_validation_comparison_versions"
                )
            }
        )
        with engine.connect() as connection:
            revision = connection.scalar(
                sa.text("SELECT version_num FROM alembic_version")
            )
        assert revision == _HEAD_REVISION
    finally:
        engine.dispose()


def test_upgrade_accepts_exact_tables_precreated_by_local_metadata_startup(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    """Local create_all may add model tables before Alembic advances."""

    database = tmp_path / "physical-v3-precreated.sqlite"
    root = Path(__file__).resolve().parents[1]
    database_url = f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    config = Config(str(root / "alembic.ini"))
    command.upgrade(config, "fb82c6e194d0")

    engine = create_database_engine(database_url)
    try:
        create_schema(engine)
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_database_engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(
                sa.text("SELECT version_num FROM alembic_version")
            )
        assert revision == _HEAD_REVISION
        inspector = sa.inspect(engine)
        assert inspector.has_table("physical_validation_snapshot_locks")
        assert inspector.has_table("physical_validation_comparison_versions")
        assert inspector.has_table("physical_observation_amendments")
    finally:
        engine.dispose()
