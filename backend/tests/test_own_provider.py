from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.config import Settings
from app.errors import PriceProviderError
from app.models import OfferKind, QuantityConfidence, SaleModel, SemanticConfidence
from app.providers.factory import create_price_provider
from app.providers.own import OwnGroceryPriceProvider

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)

BASE_URL = "http://grocery-data.test/"


def _fresh_metadata(**updates: object) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "snapshot_id": "snapshot-willys-1",
        "observed_at": datetime.now(tz=UTC).isoformat(),
        "data_age_hours": 0.1,
        "connector_status": "healthy",
    }
    metadata.update(updates)
    return metadata


def _envelope(items: list[dict[str, Any]], **updates: object) -> dict[str, Any]:
    return {"items": items, "count": len(items), **_fresh_metadata(**updates)}


def _store_row() -> dict[str, Any]:
    return {
        "id": "willys:2276",
        "chain": "willys",
        "external_id": "2276",
        "name": "Willys Lund Nova",
        "address": "Företagsvägen 10",
        "postal_code": "227 61",
        "city": "Lund",
        "latitude": 55.72,
        "longitude": 13.16,
        "coverage": "full_catalog",
        "active": True,
        **_fresh_metadata(),
    }


def _fixed_product(**updates: object) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "product-pasta",
        "chain": "willys",
        "external_product_id": "external-pasta",
        "gtin": "7310000000001",
        "name": "Spaghetti 1 kg",
        "brand": "Garant",
        "category_path": ["Skafferi", "Pasta"],
        "canonical_food": "pasta",
        "semantic_confidence": "high",
        "sale_model": "fixed_package",
        "quantity_confidence": "exact",
        "package_quantity": 1000,
        "package_unit": "g",
        "usable_quantity": 1000,
        "usable_unit": "g",
        "sale_price": 18.9,
        "regular_price": 22.9,
        "comparison_price": 18.9,
        "comparison_unit": "kg",
        "sale_unit": "st",
        "store_id": "willys:2276",
        "store_name": "Willys Lund Nova",
        "availability": "available",
        "promotions": [
            {
                "type": "sale_price",
                "price": 18.9,
                "quantity": 1,
                "description": "Veckans pris",
            }
        ],
    }
    row.update(updates)
    return row


@pytest.mark.asyncio
async def test_offer_mapping_preserves_source_purchase_cap() -> None:
    provider, client = _provider(lambda request: httpx.Response(500, request=request))
    try:
        offer = provider._offer_from_row(
            {
                "type": "multibuy",
                "price": 105,
                "quantity": 2,
                "max_quantity": 1,
                "member_only": True,
                "description": "2 för 105 kr, max 1 köp",
            },
            chain="coop",
        )
    finally:
        await client.aclose()

    assert offer is not None
    assert offer.max_quantity == 1
    assert offer.eligibility is PromotionEligibility.MEMBER
    assert offer.mechanism is PromotionMechanism.MULTIBUY
    assert offer.membership_program is MembershipProgram.COOP_MEMBER

    provider, client = _provider(
        lambda request: httpx.Response(500, request=request), use_member_prices=True
    )
    try:
        offer = provider._offer_from_row(
            {
                "type": "multibuy",
                "price": 105,
                "quantity": 2,
                "max_quantity": 1,
                "member_only": True,
                "description": "2 för 105 kr, max 1 köp",
            },
            chain="coop",
        )
    finally:
        await client.aclose()

    assert offer is not None
    assert offer.max_quantity == 1
    assert offer.eligibility is PromotionEligibility.MEMBER
    assert offer.mechanism is PromotionMechanism.MULTIBUY
    assert offer.membership_program is MembershipProgram.COOP_MEMBER


