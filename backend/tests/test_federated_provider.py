from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.errors import PriceProviderError
from app.models import (
    OfferKind,
    OfferMetadata,
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
from app.services.basket_optimizer import BasketOptimizer

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.domain.source_strategy import (
    OWN_CATALOG,
    OWN_OFFERS,
    PRIMAT_CATALOG,
    ChainSourceStrategy,
    ContextSourceStrategy,
)

NOW = datetime.now(tz=UTC)


def _provenance(
    provider: str,
    chain: Chain,
    store_id: str,
    *,
    observed_at: datetime = NOW,
    coverage: CoverageLevel = CoverageLevel.FULL_CATALOG,
) -> SourceProvenance:
    return SourceProvenance(
        source_provider=provider,
        source_channel="catalog",
        source_snapshot_id=f"{provider}-{chain.value}-snapshot",
        source_observed_at=observed_at,
        chain=chain.value,
        provider_store_id=store_id,
        coverage=coverage.value,
    )


def _store(
    chain: Chain,
    native_id: str,
    *,
    provider: str,
    coverage: CoverageLevel = CoverageLevel.FULL_CATALOG,
    observed_at: datetime = NOW,
    name: str | None = None,
) -> Store:
    return Store(
        store_id=native_id,
        source_store_id=native_id,
        name=name or f"{chain.value.title()} Centrum",
        chain=chain.value,
        city="Malmö",
        postal_code="21120",
        address="Testgatan 1",
        tier=coverage.value,
        coverage=coverage.value,
        price_context_type="online_store",
        source_provenance=_provenance(
            provider,
            chain,
            native_id,
            observed_at=observed_at,
            coverage=coverage,
        ),
    )


def _product(
    chain: Chain,
    store_id: str,
    food: str,
    price: float,
    *,
    provider: str,
    offers: list[OfferMetadata] | None = None,
    member_price: float | None = None,
    gtin: str | None = None,
) -> Product:
    return Product(
        product_id=f"{food}-{provider}",
        name=food,
        canonical_name=food,
        canonical_food=food,
        category="Mat",
        chain=chain.value,
        gtin=gtin,
        store_id=store_id,
        store_name=f"{chain.value.title()} Centrum",
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=1000,
        package_unit="g",
        usable_quantity=1000,
        usable_unit="g",
        sale_price=price,
        price=price,
        effective_price=member_price or price,
        member_price=member_price,
        offers=offers or [],
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        source_provenance=_provenance(provider, chain, store_id),
    )


class StubProvider(GroceryPriceProvider):
    def __init__(
        self,
        stores: list[Store],
        products: list[Product],
        *,
        error: bool = False,
        search_error: bool = False,
    ) -> None:
        super().__init__()
        self.stores = stores
        self.products = products
        self.error = error
        self.search_error = search_error
        self.search_calls = 0

    async def find_stores(self, postal_code: str) -> list[Store]:
        if self.error:
            raise PriceProviderError("connector broken")
        return list(self.stores)

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        self.search_calls += 1
        if self.search_error:
            raise PriceProviderError("product request broke after source selection")
        return [
            product
            for product in self.products
            if product.store_id in store_ids and query.casefold() in product.name.casefold()
        ]

    async def get_store_products(self, store_id: str) -> list[Product]:
        return [product for product in self.products if product.store_id == store_id]

    async def get_offers(self, store_id: str) -> list[Product]:
        return [
            product for product in self.products if product.store_id == store_id and product.offers
        ]


def _binding(
    source,
    provider: GroceryPriceProvider,
    *chains: Chain,
    coverage: CoverageLevel = CoverageLevel.FULL_CATALOG,
) -> ProviderBinding:
    return ProviderBinding(
        source=source,
        provider=provider,
        chains=frozenset(chains),
        coverage_by_chain={chain: coverage for chain in chains},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("relay", [False, True])
async def test_primary_healthy_and_fresh_wins_without_primary_fallback_duplicates(
    relay: bool,
) -> None:
    own_store = _store(Chain.WILLYS, "own-1", provider="own")
    primat_store = _store(
        Chain.WILLYS,
        "primat-9",
        provider="primat",
        name=own_store.name,
    )
    own = StubProvider(
        [own_store],
        [_product(Chain.WILLYS, "own-1", "ris", 20, provider="own", gtin="7310000000001")],
    )
    if relay:
        own.products[0] = own.products[0].model_copy(
            update={
                "source_provenance": own.products[0].source_provenance.model_copy(
                    update={"collection_location": "LOCAL_RELAY"}
                )
            }
        )
    primat = StubProvider(
        [primat_store],
        [
            _product(
                Chain.WILLYS,
                "primat-9",
                "ris",
                19,
                provider="primat",
                gtin="7310000000001",
            )
        ],
    )
    provider = FederatedGroceryPriceProvider(
        [
            _binding(OWN_CATALOG, own, Chain.WILLYS),
            _binding(PRIMAT_CATALOG, primat, Chain.WILLYS),
        ]
    )

    stores = await provider.find_stores("21120")
    products = await provider.search_products("ris", [store.store_id for store in stores])

    assert len(stores) == 1  # contexts, not providers
    assert len(products) == 1
    assert products[0].price == 20
    assert products[0].source_provenance is not None
    assert products[0].source_provenance.collection_location == ("LOCAL_RELAY" if relay else None)
    catalog = await provider.get_store_products(stores[0].store_id)
    assert catalog[0].source_provenance.collection_location == ("LOCAL_RELAY" if relay else None)
    assert products[0].source_provenance.source_provider == "own"
    assert products[0].source_provenance.fallback_used is False
    assert products[0].source_provenance.store_id == stores[0].store_id
    assert own.search_calls == 1
    assert primat.search_calls == 0


@pytest.mark.asyncio
async def test_stale_primary_requires_explicit_fallback_and_reports_it() -> None:
    stale = NOW - timedelta(hours=72)
    own = StubProvider(
        [_store(Chain.WILLYS, "own", provider="own", observed_at=stale)],
        [],
    )
    primat = StubProvider([_store(Chain.WILLYS, "primat", provider="primat")], [])
    bindings = [
        _binding(OWN_CATALOG, own, Chain.WILLYS),
        _binding(PRIMAT_CATALOG, primat, Chain.WILLYS),
    ]

    provider = FederatedGroceryPriceProvider(bindings, max_price_age_hours=48)
    with pytest.raises(PriceProviderError, match="fallback available but not enabled"):
        await provider.find_stores("21120")
    diagnostic = {item.chain: item for item in provider.diagnostics}[Chain.WILLYS]
    assert diagnostic.stale_stores == 1
    assert diagnostic.fallback_available is True
    assert diagnostic.fallback_used is False

    provider = FederatedGroceryPriceProvider(
        bindings,
        max_price_age_hours=48,
        allow_fallback=True,
    )
    stores = await provider.find_stores("21120")
    assert len(stores) == 1
    assert stores[0].source_provenance is not None
    assert stores[0].source_provenance.source_provider == "primat"
    assert stores[0].source_provenance.fallback_used is True
    assert {item.chain: item for item in provider.diagnostics}[Chain.WILLYS].fallback_used is True


@pytest.mark.asyncio
async def test_broken_primary_uses_fallback_only_under_explicit_policy() -> None:
    own_store = _store(Chain.WILLYS, "own", provider="own")
    primat_store = _store(Chain.WILLYS, "primat", provider="primat")
    own = StubProvider([own_store], [])
    primat = StubProvider([primat_store], [])
    bindings = [
        ProviderBinding(
            source=OWN_CATALOG,
            provider=own,
            chains=frozenset({Chain.WILLYS}),
            coverage_by_chain={Chain.WILLYS: CoverageLevel.FULL_CATALOG},
            healthy=False,
        ),
        _binding(PRIMAT_CATALOG, primat, Chain.WILLYS),
    ]

    denied = FederatedGroceryPriceProvider(bindings)
    with pytest.raises(PriceProviderError, match="fallback available but not enabled"):
        await denied.find_stores("21120")

    allowed = FederatedGroceryPriceProvider(bindings, allow_fallback=True)
    store = (await allowed.find_stores("21120"))[0]
    assert store.source_provenance is not None
    assert store.source_provenance.source_provider == "primat"
    assert store.source_provenance.fallback_used is True


@pytest.mark.asyncio
async def test_exact_context_override_uses_own_while_ica_default_remains_primat() -> None:
    gunnesbo_id = "context:ica:gunnesbo"
    other_id = "context:ica:other-lund"
    own_gunnesbo = _store(
        Chain.ICA,
        gunnesbo_id,
        provider="own",
        name="Maxi ICA Stormarknad Gunnesbo",
    )
    primat_gunnesbo = _store(
        Chain.ICA,
        gunnesbo_id,
        provider="primat",
        name="Maxi ICA Stormarknad Gunnesbo",
    )
    primat_other = _store(
        Chain.ICA,
        other_id,
        provider="primat",
        name="ICA Nära Lund",
    )
    strategy = ChainSourceStrategy(
        chain=Chain.ICA,
        primary_source=PRIMAT_CATALOG,
        context_overrides=(
            ContextSourceStrategy(
                context_id=gunnesbo_id,
                primary_source=OWN_CATALOG,
                secondary_sources=(PRIMAT_CATALOG,),
            ),
        ),
    )
    provider = FederatedGroceryPriceProvider(
        [
            _binding(OWN_CATALOG, StubProvider([own_gunnesbo], []), Chain.ICA),
            _binding(
                PRIMAT_CATALOG,
                StubProvider([primat_gunnesbo, primat_other], []),
                Chain.ICA,
            ),
        ],
        strategies={Chain.ICA: strategy},
    )

    stores = await provider.find_stores("21120")
    by_name = {store.name: store for store in stores}

    assert len(stores) == 2
    assert (
        by_name["Maxi ICA Stormarknad Gunnesbo"].source_provenance.source_provider  # type: ignore[union-attr]
        == "own"
    )
    assert by_name["ICA Nära Lund"].source_provenance.source_provider == "primat"  # type: ignore[union-attr]
    assert len([store for store in stores if "Gunnesbo" in store.name]) == 1
    context_diagnostics = {item.context_id: item for item in provider.context_diagnostics}
    assert context_diagnostics[gunnesbo_id].selected_provider.value == "own"  # type: ignore[union-attr]
    assert context_diagnostics[None].selected_provider.value == "primat"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_context_override_fallback_is_never_silent() -> None:
    context_id = "context:ica:gunnesbo"
    stale = NOW - timedelta(hours=72)
    own = StubProvider(
        [_store(Chain.ICA, context_id, provider="own", observed_at=stale)],
        [],
    )
    primat = StubProvider([_store(Chain.ICA, context_id, provider="primat")], [])
    strategy = ChainSourceStrategy(
        chain=Chain.ICA,
        primary_source=PRIMAT_CATALOG,
        context_overrides=(
            ContextSourceStrategy(
                context_id=context_id,
                primary_source=OWN_CATALOG,
                secondary_sources=(PRIMAT_CATALOG,),
            ),
        ),
    )
    bindings = [
        _binding(OWN_CATALOG, own, Chain.ICA),
        _binding(PRIMAT_CATALOG, primat, Chain.ICA),
    ]

    denied = FederatedGroceryPriceProvider(
        bindings,
        strategies={Chain.ICA: strategy},
        max_price_age_hours=48,
    )
    with pytest.raises(PriceProviderError, match="fallback available but not enabled"):
        await denied.find_stores("21120")
    denied_context = next(
        item for item in denied.context_diagnostics if item.context_id == context_id
    )
    assert denied_context.stale_stores == 1
    assert denied_context.fallback_available is True
    assert denied_context.fallback_used is False

    allowed = FederatedGroceryPriceProvider(
        bindings,
        strategies={Chain.ICA: strategy},
        max_price_age_hours=48,
        allow_fallback=True,
    )
    selected = (await allowed.find_stores("21120"))[0]
    assert selected.source_provenance is not None
    assert selected.source_provenance.source_provider == "primat"
    assert selected.source_provenance.fallback_used is True
    allowed_context = next(
        item for item in allowed.context_diagnostics if item.context_id == context_id
    )
    assert allowed_context.fallback_used is True


@pytest.mark.asyncio
async def test_broken_context_override_keeps_primary_failure_explicit() -> None:
    context_id = "context:ica:gunnesbo"
    own_provider = StubProvider([_store(Chain.ICA, context_id, provider="own")], [])
    primat_provider = StubProvider([_store(Chain.ICA, context_id, provider="primat")], [])
    strategy = ChainSourceStrategy(
        chain=Chain.ICA,
        primary_source=PRIMAT_CATALOG,
        context_overrides=(
            ContextSourceStrategy(
                context_id=context_id,
                primary_source=OWN_CATALOG,
                secondary_sources=(PRIMAT_CATALOG,),
            ),
        ),
    )
    bindings = [
        ProviderBinding(
            source=OWN_CATALOG,
            provider=own_provider,
            chains=frozenset({Chain.ICA}),
            coverage_by_chain={Chain.ICA: CoverageLevel.FULL_CATALOG},
            healthy=False,
        ),
        _binding(PRIMAT_CATALOG, primat_provider, Chain.ICA),
    ]

    denied = FederatedGroceryPriceProvider(bindings, strategies={Chain.ICA: strategy})
    with pytest.raises(PriceProviderError, match="fallback available but not enabled"):
        await denied.find_stores("21120")
    broken = next(item for item in denied.context_diagnostics if item.context_id == context_id)
    assert broken.reason.startswith("provider health is not healthy")
    assert broken.fallback_used is False

    allowed = FederatedGroceryPriceProvider(
        bindings,
        strategies={Chain.ICA: strategy},
        allow_fallback=True,
    )
    selected = (await allowed.find_stores("21120"))[0]
    assert selected.source_provenance is not None
    assert selected.source_provenance.source_provider == "primat"
    assert selected.source_provenance.fallback_used is True


@pytest.mark.asyncio
async def test_product_failure_is_visible_and_never_switches_context_mid_request() -> None:
    own = StubProvider(
        [_store(Chain.WILLYS, "own", provider="own")],
        [],
        search_error=True,
    )
    primat = StubProvider(
        [_store(Chain.WILLYS, "primat", provider="primat")],
        [_product(Chain.WILLYS, "primat", "ris", 10, provider="primat")],
    )
    provider = FederatedGroceryPriceProvider(
        [
            _binding(OWN_CATALOG, own, Chain.WILLYS),
            _binding(PRIMAT_CATALOG, primat, Chain.WILLYS),
        ],
        allow_fallback=True,
    )
    store = (await provider.find_stores("21120"))[0]

    with pytest.raises(PriceProviderError, match="Alla valda"):
        await provider.search_products("ris", [store.store_id])

    assert own.search_calls == 1
    assert primat.search_calls == 0
    diagnostic = {item.chain: item for item in provider.diagnostics}[Chain.WILLYS]
    assert diagnostic.fallback_used is False
    assert "product request broke" in diagnostic.provider_errors[-1]


@pytest.mark.asyncio
async def test_stale_price_row_is_rejected_even_when_store_snapshot_is_fresh() -> None:
    store = _store(Chain.WILLYS, "own", provider="own")
    stale_product = _product(Chain.WILLYS, "own", "ris", 10, provider="own").model_copy(
        update={
            "source_provenance": _provenance(
                "own",
                Chain.WILLYS,
                "own",
                observed_at=NOW - timedelta(hours=72),
            )
        },
        deep=True,
    )
    provider = FederatedGroceryPriceProvider(
        [_binding(OWN_CATALOG, StubProvider([store], [stale_product]), Chain.WILLYS)],
        max_price_age_hours=48,
    )
    public = (await provider.find_stores("21120"))[0]

    assert await provider.get_store_products(public.store_id) == []
    diagnostic = {item.chain: item for item in provider.diagnostics}[Chain.WILLYS]
    assert diagnostic.products_considered == {"own": 1}
    assert diagnostic.rows_rejected == 1
    assert diagnostic.stale_rows == 1


@pytest.mark.asyncio
async def test_offers_only_coverage_never_becomes_a_basket_catalog() -> None:
    store = _store(
        Chain.LIDL,
        "offers",
        provider="own",
        coverage=CoverageLevel.OFFERS_ONLY,
    )
    own = StubProvider([store], [])
    strategies = {
        Chain.LIDL: ChainSourceStrategy(
            chain=Chain.LIDL,
            primary_source=OWN_CATALOG,
        )
    }
    provider = FederatedGroceryPriceProvider(
        [
            _binding(
                OWN_CATALOG,
                own,
                Chain.LIDL,
                coverage=CoverageLevel.OFFERS_ONLY,
            )
        ],
        strategies=strategies,
    )

    with pytest.raises(PriceProviderError, match="lack complete coverage"):
        await provider.find_stores("21120")
    assert provider.diagnostics[0].basket_eligible is False


@pytest.mark.asyncio
async def test_shared_federated_product_retains_member_contracts_with_public_flattening() -> None:
    member_offer = OfferMetadata(
        kind=OfferKind.MEMBER,
        description="Klubbpris",
        price=10,
        member_program="Willys Plus",
    )
    member_multi = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="Medlem 2 för 15",
        price=15,
        required_packages=2,
        max_quantity=1,
        member_program="Willys Plus",
    )
    store = _store(Chain.WILLYS, "own", provider="own")
    own = StubProvider(
        [store],
        [
            _product(
                Chain.WILLYS,
                "own",
                "mjölk",
                20,
                provider="own",
                member_price=10,
                offers=[member_offer, member_multi],
            )
        ],
    )
    binding = _binding(OWN_CATALOG, own, Chain.WILLYS)

    disabled = FederatedGroceryPriceProvider([binding], memberships={Chain.WILLYS: False})
    disabled_store = (await disabled.find_stores("21120"))[0]
    disabled_product = (await disabled.get_store_products(disabled_store.store_id))[0]
    assert disabled_product.effective_price == 20
    assert disabled_product.member_price == 10
    assert len(disabled_product.offers) == 2
    assert disabled_product.offers[0].eligibility is PromotionEligibility.MEMBER
    assert disabled_product.offers[0].membership_program is MembershipProgram.WILLYS_PLUS
    assert disabled_product.offers[1].mechanism is PromotionMechanism.MULTIBUY
    assert disabled_product.offers[1].eligibility is PromotionEligibility.MEMBER

    enabled = FederatedGroceryPriceProvider([binding], memberships={Chain.WILLYS: True})
    enabled_store = (await enabled.find_stores("21120"))[0]
    enabled_product = (await enabled.get_store_products(enabled_store.store_id))[0]
    assert enabled_product.effective_price == 20
    assert enabled_product.member_price == 10
    assert len(enabled_product.offers) == 2
    assert enabled_product.offers[1].max_quantity == 1


@pytest.mark.asyncio
async def test_federated_shared_rows_keep_member_evidence_but_public_checkout_fields() -> None:
    def checkout_product(
        chain: Chain,
        store_id: str,
        name: str,
        *,
        sale_model: SaleModel,
        regular_price: float,
        member_price: float,
        public_offers: list[OfferMetadata] | None = None,
    ) -> Product:
        member_offer = OfferMetadata(
            kind=OfferKind.MEMBER,
            description=f"{chain.value} medlemspris",
            price=member_price,
            member_program=f"{chain.value} medlem",
        )
        fields: dict[str, object] = {
            "product_id": f"{chain.value}-{name}",
            "name": name,
            "canonical_name": name,
            "canonical_food": name,
            "category": "Mat",
            "chain": chain.value,
            "store_id": store_id,
            "store_name": f"{chain.value.title()} Centrum",
            "sale_model": sale_model,
            "sale_price": member_price,
            "price": regular_price,
            "effective_price": member_price,
            "member_price": member_price,
            "offers": [member_offer, *(public_offers or [])],
            "semantic_confidence": SemanticConfidence.HIGH,
            "quantity_confidence": QuantityConfidence.EXACT,
            "source_provenance": _provenance("own", chain, store_id),
        }
        if sale_model is SaleModel.SOLD_BY_WEIGHT:
            fields.update(
                sale_unit="kg",
                comparison_price=member_price,
                comparison_unit="kg",
                variable_weight=True,
            )
        elif sale_model is SaleModel.SOLD_BY_PIECE:
            fields.update(
                sale_unit="st",
                piece_price=member_price,
                package_quantity=1,
                package_unit="st",
                usable_quantity=1,
                usable_unit="st",
            )
        else:
            fields.update(
                sale_unit="package",
                package_quantity=500,
                package_unit="g",
                usable_quantity=500,
                usable_unit="g",
                variable_weight=sale_model is SaleModel.VARIABLE_WEIGHT_PACKAGE,
            )
        return Product(**fields)

    enabled_store = _store(Chain.WILLYS, "w", provider="own")
    disabled_store = _store(Chain.HEMKOP, "h", provider="own")
    public_weight_campaign = OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description="Publikt kilopris",
        price=90,
    )
    public_variable_campaign = OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description="Publikt paketpris",
        price=50,
    )
    public_multibuy = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="3 för 24",
        price=24,
        required_packages=3,
        max_quantity=2,
    )
    capped_multibuy = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 för 30, max en gång",
        price=30,
        required_packages=2,
        max_quantity=1,
    )
    products = [
        checkout_product(
            Chain.WILLYS,
            "w",
            "enabled-fixed",
            sale_model=SaleModel.FIXED_PACKAGE,
            regular_price=20,
            member_price=10,
        ),
        checkout_product(
            Chain.HEMKOP,
            "h",
            "disabled-weight",
            sale_model=SaleModel.SOLD_BY_WEIGHT,
            regular_price=100,
            member_price=70,
            public_offers=[public_weight_campaign],
        ),
        checkout_product(
            Chain.HEMKOP,
            "h",
            "disabled-piece",
            sale_model=SaleModel.SOLD_BY_PIECE,
            regular_price=10,
            member_price=7,
            public_offers=[public_multibuy],
        ),
        checkout_product(
            Chain.HEMKOP,
            "h",
            "disabled-variable",
            sale_model=SaleModel.VARIABLE_WEIGHT_PACKAGE,
            regular_price=60,
            member_price=40,
            public_offers=[public_variable_campaign],
        ),
        checkout_product(
            Chain.HEMKOP,
            "h",
            "disabled-fixed-multibuy",
            sale_model=SaleModel.FIXED_PACKAGE,
            regular_price=20,
            member_price=10,
            public_offers=[capped_multibuy],
        ),
    ]
    own = StubProvider([enabled_store, disabled_store], products)
    provider = FederatedGroceryPriceProvider(
        [_binding(OWN_CATALOG, own, Chain.WILLYS, Chain.HEMKOP)],
        memberships={Chain.WILLYS: True, Chain.HEMKOP: False},
    )
    stores = {store.chain: store for store in await provider.find_stores("21120")}

    enabled = (await provider.get_store_products(stores[Chain.WILLYS.value].store_id))[0]
    disabled = {
        product.name: product
        for product in await provider.get_store_products(stores[Chain.HEMKOP.value].store_id)
    }

    assert enabled.effective_price == 20
    assert enabled.sale_price == 20
    assert enabled.member_price == 10
    assert enabled.offers[0].kind is OfferKind.MEMBER

    weight = disabled["disabled-weight"]
    assert weight.member_price == 70
    assert weight.effective_price == 90
    assert weight.sale_price == 90
    assert weight.comparison_price is None
    assert [offer.description for offer in weight.offers] == [
        "hemkop medlemspris",
        "Publikt kilopris",
    ]

    piece = disabled["disabled-piece"]
    assert piece.member_price == 7
    assert piece.effective_price == 10
    assert piece.sale_price == 10
    assert piece.piece_price == 10
    assert len(piece.offers) == 2
    assert piece.offers[1].required_packages == 3
    assert piece.offers[1].max_quantity == 2

    variable = disabled["disabled-variable"]
    assert variable.member_price == 40
    assert variable.effective_price == 50
    assert variable.sale_price == 50
    assert [offer.description for offer in variable.offers] == [
        "hemkop medlemspris",
        "Publikt paketpris",
    ]

    fixed = disabled["disabled-fixed-multibuy"]
    assert fixed.member_price == 10
    assert fixed.effective_price == 20
    assert len(fixed.offers) == 2
    assert fixed.offers[1].required_packages == 2
    assert fixed.offers[1].max_quantity == 1


