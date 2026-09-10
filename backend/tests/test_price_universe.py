from __future__ import annotations

from datetime import UTC, datetime
from threading import Barrier, Thread

import pytest
from app.models.basket import OptimizedBasket
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    Product,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.provenance import SourceProvenance
from app.services.basket_calculator import BasketCalculator
from app.services.performance_trace import activate_performance_trace
from app.services.price_universe import (
    BasketResultCache,
    IneligibleMemberPriceError,
    PackageCostCache,
    PriceUniverse,
    PriceUniverseBuildConfig,
    PriceUniverseBuilder,
    PriceUniverseError,
    PriceUniverseKey,
    PriceUniverseManager,
    PriceUniverseValidationError,
    SemanticCandidateCache,
    canonical_requirement_hash,
    canonical_requirement_items,
)

NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


def _key(
    *snapshot_ids: str,
    memberships: dict[str, bool] | None = None,
    taxonomy_version: str = "taxonomy-v1",
) -> PriceUniverseKey:
    return PriceUniverseKey.create(
        city=" Lund ",
        postal_codes=("223 50", "22350"),
        snapshot_ids=snapshot_ids or ("snapshot-1",),
        memberships=memberships or {"ICA": False, "HEMKOP": False},
        source_strategy_version="strategy-v3",
        normalizer_version="normalizer-v7",
        taxonomy_version=taxonomy_version,
    )


def _offer(
    *,
    kind: OfferKind = OfferKind.CAMPAIGN,
    price: float = 9,
    required_packages: int = 1,
    max_quantity: int | None = None,
) -> OfferMetadata:
    if required_packages > 1:
        kind = OfferKind.MULTIPACK
    return OfferMetadata(
        kind=kind,
        description=f"{kind.value}-{required_packages}-{max_quantity}",
        price=price,
        required_packages=required_packages,
        max_quantity=max_quantity,
        member_program="ica" if kind == OfferKind.MEMBER else None,
    )


def _product(
    product_id: str,
    *,
    store_id: str = "ica:1",
    chain: str = "ica",
    canonical: str | None = "ris",
    name: str = "Basmatiris",
    brand: str | None = "Test",
    price: float = 20,
    effective_price: float | None = None,
    package_quantity: float = 1000,
    package_unit: str = "g",
    sale_model: SaleModel = SaleModel.FIXED_PACKAGE,
    offers: list[OfferMetadata] | None = None,
    member_price: float | None = None,
    gtin: str | None = None,
    snapshot_id: str = "snapshot-1",
    with_provenance: bool = True,
) -> Product:
    effective = price if effective_price is None else effective_price
    provenance = (
        SourceProvenance(
            source_provider="primat" if chain == "ica" else "own",
            source_channel="catalog",
            source_snapshot_id=snapshot_id,
            source_observed_at=NOW,
            chain=chain,
            store_id=store_id,
            store_name=store_id,
            price_context="online_store",
            coverage="full_catalog",
            semantic_confidence="high",
            quantity_confidence="exact",
        )
        if with_provenance
        else None
    )
    return Product(
        product_id=product_id,
        name=name,
        canonical_name=canonical or name.casefold(),
        canonical_food=canonical,
        category="Skafferi",
        store_id=store_id,
        store_name=store_id,
        brand=brand,
        chain=chain,
        gtin=gtin,
        price=price,
        effective_price=effective,
        member_price=member_price,
        sale_price=effective,
        sale_model=sale_model,
        package_quantity=package_quantity,
        package_unit=package_unit,
        usable_quantity=package_quantity,
        usable_unit=package_unit,
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        product_role="grain",
        product_form="dry",
        price_context_type="online_store",
        coverage="full_catalog",
        offers=offers or [],
        source_provenance=provenance,
    )


def _universe(
    products: list[Product] | None = None,
    *,
    key: PriceUniverseKey | None = None,
    config: PriceUniverseBuildConfig | None = None,
) -> PriceUniverse:
    return PriceUniverseBuilder(config).build(
        key or _key("snapshot-1"),
        products or [_product("rice")],
        built_at=NOW,
    )


def _candidate(product: Product) -> ProductCandidate:
    return ProductCandidate.from_product(product, match_score=1).model_copy(
        update={"semantic_evidence": ["fixture"]}
    )


