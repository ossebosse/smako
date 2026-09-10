from __future__ import annotations

import socket
import sqlite3
from pathlib import Path

import pytest
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.production_price_universe_build import (
    NetworkAccessBlockedError,
    _assert_sanitized,
    _network_disabled,
    build_city_price_universe,
)

from backend.tests.test_own_provider_grocery_data_contract import _contract_database


def _copy_sqlite_database(source_engine: object, destination: Path) -> None:
    raw_connection = source_engine.raw_connection()  # type: ignore[attr-defined]
    try:
        source = raw_connection.driver_connection
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        raw_connection.close()


@pytest.mark.asyncio
async def test_build_city_price_universe_is_offline_read_only_and_inactive(
    tmp_path: Path,
) -> None:
    source_engine, _factory = _contract_database()
    database = tmp_path / "refreshed.sqlite3"
    output = tmp_path / "prepared-universe.json"
    try:
        _copy_sqlite_database(source_engine, database)
        result = await build_city_price_universe(
            database,
            "Lund",
            "223 50",
            None,
            output,
            48.0,
        )
    finally:
        source_engine.dispose()

    artifact = PreparedPriceUniverseArtifact.model_validate_json(output.read_bytes())
    restored = artifact.restore()
    assert result["status"] == "PASS"
    assert result["persistent_activation"] is False
    assert result["mode"] == "own_only"
    assert result["network_attempts"] == 0
    assert result["database_read_only"] is True
    assert result["database_unchanged"] is True
    assert result["raw_products"] == 1
    assert result["eligible_products"] == 1
    assert restored.universe.universe_id == result["price_universe_id"]
    assert result["provider_metrics"]["own_asgi"]["network_requests"] == 0  # type: ignore[index]


def test_external_cache_sanitization_rejects_transport_secrets() -> None:
    with pytest.raises(ValueError, match="forbidden field"):
        _assert_sanitized({"stores": [], "Authorization": "secret"})

    with pytest.raises(ValueError, match="credential-shaped"):
        _assert_sanitized({"note": "Bearer should-never-be-persisted"})


def test_network_guard_fails_closed_and_reports_attempt() -> None:
    with _network_disabled() as attempts, pytest.raises(NetworkAccessBlockedError):
        socket.getaddrinfo("example.invalid", 443)
    assert attempts == {"count": 1}