@pytest.mark.asyncio
async def test_member_multibuy_quantity_one_becomes_generic_member_unit_sale() -> None:
    provider, client = _provider(lambda request: httpx.Response(500, request=request))
    try:
        offer = provider._offer_from_row(
            {
                "type": "multibuy",
                "price": 19.95,
                "quantity": 1,
                "member_only": True,
                "description": "Medlem: 1 för 19,95 kr",
            },
            chain="hemkop",
        )
    finally:
        await client.aclose()

    assert provider.use_member_prices is False
    assert offer is not None
    assert offer.kind is OfferKind.MEMBER
    assert offer.required_packages == 1
    assert offer.price == 19.95
    assert offer.eligibility is PromotionEligibility.MEMBER
    assert offer.mechanism is PromotionMechanism.SALE_PRICE
    assert offer.membership_program is MembershipProgram.HEMKOP_MEMBER


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    use_member_prices: bool = False,
    max_age_hours: float = 48,
    include_offers_only: bool = False,
) -> tuple[OwnGroceryPriceProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return (
        OwnGroceryPriceProvider(
            BASE_URL,
            use_member_prices=use_member_prices,
            max_age_hours=max_age_hours,
            include_offers_only=include_offers_only,
            client=client,
        ),
        client,
    )


@pytest.mark.asyncio
async def test_maps_stores_and_uses_public_postal_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stores"
        assert request.url.params["postal_code"] == "22350"
        return httpx.Response(200, json=_envelope([_store_row()]), request=request)

    provider, client = _provider(handler)
    try:
        stores = await provider.find_stores("223 50")
    finally:
        await client.aclose()

    assert len(stores) == 1
    assert stores[0].store_id == "willys:2276"
    assert stores[0].postal_code == "22761"
    assert stores[0].tier == "full_catalog"
    assert stores[0].source_provenance is not None
    assert stores[0].source_provenance.source_provider == "own"
    assert stores[0].source_provenance.source_snapshot_id == "snapshot-willys-1"


@pytest.mark.asyncio
async def test_maps_explicit_price_context_without_chain_special_cases() -> None:
    row = {
        **_store_row(),
        "id": "citygross:3211",
        "chain": "citygross",
        "external_id": "3211",
        "name": "City Gross Online – Malmö Hyllie",
        "city": "Malmö",
        "postal_code": "21534",
        "coverage": "full_online_catalog",
        "price_context_type": "online_store",
        "physical_store_external_id": "169",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([row]), request=request)

    provider, client = _provider(handler)
    try:
        stores = await provider.find_stores("21534")
    finally:
        await client.aclose()

    assert len(stores) == 1
    assert stores[0].price_context_type == "online_store"
    assert stores[0].physical_store_external_id == "169"


@pytest.mark.asyncio
async def test_offers_only_store_never_enters_catalog_discovery() -> None:
    offer_store = {
        **_store_row(),
        "id": "ica:1088004",
        "chain": "ica",
        "coverage": "offers_only",
        "postal_code": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([offer_store]), request=request)

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22350")
    finally:
        await client.aclose()

    provider, client = _provider(handler, include_offers_only=True)
    try:
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22350")
        stores = await provider.find_offer_stores("22350")
    finally:
        await client.aclose()
    assert [store.tier for store in stores] == ["offers_only"]
    assert stores[0].postal_code is None


@pytest.mark.asyncio
async def test_partial_catalog_store_never_enters_global_basket_discovery() -> None:
    partial_store = {
        **_store_row(),
        "id": "coop:partial",
        "chain": "coop",
        "coverage": "partial_catalog",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([partial_store]), request=request)

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22350")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_catalog_store_without_source_postal_code_remains_ineligible() -> None:
    catalog_store = {**_store_row(), "postal_code": None}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([catalog_store]), request=request)

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22350")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_offer_store_discovery_requires_explicit_diagnostic_opt_in() -> None:
    offer_store = {**_store_row(), "id": "ica:1088004", "chain": "ica", "coverage": "offers_only"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([offer_store]), request=request)

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderError, match="explicit opt-in"):
            await provider.find_offer_stores("22350")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_store_discovery_isolates_broken_chain_from_healthy_store() -> None:
    broken = {
        **_store_row(),
        "id": "coop:broken",
        "chain": "coop",
        "external_id": "broken",
        "name": "Trasig Coop",
        "connector_status": "broken",
        "snapshot_id": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                [broken, _store_row()],
                connector_status="broken",
                snapshot_id=None,
            ),
            request=request,
        )

    provider, client = _provider(handler)
    try:
        stores = await provider.find_stores("22350")
    finally:
        await client.aclose()

    assert [store.store_id for store in stores] == ["willys:2276"]


