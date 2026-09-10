from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from app.errors import PriceProviderError
from app.models import (
    Product,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
    SourceProvenance,
    Store,
)
from app.models.ingredient import NormalizedIngredient
from app.providers import FederatedGroceryPriceProvider, GroceryPriceProvider, ProviderBinding
from app.providers.own import OwnGroceryPriceProvider
from app.services.basket_optimizer import BasketOptimizer
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.price_universe_runtime import LocalPriceUniverseProvider

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.domain.source_strategy import (
    OWN_CATALOG,
    PRIMAT_CATALOG,
    ChainSourceStrategy,
)

NOW = datetime.now(tz=UTC)


def _fresh_row() -> dict[str, Any]:
    return {
        "id": "store-coop-730400",
        "external_id": "730400",
        "chain": "coop",
        "name": "Coop Online Syd",
        "address": None,
        "postal_code": None,
        "city": "Lund",
        "coverage": "full_online_catalog",
        "price_context_type": "online_fulfillment",
        "physical_store_external_id": None,
        "price_semantics": "online_price",
        "price_label": "Coop onlinepris",
        "service_area": {
            "cities": ["Lund"],
            "postal_codes": ["22350", "22660"],
            "availability_basis": "verified_pickup_context",
            "requested_postal_code": "22350",
        },
        "pickup_options": [
            {
                "physical_store_id": "physical:coop:2696",
                "physical_store_external_id": "2696",
                "pickup_point_external_id": "257611",
                "name": "Stora Coop Lund",
                "address": "Traktorvägen 2",
                "postal_code": "22660",
                "city": "Lund",
                "relation_type": "pickup_context",
                "confidence": "exact",
            },
            {
                "physical_store_id": "physical:coop:test-pickup",
                "physical_store_external_id": "test-pickup",
                "pickup_point_external_id": "test-pickup-point",
                "name": "Coop Lund Testpickup",
                "postal_code": "22350",
                "city": "Lund",
                "relation_type": "pickup_context",
                "confidence": "exact",
            },
        ],
        "active": True,
        "snapshot_id": "snapshot-coop-730400",
        "observed_at": NOW.isoformat(),
        "data_age_hours": 0.1,
        "connector_status": "healthy",
        "source_provider": "own",
        "source_channel": "catalog",
        "source_snapshot_id": "snapshot-coop-730400",
        "source_observed_at": NOW.isoformat(),
    }