@pytest.mark.asyncio
async def test_capped_non_fixed_prices_remain_metadata_not_unlimited_checkout_rates() -> None:
    store = _store(Chain.CITY_GROSS, "cg", provider="own")

    def capped_product(
        name: str,
        sale_model: SaleModel,
        *,
        member: bool,
    ) -> Product:
        regular = 100.0
        discounted = 60.0
        offer = OfferMetadata(
            kind=OfferKind.MEMBER if member else OfferKind.CAMPAIGN,
            description="Capped member price" if member else "Capped public price",
            price=discounted,
            max_quantity=3,
            member_program="City Gross Prio" if member else None,
        )
        fields: dict[str, object] = {
            "product_id": name,
            "name": name,
            "canonical_name": name,
            "canonical_food": name,
            "category": "Mat",
            "chain": Chain.CITY_GROSS.value,
            "store_id": "cg",
            "store_name": "City Gross",
            "sale_model": sale_model,
            "sale_price": discounted,
            "price": regular,
            "effective_price": discounted,
            "member_price": discounted if member else None,
            "offers": [offer],
            "semantic_confidence": SemanticConfidence.HIGH,
            "quantity_confidence": QuantityConfidence.EXACT,
            "source_provenance": _provenance("own", Chain.CITY_GROSS, "cg"),
        }
        if sale_model is SaleModel.SOLD_BY_WEIGHT:
            fields.update(
                sale_unit="kg",
                comparison_price=discounted,
                comparison_unit="kg",
                variable_weight=True,
            )
        elif sale_model is SaleModel.SOLD_BY_PIECE:
            fields.update(
                sale_unit="st",
                piece_price=discounted,
                package_quantity=1,
                package_unit="st",
                usable_quantity=1,
                usable_unit="st",
            )
        else:
            fields.update(
                sale_unit="kg",
                comparison_price=discounted,
                comparison_unit="kg",
                package_quantity=500,
                package_unit="g",
                usable_quantity=500,
                usable_unit="g",
                variable_weight=True,
            )
        return Product(**fields)

    products = [
        capped_product(
            f"{'member' if member else 'public'}-{sale_model.value}",
            sale_model,
            member=member,
        )
        for member in (False, True)
        for sale_model in (
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.SOLD_BY_PIECE,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        )
    ]
    provider = FederatedGroceryPriceProvider(
        [_binding(OWN_CATALOG, StubProvider([store], products), Chain.CITY_GROSS)],
        memberships={Chain.CITY_GROSS: True},
    )
    public_store = (await provider.find_stores("21120"))[0]

    rewritten = await provider.get_store_products(public_store.store_id)

    assert len(rewritten) == 6
    for product in rewritten:
        assert product.effective_price == 100
        assert product.sale_price == 100
        if product.sale_model is SaleModel.SOLD_BY_PIECE:
            assert product.piece_price == 100
        assert len(product.offers) == 1
        assert product.offers[0].max_quantity == 3
        if product.sale_model is not SaleModel.SOLD_BY_PIECE:
            assert product.comparison_price is None
        if product.sale_model is SaleModel.VARIABLE_WEIGHT_PACKAGE:
            assert product.sale_unit == ("kg" if product.name.startswith("member-") else None)
        if product.name.startswith("member-"):
            assert product.member_price == 60