@pytest.mark.asyncio
async def test_store_discovery_fails_when_every_store_is_unverified() -> None:
    broken = {
        **_store_row(),
        "connector_status": "broken",
        "snapshot_id": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([broken]), request=request)

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22350")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_search_maps_fixed_package_campaign_without_package_inference() -> None:
    seen_store_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/products/search"
        seen_store_ids.extend(request.url.params.get_list("store_id"))
        return httpx.Response(200, json=_envelope([_fixed_product()]), request=request)

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("pasta", ["willys:2276"])
    finally:
        await client.aclose()

    assert seen_store_ids == ["willys:2276"]
    product = products[0]
    assert product.sale_model == SaleModel.FIXED_PACKAGE
    assert product.package_quantity == 1000
    assert product.usable_quantity == 1000
    assert product.price == 22.9
    assert product.effective_price == 18.9
    assert product.offers[0].kind == OfferKind.CAMPAIGN
    assert product.source_provenance is not None
    assert product.source_provenance.source_provider == "own"
    assert product.source_provenance.source_channel == "catalog"
    assert product.source_provenance.source_snapshot_id == "snapshot-willys-1"


@pytest.mark.asyncio
async def test_shared_own_row_retains_member_unit_and_member_multibuy_contracts() -> None:
    row = _fixed_product(
        member_price=15.9,
        promotions=[
            {
                "type": "sale_price",
                "price": 18.9,
                "quantity": 1,
                "description": "Publik kampanj",
            },
            {
                "type": "member_price",
                "price": 15.9,
                "quantity": 1,
                "member_only": True,
                "description": "Willys Plus-pris",
            },
            {
                "type": "multibuy",
                "price": 28,
                "quantity": 2,
                "member_only": True,
                "description": "Willys Plus: 2 för 28 kr",
            },
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([row]), request=request)

    provider, client = _provider(handler, use_member_prices=False)
    try:
        product = (await provider.search_products("pasta", ["willys:2276"]))[0]
    finally:
        await client.aclose()

    assert product.price == 22.9
    assert product.effective_price == 18.9
    assert product.member_price == 15.9
    member_unit = next(offer for offer in product.offers if offer.kind is OfferKind.MEMBER)
    member_multi = next(
        offer
        for offer in product.offers
        if offer.mechanism is PromotionMechanism.MULTIBUY
        and offer.eligibility is PromotionEligibility.MEMBER
    )
    assert member_unit.membership_program is MembershipProgram.WILLYS_PLUS
    assert member_unit.price == 15.9
    assert member_multi.membership_program is MembershipProgram.WILLYS_PLUS
    assert member_multi.required_packages == 2
    assert member_multi.price == 28


@pytest.mark.asyncio
async def test_recipe_alias_search_uses_exact_structured_food_identity() -> None:
    peas = _fixed_product(
        id="peas",
        external_product_id="peas",
        name="Små Fina Ärter 250 g",
        canonical_food="peas",
        package_quantity=250,
        usable_quantity=250,
        sale_price=24.9,
        regular_price=24.9,
        promotions=[],
    )

    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        assert request.url.path == "/products/search"
        assert request.url.params["q"] == "peas"
        assert request.url.params["canonical_food"] == "peas"
        return httpx.Response(200, json=_envelope([peas]), request=request)

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("gröna ärtor", ["willys:2276"])
        cached = await provider.search_products("gröna ärtor", ["willys:2276"])
    finally:
        await client.aclose()

    assert [product.product_id for product in products] == ["peas"]
    assert [product.product_id for product in cached] == ["peas"]
    assert request_count == 1


@pytest.mark.asyncio
async def test_ambiguous_recipe_alias_uses_exact_identity_union_and_safe_literals() -> None:
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.url.params["q"],
                request.url.params.get("canonical_food"),
            )
        )
        return httpx.Response(200, json=_envelope([]), request=request)

    provider, client = _provider(handler)
    try:
        assert await provider.search_products("röda linser", ["willys:2276"]) == []
    finally:
        await client.aclose()

    assert seen == [
        ("lentil", "lentil"),
        ("red_lentils", "red_lentils"),
        ("röda linser", None),
        ("linser röda", None),
    ]


