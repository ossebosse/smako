from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from grocery_data.app.main import create_app
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactMetadata,
    PreparedUniverseArtifactStore,
)
from grocery_data.app.storage import (
    PhysicalStoreModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)

NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)


def _factory():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        session.add_all(
            PhysicalStoreModel(
                id=f"physical:coop:{index}",
                chain="coop",
                external_store_id=str(index),
                name=f"Coop Lund {index}",
                address=f"Testgatan {index}",
                postal_code="22350",
                city="Lund",
                official_source="fixture://coop-locator",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
            for index in range(7)
        )
        session.commit()
    return factory


def test_daily_status_exposes_nonblocking_coop_gap_without_live_requests(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("PRICE_AGE_WARNING_HOURS", "36")
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "48")
    client = TestClient(create_app(_factory()))

    response = client.get("/operations/daily-refresh/status?city=Lund")

    assert response.status_code == 200
    payload = response.json()
    assert payload["physical_stores"] == 7
    assert payload["explained_states"] == 7
    assert payload["meal_generation_live_requests"] == 0
    assert payload["physical_validation_required"] is False
    assert payload["coop_gap_non_blocking"] is True
    assert payload["chains"]["coop"]["fresh_full_basket_contexts"] == 0
    assert payload["chains"]["coop"]["alert"] == (
        "7 physical stores, 0 fresh full basket price contexts"
    )


def test_universe_status_is_read_only_and_uses_injected_manager() -> None:
    class Manager:
        active = object()

        def status(self, scope: str):  # type: ignore[no-untyped-def]
            assert scope == "city:lund"
            return {
                "universe_id": "universe-1",
                "built_at": NOW,
                "product_count": 123,
                "raw_snapshot_hash": "not-public",
            }

        def get_active(self, scope: str):  # type: ignore[no-untyped-def]
            assert scope == "city:lund"
            return self.active

    client = TestClient(create_app(_factory(), price_universe_manager=Manager()))

    payload = client.get("/price-universe/status?city=Lund").json()

    assert payload["active"] is True
    assert payload["status"] == "active"
    assert payload["universe_id"] == "universe-1"
    assert payload["rebuild_during_request"] is False
    assert payload["live_provider_requests"] == 0
    assert "raw_snapshot_hash" not in payload


def test_universe_status_reads_persistent_active_manifest_without_rebuild(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"value": "closed-local"}), encoding="utf-8")
    store = PreparedUniverseArtifactStore(tmp_path / "managed")
    observed_at = datetime.now(tz=UTC)
    store.activate(
        candidate,
        city="Lund",
        validator=lambda _payload, city: PreparedUniverseArtifactMetadata(
            city=city,
            scope_id=f"city:{city}",
            universe_id="persistent-universe",
            built_at=NOW,
            snapshot_ids=("snapshot-1",),
            product_count=456,
            canonical_index_count=48,
            oldest_observed_at=observed_at,
        ),
        activated_at=NOW,
    )
    client = TestClient(
        create_app(_factory(), price_universe_artifact_store=store)
    )

    payload = client.get("/price-universe/status?city=Lund").json()

    assert payload["active"] is True
    assert payload["status"] == "active"
    assert payload["universe_id"] == "persistent-universe"
    assert payload["product_count"] == 456
    assert payload["cache_state"] == "persistent_active_manifest"
    assert payload["rebuild_during_request"] is False
    assert payload["live_provider_requests"] == 0
    assert "artifact_file" not in payload
    assert "artifact_sha256" not in payload
