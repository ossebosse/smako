from __future__ import annotations

import asyncio
import dataclasses
import json
from collections import Counter
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
from app.services.primat_frozen_cache_collect import load_eligible_primat_contexts
from app.services.primat_phase_c_export import FrozenExternalCacheBundle
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from app.services.production_primat_refresh import (
    collect_city_primat_cache,
    plan_city_primat_refresh,
)

from grocery_data.app.domain import Chain
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
SNAPSHOT = "production-primat-refresh-test"


def _store(chain: str, native_id: str, *, name: str, city: str = "Lund") -> Store:
    store_id = f"{chain}:{native_id}"
    return Store(
        store_id=store_id,
        source_store_id=native_id,
        name=name,
        chain=chain,
        city=city,
        address=f"Testgatan {native_id[-1]}",
        postal_code="22350",
        tier="full_catalog",
        coverage="full_catalog",
        price_context_type="physical_store",
        source_provenance=SourceProvenance(
            source_provider="primat",
            source_channel="catalog",
            source_snapshot_id=SNAPSHOT,
            source_observed_at=NOW,
            chain=chain,
            store_id=store_id,
            store_name=name,
            provider_store_id=native_id,
            price_context="physical_store",
            coverage="full_catalog",
        ),
    )


def _resolution(*, drift_ica: bool = False) -> PrimatStoreResolution:
    stores = (
        _store(
            "ica",
            "1088004",
            name="Changed Gunnesbo" if drift_ica else "ICA Maxi Gunnesbo",
        ),
        _store("coop", "730400", name="Coop Online Syd"),
    )
    return PrimatStoreResolution(
        postal_code="22350",
        place_city="Lund",
        raw_rows=len(stores),
        selected_context_ids=frozenset(store.store_id for store in stores),
        stores=stores,
        observed_at=NOW,
        source_snapshot_id=SNAPSHOT,
        response_sha256="a" * 64,
        response_status=200,
        response_content_type="application/json",
        response_host="primat.nu",
        response_path="/api/v3/stores/resolve",
    )


def _database(path: Path) -> Path:
    discovery = {
        row.provider_context_id: row for row in primat_store_discovery_bundle(_resolution()).items
    }
    engine = create_database_engine(f"sqlite+pysqlite:///{path.as_posix()}")
    create_schema(engine)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        for chain, native_id, name, age_hours in (
            ("ica", "1088004", "ICA Maxi Gunnesbo", 72),
            ("coop", "730400", "Coop Online Syd", 1),
        ):
            physical_id = f"physical:{chain}:{native_id}"
            context_id = f"primat:{chain}:{native_id}"
            fingerprint = discovery[context_id].identity_fingerprint
            observed_at = NOW - timedelta(hours=age_hours)
            session.add(
                PhysicalStoreModel(
                    id=physical_id,
                    chain=chain,
                    external_store_id=native_id,
                    external_store_aliases=[],
                    name=name,
                    address=f"Testgatan {native_id[-1]}",
                    postal_code="22350",
                    city="Lund",
                    official_source=f"https://official.example/{chain}/{native_id}",
                    discovered_at=NOW,
                    last_seen_at=NOW,
                    is_active=True,
                    lifecycle_state="active",
                )
            )
            session.add(
                ProviderStoreIdentityMappingModel(
                    id=f"mapping:{chain}:{native_id}",
                    physical_store_id=physical_id,
                    provider="primat",
                    provider_context_id=context_id,
                    provider_store_id=native_id,
                    confidence="exact_id",
                    status="verified",
                    evidence="exact provider identity",
                    verified_identity_fingerprint=fingerprint,
                    observed_identity_fingerprint=fingerprint,
                    verified_at=observed_at,
                    last_checked_at=observed_at,
                    is_active=True,
                )
            )
            session.add(
                StoreContextLinkModel(
                    id=f"link:{chain}:{native_id}",
                    physical_store_id=physical_id,
                    grocery_context_id=context_id,
                    source_provider="primat",
                    source_channel="catalog",
                    grocery_context_name=name,
                    price_context_type="physical_store",
                    coverage="full_catalog",
                    relation_type="exact_store_online_context",
                    confidence="exact",
                    evidence="verified mapping",
                    basket_eligible=True,
                    offers_only=False,
                    snapshot_id="stale-price-lineage",
                    observed_at=observed_at,
                    linked_at=observed_at,
                    last_verified_at=observed_at,
                    is_active=True,
                )
            )
    engine.dispose()
    return path


