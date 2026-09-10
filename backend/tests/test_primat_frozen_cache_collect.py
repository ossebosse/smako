from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.models import (
    Product,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
    SourceProvenance,
    Store,
)
from app.providers.primat import PrimatStoreResolution
from app.services.primat_frozen_cache_collect import (
    build_frozen_external_cache,
    canonical_ingredient_query_surface,
    load_eligible_primat_contexts,
    revalidate_primat_contexts,
)
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from scripts.benchmark_lund_phase_c import _FrozenExternalProvider
from scripts.collect_lund_primat_frozen_cache import _run as run_collector

from grocery_data.app.services.catalog_recipe_coverage import (
    REPRESENTATIVE_RECIPE_BASKET,
    CatalogRecipeCoverageBenchmark,
)
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    PhysicalStoreModel,
    ProviderStoreIdentityMappingModel,
    StoreContextLinkModel,
)

NOW = datetime.now(tz=UTC).replace(microsecond=0)
SNAPSHOT = "primat-frozen-test-snapshot"
RESPONSE_HASH = "a" * 64
CONTEXTS = (
    ("1004409", "ICA Malmborgs Clemenstorget", "Clemenstorget 5", "22221"),
    ("1088004", "ICA Maxi Gunnesbo", "Traktorvägen 1", "22660"),
)


def _store(
    native_id: str,
    name: str,
    address: str,
    postal_code: str,
) -> Store:
    store_id = f"ica:{native_id}"
    return Store(
        store_id=store_id,
        source_store_id=native_id,
        name=name,
        chain="ica",
        city="Lund",
        address=address,
        postal_code=postal_code,
        tier="full_catalog",
        coverage="full_catalog",
        price_context_type="physical_store",
        source_provenance=SourceProvenance(
            source_provider="primat",
            source_channel="catalog",
            source_snapshot_id=SNAPSHOT,
            source_observed_at=NOW,
            chain="ica",
            store_id=store_id,
            store_name=name,
            provider_store_id=native_id,
            price_context="physical_store",
            coverage="full_catalog",
        ),
    )


def _resolution() -> PrimatStoreResolution:
    stores = tuple(_store(*row) for row in CONTEXTS)
    return PrimatStoreResolution(
        postal_code="22350",
        place_city="Lund",
        raw_rows=2,
        # Regression: the second eligible context is provider-unselected.
        selected_context_ids=frozenset({stores[0].store_id}),
        stores=stores,
        observed_at=NOW,
        source_snapshot_id=SNAPSHOT,
        response_sha256=RESPONSE_HASH,
        response_status=200,
        response_content_type="application/json",
        response_host="primat.nu",
        response_path="/api/v3/stores/resolve",
    )


def _product(native_id: str, index: int) -> Product:
    store = next(row for row in _resolution().stores if row.source_store_id == native_id)
    return Product(
        product_id=f"product-{native_id}-{index}",
        name=f"Testprodukt {index} 500 g",
        canonical_name="testprodukt",
        category="Test",
        store_id=store.store_id,
        store_name=store.name,
        price=10 + index,
        effective_price=10 + index,
        chain="ica",
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=500,
        package_unit="g",
        usable_quantity=500,
        usable_unit="g",
        sale_price=10 + index,
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        price_context_type="physical_store",
        coverage="full_catalog",
        source_provenance=SourceProvenance(
            source_provider="primat",
            source_channel="catalog",
            source_snapshot_id=SNAPSHOT,
            source_observed_at=NOW,
            chain="ica",
            store_id=store.store_id,
            store_name=store.name,
            provider_store_id=native_id,
            price_context="physical_store",
            coverage="full_catalog",
            semantic_confidence="high",
            quantity_confidence="exact",
        ),
    )


