from __future__ import annotations

import errno
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from typing import Any

import pytest
from app.config import Settings
from app.models import DiversityMode, PlanRequest, Product, Recipe, RecipeIngredient, Store
from app.models.basket import OptimizedBasket
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.provenance import SourceProvenance
from app.providers.base import GroceryPriceProvider
from app.services.basket_calculator import BasketCalculator
from app.services.economic_ingredient_selector import (
    EconomicIngredientPool,
    EconomicIngredientSignal,
    EconomicProductExample,
)
from app.services.ingredient_taxonomy import IngredientCategory
from app.services.meal_plan_optimizer import MealPlanService
from app.services.performance_trace import activate_performance_trace
from app.services.price_universe import (
    BasketResultCache,
    PackageCostCache,
    PriceUniverseBuildConfig,
    PriceUniverseBuilder,
    PriceUniverseKey,
)
from app.services.price_universe_runtime import (
    LocalPriceUniverseProvider,
    PreparedPriceUniverse,
    PreparedPriceUniverseManager,
    normalized_memberships,
)
from app.services.pricing_projection_prewarm import precompute_pricing_semantics
from app.services.recipe_candidate_generator import RecipeCandidateGenerator

from grocery_data.app.services import durable_files

OBSERVED_AT = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
POSTAL_CODE = "22350"
STORE_ID = "own:hemkop:4123"
SNAPSHOT_ID = "snapshot-karhogstorg"
# The two request-path/cache tests below exercise local-universe behavior, not
# freshness rejection. Keep their frozen deterministic fixture valid regardless
# of the calendar date on which the suite runs; freshness has dedicated tests.
NON_FRESHNESS_TEST_MAX_AGE_HOURS = 1_000_000.0


def _provenance(
    *,
    snapshot_id: str = SNAPSHOT_ID,
    store_id: str = STORE_ID,
    observed_at: datetime = OBSERVED_AT,
) -> SourceProvenance:
    return SourceProvenance(
        source_provider="own",
        source_channel="catalog",
        source_snapshot_id=snapshot_id,
        source_observed_at=observed_at,
        source_role="basket",
        chain="hemkop",
        store_id=store_id,
        store_name="Hemkop Lund Karhogstorg",
        price_context="online_store",
        coverage="full_online_catalog",
        semantic_confidence="high",
        quantity_confidence="exact",
    )


def _store(
    *,
    snapshot_id: str = SNAPSHOT_ID,
    store_id: str = STORE_ID,
    observed_at: datetime = OBSERVED_AT,
) -> Store:
    return Store(
        store_id=store_id,
        name="Hemkop Lund Karhogstorg",
        chain="hemkop",
        city="Lund",
        postal_code=POSTAL_CODE,
        address="Karhogstorg 2A",
        price_context_type="online_store",
        coverage="full_online_catalog",
        source_provenance=_provenance(
            snapshot_id=snapshot_id,
            store_id=store_id,
            observed_at=observed_at,
        ),
    )


def _product(
    product_id: str,
    canonical: str,
    *,
    price: float,
    quantity: float,
    unit: str = "g",
    store_id: str = STORE_ID,
    snapshot_id: str = SNAPSHOT_ID,
    index: int = 0,
    observed_at: datetime = OBSERVED_AT,
) -> Product:
    return Product(
        product_id=product_id,
        name=f"{canonical.title()} fixture {index}",
        canonical_name=canonical,
        canonical_food=canonical,
        category="fixture",
        store_id=store_id,
        store_name="Hemkop Lund Karhogstorg",
        brand="Fixture",
        chain="hemkop",
        gtin=f"73100000{index:06d}",
        price=price,
        effective_price=price,
        sale_price=price,
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=quantity,
        package_unit=unit,
        usable_quantity=quantity,
        usable_unit=unit,
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        product_role="food",
        product_form="fixed",
        price_context_type="online_store",
        coverage="full_online_catalog",
        source_provenance=_provenance(
            snapshot_id=snapshot_id,
            store_id=store_id,
            observed_at=observed_at,
        ),
    )


def _candidate(product: Product) -> ProductCandidate:
    return ProductCandidate.from_product(product, match_score=1.0).model_copy(
        update={"semantic_evidence": ["runtime fixture"]}
    )


def _pool(products: Sequence[Product]) -> EconomicIngredientPool:
    candidates = {
        product.canonical_food: [_candidate(product)]
        for product in products
        if product.canonical_food is not None
    }
    first = products[0]
    quantity = float(first.usable_quantity or first.package_quantity or 1)
    unit = first.usable_unit or first.package_unit
    normalized_unit = "st" if unit == "st" else ("liter" if unit == "ml" else "kg")
    unit_price = (
        first.effective_price
        if normalized_unit == "st"
        else (float(first.effective_price) * 1000 / quantity)
    )
    example = EconomicProductExample(
        product_id=first.product_id,
        name=first.name,
        store_id=first.store_id,
        store=first.store_name,
        package_quantity=first.package_quantity,
        package_unit=first.package_unit,
        usable_quantity=first.usable_quantity,
        usable_unit=first.usable_unit,
        quantity_confidence=first.quantity_confidence,
        price=first.price,
        effective_price=float(first.effective_price),
        normalized_unit_price=unit_price,
        normalized_unit=normalized_unit,
        match_score=1.0,
        economic_score=unit_price,
    )
    signal = EconomicIngredientSignal(
        canonical=first.canonical_food or first.canonical_name,
        display_name=first.canonical_name,
        category=IngredientCategory.PROTEIN,
        best_local_unit_price=unit_price,
        normalized_unit=normalized_unit,
        economic_score=unit_price,
        example_products=[example],
    )
    return EconomicIngredientPool(
        ingredients=[signal],
        candidates_by_name=candidates,
        semantic_candidates_by_name=candidates,
        matched_candidates_by_name=candidates,
        search_queries_executed=0,
        products_considered=len(products),
    )