def _product(store: Store) -> Product:
    return Product(
        product_id=f"product:{store.store_id}",
        name="Testmjölk 1 l",
        canonical_name="mjölk",
        category="Mejeri",
        store_id=store.store_id,
        store_name=store.name,
        price=14.9,
        effective_price=14.9,
        chain=store.chain,
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=1000,
        package_unit="ml",
        usable_quantity=1000,
        usable_unit="ml",
        sale_price=14.9,
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        price_context_type="physical_store",
        coverage="full_catalog",
        source_provenance=store.source_provenance,
    )



@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    monkeypatch.setattr("app.services.production_primat_refresh._SECONDS_BETWEEN_SEARCHES", 0)

class _FakeProvider:
    def __init__(self, resolution: PrimatStoreResolution) -> None:
        self.resolution = resolution
        self.requests = 0
        self.endpoints: Counter[str] = Counter()
        self.active_searches = 0
        self.max_active_searches = 0
        self.requested_store_ids: list[tuple[str, ...]] = []
        self.closed = False
        self.limits: list[int] = []

    @property
    def transport_report(self) -> dict[str, Any]:
        return {
            "mode": "bounded_primat_live",
            "request_limit": 149,
            "requests": self.requests,
            "endpoints": dict(sorted(self.endpoints.items())),
            "statuses": {"200": self.requests} if self.requests else {},
            "denied_requests": 0,
            "max_concurrency": 1,
            # A provider report may grow fields; the production report must
            # still copy only its fixed credential-free counter allowlist.
            "authorization": "must-not-be-copied",
        }

    async def resolve_store_candidates(self, postal_code: str) -> PrimatStoreResolution:
        assert postal_code == "22350"
        self.requests += 1
        self.endpoints["/stores/resolve"] += 1
        return self.resolution

    async def search_products(self, query: str, store_ids: list[str], limit: int = 100) -> list[Product]:
        assert query
        self.limits.append(limit)
        self.active_searches += 1
        self.max_active_searches = max(self.max_active_searches, self.active_searches)
        await asyncio.sleep(0)
        self.active_searches -= 1
        self.requests += 1
        self.endpoints["/products"] += 1
        self.requested_store_ids.append(tuple(store_ids))
        stores = {store.store_id: store for store in self.resolution.stores}
        return [_product(stores[store_id]) for store_id in store_ids]

    async def aclose(self) -> None:
        self.closed = True


def test_dry_plan_lists_only_verified_primat_primary_contexts_without_network(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "registry.sqlite")

    plan = plan_city_primat_refresh(database, "Lund", 48)

    assert plan["status"] == "planned"
    assert plan["provider_requests_planned"] == 149  # 48 benchmark + 100 recipe searches
    assert plan["credentials_included"] is False
    assert [row["context_id"] for row in plan["contexts"]] == ["primat:ica:1088004"]