def _own_provider(row: dict[str, Any]) -> tuple[OwnGroceryPriceProvider, httpx.AsyncClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stores"
        assert request.url.params["postal_code"] == "22350"
        return httpx.Response(
            200,
            json={
                "items": [row],
                "count": 1,
                "snapshot_id": "snapshot-coop-730400",
                "observed_at": NOW.isoformat(),
                "connector_status": "healthy",
            },
            request=request,
        )

    client = httpx.AsyncClient(
        base_url="http://grocery-data.test/",
        transport=httpx.MockTransport(handler),
    )
    provider = OwnGroceryPriceProvider("http://grocery-data.test/", client=client)
    return provider, client


@pytest.mark.asyncio
async def test_own_provider_accepts_verified_linked_context_without_physical_address() -> None:
    provider, client = _own_provider(_fresh_row())
    try:
        stores = await provider.find_stores("22350")
    finally:
        await client.aclose()

    assert len(stores) == 1
    context = stores[0]
    assert context.store_id == "store-coop-730400"
    assert context.source_store_id == "730400"
    assert context.address is None
    assert context.postal_code is None
    assert context.price_semantics == "online_price"
    assert context.price_label == "Coop onlinepris"
    assert context.service_area is not None
    assert context.service_area.availability_basis == "verified_pickup_context"
    assert [row.pickup_point_external_id for row in context.pickup_options] == [
        "257611",
        "test-pickup-point",
    ]


@pytest.mark.asyncio
async def test_unlinked_online_context_without_postal_code_stays_ineligible() -> None:
    row = _fresh_row()
    row["service_area"] = None
    row["pickup_options"] = []
    provider, client = _own_provider(row)
    try:
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22350")
    finally:
        await client.aclose()


class _StaticProvider(GroceryPriceProvider):
    def __init__(self, stores: list[Store], products: list[Product] | None = None) -> None:
        super().__init__()
        self.stores = stores
        self.products = products or []

    async def find_stores(self, postal_code: str) -> list[Store]:
        assert postal_code == "22350"
        return list(self.stores)

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        return [row for row in self.products if row.store_id in store_ids]

    async def get_store_products(self, store_id: str) -> list[Product]:
        return [row for row in self.products if row.store_id == store_id]

    async def get_offers(self, store_id: str) -> list[Product]:
        return []


def _native_store(provider: str, *, native_id: str) -> Store:
    row = _fresh_row()
    return Store(
        store_id=native_id,
        source_store_id=native_id,
        name=str(row["name"]),
        chain="coop",
        city="Lund",
        postal_code=None,
        address=None,
        tier="full_online_catalog",
        coverage="full_online_catalog",
        price_context_type="online_fulfillment",
        price_semantics="online_price",
        price_label="Coop onlinepris",
        service_area=row["service_area"],
        pickup_options=tuple(row["pickup_options"]),
        source_provenance=SourceProvenance(
            source_provider=provider,
            source_channel="catalog",
            source_snapshot_id=f"snapshot-{provider}-coop",
            source_observed_at=NOW,
            chain="coop",
            provider_store_id=native_id,
            coverage="full_online_catalog",
        ),
    )


@pytest.mark.asyncio
async def test_federated_context_id_excludes_provider_and_many_pickups_count_once() -> None:
    own_native = _native_store("own", native_id="730400")
    primat_native = _native_store("primat", native_id="provider-row-99")
    own_strategy = {
        Chain.COOP: ChainSourceStrategy(chain=Chain.COOP, primary_source=OWN_CATALOG)
    }
    primat_strategy = {
        Chain.COOP: ChainSourceStrategy(chain=Chain.COOP, primary_source=PRIMAT_CATALOG)
    }
    own_federated = FederatedGroceryPriceProvider(
        [
            ProviderBinding(
                source=OWN_CATALOG,
                provider=_StaticProvider([own_native, own_native]),
                chains=frozenset({Chain.COOP}),
                coverage_by_chain={Chain.COOP: CoverageLevel.FULL_ONLINE_CATALOG},
            )
        ],
        strategies=own_strategy,
    )
    primat_federated = FederatedGroceryPriceProvider(
        [
            ProviderBinding(
                source=PRIMAT_CATALOG,
                provider=_StaticProvider([primat_native]),
                chains=frozenset({Chain.COOP}),
                coverage_by_chain={Chain.COOP: CoverageLevel.FULL_ONLINE_CATALOG},
            )
        ],
        strategies=primat_strategy,
    )

    own_contexts = await own_federated.find_stores("22350")
    primat_contexts = await primat_federated.find_stores("22350")

    assert len(own_contexts) == 1
    assert len(own_contexts[0].pickup_options) == 2
    assert own_contexts[0].context_id == primat_contexts[0].context_id
    assert "own" not in own_contexts[0].context_id
    assert "primat" not in own_contexts[0].context_id


@pytest.mark.asyncio
async def test_local_price_universe_keeps_coop_context_snapshot_only() -> None:
    native = _native_store("own", native_id="730400")
    federated = FederatedGroceryPriceProvider(
        [
            ProviderBinding(
                source=OWN_CATALOG,
                provider=_StaticProvider([native]),
                chains=frozenset({Chain.COOP}),
                coverage_by_chain={Chain.COOP: CoverageLevel.FULL_ONLINE_CATALOG},
            )
        ],
        strategies={
            Chain.COOP: ChainSourceStrategy(chain=Chain.COOP, primary_source=OWN_CATALOG)
        },
    )
    context = (await federated.find_stores("22350"))[0]
    product = Product(
        product_id="7300156573186",
        name="Mellanmjölk 1.5 l",
        canonical_name="milk",
        canonical_food="milk",
        category="Mejeri & ägg",
        chain="coop",
        gtin="7300156573186",
        store_id=context.store_id,
        store_name=context.name,
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=1500,
        package_unit="ml",
        usable_quantity=1500,
        usable_unit="ml",
        sale_price=16.27,
        price=16.27,
        effective_price=16.27,
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        price_context_type="online_fulfillment",
        coverage="full_online_catalog",
        source_provenance=SourceProvenance(
            source_provider="own",
            source_channel="catalog",
            source_snapshot_id="snapshot-own-coop",
            source_observed_at=NOW,
            chain="coop",
            store_id=context.store_id,
            store_name=context.name,
            provider_store_id="730400",
            price_context="online_fulfillment",
            coverage="full_online_catalog",
            semantic_confidence="high",
            quantity_confidence="exact",
        ),
    )
    key = PriceUniverseKey.create(
        city="Lund",
        postal_codes=("22350",),
        snapshot_ids=("snapshot-own-coop",),
        memberships={"coop": False},
        source_strategy_version="test-strategy-v1",
        normalizer_version="test-normalizer-v1",
        taxonomy_version="test-taxonomy-v1",
    )
    universe = PriceUniverseBuilder().build(key, [product], built_at=NOW)
    local = LocalPriceUniverseProvider(universe, [context])

    stores = await local.find_stores("22350")
    products = await local.get_store_products(stores[0].store_id)
    basket = BasketOptimizer().optimize(
        [NormalizedIngredient(canonical_name="milk", required_quantity=1000, unit="ml")],
        {"milk": [ProductCandidate.from_product(products[0], match_score=1.0)]},
        stores,
        max_stores=1,
    )

    assert [row.context_id for row in stores] == [context.context_id]
    assert stores[0].price_label == "Coop onlinepris"
    assert len(stores[0].pickup_options) == 2
    assert [row.product_id for row in products] == ["7300156573186"]
    assert products[0].source_provenance is not None
    assert products[0].source_provenance.source_snapshot_id == "snapshot-own-coop"
    assert basket.store_count == 1
    assert basket.stores[0].store_name == "Coop Online Syd"