@pytest.mark.asyncio
async def test_legacy_snapshot_alias_fallback_is_store_bounded_and_deduplicated() -> None:
    modern = _fixed_product(
        id="modern-onion",
        external_product_id="modern-onion",
        name="Gul Lök 1 kg",
        canonical_food="yellow_onion",
        store_id="willys:modern",
        store_name="Willys Modern",
    )
    legacy = _fixed_product(
        id="legacy-onion",
        external_product_id="legacy-onion",
        name="Lök Gul 1 kg",
        canonical_food=None,
        store_id="willys:legacy",
        store_name="Willys Legacy",
    )
    seen: list[tuple[str, str | None, tuple[str, ...]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        canonical_food = request.url.params.get("canonical_food")
        store_ids = tuple(request.url.params.get_list("store_id"))
        seen.append((query, canonical_food, store_ids))
        if canonical_food == "yellow_onion":
            rows = [modern]
        elif query in {"gul lök", "lök gul"}:
            # The legacy backend can return the same exact product for more
            # than one curated alias; provider identity must collapse it.
            rows = [legacy]
        else:  # pragma: no cover - makes an unexpected query fail loudly
            raise AssertionError(f"unexpected query {query!r}")
        return httpx.Response(200, json=_envelope(rows), request=request)

    provider, client = _provider(handler)
    try:
        products = await provider.search_products(
            "yellow_onion",
            ["willys:modern", "willys:legacy"],
        )
    finally:
        await client.aclose()

    assert {(product.store_id, product.product_id) for product in products} == {
        ("willys:modern", "modern-onion"),
        ("willys:legacy", "legacy-onion"),
    }
    assert seen == [
        (
            "yellow_onion",
            "yellow_onion",
            ("willys:legacy", "willys:modern"),
        ),
        ("gul lök", None, ("willys:legacy",)),
        ("lök gul", None, ("willys:legacy",)),
    ]


@pytest.mark.asyncio
async def test_cross_chain_results_preserve_independent_source_lineage() -> None:
    observed_at = datetime.now(tz=UTC).isoformat()
    willys_store = _store_row()
    coop_store = {
        **_store_row(),
        "id": "coop:lund",
        "external_id": "coop-lund",
        "chain": "coop",
        "name": "Coop Lund",
        "coverage": "full_online_catalog",
        "snapshot_id": "snapshot-coop-1",
        "source_provider": "own",
        "source_snapshot_id": "snapshot-coop-1",
        "source_observed_at": observed_at,
    }
    willys_product = {
        **_fixed_product(),
        "source_provider": "own",
        "source_snapshot_id": "snapshot-willys-1",
        "source_observed_at": observed_at,
    }
    coop_product = {
        **_fixed_product(
            id="coop-pasta",
            external_product_id="coop-pasta",
            store_id="coop:lund",
            store_name="Coop Lund",
        ),
        "chain": "coop",
        "source_provider": "own",
        "source_snapshot_id": "snapshot-coop-1",
        "source_observed_at": observed_at,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/stores":
            return httpx.Response(
                200,
                json=_envelope([willys_store, coop_store]),
                request=request,
            )
        assert request.url.path == "/products/search"
        assert set(request.url.params.get_list("store_id")) == {
            "willys:2276",
            "coop:lund",
        }
        return httpx.Response(
            200,
            json=_envelope([willys_product, coop_product]),
            request=request,
        )

    provider, client = _provider(handler)
    try:
        stores = await provider.find_stores("22350")
        products = await provider.search_products(
            "pasta",
            [store.store_id for store in stores],
        )
    finally:
        await client.aclose()

    assert {store.chain for store in stores} == {"willys", "coop"}
    assert {
        product.source_provenance.source_snapshot_id
        for product in products
        if product.source_provenance is not None
    } == {"snapshot-willys-1", "snapshot-coop-1"}


@pytest.mark.asyncio
async def test_old_snapshot_pet_food_metadata_is_rejected_at_provider_boundary() -> None:
    pet_food = _fixed_product(
        id="pet-food",
        name="Adult Kyckling-potatis Torrfoder Hund",
        canonical_food="chicken_meat",
        semantic_confidence="high",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([pet_food]), request=request)

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("kyckling", ["willys:2276"]))[0]
    finally:
        await client.aclose()

    assert product.canonical_food == "non_human_food"
    assert product.product_role == "non_human_food"
    assert product.product_form == "pet_food"
    assert product.semantic_confidence == SemanticConfidence.REJECTED


@pytest.mark.asyncio
async def test_provider_preserves_legitimate_chicken_fillet_semantics() -> None:
    chicken = _fixed_product(
        id="chicken",
        name="Kycklingfilé 1 kg",
        canonical_food="chicken_meat",
        semantic_confidence="high",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([chicken]), request=request)

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("kyckling", ["willys:2276"]))[0]
    finally:
        await client.aclose()

    assert product.canonical_food == "chicken"
    assert product.product_role == "generic_meat"
    assert product.semantic_confidence == SemanticConfidence.HIGH


@pytest.mark.asyncio
async def test_catalog_maps_explicit_sold_by_weight_without_one_kg_package() -> None:
    pepper = _fixed_product(
        id="product-pepper",
        name="Paprika Röd",
        canonical_food="red_pepper",
        sale_model="sold_by_weight",
        quantity_confidence="derived",
        package_quantity=None,
        package_unit=None,
        usable_quantity=None,
        usable_unit=None,
        sale_price=39.9,
        regular_price=None,
        comparison_price=39.9,
        comparison_unit="kg",
        sale_unit="kg",
        promotions=[],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path in {"/catalog/willys:2276", "/catalog/willys%3A2276"}
        return httpx.Response(200, json=_envelope([pepper]), request=request)

    provider, client = _provider(handler)
    try:
        products = await provider.get_store_products("willys:2276")
    finally:
        await client.aclose()

    product = products[0]
    assert product.sale_model == SaleModel.SOLD_BY_WEIGHT
    assert product.sale_price == 39.9
    assert product.sale_unit == "kg"
    assert product.package_quantity is None
    assert product.usable_quantity is None
    assert product.canonical_food == "pepper"


@pytest.mark.asyncio
async def test_comparison_price_alone_never_creates_package_or_weight_model() -> None:
    ambiguous = _fixed_product(
        id="ambiguous-pepper",
        name="Paprika Röd",
        sale_model="unknown",
        quantity_confidence="unknown",
        package_quantity=None,
        package_unit=None,
        usable_quantity=None,
        usable_unit=None,
        sale_price=10.79,
        regular_price=None,
        comparison_price=39.9,
        comparison_unit="kg",
        sale_unit=None,
        promotions=[],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([ambiguous]), request=request)

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("paprika", ["willys:2276"]))[0]
    finally:
        await client.aclose()

    assert product.sale_model == SaleModel.UNKNOWN
    assert product.quantity_confidence == QuantityConfidence.UNKNOWN
    assert product.package_quantity is None
    assert product.comparison_price == 39.9


@pytest.mark.asyncio
async def test_source_native_comparison_unit_preserves_product_and_member_offer() -> None:
    detergent = _fixed_product(
        id="detergent",
        chain="hemkop",
        name="Color Sensitive Tvättkapslar",
        canonical_food=None,
        package_quantity=16,
        package_unit="st",
        usable_quantity=16,
        usable_unit="st",
        sale_price=42.95,
        regular_price=42.95,
        comparison_price=2.68,
        comparison_unit="tvätt",
        promotions=[
            {
                "type": "member_price",
                "price": 35,
                "quantity": 1,
                "member_only": True,
                "description": "Klubbpris",
                "valid_to": "2026-09-06",
            }
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([detergent]), request=request)

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("tvätt", ["willys:2276"]))[0]
    finally:
        await client.aclose()

    assert product.comparison_price == 2.68
    assert product.comparison_unit == "tvätt"
    assert len(product.offers) == 1
    assert product.offers[0].eligibility is PromotionEligibility.MEMBER
    assert product.offers[0].membership_program is MembershipProgram.HEMKOP_MEMBER


@pytest.mark.asyncio
async def test_missing_comparison_unit_drops_rate_pair_not_product() -> None:
    product_row = _fixed_product(
        comparison_price=2.68,
        comparison_unit="",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([product_row]), request=request)

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("pasta", ["willys:2276"]))[0]
    finally:
        await client.aclose()

    assert product.comparison_price is None
    assert product.comparison_unit is None