@pytest.mark.asyncio
async def test_refresh_uses_stale_identity_seed_revalidates_and_replaces_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _database(tmp_path / "registry.sqlite")
    # Older than the price-age limit: not eligible for prices until revalidated.
    retained = (
        load_eligible_primat_contexts(
            database,
            city="Lund",
            now=NOW,
            chains=frozenset({Chain.ICA}),
        )
    )
    assert retained == ()
    # The explicit refresh seam may use it solely as an identity seed.
    seeded = load_eligible_primat_contexts(
        database,
        city="Lund",
        now=NOW,
        chains=frozenset({Chain.ICA}),
        allow_stale_identity_seed=True,
    )
    assert [row.provider_context_id for row in seeded] == ["primat:ica:1088004"]

    provider = _FakeProvider(_resolution())
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )
    output = tmp_path / "active-primat-cache.json"
    output.write_text("previous-cache", encoding="utf-8")

    before_refresh = datetime.now(tz=UTC)
    report = await collect_city_primat_cache(
        database,
        "Lund",
        "223 50",
        output,
        48.0,
    )
    after_refresh = datetime.now(tz=UTC)

    assert report["status"] == "PASS"
    assert report["transport"]["requests"] == 149
    assert report["surface"]["recipe_queries"] == 100 and report["surface"]["queries"] == 148
    assert len(report["contexts"]) == 1
    context_report = report["contexts"][0]
    assert context_report == {
        "context_id": "primat:ica:1088004",
        "chain": "ica",
        "coverage": "full_catalog",
        "mapping_confidence": "exact_id",
        "identity_seed_age_hours": context_report["identity_seed_age_hours"],
        "stale_identity_seed": True,
        "products": 1,
    }
    # NOW belongs to fixture collection, which can precede this test by more
    # than six minutes. Verify age against the actual call's clock bounds;
    # neither rewrite the observation nor widen a freshness tolerance.
    observed_at = NOW - timedelta(hours=72)
    assert (
        (before_refresh - observed_at).total_seconds() / 3600
        <= (context_report["identity_seed_age_hours"])
        <= (after_refresh - observed_at).total_seconds() / 3600
    )
    assert len(provider.requested_store_ids) == 148
    assert provider.limits == [100] * 48 + [50] * 100  # Primat's free plan: rows a day
    assert set(provider.requested_store_ids) == {("ica:1088004",)}
    assert provider.max_active_searches == 1
    assert provider.closed is True
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [store["store_id"] for store in payload["stores"]] == ["ica:1088004"]
    assert len(payload["products"]) == 1
    encoded = (json.dumps(report) + output.read_text(encoding="utf-8")).casefold()
    output_encoded = output.read_text(encoding="utf-8").casefold()
    assert "must-not-be-copied" not in encoded
    assert "authorization" not in encoded
    assert '"cookie"' not in output_encoded
    assert "bearer " not in output_encoded


@pytest.mark.asyncio
async def test_city_without_verified_contexts_skips_before_provider_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _database(tmp_path / "registry.sqlite")
    constructed = False

    def forbidden(**_kwargs: Any) -> None:
        nonlocal constructed
        constructed = True
        raise AssertionError("network provider must not be constructed")

    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        forbidden,
    )
    output = tmp_path / "malmo-cache.json"

    report = await collect_city_primat_cache(
        database,
        "Malmö",
        "21120",
        output,
        48.0,
    )

    assert report == {
        "status": "SKIPPED",
        "reason_code": "no_verified_primat_primary_contexts",
        "city": "Malmö",
        "postal_code": "21120",
        "contexts": 0,
        "provider_requests": 0,
        "output_written": False,
        "credentials_included": False,
        "raw_http_included": False,
    }
    assert constructed is False
    assert not output.exists()


@pytest.mark.asyncio
async def test_identity_drift_keeps_existing_cache_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _database(tmp_path / "registry.sqlite")
    provider = _FakeProvider(_resolution(drift_ica=True))
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )
    output = tmp_path / "active-primat-cache.json"
    output.write_bytes(b"immutable-previous-cache")

    with pytest.raises(ValueError, match="revalidated no exact contexts"):
        await collect_city_primat_cache(
            database,
            "Lund",
            "22350",
            output,
            48.0,
        )

    assert output.read_bytes() == b"immutable-previous-cache"
    assert provider.requests == 1
    assert provider.closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["identity", "coverage"])
