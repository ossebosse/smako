from __future__ import annotations

import json
import socket
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from grocery_data import __main__ as grocery_cli
from grocery_data.app.services.closed_provider_context_activation import (
    activate_closed_primat_context_links,
    validate_closed_primat_context_links,
)
from grocery_data.app.storage import (
    PhysicalStoreModel,
    ProviderStoreIdentityMappingModel,
    StoreContextLinkModel,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

# Freshness is part of these integration assertions.  Keep the fixture current
# instead of coupling it to the repository author's wall clock.
NOW = datetime.now(tz=UTC).replace(microsecond=0)
OLD = NOW - timedelta(days=4)


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _seed_exact_context(session, external_id: str, *, mapping_store_id: str | None = None):  # type: ignore[no-untyped-def]
    physical_id = f"physical:ica:{external_id}"
    context_id = f"primat:ica:{external_id}"
    session.add(
        PhysicalStoreModel(
            id=physical_id,
            chain="ica",
            external_store_id=external_id,
            external_store_aliases=[],
            name=f"ICA {external_id}",
            city="Lund",
            official_source="https://official.example/ica",
            discovered_at=OLD,
            last_seen_at=NOW,
            is_active=True,
            lifecycle_state="active",
        )
    )
    session.add(
        ProviderStoreIdentityMappingModel(
            id=f"mapping-{external_id}",
            physical_store_id=physical_id,
            provider="primat",
            provider_context_id=context_id,
            provider_store_id=mapping_store_id or external_id,
            confidence="exact_id",
            status="verified",
            evidence="persisted strong evidence",
            verified_identity_fingerprint="a" * 64,
            observed_identity_fingerprint="a" * 64,
            verified_at=OLD,
            last_checked_at=OLD,
            is_active=True,
        )
    )
    link = StoreContextLinkModel(
        id=f"link-{external_id}",
        physical_store_id=physical_id,
        grocery_context_id=context_id,
        source_provider="primat",
        source_channel="catalog",
        grocery_context_name=f"ICA {external_id}",
        price_context_type="physical_store",
        coverage="full_catalog",
        relation_type="exact_store_online_context",
        confidence="exact",
        evidence="must be preserved",
        basket_eligible=True,
        offers_only=False,
        snapshot_id=f"old-{external_id}",
        observed_at=OLD,
        linked_at=OLD,
        last_verified_at=OLD,
        is_active=True,
    )
    session.add(link)
    session.flush()
    return link


def _provenance(
    external_id: str,
    *,
    snapshot_id: str = "primat-fresh-snapshot",
) -> dict[str, object]:
    return {
        "chain": "ica",
        "coverage": "full_catalog",
        "price_context": "physical_store",
        "provider_store_id": external_id,
        "source_channel": "catalog",
        "source_observed_at": NOW.isoformat(),
        "source_provider": "primat",
        "source_snapshot_id": snapshot_id,
        "store_id": f"ica:{external_id}",
    }


def _cache(
    path: Path,
    *external_ids: str,
    snapshot_id: str = "primat-fresh-snapshot",
) -> Path:
    stores = []
    products = []
    for external_id in external_ids:
        provenance = _provenance(external_id, snapshot_id=snapshot_id)
        stores.append(
            {
                "store_id": f"ica:{external_id}",
                "chain": "ica",
                "source_store_id": external_id,
                "physical_store_external_id": external_id,
                "coverage": "full_catalog",
                "tier": "full_catalog",
                "price_context_type": "physical_store",
                "source_provenance": provenance,
            }
        )
        products.append(
            {
                "product_id": f"product-{external_id}",
                "store_id": f"ica:{external_id}",
                "chain": "ica",
                "source_provenance": provenance,
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "lund-frozen-external-v1",
                "postal_code": "22350",
                "captured_at": NOW.isoformat(),
                "stores": stores,
                "products": products,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_exact_verified_context_link_is_refreshed_without_creating_mapping(
    storage, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    cache = _cache(tmp_path / "cache.json", "1088004")
    with session_scope(storage) as session:
        _seed_exact_context(session, "1088004")
        before_mappings = session.query(ProviderStoreIdentityMappingModel).count()
        report = activate_closed_primat_context_links(session, cache)
        link = session.query(StoreContextLinkModel).one()

        assert report.status == "activated"
        assert report.snapshot_ids == ("primat-fresh-snapshot",)
        assert report.provider_requests == 0
        assert report.mappings_created == 0
        assert link.snapshot_id == "primat-fresh-snapshot"
        assert link.observed_at == NOW
        assert link.coverage == "full_catalog"
        assert link.basket_eligible is True
        assert link.offers_only is False
        assert link.evidence == "must be preserved"
        assert session.query(ProviderStoreIdentityMappingModel).count() == before_mappings


def test_mismatched_store_is_rejected_while_exact_store_is_isolated(
    storage, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    cache = _cache(tmp_path / "cache.json", "1004409", "1088004")
    with session_scope(storage) as session:
        valid = _seed_exact_context(session, "1004409")
        rejected = _seed_exact_context(
            session, "1088004", mapping_store_id="different-provider-store"
        )
        report = activate_closed_primat_context_links(session, cache)

        assert report.status == "partially_activated"
        assert report.activated == 1
        assert report.rejected == 1
        assert valid.snapshot_id == "primat-fresh-snapshot"
        assert rejected.snapshot_id == "old-1088004"


def test_identity_preflight_is_read_only_and_reports_partial_rejection(
    storage, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    cache = _cache(tmp_path / "cache.json", "1004409", "1088004")
    with session_scope(storage) as session:
        valid = _seed_exact_context(session, "1004409")
        rejected = _seed_exact_context(
            session, "1088004", mapping_store_id="different-provider-store"
        )

        report = validate_closed_primat_context_links(session, cache)

        assert report.status == "partially_activated"
        assert report.activated == 1
        assert report.rejected == 1
        assert valid.snapshot_id == "old-1004409"
        assert rejected.snapshot_id == "old-1088004"


def test_managed_partial_candidate_rolls_back_before_lkg_context_restore(
    tmp_path: Path,
) -> None:
    database = tmp_path / "managed-activation.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        _seed_exact_context(session, "1004409")
        _seed_exact_context(session, "1088004")
    engine.dispose()

    settings = SimpleNamespace(database_url=database_url)
    candidate = _cache(
        tmp_path / "candidate.json",
        "1004409",
        "1088004",
        snapshot_id="primat-candidate-snapshot",
    )
    preflight = grocery_cli._validate_external_context_links(settings, candidate)  # type: ignore[arg-type]
    assert preflight["status"] == "activated"

    # Simulate identity drift between the read-only preflight and commit.  The
    # old per-context savepoint path would persist the first row before the
    # second row was rejected.
    drift_engine = create_database_engine(database_url)
    drift_factory = create_session_factory(drift_engine)
    with session_scope(drift_factory) as session:
        mapping = session.get(ProviderStoreIdentityMappingModel, "mapping-1088004")
        assert mapping is not None
        mapping.provider_store_id = "drifted-provider-store"
    drift_engine.dispose()

    with pytest.raises(
        ValueError,
        match="complete closed Primat context activation was rejected",
    ):
        grocery_cli._activate_external_context_links(settings, candidate)  # type: ignore[arg-type]

    verify_engine = create_database_engine(database_url)
    verify_factory = create_session_factory(verify_engine)
    with session_scope(verify_factory) as session:
        links = {
            row.id: row.snapshot_id for row in session.query(StoreContextLinkModel).all()
        }
        assert links == {
            "link-1004409": "old-1004409",
            "link-1088004": "old-1088004",
        }
    verify_engine.dispose()

    # The orchestrator may now restore the previous manifest and activate only
    # the contexts represented by that LKG; no candidate-only write survives.
    lkg = _cache(
        tmp_path / "lkg.json",
        "1004409",
        snapshot_id="primat-lkg-snapshot",
    )
    restored = grocery_cli._activate_external_context_links(settings, lkg)  # type: ignore[arg-type]
    assert restored["status"] == "activated"

    final_engine = create_database_engine(database_url)
    final_factory = create_session_factory(final_engine)
    with session_scope(final_factory) as session:
        links = {
            row.id: row.snapshot_id for row in session.query(StoreContextLinkModel).all()
        }
        assert links == {
            "link-1004409": "primat-lkg-snapshot",
            "link-1088004": "old-1088004",
        }
    final_engine.dispose()


def test_ambiguous_cache_identity_fails_before_any_link_update(
    storage, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    cache = _cache(tmp_path / "cache.json", "1088004")
    payload = json.loads(cache.read_text(encoding="utf-8"))
    payload["stores"].append(dict(payload["stores"][0]))
    cache.write_text(json.dumps(payload), encoding="utf-8")
    with session_scope(storage) as session:
        link = _seed_exact_context(session, "1088004")
        with pytest.raises(ValueError, match="ambiguous store identities"):
            activate_closed_primat_context_links(session, cache)
        assert link.snapshot_id == "old-1088004"


def test_secret_shaped_cache_is_rejected_before_database_write(
    storage, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    cache = _cache(tmp_path / "cache.json", "1088004")
    payload = json.loads(cache.read_text(encoding="utf-8"))
    payload["stores"][0]["x-csrf-token"] = "must-not-survive"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    with session_scope(storage) as session:
        link = _seed_exact_context(session, "1088004")
        with pytest.raises(ValueError, match="forbidden transport material"):
            activate_closed_primat_context_links(session, cache)
        assert link.snapshot_id == "old-1088004"


def test_activation_has_no_network_dependency(
    storage, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    cache = _cache(tmp_path / "cache.json", "1088004")

    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    with session_scope(storage) as session:
        _seed_exact_context(session, "1088004")
        report = activate_closed_primat_context_links(session, cache)
    assert report.status == "activated"
    assert report.provider_requests == 0


@pytest.mark.asyncio
async def test_daily_refresh_activates_usable_closed_cache_before_universe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "daily.sqlite"
    engine = create_database_engine(f"sqlite+pysqlite:///{database.as_posix()}")
    create_schema(engine)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        _seed_exact_context(session, "1088004")
    engine.dispose()
    cache = _cache(tmp_path / "cache.json", "1088004")
    output: list[dict[str, object]] = []

    async def closed_collection(_args: Namespace):  # type: ignore[no-untyped-def]
        return (
            {
                "run_type": "daily_own_collection",
                "cities": ["Lund"],
                "results": [
                    {
                        "chain": "willys",
                        "city": "Lund",
                        "roles": ("basket",),
                        "source_provider": "own",
                        "status": "healthy",
                        "promoted": True,
                        "snapshot_id": "own-snapshot",
                        "active_snapshot_age_hours": 1,
                    }
                ],
                "summary": {},
            },
            0,
        )

    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL", f"sqlite+pysqlite:///{database.as_posix()}"
    )
    monkeypatch.setattr(grocery_cli, "_run_collect_all", closed_collection)
    monkeypatch.setattr(grocery_cli, "_json", output.append)

    result = await grocery_cli._daily_refresh(
        Namespace(
            city=["Lund"],
            external_cache=cache,
            price_universe_candidate=None,
            price_universe_cache_root=None,
        )
    )

    assert result == 0
    external = output[0]["external_provider"]
    assert isinstance(external, dict)
    assert external["status"] == "closed_cache_available"
    activation = external["context_activation"]
    assert isinstance(activation, dict)
    assert activation["activated"] == 1
    assert activation["provider_requests"] == 0
    verify_engine = create_database_engine(
        f"sqlite+pysqlite:///{database.as_posix()}"
    )
    verify_factory = create_session_factory(verify_engine)
    with session_scope(verify_factory) as session:
        link = session.query(StoreContextLinkModel).one()
        assert link.snapshot_id == "primat-fresh-snapshot"
        assert link.observed_at == NOW
    verify_engine.dispose()