class _CountingProvider(GroceryPriceProvider):
    source_name = "fixture-own"

    def __init__(
        self,
        stores: Sequence[Store],
        products: Sequence[Product],
        *,
        fail_if_called: bool = False,
    ) -> None:
        super().__init__()
        self.stores = list(stores)
        self.products = list(products)
        self.fail_if_called = fail_if_called
        self.calls: dict[str, int] = {
            "find_stores": 0,
            "search_products": 0,
            "get_store_products": 0,
            "get_offers": 0,
        }

    def _called(self, method: str) -> None:
        self.calls[method] += 1
        if self.fail_if_called:
            raise AssertionError(f"warm request unexpectedly called provider.{method}")

    async def find_stores(self, postal_code: str) -> list[Store]:
        self._called("find_stores")
        return list(self.stores) if postal_code == POSTAL_CODE else []

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        self._called("search_products")
        allowed = set(store_ids)
        return [product for product in self.products if product.store_id in allowed]

    async def get_store_products(self, store_id: str) -> list[Product]:
        self._called("get_store_products")
        return [product for product in self.products if product.store_id == store_id]

    async def get_offers(self, store_id: str) -> list[Product]:
        self._called("get_offers")
        return []


class _StaticSelector:
    def __init__(self, pool: EconomicIngredientPool) -> None:
        self.pool = pool
        self.calls = 0

    async def select(
        self,
        provider: GroceryPriceProvider,
        stores: Sequence[Store],
    ) -> EconomicIngredientPool:
        self.calls += 1
        return self.pool


async def _build_prepared(
    *,
    products: Sequence[Product] | None = None,
    snapshot_id: str = SNAPSHOT_ID,
    memberships: Mapping[str, bool] | None = None,
) -> tuple[
    PreparedPriceUniverseManager,
    PreparedPriceUniverse,
    _CountingProvider,
    _StaticSelector,
]:
    rows = list(products or [_product("tofu", "tofu", price=25, quantity=400)])
    provider = _CountingProvider([_store(snapshot_id=snapshot_id)], rows)
    selector = _StaticSelector(_pool(rows))
    manager = PreparedPriceUniverseManager(
        build_config=PriceUniverseBuildConfig(dominance_pruning=False)
    )
    prepared = await manager.build_and_activate(
        city="Lund",
        postal_codes=[POSTAL_CODE],
        provider=provider,
        memberships=memberships or {},
        selector=selector,  # type: ignore[arg-type]
        built_at=OBSERVED_AT,
    )
    return manager, prepared, provider, selector