async def test_partial_context_drift_without_lkg_stops_before_product_requests(tmp_path, monkeypatch, failure):
    database = _database(tmp_path / "registry.sqlite")
    eligible = load_eligible_primat_contexts(
        database, city="Lund", now=NOW,
        chains=frozenset({Chain.ICA, Chain.COOP}), allow_stale_identity_seed=True,
    )
    monkeypatch.setattr("app.services.production_primat_refresh._primat_primary_contexts",
                        lambda *args, **kwargs: eligible)
    resolution = _resolution(drift_ica=failure == "identity")
    if failure == "coverage":
        from dataclasses import replace
        resolution = replace(resolution, stores=tuple(
            store.model_copy(update={"coverage": "offers_only", "tier": "offers_only"})
            if store.chain == "ica" else store for store in resolution.stores))
    provider = _FakeProvider(resolution)
    monkeypatch.setattr("app.services.production_primat_refresh._BoundedPrimatProvider.load",
                        lambda **kwargs: provider)
    output = tmp_path / "candidate.json"
    output.write_bytes(b"previous")
    with pytest.raises(ValueError, match="fresh per-context LKG") as caught:
        await collect_city_primat_cache(database, "Lund", "22350", output, 48)
    diagnostic = caught.value.refresh_diagnostic
    assert diagnostic["stage"] == "exact_context_revalidation"
    assert diagnostic["query"] is None
    assert diagnostic["provider_requests"] == 1
    assert diagnostic["context_failures"][0]["context_id"] == "primat:ica:1088004"
    assert diagnostic["context_failures"][0]["diagnostic"]["message"] == (
        "eligible Primat context drifted or lost full coverage")
    assert not provider.requested_store_ids
    assert provider.closed
    assert output.read_bytes() == b"previous"
    assert "must-not-be-copied" not in json.dumps(diagnostic)


@pytest.mark.asyncio
async def test_one_drifted_context_uses_its_fresh_lkg_while_other_context_refreshes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _database(tmp_path / "registry.sqlite")
    eligible = load_eligible_primat_contexts(
        database,
        city="Lund",
        now=NOW,
        chains=frozenset({Chain.ICA, Chain.COOP}),
        allow_stale_identity_seed=True,
    )
    assert {row.chain for row in eligible} == {Chain.ICA, Chain.COOP}
    monkeypatch.setattr(
        "app.services.production_primat_refresh._primat_primary_contexts",
        lambda *_args, **_kwargs: eligible,
    )
    provider = _FakeProvider(_resolution(drift_ica=True))
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )

    old_ica = _store("ica", "1088004", name="ICA Maxi Gunnesbo")
    lkg = FrozenExternalCacheBundle(
        postal_code="22350",
        captured_at=NOW,
        stores=(old_ica,),
        products=(_product(old_ica),),
    )
    lkg_path = tmp_path / "primat-lkg.json"
    lkg_path.write_text(lkg.model_dump_json(), encoding="utf-8")
    output = tmp_path / "refreshed.json"

    report = await collect_city_primat_cache(
        database,
        "Lund",
        "22350",
        output,
        48.0,
        lkg_path,
    )

    assert report["status"] == "PASS"
    assert report["context_failures"] == 1
    assert report["context_lkg_used"] == 1
    assert {row["status"] for row in report["contexts"] if "status" in row} == {"lkg_retained"}
    payload = FrozenExternalCacheBundle.model_validate_json(output.read_bytes())
    assert {store.store_id for store in payload.stores} == {
        "ica:1088004",
        "coop:730400",
    }
    assert {product.store_id for product in payload.products} == {
        "ica:1088004",
        "coop:730400",
    }
    assert set(provider.requested_store_ids) == {("coop:730400",)}


@pytest.mark.asyncio
async def test_product_parse_failure_retains_stage_context_and_closes_provider(
    tmp_path, monkeypatch
):
    database = _database(tmp_path / "registry.sqlite")
    provider = _FakeProvider(_resolution())

    async def failing(query, stores, limit=100):
        raise ValueError("invalid product field") from TypeError("private underlying " + str(database))

    provider.search_products = failing
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load", lambda **k: provider
    )
    output = tmp_path / "candidate.json"
    output.write_text("previous")
    with pytest.raises(ValueError, match="invalid product field") as caught:
        await collect_city_primat_cache(database, "Lund", "22350", output, 48)
    diagnostic = caught.value.refresh_diagnostic
    assert diagnostic["stage"] == "product_fetch_and_parse"
    assert diagnostic["store_ids"] == ["ica:1088004"]
    assert diagnostic["cause_type"] == "TypeError"
    assert diagnostic["provider_requests"] == 1
    assert "private underlying input" not in json.dumps(diagnostic)
    assert output.read_text() == "previous"
    assert provider.closed


