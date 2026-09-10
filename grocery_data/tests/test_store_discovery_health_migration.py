from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from grocery_data.app.domain import Chain, ConnectorStatus
from grocery_data.app.services.store_coverage import StoreCoverageAuditor
from grocery_data.app.storage import (
    PhysicalStoreDiscoveryHealthRepository,
    create_database_engine,
    create_session_factory,
    session_scope,
)

_A8_REVISION = "a8d3e5f7b901"
_HEAD_REVISION = "f7b2c3d4e5a6"


def _config(database: Path, monkeypatch) -> Config:  # type: ignore[no-untyped-def]
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        f"sqlite+pysqlite:///{database.resolve().as_posix()}",
    )
    return Config(str(root / "alembic.ini"))


def _schema(database: Path) -> tuple[set[str], str]:
    engine = create_database_engine(f"sqlite+pysqlite:///{database.resolve().as_posix()}")
    try:
        tables = set(sa.inspect(engine).get_table_names())
        with engine.connect() as connection:
            revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        assert isinstance(revision, str)
        return tables, revision
    finally:
        engine.dispose()


def test_fresh_upgrade_and_downgrade_retain_logical_a8_health_table(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "fresh.sqlite"
    config = _config(database, monkeypatch)

    command.upgrade(config, "head")
    tables, revision = _schema(database)
    assert revision == _HEAD_REVISION
    assert "physical_store_discovery_health" in tables

    # The repair is a no-op on a fresh history. The table logically belongs to
    # a8 and must still be present after downgrading only the repair revision.
    command.downgrade(config, _A8_REVISION)
    tables, revision = _schema(database)
    assert revision == _A8_REVISION
    assert "physical_store_discovery_health" in tables

    command.upgrade(config, "head")
    assert _schema(database)[1] == _HEAD_REVISION


def test_upgrade_repairs_an_already_stamped_a8_database_and_repository_reads_it(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "already-a8.sqlite"
    config = _config(database, monkeypatch)
    command.upgrade(config, _A8_REVISION)

    # Reproduce the historical drift exactly: the DB is stamped a8 but lacks
    # the discovery-health table that was appended to that revision later.
    engine = create_database_engine(f"sqlite+pysqlite:///{database.resolve().as_posix()}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE physical_store_discovery_health")
    finally:
        engine.dispose()
    tables, revision = _schema(database)
    assert revision == _A8_REVISION
    assert "physical_store_discovery_health" not in tables

    command.upgrade(config, "head")
    tables, revision = _schema(database)
    assert revision == _HEAD_REVISION
    assert "physical_store_discovery_health" in tables

    # Exercise the repository and the same auditor read used by both the
    # coverage API and CLI against the repaired, migrated schema.
    engine = create_database_engine(f"sqlite+pysqlite:///{database.resolve().as_posix()}")
    factory = create_session_factory(engine)
    try:
        now = datetime.now(tz=UTC)
        with session_scope(factory) as session:
            PhysicalStoreDiscoveryHealthRepository(session).record(
                chain=Chain.HEMKOP,
                city="Lund",
                status=ConnectorStatus.HEALTHY,
                complete=True,
                discovered_count=2,
                previous_count=2,
                observed_at=now,
            )
            report = StoreCoverageAuditor(session).audit(
                city="Lund",
                official_stores=(),
                now=now,
            )
            assert report.discovery_health[Chain.HEMKOP].discovered_count == 2
            assert report.discovery_health[Chain.HEMKOP].status is ConnectorStatus.HEALTHY
    finally:
        engine.dispose()

    command.downgrade(config, _A8_REVISION)
    tables, revision = _schema(database)
    assert revision == _A8_REVISION
    assert "physical_store_discovery_health" in tables
