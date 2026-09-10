from __future__ import annotations

from collections.abc import Sequence

import pytest
from app.models import NormalizedIngredient, Product, QuantityConfidence, Store
from app.services.basket_optimizer import BasketOptimizer, BasketVerificationPolicy
from app.services.economic_ingredient_selector import EconomicIngredientSelector
from app.services.ingredient_taxonomy import (
    INGREDIENT_TAXONOMY,
    IngredientCategory,
    IngredientTaxonomyEntry,
    get_taxonomy_entry,
    ingredients_in_category,
)

STORES = (
    Store(
        store_id="s1",
        name="Butik Ett",
        chain="Test",
        city="Lund",
        postal_code="22350",
    ),
    Store(
        store_id="s2",
        name="Butik Två",
        chain="Test",
        city="Lund",
        postal_code="22350",
    ),
)


def _product(
    product_id: str,
    name: str,
    canonical_name: str,
    *,
    store: Store = STORES[0],
    package_quantity: float = 500,
    package_unit: str = "g",
    price: float = 20,
    effective_price: float | None = None,
    category: str = "Testkategori",
    quantity_confidence: QuantityConfidence = QuantityConfidence.UNKNOWN,
) -> Product:
    return Product(
        product_id=product_id,
        name=name,
        canonical_name=canonical_name,
        category=category,
        store_id=store.store_id,
        store_name=store.name,
        package_quantity=package_quantity,
        package_unit=package_unit,
        price=price,
        effective_price=effective_price,
        quantity_confidence=quantity_confidence,
    )