@pytest.mark.asyncio
async def test_finished_full_catalog_replaces_the_searches(tmp_path, monkeypatch) -> None:
    from app.services.primat_ica_catalog import CatalogStore

    database = _database(tmp_path / "registry.sqlite")
    resolution = _resolution()
    stores = {store.store_id: store for store in resolution.stores}
    now = datetime.now(tz=UTC)
    catalog = CatalogStore(tmp_path / "catalog.sqlite")
    recent, expired = now - timedelta(days=3), now - timedelta(days=20)
    for number, fetched_at in ((1, recent), (2, expired)):
        catalog.upsert_rows([{"chain": "ica", "store_id": "1088004", "product_id": f"p{number}",
                              "name": f"Vara {number}", "category": "Mejeri & Ost > Mjölk",
                              "price": 14.9}], fetched_at)
        catalog.save_meta("ica", f"p{number}", {"amount": 1, "unit": "l"}, fetched_at)
    catalog.put("round_completed_at", recent.isoformat())
    catalog.commit()
    catalog.close()
    monkeypatch.setenv("PRIMAT_ICA_CATALOG_SOURCE", "true")
    monkeypatch.setenv("PRIMAT_ICA_CATALOG_DB", str(tmp_path / "catalog.sqlite"))
    monkeypatch.setenv("PRIMAT_ICA_CATALOG_MIN_PRODUCTS", "1")

    provider = _FakeProvider(resolution)
    parsed: list[dict[str, Any]] = []

    def parse(row: dict[str, Any]) -> Product:
        parsed.append(row)
        store = stores[f"ica:{row['store_id']}"]
        return _product(store).model_copy(update={"product_id": row["product_id"]})

    provider._parse_product = parse  # type: ignore[attr-defined]
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )
    output = tmp_path / "active-primat-cache.json"
    report = await collect_city_primat_cache(database, "Lund", "22350", output, 336.0)

    assert report["status"] == "PASS"
    assert report["surface"]["source"] == "catalog"
    assert report["surface"]["catalog_products"] == 1
    assert report["transport"]["requests"] == 1
    assert report["transport"]["endpoints"] == {"/stores/resolve": 1}
    assert provider.requested_store_ids == []
    assert [row["product_id"] for row in parsed] == ["p1"]  # p2 is past 14 days
    payload = json.loads(output.read_text(encoding="utf-8"))
    [product] = payload["products"]
    observed = datetime.fromisoformat(product["source_provenance"]["source_observed_at"])
    assert observed == recent


@pytest.mark.asyncio
async def test_unfinished_catalog_keeps_the_searches(tmp_path, monkeypatch) -> None:
    from app.services.primat_ica_catalog import CatalogStore

    database = _database(tmp_path / "registry.sqlite")
    CatalogStore(tmp_path / "catalog.sqlite").close()
    monkeypatch.setenv("PRIMAT_ICA_CATALOG_SOURCE", "true")
    monkeypatch.setenv("PRIMAT_ICA_CATALOG_DB", str(tmp_path / "catalog.sqlite"))
    provider = _FakeProvider(_resolution())
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )
    report = await collect_city_primat_cache(
        database, "Lund", "22350", tmp_path / "out.json", 48.0
    )
    assert report["surface"]["source"] == "searches"
    assert report["transport"]["requests"] == 149


@pytest.mark.asyncio
async def test_last_known_prices_older_than_the_limit_are_left_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _database(tmp_path / "registry.sqlite")
    eligible = load_eligible_primat_contexts(
        database,
        city="Lund",
        now=NOW,
        chains=frozenset({Chain.ICA, Chain.COOP}),
        allow_stale_identity_seed=True,
    )
    monkeypatch.setattr(
        "app.services.production_primat_refresh._primat_primary_contexts",
        lambda *_args, **_kwargs: eligible,
    )
    provider = _FakeProvider(_resolution(drift_ica=True))
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )
    old_ica = _store("ica", "1088004", name="ICA Maxi Gunnesbo")
    old_at = datetime.now(tz=UTC) - timedelta(days=20)
    old_ica = old_ica.model_copy(update={"source_provenance": old_ica.source_provenance.model_copy(
        update={"source_observed_at": old_at})})
    old_product = _product(old_ica)
    lkg = FrozenExternalCacheBundle(
        postal_code="22350", captured_at=old_at, stores=(old_ica,), products=(old_product,),
    )
    lkg_path = tmp_path / "primat-lkg.json"
    lkg_path.write_text(lkg.model_dump_json(), encoding="utf-8")
    output = tmp_path / "refreshed.json"

    report = await collect_city_primat_cache(database, "Lund", "22350", output, 336.0, lkg_path)

    assert report["status"] == "PASS"
    assert report["context_lkg_used"] == 0 and report["context_lkg_expired"] == 1
    assert {row["status"] for row in report["contexts"] if "status" in row} == {"lkg_expired"}
    payload = FrozenExternalCacheBundle.model_validate_json(output.read_bytes())
    assert {store.store_id for store in payload.stores} == {"coop:730400"}