@pytest.mark.asyncio
async def test_startup_pricing_semantics_is_reused_by_first_plan_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    products = [
        _product("tofu", "tofu", price=25, quantity=400, index=1),
        _product("rice", "ris", price=20, quantity=1000, index=2),
        _product("carrot", "morot", price=15, quantity=1000, index=3),
    ]
    manager, prepared, _, _ = await _build_prepared(products=products)
    settings = Settings(
        price_provider="auto",
        meal_plan_strategy="optimized",
        price_universe_required=True,
        max_price_age_hours=NON_FRESHNESS_TEST_MAX_AGE_HOURS,
    )
    service = MealPlanService(
        settings,
        candidate_generator=_FixtureCandidateGenerator(),
        price_universe_manager=manager,
    )

    report = precompute_pricing_semantics(
        settings,
        prepared,
        manager=manager,
        selector=service.economic_selector,
    )
    assert report.status == "miss_filled"
    assert report.live_provider_requests == 0
    assert prepared.pricing_projection_cache.stats.misses == 2
    assert report.public_projection_prepared is True

    def unexpected_rebuild(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("first request rebuilt startup pricing semantics")

    monkeypatch.setattr(
        "app.services.meal_plan_optimizer.prepare_economic_pool_for_pricing",
        unexpected_rebuild,
    )

    async def no_legacy(*args: Any, **kwargs: Any) -> tuple[None, str]:
        return None, "fixture-no-legacy"

    monkeypatch.setattr(service, "_legacy_plan_from_pool", no_legacy)
    request = PlanRequest(
        postal_code=POSTAL_CODE,
        recipes=1,
        servings=4,
        max_stores=1,
        strategy="optimized",
        candidate_recipe_count=10,
        beam_width=5,
        optimization_iterations=0,
        min_kcal_per_serving=0,
        max_kcal_per_serving=3000,
        min_protein_g_per_serving=0,
        min_vegetable_g_per_serving=0,
    )

    await service.create_plan(request)

    assert prepared.pricing_projection_cache.stats.hits >= 1
    # Both semantic and public/date views were process-prepared; the request
    # only reads them.
    assert prepared.pricing_projection_cache.stats.misses == 2


@pytest.mark.asyncio
async def test_activated_replacement_has_an_isolated_pricing_projection_cache() -> None:
    manager, prepared, _, _ = await _build_prepared()
    settings = Settings()
    selector = MealPlanService(settings).economic_selector

    first = precompute_pricing_semantics(
        settings,
        prepared,
        manager=manager,
        selector=selector,
    )
    assert first.status == "miss_filled"
    assert prepared.pricing_projection_cache.stats.entries == 2

    replacement = PreparedPriceUniverse(
        universe=prepared.universe,
        stores=prepared.stores,
        economic_pool=prepared.economic_pool,
        source_name=prepared.source_name,
        source_diagnostics=prepared.source_diagnostics,
        oldest_observed_at=prepared.oldest_observed_at,
    )
    manager.activate(replacement)

    assert replacement.pricing_projection_cache is not prepared.pricing_projection_cache
    assert replacement.pricing_projection_cache.stats.entries == 0
    second = precompute_pricing_semantics(
        settings,
        replacement,
        manager=manager,
        selector=selector,
    )

    assert second.status == "miss_filled"
    assert replacement.pricing_projection_cache.stats.entries == 2
    assert prepared.pricing_projection_cache.stats.entries == 2


@pytest.mark.asyncio
async def test_concurrent_readers_observe_only_complete_prepared_runtime_swaps() -> None:
    manager, active, _, _ = await _build_prepared()
    replacement_store = active.stores[0].model_copy(update={"name": "Replacement"})
    replacement = PreparedPriceUniverse(
        universe=active.universe,
        stores=(replacement_store,),
        economic_pool=active.economic_pool,
        source_name="replacement",
        source_diagnostics=active.source_diagnostics,
        oldest_observed_at=active.oldest_observed_at,
    )
    expected = {
        (active.source_name, active.stores[0].name),
        (replacement.source_name, replacement.stores[0].name),
    }
    start = Barrier(4)
    observations: list[tuple[str, str] | None] = []

    def read_active() -> None:
        start.wait()
        for _ in range(2_000):
            current = manager.get_active(active.universe.key.scope_id)
            observations.append(
                None if current is None else (current.source_name, current.stores[0].name)
            )

    readers = [Thread(target=read_active) for _ in range(3)]
    for reader in readers:
        reader.start()
    start.wait()
    for index in range(2_000):
        manager.activate(replacement if index % 2 else active)
    for reader in readers:
        reader.join()

    assert len(observations) == 6_000
    assert set(observations) <= expected


@pytest.mark.asyncio
async def test_prebuild_is_the_only_provider_io_and_request_reads_are_local() -> None:
    manager, prepared, provider, selector = await _build_prepared()

    assert provider.calls == {
        "find_stores": 1,
        "search_products": 0,
        "get_store_products": 1,
        "get_offers": 0,
    }
    assert selector.calls == 1
    calls_after_prebuild = dict(provider.calls)

    assert manager.get_for_request(POSTAL_CODE, normalized_memberships({})) is prepared
    status = manager.status("city:lund")

    assert provider.calls == calls_after_prebuild
    assert status["active"] is True
    assert status["universe_id"] == prepared.universe.universe_id
    assert status["snapshot_ids"] == (SNAPSHOT_ID,)
    assert status["product_count"] == 1


@pytest.mark.asyncio
async def test_request_lookup_uses_public_artifact_only_without_member_evidence() -> None:
    manager, prepared, _, _ = await _build_prepared(memberships={"hemkop": False})

    assert manager.get_for_request(POSTAL_CODE, {"hemkop": False}) is prepared
    assert manager.get_for_request(POSTAL_CODE, {"hemkop": True}) is prepared
    assert manager.get_for_request("21120", {"hemkop": False}) is None


@pytest.mark.asyncio
async def test_request_lookup_reuses_shared_artifact_with_member_evidence() -> None:
    manager, prepared, _, _ = await _build_prepared(memberships={"hemkop": False})
    product = prepared.universe.products[0].model_copy(
        update={
            "member_price": 8.0,
            "offers": [
                OfferMetadata(
                    kind=OfferKind.MEMBER,
                    description="Hemköp Klubb",
                    price=8.0,
                    member_program="Hemköp Klubb",
                )
            ],
        }
    )
    restricted = replace(
        prepared,
        universe=prepared.universe.model_copy(update={"products": [product]}),
    )
    manager.activate(restricted)

    assert manager.get_for_request(POSTAL_CODE, {"hemkop": False}) is restricted
    assert manager.get_for_request(POSTAL_CODE, {"hemkop": True}) is restricted


@pytest.mark.asyncio
async def test_prepared_artifact_round_trip_is_restart_ready_and_fails_closed(
    tmp_path: Path,
) -> None:
    _, prepared, _, _ = await _build_prepared()
    destination = tmp_path / "lund-price-universe.json"

    PreparedPriceUniverseManager.write_artifact(prepared, destination)
    restarted = PreparedPriceUniverseManager()
    with activate_performance_trace() as trace:
        restored = restarted.load_file_and_activate(destination)

    assert restored.universe.universe_id == prepared.universe.universe_id
    assert restored.economic_pool == prepared.economic_pool
    assert restarted.get_for_request(POSTAL_CODE, normalized_memberships({})) is restored
    assert not destination.with_name(destination.name + ".tmp").exists()
    load_metrics = trace.snapshot().span_statistics
    assert load_metrics["price_universe_file_read"]["calls"] == 1
    assert load_metrics["price_universe_parse_and_validate"]["calls"] == 1
    assert load_metrics["price_universe_restore_indexes"]["calls"] == 1
    assert load_metrics["price_universe_atomic_activation"]["calls"] == 1

    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["canonical_candidates"][0]["candidates"][0]["source_provenance"][
        "source_snapshot_id"
    ] = "tampered-snapshot"
    with pytest.raises(ValueError, match="snapshot provenance"):
        PreparedPriceUniverseManager().load_and_activate(json.dumps(payload))


@pytest.mark.asyncio
async def test_prepared_artifact_enospc_preserves_previous_restart_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, prepared, _, _ = await _build_prepared()
    destination = tmp_path / "lund-price-universe.json"
    destination.write_bytes(b"previous-restart-cache")

    def disk_full(_descriptor: int) -> None:
        raise OSError(errno.ENOSPC, "fault injection")

    monkeypatch.setattr(durable_files.os, "fsync", disk_full)

    with pytest.raises(OSError) as error:
        PreparedPriceUniverseManager.write_artifact(prepared, destination)

    assert error.value.errno == errno.ENOSPC
    assert destination.read_bytes() == b"previous-restart-cache"
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.asyncio
async def test_failed_rebuild_leaves_the_previous_universe_active() -> None:
    manager, active, _, _ = await _build_prepared()
    changed_store = _store(snapshot_id="snapshot-broken")
    broken_provider = _CountingProvider([changed_store], [])
    selector = _StaticSelector(active.economic_pool)

    with pytest.raises(ValueError, match="provider returned no products"):
        await manager.build_and_activate(
            city="Lund",
            postal_codes=[POSTAL_CODE],
            provider=broken_provider,
            memberships={},
            selector=selector,  # type: ignore[arg-type]
            built_at=OBSERVED_AT + timedelta(hours=1),
        )

    assert manager.get_active("city:lund") is active
    assert manager.status("city:lund")["universe_id"] == active.universe.universe_id


@pytest.mark.asyncio
async def test_local_provider_prefilter_is_bounded_and_context_scoped() -> None:
    second_store_id = "own:hemkop:9999"
    products = [
        _product(
            f"rice-a-{index}",
            "ris",
            price=10 + index,
            quantity=500 + index * 100,
            index=index,
        )
        for index in range(6)
    ] + [
        _product(
            f"rice-b-{index}",
            "ris",
            price=12 + index,
            quantity=500 + index * 100,
            store_id=second_store_id,
            index=100 + index,
        )
        for index in range(6)
    ]
    key = PriceUniverseKey.create(
        city="Lund",
        postal_codes=[POSTAL_CODE],
        snapshot_ids=[SNAPSHOT_ID],
        memberships=normalized_memberships({}),
        source_strategy_version="fixture-strategy",
        normalizer_version="fixture-normalizer",
        taxonomy_version="fixture-taxonomy",
    )
    universe = PriceUniverseBuilder(
        PriceUniverseBuildConfig(
            dominance_pruning=False,
            max_products_per_canonical_per_context=2,
            max_products_per_canonical_global=3,
        )
    ).build(key, products, built_at=OBSERVED_AT)
    provider = LocalPriceUniverseProvider(
        universe,
        [_store(), _store(store_id=second_store_id)],
    )

    both = await provider.search_products("ris", [STORE_ID, second_store_id, "unknown"])
    one = await provider.search_products("ris", [STORE_ID])

    assert 0 < len(both) <= 3
    assert len(one) <= 2
    assert {product.store_id for product in one} == {STORE_ID}
    assert await provider.search_products("definitely absent", [STORE_ID]) == []
    assert len(await provider.get_store_products(STORE_ID)) == 6
    assert await provider.get_store_products("unknown") == []


def test_package_and_basket_caches_hit_on_normalized_warm_keys() -> None:
    product = _product("rice", "ris", price=20, quantity=1000)
    key = PriceUniverseKey.create(
        city="Lund",
        postal_codes=[POSTAL_CODE],
        snapshot_ids=[SNAPSHOT_ID],
        memberships=normalized_memberships({}),
        source_strategy_version="fixture-strategy",
        normalizer_version="fixture-normalizer",
        taxonomy_version="fixture-taxonomy",
    )
    universe = PriceUniverseBuilder().build(key, [product], built_at=OBSERVED_AT)
    candidate = _candidate(product)
    calculator = BasketCalculator()
    package_cache = PackageCostCache()
    package_factory_calls = 0

    def package_factory() -> Any:
        nonlocal package_factory_calls
        package_factory_calls += 1
        return calculator.quote_item(
            NormalizedIngredient(
                canonical_name="ris",
                required_quantity=1000,
                unit="g",
            ),
            candidate,
        )

    first_quote = package_cache.get_or_compute(
        universe,
        candidate,
        required_quantity=1,
        required_unit="kg",
        calculator_version="fixture-v1",
        factory=package_factory,
    )
    second_quote = package_cache.get_or_compute(
        universe,
        candidate,
        required_quantity=1000,
        required_unit="g",
        calculator_version="fixture-v1",
        factory=package_factory,
    )

    basket_cache = BasketResultCache()
    basket_factory_calls = 0

    def basket_factory() -> OptimizedBasket:
        nonlocal basket_factory_calls
        basket_factory_calls += 1
        return OptimizedBasket(total=0, stores=[], max_stores=1)

    first_basket = basket_cache.get_or_compute(
        universe,
        [("ris", 1, "kg")],
        allowed_context_ids=[STORE_ID],
        max_stores=1,
        optimizer_version="fixture-v1",
        factory=basket_factory,
    )
    second_basket = basket_cache.get_or_compute(
        universe,
        [("ris", 1000, "g")],
        allowed_context_ids=[STORE_ID],
        max_stores=1,
        optimizer_version="fixture-v1",
        factory=basket_factory,
    )

    assert first_quote is second_quote
    assert package_factory_calls == 1
    assert package_cache.stats.model_dump() == {
        "hits": 1,
        "misses": 1,
        "evictions": 0,
        "entries": 1,
    }
    assert first_basket is second_basket
    assert basket_factory_calls == 1
    assert basket_cache.stats.hits == 1
    assert basket_cache.stats.misses == 1


def test_prepared_status_marks_oldest_snapshot_stale() -> None:
    product = _product("rice", "ris", price=20, quantity=1000)
    key = PriceUniverseKey.create(
        city="Lund",
        postal_codes=[POSTAL_CODE],
        snapshot_ids=[SNAPSHOT_ID],
        memberships=normalized_memberships({}),
        source_strategy_version="fixture-strategy",
        normalizer_version="fixture-normalizer",
        taxonomy_version="fixture-taxonomy",
    )
    universe = PriceUniverseBuilder().build(key, [product], built_at=OBSERVED_AT)
    prepared = PreparedPriceUniverse(
        universe=universe,
        stores=(_store(),),
        economic_pool=_pool([product]),
        source_name="fixture-own",
        oldest_observed_at=OBSERVED_AT,
    )

    status = prepared.status(
        now=OBSERVED_AT + timedelta(hours=49),
        warning_age_hours=36,
        stale_age_hours=48,
        cache_state="warm",
    )

    assert status.status == "stale"
    assert status.oldest_price_age_hours == 49
    assert status.cache_state == "warm"
    assert status.live_chain_requests == 0


def test_prepared_request_view_excludes_only_stale_context_and_reports_degraded() -> None:
    fresh_store_id = "own:willys:100"
    stale_store_id = "primat:coop:730400"
    evaluated_at = OBSERVED_AT + timedelta(hours=50)
    fresh_observed_at = evaluated_at - timedelta(hours=2)
    fresh = _product(
        "fresh-rice",
        "ris",
        price=19,
        quantity=1000,
        store_id=fresh_store_id,
        snapshot_id="snapshot-willys-fresh",
        index=20,
        observed_at=fresh_observed_at,
    )
    stale = _product(
        "stale-pasta",
        "pasta",
        price=10,
        quantity=500,
        store_id=stale_store_id,
        snapshot_id="snapshot-coop-lkg",
        index=21,
        observed_at=OBSERVED_AT,
    )
    key = PriceUniverseKey.create(
        city="Lund",
        postal_codes=[POSTAL_CODE],
        snapshot_ids=["snapshot-willys-fresh", "snapshot-coop-lkg"],
        memberships=normalized_memberships({}),
        source_strategy_version="fixture-strategy",
        normalizer_version="fixture-normalizer",
        taxonomy_version="fixture-taxonomy",
    )
    universe = PriceUniverseBuilder().build(key, [fresh, stale], built_at=evaluated_at)
    prepared = PreparedPriceUniverse(
        universe=universe,
        stores=(
            _store(
                snapshot_id="snapshot-willys-fresh",
                store_id=fresh_store_id,
                observed_at=fresh_observed_at,
            ),
            _store(
                snapshot_id="snapshot-coop-lkg",
                store_id=stale_store_id,
                observed_at=OBSERVED_AT,
            ),
        ),
        economic_pool=_pool([fresh, stale]),
        source_name="fixture-federated",
        oldest_observed_at=OBSERVED_AT,
    )

    status = prepared.status(
        now=evaluated_at,
        warning_age_hours=36,
        stale_age_hours=48,
    )
    view = prepared.request_view(now=evaluated_at, stale_age_hours=48)

    assert status.status == "degraded"
    assert status.usable_context_count == 1
    assert status.excluded_stale_context_count == 1
    assert status.excluded_stale_context_ids == (stale_store_id,)
    assert status.oldest_price_age_hours == 50
    assert status.oldest_usable_price_age_hours == 2
    assert [store.store_id for store in view.stores] == [fresh_store_id]
    assert view.usable_context_ids == (fresh_store_id,)
    assert view.excluded_stale_context_ids == (stale_store_id,)
    assert {
        candidate.store_id
        for candidates in view.economic_pool.matched_candidates_by_name.values()
        for candidate in candidates
    } == {fresh_store_id}
    assert "pasta" not in view.economic_pool.candidates_by_name


class _FixtureCandidateGenerator(RecipeCandidateGenerator):
    def generate_candidates(
        self,
        economic_ingredients: Any,
        count: int = 80,
        servings: int = 4,
    ) -> list[Recipe]:
        pantry = (
            ("salt", "g"),
            ("black_pepper", "g"),
            ("water", "ml"),
            ("neutral_cooking_oil", "ml"),
        )
        recipes: list[Recipe] = []
        for index in range(count):
            extras = [
                RecipeIngredient(
                    name=name,
                    canonical_name=name,
                    quantity=5,
                    unit=unit,  # type: ignore[arg-type]
                )
                for bit, (name, unit) in enumerate(pantry)
                if index & (1 << bit)
            ]
            recipes.append(
                Recipe(
                    name=f"Tofuratt {index}",
                    servings=servings,
                    ingredients=[
                        RecipeIngredient(
                            name="tofu",
                            canonical_name="tofu",
                            quantity=400,
                            unit="g",
                        ),
                        RecipeIngredient(
                            name="ris",
                            canonical_name="ris",
                            quantity=320,
                            unit="g",
                        ),
                        RecipeIngredient(
                            name="morot",
                            canonical_name="morot",
                            quantity=400,
                            unit="g",
                        ),
                        *extras,
                    ],
                    instructions=["Tillaga och servera."],
                )
            )
        return recipes


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["balanced", "cheapest"])
async def test_public_five_dinner_own_only_uses_local_provider_without_live_configuration(
    monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    """The deployed OWN-only release has an artifact, but no live OWN API URL."""
    manager, prepared, _, _ = await _build_prepared(
        products=[_product("rice", "ris", price=20, quantity=1000)],
    )
    service = MealPlanService(
        Settings(price_provider="auto", own_sources_only=True,
                 own_grocery_base_url=None, price_universe_required=True),
        price_universe_manager=manager,
    )
    request = PlanRequest(
        postal_code="22350", recipes=5, servings=2, max_stores=3,
        purchase_planning_mode="exact", diversity_mode=mode,
        diet_preference="mixed", strategy="optimized",
        memberships=["ICA_STAMMIS", "COOP_MEMBER", "HEMKOP_MEMBER",
                     "LIDL_PLUS", "WILLYS_PLUS", "CITY_GROSS_PRIO"],
    )
    original = request.model_dump()
    marker = object()

    async def inspect_builder(actual, provider):
        assert actual.model_dump() == original
        assert isinstance(provider, LocalPriceUniverseProvider)
        assert provider.universe is prepared.universe
        return marker

    monkeypatch.setattr(service, "_build_optimized_with_provider", inspect_builder)
    assert await service.create_plan(request) is marker


@pytest.mark.asyncio
async def test_meal_plan_uses_prepared_universe_without_provider_io_and_keeps_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    products = [
        _product("tofu", "tofu", price=25, quantity=400, index=1),
        _product("rice", "ris", price=20, quantity=1000, index=2),
        _product("carrot", "morot", price=15, quantity=1000, index=3),
    ]
    manager, prepared, _, _ = await _build_prepared(products=products)
    warm_provider = _CountingProvider([], [], fail_if_called=True)
    monkeypatch.setattr(
        "app.services.meal_plan_optimizer.create_price_provider",
        lambda *args, **kwargs: warm_provider,
    )
    service = MealPlanService(
        Settings(
            price_provider="auto",
            meal_plan_strategy="optimized",
            price_universe_required=True,
            max_price_age_hours=NON_FRESHNESS_TEST_MAX_AGE_HOURS,
        ),
        candidate_generator=_FixtureCandidateGenerator(),
        price_universe_manager=manager,
    )
    reload_attempts: list[Path] = []

    def unexpected_reload(path: Path) -> PreparedPriceUniverse:
        reload_attempts.append(path)
        raise AssertionError("normal planner request reloaded the PriceUniverse")

    monkeypatch.setattr(manager, "load_file_and_activate", unexpected_reload)

    async def no_legacy(*args: Any, **kwargs: Any) -> tuple[None, str]:
        return None, "fixture-no-legacy"

    monkeypatch.setattr(service, "_legacy_plan_from_pool", no_legacy)
    request = PlanRequest(
        postal_code=POSTAL_CODE,
        recipes=1,
        servings=4,
        max_stores=1,
        strategy="optimized",
        candidate_recipe_count=10,
        beam_width=5,
        optimization_iterations=0,
        min_kcal_per_serving=0,
        max_kcal_per_serving=3000,
        min_protein_g_per_serving=0,
        min_vegetable_g_per_serving=0,
    )

    plan = await service.create_plan(request)
    warm_plan = await service.create_plan(request)

    assert warm_provider.calls == {
        "find_stores": 0,
        "search_products": 0,
        "get_store_products": 0,
        "get_offers": 0,
    }
    assert plan.data_source == "fixture-own"
    assert warm_plan.optimized_basket == plan.optimized_basket
    assert plan.data is not None
    assert plan.data.price_universe_id == prepared.universe.universe_id
    assert plan.data.snapshot_ids == (SNAPSHOT_ID,)
    assert plan.data.product_count == 3
    assert plan.data.cache_state == "warm"
    assert plan.data.live_chain_requests == 0
    selected = [item for group in plan.optimized_basket.stores for item in group.items]
    assert selected
    assert all(item.source_provenance is not None for item in selected)
    assert {item.source_provenance.source_snapshot_id for item in selected} == {SNAPSHOT_ID}
    assert {item.source_provenance.source_provider for item in selected} == {"own"}
    assert prepared.basket_cache.stats.hits > 0
    # Independent initial and Balanced-conditioned searches both reuse results.
    assert prepared.menu_search_cache.stats.hits == 2
    assert prepared.menu_search_cache.stats.misses == 2
    assert reload_attempts == []


@pytest.mark.asyncio
async def test_menu_search_cache_is_shared_by_modes_but_isolates_real_policy_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    products = [
        _product("tofu", "tofu", price=25, quantity=400, index=1),
        _product("rice", "ris", price=20, quantity=1000, index=2),
        _product("carrot", "morot", price=15, quantity=1000, index=3),
    ]
    manager, prepared, _, _ = await _build_prepared(products=products)
    warm_provider = _CountingProvider([], [], fail_if_called=True)
    monkeypatch.setattr(
        "app.services.meal_plan_optimizer.create_price_provider",
        lambda *args, **kwargs: warm_provider,
    )
    service = MealPlanService(
        Settings(
            price_provider="auto",
            meal_plan_strategy="optimized",
            price_universe_required=True,
            max_price_age_hours=NON_FRESHNESS_TEST_MAX_AGE_HOURS,
        ),
        candidate_generator=_FixtureCandidateGenerator(),
        price_universe_manager=manager,
    )

    async def no_legacy(*args: Any, **kwargs: Any) -> tuple[None, str]:
        return None, "fixture-no-legacy"

    monkeypatch.setattr(service, "_legacy_plan_from_pool", no_legacy)
    shared = {
        "postal_code": POSTAL_CODE,
        "recipes": 1,
        "servings": 4,
        "max_stores": 1,
        "strategy": "optimized",
        "candidate_recipe_count": 10,
        "beam_width": 5,
        "optimization_iterations": 0,
        "min_kcal_per_serving": 0,
        "max_kcal_per_serving": 3000,
        "min_protein_g_per_serving": 0,
        "min_vegetable_g_per_serving": 0,
    }

    mode_plans = [
        await service.create_plan(PlanRequest(**shared, diversity_mode=mode))
        for mode in DiversityMode
    ]

    shared_stats = prepared.menu_search_cache.stats
    assert shared_stats.misses == 2
    assert shared_stats.hits == 4
    assert shared_stats.entries == 2
    assert [plan.diversity_mode for plan in mode_plans] == list(DiversityMode)

    override_request = PlanRequest(
        **shared,
        diversity_mode=DiversityMode.BALANCED,
        max_same_recipe_family=1,
    )
    override_plan = await service.create_plan(override_request)
    repeated_override = await service.create_plan(override_request)

    isolated_stats = prepared.menu_search_cache.stats
    assert isolated_stats.misses == 4
    assert isolated_stats.hits == 6
    assert isolated_stats.entries == 4
    assert warm_provider.calls == {
        "find_stores": 0,
        "search_products": 0,
        "get_store_products": 0,
        "get_offers": 0,
    }

    for plan in [*mode_plans, override_plan, repeated_override]:
        assert plan.data is not None
        assert plan.data.price_universe_id == prepared.universe.universe_id
        assert plan.data.snapshot_ids == (SNAPSHOT_ID,)
        assert plan.data.live_chain_requests == 0
        assert plan.quality is not None
        selected_option = plan.plans[plan.diversity_mode]
        # The deliberately narrow one-recipe fixture can miss structural targets;
        # cache reuse must preserve that limitation, never manufacture a PASS.
        assert plan.quality.status.value == (
            "PASS" if selected_option.variation_target_met else "FAIL"
        )
        if not selected_option.variation_target_met:
            assert selected_option.variation_limitations
        assert plan.quality.basket_audit.passed is True
        selected = [item for group in plan.optimized_basket.stores for item in group.items]
        assert selected
        assert all(item.source_provenance is not None for item in selected)
        assert {item.source_provenance.source_snapshot_id for item in selected} == {SNAPSHOT_ID}
        assert {item.source_provenance.source_provider for item in selected} == {"own"}


@pytest.mark.asyncio
async def test_activation_requires_every_configured_fresh_context(tmp_path):
    from grocery_data.app.services.prepared_universe_activation import (
        validate_backend_prepared_universe_artifact,
    )

    _manager, prepared, _provider, _selector = await _build_prepared()
    output = tmp_path / "candidate.json"
    PreparedPriceUniverseManager.write_artifact(prepared, output)
    payload = json.loads(output.read_bytes())
    with pytest.raises(ValueError, match="lacks required usable contexts.*missing-store"):
        validate_backend_prepared_universe_artifact(
            payload, "Lund", required_context_ids=("missing-store",), max_price_age_hours=1_000_000
        )
    context = prepared._context_oldest_observed_at[0][0]
    with pytest.raises(ValueError, match="lacks required usable contexts"):
        validate_backend_prepared_universe_artifact(
            payload, "Lund", required_context_ids=(context,)
        )


@pytest.mark.asyncio
async def test_runtime_readiness_warns_at_36_and_requires_all_contexts_at_48(monkeypatch):
    from app.services import beta_observability as ops

    _manager, prepared, _provider, _selector = await _build_prepared()
    context = prepared._context_oldest_observed_at[0][0]
    settings = Settings(
        price_universe_required=True, price_universe_required_context_ids=(context,)
    )
    monkeypatch.setattr(ops.GLOBAL_PREPARED_PRICE_UNIVERSES, "get_active", lambda scope: prepared)
    fresh = ops.active_price_status(settings, now=OBSERVED_AT + timedelta(hours=35.99))
    aging = ops.active_price_status(settings, now=OBSERVED_AT + timedelta(hours=36))
    stale = ops.active_price_status(settings, now=OBSERVED_AT + timedelta(hours=48))
    assert fresh["required_contexts_usable"] and not fresh["requires_attention"]
    assert aging["required_contexts_usable"] and aging["requires_attention"]
    assert not stale["required_contexts_usable"] and stale["requires_attention"]
    assert stale["missing_required_context_ids"] == [context]


def test_campaign_survives_48h_but_expires_locally_without_rebuild():
    from datetime import date

    from grocery_data.app.domain.campaign_validity import CampaignEvidence
    observed = datetime(2026,9,14,8,tzinfo=UTC)
    p = _product("campaign-rice", "ris", price=20, quantity=1000, observed_at=observed)
    proof = CampaignEvidence(store_external_id='official', offer_id='campaign-rice',
        source_reference='raw:retained', observed_current_at=observed, checked_at=observed)
    p = p.model_copy(update={'chain':'ica','price':None,'coverage':'offers_only',
        'offers':[OfferMetadata(kind=OfferKind.CAMPAIGN,description="fixture public campaign",price=20,valid_to=date(2026,9,20),campaign_evidence=proof)],
        'source_provenance':p.source_provenance.model_copy(update={'chain':'ica',
            'source_channel':'offers','provider_store_id':'official','coverage':'offers_only'})})
    key = PriceUniverseKey.create(city='Lund',postal_codes=[POSTAL_CODE],snapshot_ids=[SNAPSHOT_ID],
        memberships=normalized_memberships({}), source_strategy_version='fixture',
        normalizer_version='fixture',taxonomy_version='fixture')
    universe=PriceUniverseBuilder().build(key,[p],built_at=observed)
    prepared=PreparedPriceUniverse(universe=universe,stores=(_store(observed_at=observed),),
        economic_pool=_pool([p]),source_name='fixture',oldest_observed_at=observed)
    before=datetime(2026,9,20,21,59,tzinfo=UTC)
    after=datetime(2026,9,20,22,0,tzinfo=UTC)
    assert prepared.request_view(now=before).usable_context_ids == (STORE_ID,)
    assert prepared.request_view(now=after).usable_context_ids == ()
    assert not p.offers[0].is_active(date(2026,9,13))
    assert p.offers[0].valid_from is None
    assert p.source_provenance.source_observed_at == observed
    # A wrong-store proof does not get the age exemption.
    bad=p.model_copy(update={'source_provenance':p.source_provenance.model_copy(update={'provider_store_id':'other'})})
    broken=PreparedPriceUniverse(universe=PriceUniverseBuilder().build(key,[bad],built_at=observed),
        stores=(_store(observed_at=observed),),economic_pool=_pool([bad]),source_name='fixture',oldest_observed_at=observed)
    assert not broken.request_view(now=before).usable_context_ids

@pytest.mark.parametrize('cache_name', ['MenuSearchResultCache', 'PricingProjectionCache'])
def test_cache_status_stays_available_during_computation(cache_name):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.services import price_universe_runtime
    cache = getattr(price_universe_runtime, cache_name)()
    entered, release = Event(), Event()
    value = object()
    def slow():
        entered.set()
        assert release.wait(5)
        return value
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(cache.get_or_compute, 'same', slow)
        try:
            assert entered.wait(2)
            status = pool.submit(lambda: cache.stats).result(timeout=1)
            assert status.misses == 1 and status.entries == 0
            second = pool.submit(cache.get_or_compute, 'same', lambda: pytest.fail('duplicate computation'))
        finally:
            release.set()
        assert first.result(timeout=2) is second.result(timeout=2) is value
    assert cache.stats.hits == 1 and cache.stats.entries == 1