@pytest.mark.asyncio
async def test_sold_by_piece_maps_estimated_weight_and_piece_price() -> None:
    onion = _fixed_product(
        id="product-onion",
        name="Gul lök",
        canonical_food="onion",
        sale_model="sold_by_piece",
        quantity_confidence="estimated",
        package_quantity=1,
        package_unit="st",
        usable_quantity=1,
        usable_unit="st",
        average_weight_kg=0.175,
        sale_price=3,
        regular_price=3,
        comparison_price=None,
        comparison_unit=None,
        sale_unit="st",
        promotions=[],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([onion]), request=request)

    provider, client = _provider(handler)
    try:
        product = (await provider.get_store_products("willys:2276"))[0]
    finally:
        await client.aclose()

    assert product.sale_model == SaleModel.SOLD_BY_PIECE
    assert product.piece_price == 3
    assert product.estimated_piece_weight == pytest.approx(175)
    assert product.canonical_food == "yellow_onion"


@pytest.mark.asyncio
async def test_multipack_remains_conditional_structured_offer() -> None:
    product_row = _fixed_product(
        sale_price=22.9,
        regular_price=22.9,
        promotions=[
            {
                "type": "multibuy",
                "price": 35,
                "quantity": 2,
                "description": "2 för 35 kr",
                "member_only": False,
            }
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([product_row]), request=request)

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("pasta", ["willys:2276"]))[0]
    finally:
        await client.aclose()

    assert product.effective_price == 22.9
    assert product.offers == [product.offers[0]]
    assert product.offers[0].kind == OfferKind.MULTIPACK
    assert product.offers[0].required_packages == 2
    assert product.offers[0].price == 35