def test_key_identity_is_order_independent_and_covers_every_version_input() -> None:
    left = PriceUniverseKey.create(
        city="LUND",
        postal_codes=("223 50", "22221"),
        snapshot_ids=("b", "a", "a"),
        memberships={"ICA": False, "Hemkop": True},
        source_strategy_version="s1",
        normalizer_version="n1",
        taxonomy_version="t1",
    )
    right = PriceUniverseKey.create(
        city="lund",
        postal_codes=("22221", "22350"),
        snapshot_ids=("a", "b"),
        memberships={"hemkop": True, "ica": False},
        source_strategy_version="s1",
        normalizer_version="n1",
        taxonomy_version="t1",
    )

    assert left == right
    assert left.universe_id == right.universe_id
    assert left.snapshot_ids == ("a", "b")
    assert left.postal_codes == ("22221", "22350")
    assert left.scope_id == "city:lund"
    assert left.geographic_scope_id == "city:lund|postal:22221,22350"
    assert left.scope == left.scope_id
    assert left.universe_id != left.model_copy(update={"taxonomy_version": "t2"}).universe_id
    assert left.universe_id != left.model_copy(update={"snapshot_ids": ("c",)}).universe_id


def test_builder_creates_canonical_and_secondary_indexes_and_availability_bitsets() -> None:
    products = [
        _product("rice-a", store_id="ica:1", gtin="7312345678901"),
        _product("rice-b", store_id="hemkop:2", chain="hemkop", snapshot_id="snapshot-2"),
        _product(
            "beans",
            store_id="hemkop:2",
            chain="hemkop",
            canonical="bönor",
            name="Vita bönor",
            snapshot_id="snapshot-2",
        ),
        _product("unknown", canonical=None, name="Mystery food").model_copy(
            update={"canonical_food": None}
        ),
    ]
    universe = _universe(products, key=_key("snapshot-2", "snapshot-1"))

    assert {row.product_id for row in universe.products_for_canonical("basmatiris")} == {
        "rice-a",
        "rice-b",
    }
    assert universe.products_for_gtin("7312345678901")[0].product_id == "rice-a"
    assert {row.product_id for row in universe.products_for_context("hemkop:2")} == {
        "beans",
        "rice-b",
    }
    assert universe.contexts_for_canonical("ris") == ("hemkop:2", "ica:1")
    assert universe.semantic_prefilter("mystery food")[0].product_id == "unknown"
    assert universe.stats.raw_products == 4
    assert universe.stats.eligible_products == 3
    assert universe.stats.products_without_canonical == 1
    assert universe.stats.post_pruning_products == universe.stats.canonical_mappings
    assert set(universe.by_canonical) >= {"ris", "bönor"}


def test_semantic_prefilter_combines_structured_candidates_with_legacy_lexical_rows() -> None:
    structured = _product("structured", canonical="ris", name="Basmatiris")
    legacy = _product("legacy", canonical=None, name="Ris deluxe").model_copy(
        update={"canonical_food": None}
    )
    irrelevant = _product("other", canonical=None, name="Pasta deluxe").model_copy(
        update={"canonical_food": None}
    )
    universe = _universe([structured, legacy, irrelevant])

    assert {row.product_id for row in universe.semantic_prefilter("ris")} == {
        "structured",
        "legacy",
    }


def test_serialized_universe_round_trip_preserves_products_and_provenance() -> None:
    universe = _universe()

    restored = PriceUniverse.from_json(universe.to_json())

    assert restored.universe_id == universe.universe_id
    assert restored.products_digest == universe.products_digest
    assert restored.products == universe.products
    assert restored.products[0].source_provenance == universe.products[0].source_provenance
    assert restored.products_for_canonical("ris")[0].product_id == "rice"


def test_build_fails_closed_for_missing_mismatched_or_wrong_snapshot_provenance() -> None:
    with pytest.raises(PriceUniverseError, match="missing source provenance"):
        _universe([_product("missing", with_provenance=False)])
    mismatched = _product("mismatch").model_copy(
        update={
            "source_provenance": _product("source").source_provenance.model_copy(
                update={"store_id": "ica:other"}
            )
        }
    )
    with pytest.raises(PriceUniverseError, match="context disagrees"):
        _universe([mismatched])
    with pytest.raises(PriceUniverseError, match="outside the universe key"):
        _universe([_product("wrong-snapshot", snapshot_id="other")])


def test_exact_economic_duplicate_is_dominated_but_different_names_are_conservative() -> None:
    cheap = _product("cheap", price=20, name="Basmatiris 1 kg")
    expensive = _product("expensive", price=25, name="Basmatiris 1 kg")
    meaningful_alternative = _product("jasmine", price=30, name="Jasminris 1 kg")

    universe = _universe([expensive, meaningful_alternative, cheap])

    assert {row.product_id for row in universe.products_for_canonical("ris")} == {
        "cheap",
        "jasmine",
    }
    assert universe.stats.dominance_pruned == 1