class _SplitResolveProvider(_FakeProvider):
    """Primat's postcode lookup misses the Coop store; a lookup near it finds it."""

    def __init__(self, resolution: PrimatStoreResolution) -> None:
        super().__init__(resolution)
        self.coordinate_lookups: list[tuple[float, float]] = []

    async def resolve_store_candidates(self, postal_code=None, *, latitude=None, longitude=None):
        self.requests += 1
        self.endpoints["/stores/resolve"] += 1
        wanted = "ica" if latitude is None else "coop"
        if latitude is not None:
            self.coordinate_lookups.append((latitude, longitude))
        stores = tuple(store for store in self.resolution.stores if store.chain == wanted)
        return dataclasses.replace(
            self.resolution,
            stores=stores,
            raw_rows=len(stores),
            selected_context_ids=frozenset(store.store_id for store in stores),
        )


@pytest.mark.asyncio
async def test_a_verified_store_outside_the_postcode_lookup_is_found_by_coordinates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlite3

    database = _database(tmp_path / "registry.sqlite")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE physical_stores SET latitude=55.58, longitude=13.0 "
            "WHERE id='physical:coop:730400'"
        )
    eligible = load_eligible_primat_contexts(
        database, city="Lund", now=NOW, chains=frozenset({Chain.ICA, Chain.COOP}),
        allow_stale_identity_seed=True,
    )
    monkeypatch.setattr(
        "app.services.production_primat_refresh._primat_primary_contexts",
        lambda *_args, **_kwargs: eligible,
    )
    provider = _SplitResolveProvider(_resolution())
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )
    report = await collect_city_primat_cache(
        database, "Lund", "22350", tmp_path / "out.json", 48.0
    )
    assert report["status"] == "PASS"
    assert provider.coordinate_lookups == [(55.58, 13.0)]
    assert report["transport"]["endpoints"]["/stores/resolve"] == 2
    assert report["context_failures"] == 0
    payload = FrozenExternalCacheBundle.model_validate_json((tmp_path / "out.json").read_bytes())
    assert {store.store_id for store in payload.stores} == {"ica:1088004", "coop:730400"}


@pytest.mark.asyncio
async def test_price_build_leaves_out_a_cached_store_past_the_age_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.production_price_universe_build import _load_external_cache

    database = _database(tmp_path / "registry.sqlite")  # ICA link 72 h old
    provider = _FakeProvider(_resolution())
    monkeypatch.setattr(
        "app.services.production_primat_refresh._BoundedPrimatProvider.load",
        lambda **_kwargs: provider,
    )
    cache = tmp_path / "cache.json"
    await collect_city_primat_cache(database, "Lund", "22350", cache, 48.0)
    import sqlite3

    with sqlite3.connect(database) as connection:  # links as activation leaves them
        connection.execute("UPDATE store_context_links SET snapshot_id=?", (SNAPSHOT,))

    # Within a 14-day limit the 72 h old ICA store is used ...
    _loaded, chains = _load_external_cache(
        cache, database=database, city="Lund", postal_code="22350", max_age_hours=336.0, now=NOW,
    )
    assert chains == frozenset({Chain.ICA})
    # ... past a 48 h limit it is left out instead of failing on scope.
    with pytest.raises(ValueError, match="only expired contexts"):
        _load_external_cache(
            cache, database=database, city="Lund", postal_code="22350", max_age_hours=48.0,
            now=NOW,
        )