@pytest.mark.asyncio
async def test_get_offers_uses_embedded_offer_product_without_catalog_read() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/offers":
            return httpx.Response(
                200,
                json=_envelope(
                    [
                        {
                            "type": "multibuy",
                            "price": 35,
                            "quantity": 2,
                            "description": "2 för 35 kr",
                            "product_id": "product-pasta",
                            "store_id": "willys:2276",
                            "chain": "willys",
                            "product": _fixed_product(
                                sale_price=22.9,
                                regular_price=22.9,
                                promotions=[],
                            ),
                        }
                    ]
                ),
                request=request,
            )
        return httpx.Response(500, request=request)

    provider, client = _provider(handler)
    try:
        products = await provider.get_offers("willys:2276")
    finally:
        await client.aclose()

    assert calls[0] == "/offers"
    assert calls == ["/offers"]
    assert products[0].offers[0].kind == OfferKind.MULTIPACK


@pytest.mark.asyncio
async def test_offers_only_conditional_price_never_falls_back_to_catalog() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/offers":
            return httpx.Response(
                200,
                json=_envelope(
                    [
                        {
                            "type": "multibuy",
                            "price": 59,
                            "quantity": 2,
                            "description": "2 för 59 kr",
                            "product_id": "coop-group",
                            "store_id": "coop:2696",
                            "chain": "coop",
                            "store_coverage": "offers_only",
                            "source_channel": "offers",
                            "product": {
                                **_fixed_product(
                                    id="coop-group",
                                    store_id="coop:2696",
                                    chain="coop",
                                    sale_price=None,
                                    regular_price=None,
                                    promotions=[],
                                ),
                                "source_channel": "offers",
                            },
                        }
                    ]
                ),
                request=request,
            )
        return httpx.Response(500, request=request)

    provider, client = _provider(handler, include_offers_only=True)
    try:
        products = await provider.get_offers("coop:2696")
    finally:
        await client.aclose()

    assert calls == ["/offers"]
    assert products == []