class _RecordingProvider:
    def __init__(self, rows: dict[str, list[Product]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        self.calls.append((query, tuple(store_ids)))
        return list(self.rows.get(query, []))


def _entries(*canonical_names: str) -> Sequence[IngredientTaxonomyEntry]:
    entries = [get_taxonomy_entry(name) for name in canonical_names]
    assert all(entry is not None for entry in entries)
    return [entry for entry in entries if entry is not None]


def test_taxonomy_reuses_existing_aliases_and_has_a_bounded_meal_scope() -> None:
    assert get_taxonomy_entry("spaghetti").canonical == "pasta"  # type: ignore[union-attr]
    assert get_taxonomy_entry("röda linser").canonical == "linser"  # type: ignore[union-attr]
    assert {entry.canonical for entry in ingredients_in_category("protein")} >= {
        "kyckling",
        "ägg",
        "falukorv",
    }
    assert len({entry.search_query for entry in INGREDIENT_TAXONOMY}) <= 45
    assert all(entry.canonical not in {"mjöl", "socker", "salt"} for entry in INGREDIENT_TAXONOMY)


@pytest.mark.asyncio
async def test_selector_builds_public_signals_and_keeps_store_candidates_internal() -> None:
    from app.providers.mock import MockPriceProvider

    provider = MockPriceProvider()
    stores = await provider.find_stores("22350")

    pool = await EconomicIngredientSelector().select(provider, stores)

    names = {signal.canonical for signal in pool.ingredients}
    assert {
        "ägg",
        "potatis",
        "ris",
        "morot",
        "linser",
        "crème fraiche",
        "krossade tomater",
    } <= names
    assert pool.search_queries_executed <= 45
    assert len(pool.candidates_by_name["potatis"]) == len(stores)
    assert {candidate.store_id for candidate in pool.candidates_by_name["potatis"]} == {
        store.store_id for store in stores
    }

    public_payload = pool.model_dump(mode="json")
    assert "candidates_by_name" not in public_payload
    assert len(pool.to_cheap_ingredients()) == len(pool.ingredients)


@pytest.mark.asyncio
async def test_selector_rejects_critical_broad_search_false_matches() -> None:
    provider = _RecordingProvider(
        {
            "linser": [
                _product("yellow-peas", "Ärter Gula 500 g", "linser"),
                _product(
                    "lentils",
                    "Röda Linser 500 g",
                    "linser",
                    category="Torra baljväxter",
                ),
            ],
            "ris": [
                _product("porridge-rice", "Grötris 1 kg", "ris", package_quantity=1000),
                _product("rice", "Basmatiris 1 kg", "ris", package_quantity=1000),
            ],
            "crème fraiche": [
                _product(
                    "potato-salad",
                    "Potatissallad Crème Fraiche 500 ml",
                    "crème fraiche",
                    package_unit="ml",
                ),
                _product(
                    "creme-fraiche",
                    "Arla Crème Fraiche 500 ml",
                    "crème fraiche",
                    package_unit="ml",
                ),
            ],
            "ost": [
                _product("grill-cheese", "Grillost Original 500 g", "ost"),
                _product("cheese", "Garant Hushållsost 500 g", "ost"),
            ],
        }
    )
    selector = EconomicIngredientSelector(
        taxonomy=_entries("linser", "ris", "crème fraiche", "ost")
    )

    pool = await selector.select(provider, STORES[:1])

    assert {
        name: [candidate.product_id for candidate in candidates]
        for name, candidates in pool.candidates_by_name.items()
    } == {
        "linser": ["lentils"],
        "ris": ["rice"],
        "crème fraiche": ["creme-fraiche"],
        "ost": ["cheese"],
    }


@pytest.mark.asyncio
async def test_selector_accepts_primat_noun_first_yellow_onion_name() -> None:
    provider = _RecordingProvider(
        {
            "gul lök": [
                _product(
                    "yellow-onion",
                    "Lök Gul Sverige 1 kg",
                    "gul lök",
                    package_quantity=1000,
                    price=14.9,
                )
            ]
        }
    )

    pool = await EconomicIngredientSelector(taxonomy=_entries("gul lök")).select(
        provider, STORES[:1]
    )

    assert [candidate.product_id for candidate in pool.candidates_by_name["gul lök"]] == [
        "yellow-onion"
    ]


@pytest.mark.asyncio
async def test_selector_scores_package_fit_and_preserves_multiple_store_options() -> None:
    # The 2 kg bag has the lowest theoretical kg price. For a representative
    # 1.2 kg dinner the 500 g bag has slightly better package fit, so it is the
    # stronger generation signal. Both remain available to the exact optimizer.
    provider = _RecordingProvider(
        {
            "potatis": [
                _product(
                    "large-s1",
                    "Potatis 2 kg",
                    "potatis",
                    package_quantity=2000,
                    price=19.90,
                ),
                _product(
                    "small-s1",
                    "Potatis 500 g",
                    "potatis",
                    package_quantity=500,
                    price=5.10,
                ),
                _product(
                    "large-s2",
                    "Potatis 2 kg",
                    "potatis",
                    store=STORES[1],
                    package_quantity=2000,
                    price=21,
                ),
            ]
        }
    )
    selector = EconomicIngredientSelector(
        taxonomy=_entries("potatis"),
        max_candidates_per_store=3,
    )

    pool = await selector.select(provider, STORES)

    signal = pool.ingredients[0]
    assert signal.example_products[0].product_id == "small-s1"
    assert {candidate.product_id for candidate in pool.candidates_by_name["potatis"]} == {
        "large-s1",
        "small-s1",
        "large-s2",
    }
    assert provider.calls == [("potatis", ("s1", "s2"))]


@pytest.mark.asyncio
async def test_selector_keeps_fifth_ranked_bulk_sku_when_it_wins_for_weekly_demand() -> None:
    # For one 1.2 kg meal, each 1 kg SKU is cheaper to buy than the 6 kg bag.
    # The four-SKU cap would therefore discard the bulk product under a simple
    # single-meal ranking. Across five meals (6 kg), the bulk SKU wins 27 vs 30.
    small_products = [
        _product(
            f"small-{index}",
            f"Potatis 1 kg variant {index}",
            "potatis",
            package_quantity=1000,
            price=5,
        )
        for index in range(4)
    ]
    bulk = _product(
        "weekly-bulk",
        "Potatis 6 kg",
        "potatis",
        package_quantity=6000,
        price=27,
    )
    provider = _RecordingProvider({"potatis": [*small_products, bulk]})
    selector = EconomicIngredientSelector(
        taxonomy=_entries("potatis"),
        max_candidates_per_store=4,
    )

    pool = await selector.select(provider, STORES[:1])

    retained = pool.candidates_by_name["potatis"]
    assert len(retained) == 4
    assert "weekly-bulk" in {candidate.product_id for candidate in retained}

    basket = BasketOptimizer().optimize(
        [
            NormalizedIngredient(
                canonical_name="potatis",
                required_quantity=6000,
                unit="g",
            )
        ],
        pool.candidates_by_name,
        STORES[:1],
        max_stores=1,
    )
    assert basket.total == 27
    assert basket.stores[0].items[0].product_id == "weekly-bulk"


@pytest.mark.asyncio
async def test_strict_selector_does_not_let_unknown_quantity_crowd_out_safe_product() -> None:
    provider = _RecordingProvider(
        {
            "potatis": [
                _product(
                    "unknown-cheap",
                    "Potatis 1 kg osäker",
                    "potatis",
                    package_quantity=1000,
                    price=1,
                    quantity_confidence=QuantityConfidence.UNKNOWN,
                ),
                _product(
                    "verified",
                    "Potatis 1 kg verifierad",
                    "potatis",
                    package_quantity=1000,
                    price=20,
                    quantity_confidence=QuantityConfidence.EXACT,
                ),
            ]
        }
    )
    selector = EconomicIngredientSelector(
        taxonomy=_entries("potatis"),
        max_candidates_per_store=1,
        verification_policy=BasketVerificationPolicy.strict_live(),
    )

    pool = await selector.select(provider, STORES[:1])

    assert [row.product_id for row in pool.candidates_by_name["potatis"]] == ["verified"]
    assert pool.ingredients[0].example_products[0].quantity_confidence == QuantityConfidence.EXACT


@pytest.mark.asyncio
async def test_category_limit_keeps_the_best_economic_ingredient() -> None:
    provider = _RecordingProvider(
        {
            "potatis": [
                _product(
                    "potato",
                    "Potatis 1 kg",
                    "potatis",
                    package_quantity=1000,
                    price=10,
                )
            ],
            "pasta": [
                _product(
                    "pasta",
                    "Spaghetti 1 kg",
                    "pasta",
                    package_quantity=1000,
                    price=30,
                )
            ],
        }
    )
    selector = EconomicIngredientSelector(
        taxonomy=_entries("potatis", "pasta"),
        max_ingredients_per_category={IngredientCategory.CARBOHYDRATE: 1},
    )

    pool = await selector.select(provider, STORES[:1])

    assert [signal.canonical for signal in pool.ingredients] == ["potatis"]
    assert set(pool.candidates_by_name) == {"potatis"}


def test_selector_refuses_a_taxonomy_that_exceeds_its_request_budget() -> None:
    with pytest.raises(ValueError, match="requires 2 searches"):
        EconomicIngredientSelector(
            taxonomy=_entries("potatis", "pasta"),
            max_searches=1,
        )
