from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from grocery_data.app.storage import create_database_engine, create_session_factory
from grocery_data.app.storage.models import PhysicalObservationV2EvidenceModel

_BARCODE_REVISION = "e4b7a1d29c60"
_IDENTIFIER_V2_REVISION = "f95c3d7a102e"
_HEAD_REVISION = "f7b2c3d4e5a6"
_TABLE = "physical_observation_v2_evidence"


def _config(database: Path, monkeypatch) -> Config:  # type: ignore[no-untyped-def]
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        f"sqlite+pysqlite:///{database.resolve().as_posix()}",
    )
    return Config(str(root / "alembic.ini"))


def _engine(database: Path):  # type: ignore[no-untyped-def]
    return create_database_engine(
        f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    )


def _columns(database: Path) -> set[str]:
    engine = _engine(database)
    try:
        return {
            column["name"] for column in sa.inspect(engine).get_columns(_TABLE)
        }
    finally:
        engine.dispose()


def _revision(database: Path) -> str:
    engine = _engine(database)
    try:
        with engine.connect() as connection:
            value = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        assert isinstance(value, str)
        return value
    finally:
        engine.dispose()


def test_upgrade_repairs_exact_early_create_all_table_without_losing_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "early-v2.sqlite"
    config = _config(database, monkeypatch)
    command.upgrade(config, _BARCODE_REVISION)
    engine = _engine(database)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"""
                CREATE TABLE {_TABLE} (
                    observation_id VARCHAR(64) PRIMARY KEY,
                    identification_evidence VARCHAR(64) NOT NULL,
                    regular_shelf_price NUMERIC(18, 6),
                    created_at DATETIME NOT NULL
                )
                """
            )
            connection.execute(
                sa.text(
                    f"INSERT INTO {_TABLE} "
                    "(observation_id, identification_evidence, "
                    "regular_shelf_price, created_at) "
                    "VALUES (:id, :evidence, :price, :created)"
                ),
                {
                    "id": "rolled-back-field-retry-evidence",
                    "evidence": "weight_source_product",
                    "price": "46.95",
                    "created": "2026-08-29 12:00:00",
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    assert _revision(database) == _HEAD_REVISION
    assert {"regular_shelf_price", "weight_price_type"} <= _columns(database)
    engine = _engine(database)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT identification_evidence, regular_shelf_price, "
                    f"weight_price_type FROM {_TABLE} WHERE observation_id = :id"
                ),
                {"id": "rolled-back-field-retry-evidence"},
            ).one()
        assert row.identification_evidence == "weight_source_product"
        assert str(row.regular_shelf_price) == "46.95"
        assert row.weight_price_type is None
    finally:
        engine.dispose()

    # Reproduce the ORM INSERT that previously failed with ``no column named
    # weight_price_type``.  This table was intentionally created without its
    # later foreign key in the historical-shape setup above, so no catalog or
    # physical-price row is needed for this schema regression.
    engine = _engine(database)
    factory = create_session_factory(engine)
    try:
        with factory() as database_session:
            database_session.add(
                PhysicalObservationV2EvidenceModel(
                    observation_id="field-retry-after-repair",
                    identification_evidence="weight_source_product",
                    regular_shelf_price="46.95",
                    weight_price_type="sale",
                )
            )
            database_session.commit()
        with engine.connect() as connection:
            assert connection.scalar(
                sa.text(
                    f"SELECT weight_price_type FROM {_TABLE} "
                    "WHERE observation_id = :id"
                ),
                {"id": "field-retry-after-repair"},
            ) == "sale"
    finally:
        engine.dispose()

    # A normal repeated startup is a no-op at the current revision.
    command.upgrade(config, "head")
    assert _revision(database) == _HEAD_REVISION


def test_post_f95_repair_handles_a_stamped_database_missing_weight_type(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "stamped-f95.sqlite"
    config = _config(database, monkeypatch)
    command.upgrade(config, _IDENTIFIER_V2_REVISION)
    engine = _engine(database)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"ALTER TABLE {_TABLE} DROP COLUMN weight_price_type"
            )
    finally:
        engine.dispose()
    assert "weight_price_type" not in _columns(database)

    command.upgrade(config, "head")

    assert _revision(database) == _HEAD_REVISION
    assert "weight_price_type" in _columns(database)