@pytest.mark.parametrize("status", ["broken", "degraded", "unknown", "unverified"])
@pytest.mark.asyncio
async def test_rejects_nonhealthy_connector_status(status: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope([_fixed_product()], connector_status=status),
            request=request,
        )

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderError, match="inte verifierad"):
            await provider.search_products("pasta", ["willys:2276"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["healthy", "stale"])
async def test_retains_old_promoted_snapshot(status) -> None:
    stale_time = datetime.now(tz=UTC) - timedelta(hours=72)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                [_fixed_product()],
                observed_at=stale_time.isoformat(),
                data_age_hours=72,
                connector_status=status,
            ),
            request=request,
        )

    provider, client = _provider(handler, max_age_hours=48)
    try:
        products = await provider.search_products("pasta", ["willys:2276"])
        assert products
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_missing_snapshot_and_freshness_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [_fixed_product()]}, request=request)

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderError, match="saknar verifierbar"):
            await provider.search_products("pasta", ["willys:2276"])
    finally:
        await client.aclose()


def test_factory_supports_explicit_own_provider() -> None:
    provider = create_price_provider(
        Settings(
            price_provider="own",
            own_grocery_base_url=BASE_URL,
            own_grocery_max_age_hours=24,
        )
    )
    assert isinstance(provider, OwnGroceryPriceProvider)
    assert provider.max_age_hours == 24


def test_factory_requires_own_base_url() -> None:
    with pytest.raises(ValueError, match="OWN_GROCERY_BASE_URL"):
        create_price_provider(Settings(price_provider="own"))


@pytest.mark.asyncio
async def test_query_coverage_uses_registry_contract_without_enabling_offers_catalog() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/registry/ica/stores/ica-store/basket-coverage"
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={
                "requested_ingredients": 2,
                "safely_priced_ingredients": 1,
                "coverage_ratio": 0.5,
                "complete_for_request": False,
                "missing_ingredients": ["ägg"],
            },
            request=request,
        )

    provider, client = _provider(handler)
    try:
        result = await provider.get_query_coverage("ica-store", ["mjölk", "ägg"])
    finally:
        await client.aclose()
    assert not result["complete_for_request"]
    assert result["missing_ingredients"] == ["ägg"]


def test_optional_relay_provenance_preserves_legacy_serialization():
    from app.models.provenance import SourceProvenance

    legacy = SourceProvenance(
        source_provider="own",
        source_channel="catalog",
        source_snapshot_id="prior",
        source_observed_at=datetime.now(UTC),
    )
    assert "collection_location" not in legacy.model_dump(mode="json")
    relay = legacy.model_copy(update={"collection_location": "LOCAL_RELAY"})
    assert relay.model_dump(mode="json")["collection_location"] == "LOCAL_RELAY"
    assert relay.source_provider == "own"