@pytest.mark.asyncio
async def test_explicit_own_offer_channel_reuses_full_context_without_offer_as_catalog() -> None:
    offer = OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description="Veckans pris",
        price=15,
        max_quantity=2,
    )
    native = _store(Chain.WILLYS, "own", provider="own")
    own = StubProvider(
        [native],
        [_product(Chain.WILLYS, "own", "pasta", 20, provider="own", offers=[offer])],
    )
    provider = FederatedGroceryPriceProvider(
        [_binding(OWN_CATALOG, own, Chain.WILLYS)],
        offer_bindings=[_binding(OWN_OFFERS, own, Chain.WILLYS)],
    )
    store = (await provider.find_stores("21120"))[0]

    products = await provider.get_offers(store.store_id)

    assert len(products) == 1
    assert products[0].store_id == store.store_id
    assert products[0].offers[0].max_quantity == 2
    assert products[0].source_provenance is not None
    assert products[0].source_provenance.source_channel == "offers"


@pytest.mark.asyncio
async def test_connector_failure_isolated_and_own_only_excludes_licensed_primary() -> None:
    willys = StubProvider([], [], error=True)
    hemkop_store = _store(Chain.HEMKOP, "h", provider="own")
    hemkop = StubProvider([hemkop_store], [])
    primat_ica = StubProvider([_store(Chain.ICA, "i", provider="primat")], [])
    provider = FederatedGroceryPriceProvider(
        [
            _binding(OWN_CATALOG, willys, Chain.WILLYS),
            _binding(OWN_CATALOG, hemkop, Chain.HEMKOP),
            _binding(PRIMAT_CATALOG, primat_ica, Chain.ICA),
        ],
        own_sources_only=True,
    )

    stores = await provider.find_stores("21120")
    assert [store.chain for store in stores] == ["hemkop"]
    diagnostics = {item.chain: item for item in provider.diagnostics}
    assert diagnostics[Chain.WILLYS].provider_errors
    assert diagnostics[Chain.ICA].reason == "primary provider excluded by OWN-only policy"


