"""The live SQLite WAL is copied; source timestamps and builder gates survive."""

import sqlite3
from contextlib import closing

import pytest
from app.services import production_price_universe_build as builder

import grocery_data.__main__ as cli


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_build", [False, True])
async def test_managed_build_uses_closed_input_during_consumer_writes(
    tmp_path, monkeypatch, fail_build
):
    database = tmp_path / "live.sqlite3"
    live = sqlite3.connect(database)
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("CREATE TABLE observations (observed_at TEXT)")
    observed_at = "2026-09-09T14:33:52+00:00"
    live.execute("INSERT INTO observations VALUES (?)", (observed_at,))
    live.commit()
    inputs = []

    async def build(closed, city, postal, cache, output, max_age):
        inputs.append(closed)
        assert closed != database and closed.exists()
        assert (city, postal, cache, max_age) == ("Lund", "22350", None, 48)
        before = builder._file_state(closed)
        # Simulate concurrent consumer telemetry after capture, with source
        # data still committed in the WAL when the consistent copy was made.
        live.execute("CREATE TABLE consumer_telemetry (event TEXT)")
        live.execute("INSERT INTO consumer_telemetry VALUES ('search')")
        live.commit()
        with closing(
            sqlite3.connect(f"file:{closed.as_posix()}?mode=ro&immutable=1", uri=True)
        ) as frozen:
            assert frozen.execute("SELECT observed_at FROM observations").fetchall() == [
                (observed_at,)
            ]
            assert frozen.execute(
                "SELECT count(*) FROM sqlite_master WHERE name='consumer_telemetry'"
            ).fetchone() == (0,)
        assert builder._file_state(closed) == before
        if fail_build:
            raise ValueError("source gate rejected")
        return {"status": "PASS", "network_attempts": 0}

    monkeypatch.setattr(builder, "build_city_price_universe", build)
    try:
        kwargs = {
            "database": database,
            "city": "Lund",
            "postal_code": "22350",
            "external_cache": None,
            "output": tmp_path / "candidates" / "universe.json",
            "max_price_age_hours": 48,
        }
        if fail_build:
            with pytest.raises(ValueError, match="source gate rejected"):
                await cli._build_production_price_universe(**kwargs)
        else:
            assert (await cli._build_production_price_universe(**kwargs))["status"] == "PASS"
        assert inputs and not inputs[0].exists()
        assert live.execute("SELECT observed_at FROM observations").fetchall() == [(observed_at,)]
    finally:
        live.close()


@pytest.mark.asyncio
async def test_real_managed_builder_uses_closed_database(tmp_path):
    from backend.tests.test_own_provider_grocery_data_contract import _contract_database
    from backend.tests.test_production_price_universe_build import _copy_sqlite_database

    engine, _ = _contract_database()
    database = tmp_path / "live.sqlite3"
    try:
        _copy_sqlite_database(engine, database)
        report = await cli._build_production_price_universe(
            database=database,
            city="Lund",
            postal_code="22350",
            external_cache=None,
            output=tmp_path / "candidate.json",
            max_price_age_hours=48,
        )
    finally:
        engine.dispose()
    assert report["status"] == "PASS"
    assert report["database_unchanged"] and report["network_attempts"] == 0
    assert report["raw_products"] == 1
    assert not list(tmp_path.glob(".price-universe-source-*"))


@pytest.mark.asyncio
async def test_immutable_builder_still_rejects_mutated_input(tmp_path, monkeypatch):
    from app.services.price_universe_runtime import PreparedPriceUniverseManager

    from backend.tests.test_own_provider_grocery_data_contract import _contract_database
    from backend.tests.test_production_price_universe_build import _copy_sqlite_database

    engine, _ = _contract_database()
    database = tmp_path / "input.sqlite3"
    original = PreparedPriceUniverseManager.build_and_activate

    async def concurrent_write(*args, **kwargs):
        prepared = await original(*args, **kwargs)
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("CREATE TABLE consumer_telemetry (event TEXT)")
            connection.commit()
        return prepared

    monkeypatch.setattr(PreparedPriceUniverseManager, "build_and_activate", concurrent_write)
    try:
        _copy_sqlite_database(engine, database)
        with pytest.raises(
            RuntimeError, match="database changed during immutable PriceUniverse build"
        ):
            await builder.build_city_price_universe(
                database, "Lund", "22350", None, tmp_path / "candidate.json", 48
            )
        assert not (tmp_path / "candidate.json").exists()
    finally:
        engine.dispose()