def _mapping_database(
    path: Path,
    *,
    extra_offers_only: bool = False,
) -> Path:
    resolution = _resolution()
    candidates = {
        row.provider_context_id: row
        for row in primat_store_discovery_bundle(resolution).items
    }
    engine = create_database_engine(f"sqlite+pysqlite:///{path.as_posix()}")
    create_schema(engine)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        rows = list(CONTEXTS)
        if extra_offers_only:
            rows.append(("1003999", "ICA Offers", "Testgatan 1", "22222"))
        for native_id, name, address, postal_code in rows:
            physical_id = f"physical:ica:{native_id}"
            context_id = f"primat:ica:{native_id}"
            candidate = candidates.get(context_id)
            fingerprint = (
                candidate.identity_fingerprint if candidate is not None else "b" * 64
            )
            session.add(
                PhysicalStoreModel(
                    id=physical_id,
                    chain="ica",
                    external_store_id=native_id,
                    external_store_aliases=[],
                    name=name,
                    address=address,
                    postal_code=postal_code,
                    city="Lund",
                    official_source=f"https://official.example/ica/{native_id}",
                    discovered_at=NOW,
                    last_seen_at=NOW,
                    is_active=True,
                    lifecycle_state="active",
                )
            )
            session.add(
                ProviderStoreIdentityMappingModel(
                    id=f"mapping-{native_id}",
                    physical_store_id=physical_id,
                    provider="primat",
                    provider_context_id=context_id,
                    provider_store_id=native_id,
                    confidence="exact_id",
                    status="verified",
                    evidence="exact provider ID",
                    verified_identity_fingerprint=fingerprint,
                    observed_identity_fingerprint=fingerprint,
                    verified_at=NOW,
                    last_checked_at=NOW,
                    is_active=True,
                )
            )
            is_full = candidate is not None
            session.add(
                StoreContextLinkModel(
                    id=f"link-{native_id}",
                    physical_store_id=physical_id,
                    grocery_context_id=context_id,
                    source_provider="primat",
                    source_channel="catalog",
                    grocery_context_name=name,
                    price_context_type="physical_store",
                    coverage="full_catalog" if is_full else "offers_only",
                    relation_type="exact_store_online_context",
                    confidence="exact",
                    evidence="verified mapping + smoke" if is_full else "offers only",
                    basket_eligible=is_full,
                    offers_only=not is_full,
                    snapshot_id=SNAPSHOT,
                    observed_at=NOW,
                    linked_at=NOW,
                    last_verified_at=NOW,
                    is_active=True,
                )
            )
    engine.dispose()
    return path


def test_query_surface_is_exactly_the_shared_versioned_48() -> None:
    surface = canonical_ingredient_query_surface()

    assert tuple(row.canonical for row in surface.items) == tuple(
        row.canonical for row in CatalogRecipeCoverageBenchmark.ingredient_set
    )
    assert len(surface.items) == 48
    assert len({" ".join(row.query.casefold().split()) for row in surface.items}) == 48
    assert set(REPRESENTATIVE_RECIPE_BASKET).issubset(
        row.canonical for row in surface.items
    )
    assert surface.sha256 == "11c054baeb08e5033fc00882a4d0e494362fc84a5b829217828abb677fa7f89f"


def test_immutable_loader_excludes_offers_probable_and_stale_links(
    tmp_path: Path,
) -> None:
    database = _mapping_database(tmp_path / "mapping.sqlite", extra_offers_only=True)

    eligible = load_eligible_primat_contexts(database, now=NOW + timedelta(hours=1))
    assert {row.provider_context_id for row in eligible} == {
        "primat:ica:1004409",
        "primat:ica:1088004",
    }

    import sqlite3

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE provider_store_identity_mappings SET confidence='probable' "
            "WHERE provider_store_id='1004409'"
        )
        connection.execute(
            "UPDATE store_context_links SET observed_at=? "
            "WHERE grocery_context_id='primat:ica:1088004'",
            ((NOW - timedelta(hours=49)).isoformat(),),
        )
        connection.commit()
    finally:
        connection.close()

    assert load_eligible_primat_contexts(database, now=NOW) == ()


def test_bundle_revalidates_unselected_context_and_rejects_conflicts(
    tmp_path: Path,
) -> None:
    resolution = _resolution()
    database = _mapping_database(tmp_path / "mapping.sqlite")
    eligible = load_eligible_primat_contexts(database, now=NOW + timedelta(minutes=1))
    contexts = revalidate_primat_contexts(resolution, eligible)
    products = [_product("1004409", 1), _product("1088004", 1)]

    bundle = build_frozen_external_cache(resolution, contexts, products)

    assert len(contexts) == 2
    assert {row.store.store_id for row in contexts} == {
        "ica:1004409",
        "ica:1088004",
    }
    assert len(bundle.stores) == 2
    assert len(bundle.products) == 2
    assert all(row.coverage == "full_catalog" for row in bundle.stores)
    conflicting = products[0].model_copy(update={"price": 999, "effective_price": 999})
    with pytest.raises(ValueError, match="changed during bounded collection"):
        build_frozen_external_cache(
            resolution,
            contexts,
            [*products, conflicting],
        )
    drifted = replace(
        resolution,
        stores=(
            resolution.stores[0].model_copy(update={"name": "Changed identity"}),
            resolution.stores[1],
        ),
    )
    with pytest.raises(ValueError, match="drifted or lost full coverage"):
        revalidate_primat_contexts(drifted, eligible)