@pytest.mark.asyncio
async def test_provenance_survives_candidate_optimizer_and_global_two_store_optimum() -> None:
    own_stores = [
        _store(Chain.WILLYS, "w", provider="own"),
        _store(Chain.HEMKOP, "h", provider="own"),
    ]
    primat_store = _store(Chain.ICA, "i", provider="primat")
    own_prices = {
        (Chain.WILLYS, "w"): {"ris": 1, "kyckling": 100, "ägg": 100},
        (Chain.HEMKOP, "h"): {"ris": 100, "kyckling": 1, "ägg": 10},
    }
    own_products = [
        _product(chain, store_id, food, price, provider="own")
        for (chain, store_id), prices in own_prices.items()
        for food, price in prices.items()
    ]
    primat_products = [
        _product(Chain.ICA, "i", food, price, provider="primat")
        for food, price in {"ris": 5, "kyckling": 100, "ägg": 1}.items()
    ]
    provider = FederatedGroceryPriceProvider(
        [
            _binding(
                OWN_CATALOG, StubProvider(own_stores, own_products), Chain.WILLYS, Chain.HEMKOP
            ),
            _binding(PRIMAT_CATALOG, StubProvider([primat_store], primat_products), Chain.ICA),
        ]
    )
    stores = await provider.find_stores("21120")
    products = await provider.get_store_products(stores[0].store_id)
    for store in stores[1:]:
        products.extend(await provider.get_store_products(store.store_id))
    candidates: dict[str, list[ProductCandidate]] = {
        food: [
            ProductCandidate.from_product(product, 1.0)
            for product in products
            if product.canonical_food == food
        ]
        for food in ("ris", "kyckling", "ägg")
    }
    ingredients = [
        NormalizedIngredient(canonical_name=food, required_quantity=1000, unit="g")
        for food in candidates
    ]

    basket = BasketOptimizer().optimize(ingredients, candidates, stores, max_stores=2)

    assert basket.total == 7
    assert basket.store_count == 2
    assert {group.store_name for group in basket.stores} == {
        "Hemkop Centrum",
        "Ica Centrum",
    }
    for group in basket.stores:
        for item in group.items:
            assert item.source_provenance is not None
            assert item.source_provenance.chain in {"hemkop", "ica"}
            assert item.source_provenance.store_id == item.store_id
            assert item.source_provenance.source_snapshot_id