def test_dominance_never_merges_different_promotion_conditions_or_caps() -> None:
    products = [
        _product(
            "two-for",
            price=20,
            offers=[_offer(price=30, required_packages=2)],
        ),
        _product(
            "three-for",
            price=20,
            offers=[_offer(price=40, required_packages=3)],
        ),
        _product(
            "capped",
            price=20,
            offers=[_offer(price=10, max_quantity=1)],
        ),
        _product(
            "uncapped",
            price=20,
            offers=[_offer(price=10, max_quantity=None)],
        ),
    ]

    universe = _universe(products)

    assert {row.product_id for row in universe.products_for_canonical("ris")} == {
        "two-for",
        "three-for",
        "capped",
        "uncapped",
    }
    assert universe.stats.dominance_pruned == 0


def test_stratified_top_k_keeps_context_package_and_promotion_diversity() -> None:
    products = [
        _product("s1-500", store_id="ica:1", package_quantity=500, price=12),
        _product("s1-1000", store_id="ica:1", package_quantity=1000, price=20),
        _product(
            "s1-promo",
            store_id="ica:1",
            package_quantity=1000,
            price=22,
            offers=[_offer(price=30, required_packages=2)],
        ),
        _product("s2-500", store_id="ica:2", package_quantity=500, price=13),
        _product("s2-1000", store_id="ica:2", package_quantity=1000, price=21),
    ]
    config = PriceUniverseBuildConfig(
        max_products_per_canonical_per_context=2,
        max_products_per_canonical_global=4,
    )

    universe = _universe(products, config=config)
    selected = universe.products_for_canonical("ris")

    assert len(selected) == 4
    assert {row.store_id for row in selected} == {"ica:1", "ica:2"}
    assert {row.package_quantity for row in selected} == {500, 1000}
    assert universe.stats.per_context_top_k_pruned == 1
    assert universe.stats.global_top_k_pruned == 0


def test_disabled_member_checkout_price_rejected_but_public_equal_price_is_safe() -> None:
    member_offer = _offer(kind=OfferKind.MEMBER, price=15)
    leaked = _product(
        "member",
        price=20,
        effective_price=15,
        member_price=15,
        offers=[member_offer],
    )
    with pytest.raises(IneligibleMemberPriceError):
        _universe([leaked], key=_key("snapshot-1", memberships={"ica": False}))

    enabled = _universe([leaked], key=_key("snapshot-1", memberships={"ica": True}))
    assert enabled.products[0].effective_price == 15

    public_same_price = leaked.model_copy(
        update={"offers": [member_offer, _offer(kind=OfferKind.CAMPAIGN, price=15)]}
    )
    safe = _universe(
        [public_same_price],
        key=_key("snapshot-1", memberships={"ica": False}),
    )
    assert safe.products[0].effective_price == 15


def test_atomic_manager_keeps_active_universe_after_broken_build_or_validation() -> None:
    manager = PriceUniverseManager()
    first_key = _key("snapshot-1")
    first = manager.build_and_activate(first_key, [_product("first")], built_at=NOW)
    next_key = _key("snapshot-2")

    with pytest.raises(PriceUniverseError):
        manager.build_and_activate(
            next_key,
            [_product("broken", snapshot_id="wrong")],
            built_at=NOW,
        )
    assert manager.get_active(first_key.scope_id) is first

    with pytest.raises(PriceUniverseValidationError):
        manager.build_and_activate(
            next_key,
            [_product("next", snapshot_id="snapshot-2")],
            validator=lambda _candidate: False,
            built_at=NOW,
        )
    assert manager.get_active(first_key.scope_id) is first
    assert manager.status(first_key.scope_id).universe_id == first.universe_id