@pytest.mark.asyncio
async def test_collector_spends_one_resolve_plus_48_shared_queries_and_exports_v1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolution = _resolution()
    database = _mapping_database(tmp_path / "mapping.sqlite")
    surface = canonical_ingredient_query_surface()

    class FakeProvider:
        def __init__(self) -> None:
            self.requests = 0
            self.endpoints: Counter[str] = Counter()
            self.queries: list[tuple[str, tuple[str, ...]]] = []

        @property
        def transport_report(self) -> dict[str, Any]:
            return {
                "mode": "bounded_primat_live",
                "request_limit": 49,
                "requests": self.requests,
                "endpoints": dict(sorted(self.endpoints.items())),
                "statuses": {"200": self.requests} if self.requests else {},
                "denied_requests": 0,
                "max_concurrency": 1,
            }

        async def resolve_store_candidates(self, postal_code: str) -> PrimatStoreResolution:
            assert postal_code == "22350"
            self.requests += 1
            self.endpoints["/stores/resolve"] += 1
            return resolution

        async def search_products(
            self,
            query: str,
            store_ids: list[str],
        ) -> list[Product]:
            self.requests += 1
            self.endpoints["/products"] += 1
            self.queries.append((query, tuple(store_ids)))
            index = len(self.queries)
            return [_product(native_id, index) for native_id, *_rest in CONTEXTS]

        async def aclose(self) -> None:
            return None

    provider = FakeProvider()
    monkeypatch.setattr(
        "scripts.collect_lund_primat_frozen_cache._BoundedPrimatProvider.load",
        lambda **kwargs: provider,
    )
    output = tmp_path / "lund-frozen-external-v1.json"
    args = argparse.Namespace(
        allow_bounded_primat_frozen_cache_collection=True,
        city="Lund",
        postal_code="22350",
        database=database,
        context_id=["primat:ica:1004409", "primat:ica:1088004"],
        max_age_hours=48.0,
        output=output,
    )

    report = await run_collector(args)

    assert report["status"] == "PASS"
    assert report["optimizer_runs"] == 0
    assert report["transport"]["requests"] == 49
    assert report["transport"]["endpoints"] == {
        "/products": 48,
        "/stores/resolve": 1,
    }
    assert [query for query, _store_ids in provider.queries] == [
        row.query for row in surface.items
    ]
    assert all(
        store_ids == ("ica:1004409", "ica:1088004")
        for _query, store_ids in provider.queries
    )
    assert report["output"]["schema_version"] == "lund-frozen-external-v1"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "lund-frozen-external-v1"
    assert len(payload["stores"]) == 2
    assert len(payload["products"]) == 96
    frozen = _FrozenExternalProvider.load(
        output,
        postal_code="22350",
        exact_contexts=frozenset(
            {
                ("ica", "primat:ica:1004409"),
                ("ica", "primat:ica:1088004"),
            }
        ),
    )
    frozen_stores = await frozen.find_stores("22350")
    assert len(frozen_stores) == 2
    encoded = output.read_text(encoding="utf-8").casefold()
    assert "authorization" not in encoded
    assert "cookie" not in encoded
    assert "bearer " not in encoded


@pytest.mark.asyncio
async def test_collector_requires_opt_in_before_database_or_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed = False

    def forbidden(**_kwargs: Any) -> None:
        nonlocal constructed
        constructed = True
        raise AssertionError

    monkeypatch.setattr(
        "scripts.collect_lund_primat_frozen_cache._BoundedPrimatProvider.load",
        forbidden,
    )
    args = argparse.Namespace(
        allow_bounded_primat_frozen_cache_collection=False,
        city="Lund",
        postal_code="22350",
        database=tmp_path / "missing.sqlite",
        context_id=["primat:ica:1004409", "primat:ica:1088004"],
        max_age_hours=48.0,
        output=tmp_path / "not-written.json",
    )

    with pytest.raises(PermissionError):
        await run_collector(args)
    assert constructed is False
    assert not args.output.exists()


@pytest.mark.asyncio
async def test_collector_refuses_scope_mismatch_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _mapping_database(tmp_path / "mapping.sqlite")
    constructed = False

    def forbidden(**_kwargs: Any) -> None:
        nonlocal constructed
        constructed = True
        raise AssertionError

    monkeypatch.setattr(
        "scripts.collect_lund_primat_frozen_cache._BoundedPrimatProvider.load",
        forbidden,
    )
    args = argparse.Namespace(
        allow_bounded_primat_frozen_cache_collection=True,
        city="Lund",
        postal_code="22350",
        database=database,
        context_id=["primat:ica:1004409", "primat:ica:not-eligible"],
        max_age_hours=48.0,
        output=tmp_path / "not-written.json",
    )

    with pytest.raises(ValueError, match="complete eligible ICA scope"):
        await run_collector(args)
    assert constructed is False
    assert not args.output.exists()