def test_atomic_manager_reuses_same_identity_under_concurrent_builds() -> None:
    manager = PriceUniverseManager()
    key = _key("snapshot-1")
    barrier = Barrier(3)
    results: list[PriceUniverse] = []

    def build() -> None:
        barrier.wait()
        results.append(manager.build_and_activate(key, [_product("rice")], built_at=NOW))

    threads = [Thread(target=build), Thread(target=build)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert len(results) == 2
    assert results[0] is results[1]
    assert manager.get_active(key.scope_id) is results[0]


def test_semantic_cache_is_scoped_by_universe_contexts_and_matcher_version() -> None:
    universe = _universe()
    cache = SemanticCandidateCache()
    calls = 0
    candidate = _candidate(universe.products[0])

    def load() -> list[ProductCandidate]:
        nonlocal calls
        calls += 1
        return [candidate]

    assert cache.get_or_compute(
        universe,
        "basmatiris",
        allowed_context_ids=("ica:1",),
        matcher_version="matcher-v1",
        factory=load,
    ) == (candidate,)
    cache.get_or_compute(
        universe,
        "ris",
        allowed_context_ids=("ica:1",),
        matcher_version="matcher-v1",
        factory=load,
    )
    cache.get_or_compute(
        universe,
        "ris",
        allowed_context_ids=("ica:2",),
        matcher_version="matcher-v1",
        factory=load,
    )

    assert calls == 2
    assert cache.stats.hits == 1
    assert cache.stats.misses == 2


def test_package_cache_normalizes_quantity_and_keeps_multibuy_caps_in_key() -> None:
    product = _product(
        "rice",
        offers=[_offer(price=30, required_packages=2, max_quantity=1)],
    )
    universe = _universe([product])
    candidate = _candidate(product)
    ingredient = NormalizedIngredient(canonical_name="ris", required_quantity=1000, unit="g")
    calculator = BasketCalculator()
    cache = PackageCostCache()
    calls = 0

    def quote():
        nonlocal calls
        calls += 1
        return calculator.quote_item(ingredient, candidate)

    first = cache.get_or_compute(
        universe,
        candidate,
        required_quantity=1,
        required_unit="kg",
        calculator_version="basket-calculator-v1",
        factory=quote,
    )
    second = cache.get_or_compute(
        universe,
        candidate,
        required_quantity=1000,
        required_unit="g",
        calculator_version="basket-calculator-v1",
        factory=quote,
    )
    changed_cap = candidate.model_copy(
        update={"offers": [_offer(price=30, required_packages=2, max_quantity=2)]}
    )
    cache.get_or_compute(
        universe,
        changed_cap,
        required_quantity=1000,
        required_unit="g",
        calculator_version="basket-calculator-v1",
        factory=quote,
    )

    assert first is second
    assert first.source_provenance == candidate.source_provenance
    assert calls == 2
    assert cache.stats.hits == 1
    assert cache.stats.misses == 2


def test_canonical_requirement_hash_is_sorted_aggregated_and_unit_normalized() -> None:
    left = [
        ("matris", 0.5, "kg"),
        ("gul lök", 200, "g"),
        ("ris", 500, "g"),
    ]
    right = [("gul lök", 200, "g"), ("ris", 1000, "g")]

    assert canonical_requirement_items(left) == (
        ("gul lök", "200", "g"),
        ("ris", "1000", "g"),
    )
    assert canonical_requirement_hash(left) == canonical_requirement_hash(right)


def test_basket_cache_separates_store_limit_and_contexts_and_preserves_result() -> None:
    universe = _universe()
    cache = BasketResultCache(max_entries=2)
    requirements = [("ris", 1000, "g")]
    basket = OptimizedBasket(total=0, stores=[], max_stores=1)
    calls = 0

    def load() -> OptimizedBasket:
        nonlocal calls
        calls += 1
        return basket

    first = cache.get_or_compute(
        universe,
        requirements,
        allowed_context_ids=("ica:1",),
        max_stores=1,
        optimizer_version="optimizer-v1",
        factory=load,
    )
    second = cache.get_or_compute(
        universe,
        list(reversed(requirements)),
        allowed_context_ids=("ica:1",),
        max_stores=1,
        optimizer_version="optimizer-v1",
        factory=load,
    )
    cache.get_or_compute(
        universe,
        requirements,
        allowed_context_ids=("ica:1",),
        max_stores=2,
        optimizer_version="optimizer-v1",
        factory=load,
    )
    cache.get_or_compute(
        universe,
        requirements,
        allowed_context_ids=("ica:2",),
        max_stores=2,
        optimizer_version="optimizer-v1",
        factory=load,
    )

    assert first is second is basket
    assert calls == 3
    assert cache.stats.hits == 1
    assert cache.stats.misses == 3
    assert cache.stats.evictions == 1


def test_builder_and_cache_emit_request_local_performance_metrics() -> None:
    with activate_performance_trace() as trace:
        universe = _universe()
        cache = SemanticCandidateCache()
        candidate = _candidate(universe.products[0])
        for _ in range(2):
            cache.get_or_compute(
                universe,
                "ris",
                matcher_version="matcher-v1",
                factory=lambda: [candidate],
            )

    snapshot = trace.snapshot()
    assert snapshot.timings_ms["build_price_universe"] >= 0
    assert snapshot.operation_counters["price_universe_raw_products"] == 1
    assert snapshot.operation_counters["price_universe_products_post_pruning"] == 1
    assert snapshot.operation_counters["semantic_cache_misses"] == 1
    assert snapshot.operation_counters["semantic_cache_hits"] == 1
