from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx
import pytest
from app.errors import (
    PriceProviderAuthenticationError,
    PriceProviderRateLimitError,
)
from app.models import NormalizedIngredient, OfferKind, ProductCandidate
from app.models.product import QuantityConfidence, SaleModel
from app.providers.primat import PrimatPriceProvider
from app.services.basket_calculator import BasketCalculator
from app.services.product_matcher import ProductMatcher

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)

BASE_URL = "https://primat.nu/api/v3/"


def _json_response(
    request: httpx.Request,
    payload: dict[str, Any],
    status: int = 200,
) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    use_member_prices: bool = False,
) -> tuple[PrimatPriceProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        transport=httpx.MockTransport(handler),
    )
    return (
        PrimatPriceProvider(
            api_key="primat_live_test",
            use_member_prices=use_member_prices,
            client=client,
        ),
        client,
    )


def _prices(
    *,
    regular: float | None,
    member: float | None = None,
    multiprice: tuple[float, int] | None = None,
    member_multiprice: tuple[float, int] | None = None,
    offer: dict[str, Any] | None = None,
    comparison: tuple[float, str] | None = None,
) -> dict[str, Any]:
    return {
        "regular": regular,
        "member": member,
        "multiprice": {
            "price": multiprice[0] if multiprice else None,
            "quantity": multiprice[1] if multiprice else None,
        },
        "member_multiprice": {
            "price": member_multiprice[0] if member_multiprice else None,
            "quantity": member_multiprice[1] if member_multiprice else None,
        },
        "comparison": (
            {"price": comparison[0], "unit": comparison[1]} if comparison is not None else None
        ),
        "offer": offer,
        # This convenience fold can include member/multibuy prices. The adapter
        # must deliberately derive eligibility from the individual facts.
        "effective": min(
            value
            for value in (
                regular,
                member,
                multiprice[0] if multiprice else None,
                member_multiprice[0] if member_multiprice else None,
                offer.get("price") if offer else None,
            )
            if value is not None
        ),
    }


def _product_row(
    product_id: str,
    *,
    prices: dict[str, Any],
    name: str = "Garant Pasta",
    amount: float = 500,
    unit: str = "g",
    chain: str = "willys",
    store_id: str = "2354",
) -> dict[str, Any]:
    return {
        "chain": chain,
        "store_id": store_id,
        "product_id": product_id,
        "name": name,
        "brand": "Garant",
        "category": "Skafferi > Pasta",
        "amount": amount,
        "unit": unit,
        "package": f"{amount} {unit}",
        "available": True,
        "prices": prices,
    }


@pytest.mark.parametrize(
    ("name", "package", "expected"),
    [
        ("Fläskfilé Klass 1", "500 g", False),
        ("Påskmust", "1 flaska", False),
        ("Morötter ask", None, True),
        ("Paprika 2-pack", None, True),
        ("Morötter 1 kg", None, True),
    ],
)
def test_packaging_evidence_is_token_bound(
    name: str,
    package: str | None,
    expected: bool,
) -> None:
    assert PrimatPriceProvider._looks_explicitly_packaged(name, package) is expected


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf"), "NaN", "Infinity", "-Infinity"],
)
def test_positive_float_rejects_non_finite_values(value: object) -> None:
    assert PrimatPriceProvider._positive_float(value) is None


@pytest.mark.asyncio
async def test_non_finite_explicit_unit_rate_and_campaign_offer_fail_closed() -> None:
    invalid_weight_offer = {
        "price": "Infinity",
        "label": "39,90 kr/kg",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }
    invalid_package_offer = {
        "price": "Infinity",
        "label": "Veckans pris",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def prices_with_invalid_offer(regular: float, offer: dict[str, Any]) -> dict[str, Any]:
        prices = _prices(regular=regular)
        prices["offer"] = offer
        return prices

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "paprika-rate",
                        name="Paprika Röd Klass 1",
                        amount=200,
                        unit="g",
                        prices=prices_with_invalid_offer(49.90, invalid_weight_offer),
                    )
                    | {"category": "Färsk > Frukt/Grönt/Blommor"},
                    _product_row(
                        "pasta-offer",
                        name="Garant Pasta 500 g",
                        prices=prices_with_invalid_offer(20, invalid_package_offer),
                    ),
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("mat", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    assert by_id["paprika-rate"].sale_model == SaleModel.UNKNOWN
    assert by_id["paprika-rate"].offers == []
    assert by_id["pasta-offer"].effective_price == 20
    assert by_id["pasta-offer"].offers == []

    ingredient = NormalizedIngredient(
        canonical_name="paprika",
        required_quantity=350,
        unit="g",
    )
    assert ProductMatcher().match(ingredient, [by_id["paprika-rate"]]) == []


@pytest.mark.parametrize(
    ("amount", "expected_quantity", "expected_confidence"),
    [
        (None, 500, QuantityConfidence.DERIVED),
        (250, 500, QuantityConfidence.DERIVED),
        (500, 500, QuantityConfidence.EXACT),
    ],
)
def test_multiplicative_package_text_represents_the_complete_package(
    amount: float | None,
    expected_quantity: float,
    expected_confidence: QuantityConfidence,
) -> None:
    result = PrimatPriceProvider._normalise_package(
        amount,
        "g" if amount is not None else None,
        "2 x 250 g",
        "Pasta 2 x 250 g",
    )

    assert result == (expected_quantity, "g", expected_confidence)


def test_conflicting_structured_and_multiplicative_package_quantities_fail_closed() -> None:
    assert (
        PrimatPriceProvider._normalise_package(
            300,
            "g",
            "2 x 250 g",
            "Pasta 2 x 250 g",
        )
        is None
    )


def test_conflicting_structured_and_visible_package_quantities_fail_closed() -> None:
    assert (
        PrimatPriceProvider._normalise_package(
            500,
            "g",
            "500 g",
            "Pasta 1 kg",
        )
        is None
    )


def test_multi_quantity_product_name_requires_a_reconciled_structured_total() -> None:
    assert (
        PrimatPriceProvider._normalise_package(
            500,
            "g",
            "500 g",
            "Matkit pasta 500 g sås 200 g",
        )
        is None
    )
    assert PrimatPriceProvider._normalise_package(
        700,
        "g",
        "700 g",
        "Matkit pasta 500 g sås 200 g",
    ) == (700, "g", QuantityConfidence.EXACT)
    assert (
        PrimatPriceProvider._normalise_package(
            None,
            None,
            None,
            "Matkit pasta 500 g sås 200 g",
        )
        is None
    )
    assert (
        PrimatPriceProvider._normalise_package(
            None,
            None,
            None,
            "Matkit pasta 500 g sås 500 g",
        )
        is None
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Paprika Röd Klass 1", "produce"),
        ("Paprikor Röda Klass 1", "produce"),
        ("Morot Klass 1", "produce"),
        ("Lök Gul Klass 1", "produce"),
        ("Gula lökar Klass 1", "produce"),
        ("Gurkor Klass 1", "produce"),
        ("Bananer Klass 1", "produce"),
        ("Citroner Klass 1", "produce"),
        ("Avokados Klass 1", "produce"),
        ("Potatis Klass 1", "produce"),
        ("Avokado", "produce"),
        ("Paprikapulver", None),
        ("Potatissallad", None),
        ("Baguetter Vitlök", None),
        ("Krossade tomater", None),
    ],
)
def test_shallow_category_produce_recognition_is_whole_token_based(
    name: str,
    expected: str | None,
) -> None:
    assert PrimatPriceProvider._fresh_product_kind(name, "") == expected


@pytest.mark.asyncio
async def test_plural_loose_produce_without_category_never_becomes_a_fixed_package() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "7310000000010",
                        name="Paprikor Röda Klass 1",
                        amount=1000,
                        unit="g",
                        prices=_prices(regular=10.79, comparison=(10.79, "kg")),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "",
                        "package": "1kg",
                    },
                    _product_row(
                        "2317468800003",
                        name="Gula lökar Klass 1",
                        amount=1000,
                        unit="g",
                        prices=_prices(regular=12.90, comparison=(12.90, "kg")),
                    )
                    | {
                        "gtin": "2317468800003",
                        "category": "",
                        "package": "1kg",
                    },
                    _product_row(
                        "2359634700007",
                        name="Gurkor Klass 1",
                        amount=1000,
                        unit="g",
                        prices=_prices(regular=10.79, comparison=(39.90, "kg")),
                    )
                    | {
                        "gtin": "2359634700007",
                        "category": "",
                        "package": "1kg",
                    },
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("klass 1", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    fixed_gtin = by_id["7310000000010"]
    assert fixed_gtin.sale_model == SaleModel.UNKNOWN
    assert fixed_gtin.package_quantity is None
    assert fixed_gtin.quantity_confidence == QuantityConfidence.UNKNOWN

    variable_gtin = by_id["2317468800003"]
    assert variable_gtin.sale_model == SaleModel.SOLD_BY_WEIGHT
    assert variable_gtin.package_quantity is None
    assert variable_gtin.sale_price == 12.90
    assert variable_gtin.sale_unit == "kg"
    assert variable_gtin.quantity_confidence == QuantityConfidence.DERIVED

    incomplete_rate = by_id["2359634700007"]
    assert incomplete_rate.sale_model == SaleModel.UNKNOWN
    assert incomplete_rate.package_quantity is None
    assert incomplete_rate.quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.asyncio
async def test_resolve_uses_postcode_bearer_auth_and_composite_store_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/stores/resolve"
        assert dict(request.url.params) == {"postcode": "22350"}
        assert request.headers["Authorization"] == "Bearer primat_live_test"
        return _json_response(
            request,
            {
                "place": {
                    "locality": "Lund",
                    "postal_code": "22350",
                    "latitude": 55.7028,
                    "longitude": 13.1927,
                },
                "default_selection": ["willys:2354", "ica:1004409"],
                "stores": [
                    {
                        "chain": "willys",
                        "store_id": "2354",
                        "key": "willys:2354",
                        "name": "Willys Lund Nova",
                        "city": "Lund",
                        "postal_code": "22350",
                        "latitude": 55.7028,
                        "longitude": 13.1927,
                        "km": 2.4,
                        "tier": "full",
                        "selected": True,
                    },
                    {
                        "chain": "ica",
                        "store_id": "1004409",
                        # Verify the documented chain:id fallback as well.
                        "name": "ICA Kvantum Clemenstorget",
                        "city": "Lund",
                        "km": 0.5,
                        "tier": "full",
                        "selected": True,
                    },
                    {
                        "chain": "coop",
                        "store_id": "106430",
                        "key": "coop:106430",
                        "name": "Coop Mårtenstorget",
                        "city": "Lund",
                        "km": 0.3,
                        "tier": "offers_only",
                        "selected": False,
                    },
                ],
            },
        )

    provider, client = _provider(handler)
    try:
        stores = await provider.find_stores("223 50")
    finally:
        await client.aclose()

    assert [store.store_id for store in stores] == ["willys:2354", "ica:1004409"]
    assert stores[0].name == "Willys Lund Nova"
    assert stores[0].city == "Lund"
    assert stores[0].postal_code == "22350"
    assert stores[0].distance_km == 2.4
    assert stores[0].tier == "full"
    assert stores[0].latitude == 55.7028
    assert stores[0].longitude == 13.1927


@pytest.mark.asyncio
async def test_store_candidate_resolution_keeps_unselected_public_rows_and_safe_metadata() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _json_response(
            request,
            {
                "place": {"locality": "Lund", "postal_code": "22350"},
                "default_selection": ["ica:selected"],
                "stores": [
                    {
                        "chain": "ica",
                        "store_id": "selected",
                        "key": "ica:selected",
                        "name": "ICA Selected",
                        "selected": True,
                        "tier": "full",
                    },
                    {
                        "chain": "coop",
                        "store_id": "unselected",
                        "key": "coop:unselected",
                        "name": "Coop Unselected",
                        "selected": False,
                        "tier": "full",
                    },
                    {
                        "chain": "coop",
                        "store_id": "staff",
                        "key": "coop:staff",
                        "name": "Endast Personal Lund",
                        "selected": False,
                        "tier": "full",
                    },
                ],
            },
        )

    provider, client = _provider(handler)
    try:
        resolution = await provider.resolve_store_candidates("22350")
    finally:
        await client.aclose()

    assert calls == 1
    assert resolution.raw_rows == 3
    assert [row.store_id for row in resolution.stores] == [
        "ica:selected",
        "coop:unselected",
    ]
    assert resolution.selected_context_ids == frozenset({"ica:selected"})
    assert resolution.response_status == 200
    assert resolution.response_content_type.startswith("application/json")
    assert resolution.response_host == "primat.nu"
    assert resolution.response_path == "/api/v3/stores/resolve"
    assert len(resolution.response_sha256) == 64


@pytest.mark.asyncio
async def test_resolve_excludes_explicit_non_customer_contexts_even_when_selected_full() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "place": {"locality": "Malmö", "postal_code": "21120"},
                "default_selection": [
                    "coop:staff",
                    "coop:internal",
                    "coop:public",
                    "coop:personalvagen",
                ],
                "stores": [
                    {
                        "chain": "coop",
                        "store_id": "staff",
                        "key": "coop:staff",
                        "name": "Endast Personal DS Syd",
                        "tier": "full",
                        "selected": True,
                    },
                    {
                        "chain": "coop",
                        "store_id": "internal",
                        "key": "coop:internal",
                        "name": "Coop Syd",
                        "tier": "full",
                        "selected": True,
                        "customer_facing": False,
                    },
                    {
                        "chain": "coop",
                        "store_id": "public",
                        "key": "coop:public",
                        "name": "Coop Värnhem",
                        "tier": "full",
                        "selected": True,
                        "customer_facing": True,
                    },
                    {
                        "chain": "coop",
                        "store_id": "personalvagen",
                        "key": "coop:personalvagen",
                        "name": "Coop Personalvägen",
                        "tier": "full",
                        "selected": True,
                    },
                ],
            },
        )

    provider, client = _provider(handler)
    try:
        stores = await provider.find_stores("21120")
    finally:
        await client.aclose()

    assert [store.store_id for store in stores] == ["coop:public", "coop:personalvagen"]


@pytest.mark.asyncio
async def test_product_search_parses_nested_price_and_canonical_package() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "pasta-1500",
                        name="Garant Spaghetti 1,5 kg",
                        amount=1.5,
                        unit="kg",
                        # A flat value must not override the v3 nested fact.
                        prices=_prices(regular=24.9),
                    )
                    | {"price": 999.0},
                    _product_row(
                        "milk-1500",
                        name="Mjölk 1,5 liter",
                        amount=1.5,
                        unit="l",
                        prices=_prices(regular=19.9),
                    ),
                    _product_row(
                        "eggs-12",
                        name="Ägg 12-pack",
                        amount=12,
                        unit="st",
                        prices=_prices(regular=34.9),
                    ),
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("pasta", ["willys:2354"])
    finally:
        await client.aclose()

    assert len(requests) == 1
    assert requests[0].url.path == "/api/v3/products"
    assert requests[0].url.params["q"] == "pasta"
    assert requests[0].url.params["stores"] == "willys:2354"
    assert requests[0].url.params["limit"] == "100"
    assert len(products) == 3
    by_id = {product.product_id: product for product in products}
    product = by_id["pasta-1500"]
    assert product.product_id == "pasta-1500"
    assert product.store_id == "willys:2354"
    assert product.package_quantity == 1500
    assert product.package_unit == "g"
    assert product.price == product.effective_price == 24.9
    assert product.normalized_unit_price == 16.6
    assert by_id["milk-1500"].package_quantity == 1500
    assert by_id["milk-1500"].package_unit == "ml"
    assert by_id["milk-1500"].price == 19.9
    assert by_id["eggs-12"].package_quantity == 12
    assert by_id["eggs-12"].package_unit == "st"
    assert by_id["eggs-12"].price == 34.9


@pytest.mark.asyncio
async def test_product_search_maps_explicit_and_derived_drained_weight() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "explicit",
                        name="Kidneybönor 380 g",
                        amount=380,
                        unit="g",
                        prices=_prices(regular=12.9),
                    )
                    | {"drained_weight": 230, "drained_unit": "g"},
                    _product_row(
                        "derived",
                        name="Kidneybönor 380 g",
                        amount=230,
                        unit="g",
                        prices=_prices(regular=13.9),
                    ),
                    _product_row(
                        "estimated",
                        name="Kidneybönor",
                        amount=380,
                        unit="g",
                        prices=_prices(regular=11.9),
                    ),
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("kidneybönor", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    assert by_id["explicit"].package_quantity == 380
    assert by_id["explicit"].usable_quantity == 230
    assert by_id["explicit"].quantity_confidence == QuantityConfidence.EXACT
    assert by_id["derived"].package_quantity == 380
    assert by_id["derived"].usable_quantity == 230
    assert by_id["derived"].quantity_confidence == QuantityConfidence.DERIVED
    assert by_id["estimated"].usable_quantity == 380
    assert by_id["estimated"].quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.asyncio
async def test_dry_lentils_do_not_inherit_drained_weight_from_broad_category() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "dry-lentils",
                        name="Gröna Linser 800 g",
                        amount=800,
                        unit="g",
                        prices=_prices(regular=23.9),
                    )
                    | {"category": "Skafferi > Bönor och linser"},
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("linser", ["willys:2354"]))[0]
    finally:
        await client.aclose()

    assert product.package_quantity == 800
    assert product.usable_quantity == 800
    assert product.quantity_confidence == QuantityConfidence.EXACT


@pytest.mark.asyncio
async def test_live_shape_comparison_price_never_becomes_paprika_package_size() -> None:
    """Anonymised Primat shapes: a rate is not a one-kilogram package."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "2317468800003",
                        name="Paprika Röd",
                        amount=1000,
                        unit="g",
                        prices=_prices(
                            regular=10.79,
                            comparison=(10.79, "kg"),
                        ),
                    )
                    | {
                        "gtin": "2317468800003",
                        "brand": "Nederländerna",
                        "category": "Färsk > Frukt/Grönt/Blommor",
                        "package": "1kg",
                    },
                    _product_row(
                        "100149359_KG",
                        name="Paprika Röd Klass 1",
                        amount=200,
                        unit="g",
                        prices=_prices(
                            regular=9.98,
                            comparison=(49.90, "kg"),
                        ),
                    )
                    | {
                        "brand": None,
                        "category": "Färsk > Frukt/Grönt/Blommor",
                        "package": "200 g",
                    },
                    _product_row(
                        "spetspaprika_ST",
                        name="Spetspaprika",
                        amount=200,
                        unit="g",
                        prices=_prices(
                            regular=14.90,
                            comparison=(74.50, "kg"),
                        ),
                    )
                    | {
                        "brand": None,
                        "category": "Färsk > Frukt/Grönt/Blommor",
                        "package": "200 g",
                    },
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("paprika", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    verified_variable_gtin = by_id["2317468800003"]
    assert verified_variable_gtin.sale_model == SaleModel.SOLD_BY_WEIGHT
    assert verified_variable_gtin.quantity_confidence == QuantityConfidence.DERIVED
    assert verified_variable_gtin.package_quantity is None
    assert verified_variable_gtin.package_unit is None
    assert verified_variable_gtin.sale_price == 10.79
    assert verified_variable_gtin.sale_unit == "kg"
    assert verified_variable_gtin.comparison_price == 10.79
    assert verified_variable_gtin.comparison_unit == "kg"

    suffix_only = by_id["100149359_KG"]
    assert suffix_only.sale_model == SaleModel.UNKNOWN
    assert suffix_only.quantity_confidence == QuantityConfidence.UNKNOWN
    assert suffix_only.package_quantity is None
    assert suffix_only.usable_quantity is None
    assert suffix_only.comparison_price == 49.90
    assert suffix_only.comparison_unit == "kg"

    piece_suffix_only = by_id["spetspaprika_ST"]
    assert piece_suffix_only.sale_model == SaleModel.UNKNOWN
    assert piece_suffix_only.package_quantity is None
    assert piece_suffix_only.estimated_piece_weight is None


@pytest.mark.asyncio
async def test_fresh_produce_requires_complete_weight_sale_evidence() -> None:
    """A variable prefix without a reconciled kg rate remains unknown."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "2317468800003",
                        name="Paprika Röd",
                        amount=1000,
                        unit="g",
                        prices=_prices(
                            regular=10.79,
                            comparison=(39.90, "kg"),
                        ),
                    )
                    | {
                        "gtin": "2317468800003",
                        "category": "Färsk > Frukt/Grönt/Blommor",
                        "package": "1kg",
                    }
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("paprika", ["willys:2354"]))[0]
    finally:
        await client.aclose()

    assert product.sale_model == SaleModel.UNKNOWN
    assert product.package_quantity is None
    assert product.comparison_price == 39.90


@pytest.mark.asyncio
async def test_explicit_offer_units_distinguish_weight_and_piece_sales() -> None:
    active_weight_offer = {
        "price": 39.90,
        "label": "39,90 kr/kg",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }
    active_piece_offer = {
        "price": 14.90,
        "label": "14,90/st denna vecka",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "paprika_KG",
                        name="Paprika Röd Klass 1",
                        amount=200,
                        unit="g",
                        prices=_prices(
                            regular=49.90,
                            comparison=(49.90, "kg"),
                            offer=active_weight_offer,
                        ),
                    )
                    | {"category": "Färsk > Frukt/Grönt/Blommor"},
                    _product_row(
                        "spetspaprika_ST",
                        name="Spetspaprika",
                        amount=200,
                        unit="g",
                        prices=_prices(
                            regular=14.90,
                            comparison=(74.50, "kg"),
                            offer=active_piece_offer,
                        ),
                    )
                    | {"category": "Färsk > Frukt/Grönt/Blommor"},
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("paprika", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    weight = by_id["paprika_KG"]
    assert weight.sale_model == SaleModel.SOLD_BY_WEIGHT
    assert weight.sale_price == 39.90
    assert weight.sale_unit == "kg"
    assert weight.package_quantity is None
    assert weight.quantity_confidence == QuantityConfidence.DERIVED
    assert weight.offers == []  # a kg rate must not become a package campaign

    piece = by_id["spetspaprika_ST"]
    assert piece.sale_model == SaleModel.SOLD_BY_PIECE
    assert piece.sale_price == piece.piece_price == 14.90
    assert piece.sale_unit == "st"
    assert piece.package_quantity == 1
    assert piece.package_unit == "st"
    assert piece.usable_quantity == 200
    assert piece.usable_unit == "g"
    assert piece.estimated_piece_weight == 200
    assert piece.quantity_confidence == QuantityConfidence.ESTIMATED
    assert piece.offers == []


@pytest.mark.asyncio
async def test_package_quantity_plus_per_kg_label_does_not_reprice_package_total_as_rate() -> None:
    """Sanitised live Lidl shape: 74.90 is the 1.5 kg package total."""

    package_total_offer = {
        "price": 74.90,
        "label": "1.5 kg | /kg",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "7310000000010",
                        name="Blandfärs",
                        amount=1500,
                        unit="g",
                        chain="lidl",
                        store_id="1000",
                        prices=_prices(
                            regular=74.90,
                            comparison=(49.93, "kg"),
                            offer=package_total_offer,
                        ),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Färsk > Kött > Köttfärs",
                        "package": "1.5kg",
                    }
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("blandfärs", ["lidl:1000"]))[0]
    finally:
        await client.aclose()

    assert product.sale_model == SaleModel.FIXED_PACKAGE
    assert product.package_quantity == product.usable_quantity == 1500
    assert product.package_unit == product.usable_unit == "g"
    assert product.sale_price == 74.90
    assert product.sale_unit == "package"
    assert product.quantity_confidence == QuantityConfidence.EXACT

    quote = BasketCalculator().quote_item(
        NormalizedIngredient(
            canonical_name="blandfärs",
            required_quantity=1000,
            unit="g",
        ),
        ProductCandidate.from_product(product, match_score=1),
    )
    assert quote.packages_needed == 1
    assert quote.purchased_quantity == 1500
    assert quote.total_price == Decimal("74.90")


@pytest.mark.asyncio
async def test_package_quantity_plus_genuine_per_kg_offer_converts_rate_once() -> None:
    """Nearby shape: a real 39.90 kr/kg offer on the same package costs 59.85."""

    genuine_rate_offer = {
        "price": 39.90,
        "label": "1.5 kg | 39.90 kr/kg",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "7310000000010",
                        name="Blandfärs",
                        amount=1500,
                        unit="g",
                        chain="lidl",
                        store_id="1000",
                        prices=_prices(
                            regular=74.90,
                            comparison=(49.93, "kg"),
                            offer=genuine_rate_offer,
                        ),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Färsk > Kött > Köttfärs",
                        "package": "1.5kg",
                    }
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("blandfärs", ["lidl:1000"]))[0]
    finally:
        await client.aclose()

    assert product.sale_model == SaleModel.FIXED_PACKAGE
    assert product.package_quantity == 1500
    assert len(product.offers) == 1
    assert product.offers[0].price == 59.85

    quote = BasketCalculator().quote_item(
        NormalizedIngredient(
            canonical_name="blandfärs",
            required_quantity=1000,
            unit="g",
        ),
        ProductCandidate.from_product(product, match_score=1),
    )
    assert quote.packages_needed == 1
    assert quote.total_price == Decimal("59.85")


@pytest.mark.asyncio
async def test_source_declared_sale_models_require_and_preserve_physical_evidence() -> None:
    """Captured Primat-like rows: explicit models win, but cannot invent a rate."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "explicit-fixed",
                        name="Pasta 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=20),
                    )
                    | {"sale_model": "fixed_package"},
                    _product_row(
                        "explicit-weight",
                        name="Paprika",
                        amount=200,
                        unit="g",
                        prices=_prices(regular=39.90),
                    )
                    | {"sale_model": "sold_by_weight", "sale_unit": "kg"},
                    _product_row(
                        "explicit-piece",
                        name="Avokado",
                        amount=175,
                        unit="g",
                        prices=_prices(regular=3),
                    )
                    | {"sale_model": "sold_by_piece", "piece_price": 3},
                    _product_row(
                        "explicit-variable-package",
                        name="Köttfärs cirka 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=50),
                    )
                    | {"sale_model": "variable_weight_package"},
                    _product_row(
                        "explicit-unknown",
                        name="Mystisk vara 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=10),
                    )
                    | {"sale_model": "unknown"},
                    _product_row(
                        "unsupported-model",
                        name="Mystisk vara 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=10),
                    )
                    | {"sale_model": "magic_package"},
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("sale models", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    assert by_id["explicit-fixed"].sale_model == SaleModel.FIXED_PACKAGE
    assert by_id["explicit-weight"].sale_model == SaleModel.SOLD_BY_WEIGHT
    assert by_id["explicit-weight"].sale_price == 39.90
    assert by_id["explicit-weight"].sale_unit == "kg"
    assert by_id["explicit-piece"].sale_model == SaleModel.SOLD_BY_PIECE
    assert by_id["explicit-piece"].piece_price == 3
    assert by_id["explicit-piece"].estimated_piece_weight == 175

    variable = by_id["explicit-variable-package"]
    assert variable.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE
    assert variable.package_quantity == variable.usable_quantity == 500
    assert variable.sale_price == 50
    assert variable.sale_unit == "package"
    assert variable.quantity_confidence == QuantityConfidence.ESTIMATED

    for product_id in ("explicit-unknown", "unsupported-model"):
        product = by_id[product_id]
        assert product.sale_model == SaleModel.UNKNOWN
        assert product.package_quantity is None
        assert product.usable_quantity is None
        assert product.quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.asyncio
async def test_weight_and_piece_declarations_without_rate_evidence_fail_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "legacy-weight-flag",
                        name="Paprika",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=50),
                    )
                    | {"sold_by_weight": True},
                    _product_row(
                        "declared-weight",
                        name="Paprika",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=50),
                    )
                    | {"sale_model": "sold_by_weight"},
                    _product_row(
                        "declared-piece",
                        name="Avokado",
                        amount=175,
                        unit="g",
                        prices=_prices(regular=12.90),
                    )
                    | {"sale_model": "sold_by_piece"},
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("unsafe rates", ["willys:2354"])
    finally:
        await client.aclose()

    assert len(products) == 3
    for product in products:
        assert product.sale_model == SaleModel.UNKNOWN
        assert product.sale_unit is None
        assert product.package_quantity is None
        assert product.quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.asyncio
async def test_variable_weight_flag_keeps_ordinary_price_as_representative_package_price() -> None:
    """A 50 kr item is not a 50 kr/kg rate unless Primat explicitly says so."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "variable-500",
                        name="Köttfärs cirka 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=50),
                    )
                    | {"variable_weight": True}
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("köttfärs", ["willys:2354"]))[0]
    finally:
        await client.aclose()

    assert product.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE
    assert product.sale_price == 50
    assert product.sale_unit == "package"
    assert product.comparison_price is None

    resolution = BasketCalculator().quote_item(
        NormalizedIngredient(
            canonical_name="köttfärs",
            required_quantity=700,
            unit="g",
        ),
        ProductCandidate.from_product(product, match_score=1),
    )
    assert resolution.packages_needed == 2
    assert resolution.purchased_quantity == 1000
    assert resolution.total_price == 100
    assert resolution.unit_price == 50


@pytest.mark.asyncio
async def test_conflicting_captured_package_shapes_remain_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "conflicting-pasta",
                        name="Pasta 1 kg",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=19.90),
                    ),
                    _product_row(
                        "ambiguous-kit",
                        name="Matkit pasta 500 g sås 200 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=59.90),
                    ),
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("pasta", ["willys:2354"])
    finally:
        await client.aclose()

    assert len(products) == 2
    for product in products:
        assert product.sale_model == SaleModel.UNKNOWN
        assert product.package_quantity is None
        assert product.usable_quantity is None
        assert product.quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.asyncio
async def test_unit_rate_offer_does_not_override_a_clearly_fixed_package() -> None:
    weight_rate_offer = {
        "price": 80.0,
        "label": "80 kr/kg",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }
    catalogue_item_offer = {
        "price": 25.0,
        "label": "25 kr/st",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "fixed-chicken",
                        name="Kycklingfilé 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(
                            regular=50,
                            comparison=(100, "kg"),
                            offer=weight_rate_offer,
                        ),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Färsk > Kött",
                    },
                    _product_row(
                        "fixed-eggs",
                        name="Ägg 12-pack",
                        amount=12,
                        unit="st",
                        prices=_prices(
                            regular=30,
                            comparison=(2.50, "st"),
                            offer=catalogue_item_offer,
                        ),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Mejeri > Ägg",
                    },
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("middag", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    chicken = by_id["fixed-chicken"]
    assert chicken.sale_model == SaleModel.FIXED_PACKAGE
    assert chicken.package_quantity == 500
    assert chicken.effective_price == 40
    assert chicken.offers[0].price == 40
    chicken_item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="kyckling", required_quantity=350, unit="g"),
        ProductCandidate.from_product(chicken, match_score=1),
    )
    assert chicken_item.packages_needed == 1
    assert chicken_item.total_price == 40

    eggs = by_id["fixed-eggs"]
    assert eggs.sale_model == SaleModel.FIXED_PACKAGE
    assert eggs.package_quantity == eggs.usable_quantity == 12
    assert eggs.package_unit == eggs.usable_unit == "st"
    assert eggs.effective_price == 25
    egg_item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="ägg", required_quantity=12, unit="st"),
        ProductCandidate.from_product(eggs, match_score=1),
    )
    assert egg_item.packages_needed == 1
    assert egg_item.total_price == 25


@pytest.mark.asyncio
async def test_variable_measure_meat_and_cheese_are_not_freely_divisible() -> None:
    chicken_offer = {
        "price": 105.0,
        "label": "105 kr/kg",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "2359634700007",
                        name="Kycklingfilé Bröstfilé Sverige",
                        amount=850,
                        unit="g",
                        prices=_prices(
                            regular=101.15,
                            comparison=(119.0, "kg"),
                            offer=chicken_offer,
                        ),
                    )
                    | {
                        "gtin": "2359634700007",
                        "category": "Färsk > Kött > Fågel",
                        "package": "850 g",
                    },
                    _product_row(
                        "2317237300000",
                        name="Hushållsost",
                        amount=1100,
                        unit="g",
                        prices=_prices(
                            regular=107.23,
                            comparison=(97.48, "kg"),
                        ),
                    )
                    | {
                        "gtin": "2317237300000",
                        "category": "Färsk > Ost",
                        "package": "1100 g",
                    },
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("färskvara", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    chicken = by_id["2359634700007"]
    assert chicken.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE
    assert chicken.package_quantity == chicken.usable_quantity == 850
    assert chicken.package_unit == chicken.usable_unit == "g"
    assert chicken.sale_price == 105.0
    assert chicken.sale_unit == "kg"
    assert chicken.comparison_price == 119.0
    assert chicken.quantity_confidence == QuantityConfidence.ESTIMATED
    assert chicken.offers == []

    cheese = by_id["2317237300000"]
    assert cheese.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE
    assert cheese.package_quantity == cheese.usable_quantity == 1100
    assert cheese.sale_price == 97.48
    assert cheese.sale_unit == "kg"
    assert cheese.quantity_confidence == QuantityConfidence.ESTIMATED


@pytest.mark.asyncio
async def test_fixed_gtin_produce_and_regular_dry_packages_remain_fixed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "7310865004703",
                        name="Morötter 1 kg",
                        amount=1,
                        unit="kg",
                        prices=_prices(regular=18.90, comparison=(18.90, "kg")),
                    )
                    | {
                        "gtin": "7310865004703",
                        "category": "Färsk > Frukt/Grönt/Blommor",
                    },
                    _product_row(
                        "pasta-500",
                        name="Pasta 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=19.90, comparison=(39.80, "kg")),
                    ),
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("mat", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    for product_id, expected_quantity in (
        ("7310865004703", 1000),
        ("pasta-500", 500),
    ):
        product = by_id[product_id]
        assert product.sale_model == SaleModel.FIXED_PACKAGE
        assert product.package_quantity == expected_quantity
        assert product.quantity_confidence == QuantityConfidence.EXACT


@pytest.mark.asyncio
async def test_fixed_item_gtin_does_not_make_bare_class_one_produce_a_package() -> None:
    """Anonymised live shapes: GTIN identity is not package-size evidence."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "7310000000010",
                        name="Morot Klass 1",
                        amount=100,
                        unit="g",
                        prices=_prices(
                            regular=1.79,
                            comparison=(17.90, "kg"),
                        ),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Färsk > Frukt/Grönt/Blommor",
                        "package": "100 g",
                    },
                    _product_row(
                        "7310000000027",
                        name="Lök Gul Klass 1",
                        amount=175,
                        unit="g",
                        prices=_prices(
                            regular=1.91,
                            comparison=(10.91, "kg"),
                        ),
                    )
                    | {
                        "gtin": "7310000000027",
                        "category": "Färsk > Frukt/Grönt/Blommor",
                        "package": "175 g",
                    },
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("klass 1", ["willys:2354"])
    finally:
        await client.aclose()

    assert {product.product_id for product in products} == {
        "7310000000010",
        "7310000000027",
    }
    for product in products:
        assert product.sale_model == SaleModel.UNKNOWN
        assert product.quantity_confidence == QuantityConfidence.UNKNOWN
        assert product.package_quantity is None
        assert product.package_unit is None
        assert product.usable_quantity is None
        assert product.comparison_unit == "kg"


@pytest.mark.asyncio
async def test_non_shallow_category_does_not_certify_bare_whole_produce_package() -> None:
    """Name identity must keep loose produce conservative in any category."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "small-carrots",
                        name="Små morötter",
                        amount=400,
                        unit="g",
                        prices=_prices(regular=29.95, comparison=(74.88, "kg")),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Matlagning > Rotfrukter",
                    },
                    _product_row(
                        "bare-broccoli",
                        name="Broccoli",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=24.90, comparison=(49.80, "kg")),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Middagstillbehör > Vegetariskt",
                    },
                    _product_row(
                        "frozen-broccoli",
                        name="Broccoli Fryst",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=24.90, comparison=(49.80, "kg")),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Frys > Grönsaker",
                    },
                    _product_row(
                        "visible-broccoli-package",
                        name="Broccoli 500 g",
                        amount=500,
                        unit="g",
                        prices=_prices(regular=24.90, comparison=(49.80, "kg")),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "Middagstillbehör > Vegetariskt",
                    },
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("grönsaker", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    for product_id in ("small-carrots", "bare-broccoli"):
        product = by_id[product_id]
        assert product.sale_model == SaleModel.UNKNOWN
        assert product.quantity_confidence == QuantityConfidence.UNKNOWN
        assert product.package_quantity is None
        assert product.usable_quantity is None

    for product_id in ("frozen-broccoli", "visible-broccoli-package"):
        product = by_id[product_id]
        assert product.sale_model == SaleModel.FIXED_PACKAGE
        assert product.package_quantity == product.usable_quantity == 500
        assert product.quantity_confidence == QuantityConfidence.EXACT


@pytest.mark.asyncio
async def test_fixed_canned_whole_vegetable_without_drained_weight_is_unknown() -> None:
    """Anonymised live shape: gross can weight is not usable carrot weight."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "7310000000010",
                        name="Små morötter",
                        amount=400,
                        unit="g",
                        prices=_prices(regular=18.46, comparison=(46.15, "kg")),
                        chain="coop",
                        store_id="1234",
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": ("Skafferi > Grönsakskonserver > Övriga grönsakskonserver"),
                        "package": "400 g",
                    },
                    *[
                        _product_row(
                            product_id,
                            name=name,
                            amount=400,
                            unit="g",
                            prices=_prices(regular=19.90, comparison=(49.75, "kg")),
                            chain="coop",
                            store_id="1234",
                        )
                        | {
                            "category": "Skafferi > Grönsakskonserver",
                            "package": "400 g",
                        }
                        for product_id, name in (
                            ("preserved-cucumber", "Gurka"),
                            ("preserved-mushroom", "Champinjoner"),
                            ("preserved-olives", "Oliver"),
                        )
                    ],
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("morot", ["coop:1234"])
    finally:
        await client.aclose()

    # The package and its checkout price are real, but no source field proves
    # the drained amount available to the recipe.
    assert len(products) == 4
    for product in products:
        assert product.sale_model == SaleModel.FIXED_PACKAGE
        assert product.package_quantity == 400
        assert product.package_unit == "g"
        assert product.usable_quantity == 400
        assert product.usable_unit == "g"
        assert product.quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.asyncio
async def test_missing_category_does_not_make_bare_produce_a_fixed_package() -> None:
    """Shallow live rows still require physical sale evidence, not just amount."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "2317468800003",
                        name="Paprika Röd",
                        amount=1000,
                        unit="g",
                        prices=_prices(
                            regular=10.79,
                            comparison=(39.90, "kg"),
                        ),
                    )
                    | {
                        "gtin": "2317468800003",
                        "category": "",
                        "package": "1kg",
                    },
                    _product_row(
                        "7310000000010",
                        name="Morot Klass 1",
                        amount=100,
                        unit="g",
                        prices=_prices(
                            regular=1.79,
                            comparison=(17.90, "kg"),
                        ),
                    )
                    | {
                        "gtin": "7310000000010",
                        "category": "",
                        "package": "100 g",
                    },
                    _product_row(
                        "7310000000027",
                        name="Lök Gul Klass 1",
                        amount=175,
                        unit="g",
                        prices=_prices(
                            regular=1.91,
                            comparison=(10.91, "kg"),
                        ),
                    )
                    | {
                        "gtin": "7310000000027",
                        "category": "",
                        "package": "175 g",
                    },
                    _product_row(
                        "visible-package",
                        name="Morötter 1 kg",
                        amount=1,
                        unit="kg",
                        prices=_prices(
                            regular=18.90,
                            comparison=(18.90, "kg"),
                        ),
                    )
                    | {"category": ""},
                    _product_row(
                        "source-declared-package",
                        name="Morot Klass 1",
                        amount=100,
                        unit="g",
                        prices=_prices(
                            regular=1.79,
                            comparison=(17.90, "kg"),
                        ),
                    )
                    | {"category": "", "sale_model": "fixed_package"},
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("färskvaror", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    for product_id in (
        "2317468800003",
        "7310000000010",
        "7310000000027",
    ):
        product = by_id[product_id]
        assert product.sale_model == SaleModel.UNKNOWN
        assert product.quantity_confidence == QuantityConfidence.UNKNOWN
        assert product.package_quantity is None
        assert product.usable_quantity is None

    for product_id in ("visible-package", "source-declared-package"):
        product = by_id[product_id]
        assert product.sale_model == SaleModel.FIXED_PACKAGE
        assert product.quantity_confidence == QuantityConfidence.EXACT
        assert product.package_quantity is not None


@pytest.mark.asyncio
async def test_comparable_bean_amount_without_independent_quantity_evidence_is_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "beans-comparable-basis",
                        name="Kidneybönor",
                        amount=230,
                        unit="g",
                        prices=_prices(
                            regular=9.90,
                            comparison=(43.04, "kg"),
                        ),
                    )
                    | {"category": "Skafferi > Bönor och linser"}
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("bönor", ["willys:2354"]))[0]
    finally:
        await client.aclose()

    assert product.sale_model == SaleModel.FIXED_PACKAGE
    assert product.package_quantity == 230
    assert product.usable_quantity == 230
    assert product.quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.asyncio
async def test_product_search_does_not_assign_query_as_product_identity() -> None:
    """A loose Primat result must still pass deterministic semantic matching."""

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "tortilla",
                        name="Tortillabröd Medium 8-pack",
                        amount=8,
                        unit="st",
                        prices=_prices(regular=24.9),
                    )
                    | {"category": "Texmex > Tortillabröd"},
                    _product_row(
                        "sauce",
                        name="Tacosås Mild 230 g",
                        amount=230,
                        unit="g",
                        prices=_prices(regular=17.9),
                    )
                    | {"category": "Texmex > Såser"},
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.search_products("tortillas", ["willys:2354"])
    finally:
        await client.aclose()

    assert len(requests) == 1
    by_id = {product.product_id: product for product in products}
    assert by_id["tortilla"].canonical_name == "tortillas"
    assert by_id["sauce"].canonical_name == "tacosås mild 230 g"

    candidates = ProductMatcher().match(
        NormalizedIngredient(
            canonical_name="tortillas",
            required_quantity=8,
            unit="st",
        ),
        products,
        store_ids=["willys:2354"],
    )
    assert [candidate.product_id for candidate in candidates] == ["tortilla"]


@pytest.mark.asyncio
async def test_product_search_reuses_normalized_request_scoped_cache() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "pasta",
                        name="Garant Pasta 500 g",
                        prices=_prices(regular=18.9),
                    )
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        first = await provider.search_products(
            "  PASTA  ", ["ica:1004409", "willys:2354", "ica:1004409"]
        )
        second = await provider.search_products("pasta", ["willys:2354", "ica:1004409"])
        # An explicit synonym remains a distinct catalogue search. The service
        # layer owns that choice and can merge the two result sets.
        await provider.search_products("spaghetti", ["willys:2354", "ica:1004409"])
    finally:
        await client.aclose()

    assert first == second
    assert first is not second
    assert len(requests) == 2
    assert requests[0].url.params["q"] == "PASTA"
    assert requests[0].url.params["stores"] == "ica:1004409,willys:2354"
    assert requests[1].url.params["q"] == "spaghetti"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("use_member_prices", "expected_member_effective"),
    [(False, 49.9), (True, 39.9)],
)
async def test_public_offer_and_member_price_have_separate_eligibility(
    use_member_prices: bool,
    expected_member_effective: float,
) -> None:
    public_offer = {
        "price": 34.9,
        "label": "Veckans pris",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }
    member_offer = {
        "price": 39.9,
        "label": "MedMera: Medlemspris",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "public",
                        name="Publik kampanj",
                        prices=_prices(regular=49.9, offer=public_offer),
                    ),
                    _product_row(
                        "member",
                        name="Medlemskampanj",
                        prices=_prices(regular=49.9, member=39.9, offer=member_offer),
                    ),
                ]
            },
        )

    provider, client = _provider(handler, use_member_prices=use_member_prices)
    try:
        products = await provider.search_products("kampanj", ["willys:2354"])
    finally:
        await client.aclose()

    by_id = {product.product_id: product for product in products}
    public = by_id["public"]
    member = by_id["member"]

    assert public.price == 49.9
    assert public.effective_price == 34.9
    assert [offer.kind for offer in public.offers] == [OfferKind.CAMPAIGN]

    assert member.price == 49.9
    assert member.member_price == 39.9
    assert member.effective_price == expected_member_effective
    assert OfferKind.CAMPAIGN not in {offer.kind for offer in member.offers}
    assert [offer.kind for offer in member.offers] == [OfferKind.MEMBER]
    assert member.offers[0].eligibility is PromotionEligibility.MEMBER
    assert member.offers[0].membership_program is MembershipProgram.WILLYS_PLUS


@pytest.mark.asyncio
async def test_public_multipack_is_conditional_and_uses_group_price() -> None:
    multi_offer = {
        "price": 10.0,
        "label": "3 för 30 kr",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "tomatoes",
                        name="Krossade tomater",
                        amount=400,
                        unit="g",
                        prices=_prices(
                            regular=12.9,
                            multiprice=(10.0, 3),
                            offer=multi_offer,
                        ),
                    )
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        product = (await provider.search_products("tomater", ["willys:2354"]))[0]
    finally:
        await client.aclose()

    assert product.effective_price == product.price == 12.9
    assert len(product.offers) == 1
    offer = product.offers[0]
    assert offer.kind == OfferKind.MULTIPACK
    assert offer.required_packages == 3
    assert offer.price == 30.0

    candidate = ProductCandidate.from_product(product, match_score=1.0)
    calculator = BasketCalculator()
    below_threshold = calculator.calculate_item(
        NormalizedIngredient(canonical_name="krossade tomater", required_quantity=400, unit="g"),
        candidate,
    )
    eligible = calculator.calculate_item(
        NormalizedIngredient(canonical_name="krossade tomater", required_quantity=1200, unit="g"),
        candidate,
    )
    assert below_threshold.packages_needed == 1
    assert below_threshold.total_price == 12.9
    assert eligible.packages_needed == 3
    assert eligible.total_price == 30.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "use_member_prices",
    [False, True],
)
async def test_member_multipack_is_retained_for_shared_request_time_policy(
    use_member_prices: bool,
) -> None:
    member_offer = {
        "price": 8.0,
        "label": "Medlem: 3 för 24 kr",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "member-tomatoes",
                        name="Krossade tomater",
                        amount=400,
                        unit="g",
                        prices=_prices(
                            regular=12.9,
                            member_multiprice=(8.0, 3),
                            offer=member_offer,
                        ),
                    )
                ]
            },
        )

    provider, client = _provider(handler, use_member_prices=use_member_prices)
    try:
        product = (await provider.search_products("tomater", ["willys:2354"]))[0]
    finally:
        await client.aclose()

    # Source normalization is shared: the contract survives regardless of the
    # legacy caller flag, while the flattened one-package price stays public.
    # UserPricingContext applies the member contract later at request time.
    assert product.effective_price == product.price == 12.9
    assert len(product.offers) == 1
    offer = product.offers[0]
    assert offer.eligibility is PromotionEligibility.MEMBER
    assert offer.mechanism is PromotionMechanism.MULTIBUY
    assert offer.membership_program is MembershipProgram.WILLYS_PLUS
    assert offer.required_packages == 3
    assert offer.price == 24


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (401, PriceProviderAuthenticationError),
        (403, PriceProviderAuthenticationError),
        (429, PriceProviderRateLimitError),
    ],
)
async def test_authentication_and_rate_limit_errors_are_typed(
    status: int,
    exception_type: type[Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        code = "invalid_api_key" if status in {401, 403} else "rate_limited"
        return _json_response(
            request,
            {"error": {"code": code, "message": f"upstream {code}"}},
            status=status,
        )

    provider, client = _provider(handler)
    try:
        with pytest.raises(exception_type, match="upstream"):
            await provider.find_stores("22350")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_upstream_error_cannot_echo_api_key_into_exception() -> None:
    api_key = "test-secret-that-must-not-leak"

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {"error": {"message": f"invalid Bearer {api_key}; key={api_key}"}},
            status=401,
        )

    client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    provider = PrimatPriceProvider(api_key=api_key, client=client)
    try:
        with pytest.raises(PriceProviderAuthenticationError) as caught:
            await provider.find_stores("22350")
    finally:
        await client.aclose()

    message = str(caught.value)
    assert api_key not in message
    assert "[REDACTED]" in message


@pytest.mark.asyncio
async def test_prices_pagination_follows_cursor_and_stops_on_repeated_cursor() -> None:
    seen_cursors: list[str | None] = []

    def flat_row(product_id: str, name: str, price: float) -> dict[str, Any]:
        return {
            "chain": "willys",
            "store_id": "2354",
            "product_id": product_id,
            "name": name,
            "brand": "Garant",
            "price": price,
            "member_price": None,
            "multi_price": None,
            "multi_count": None,
            "member_multi_price": None,
            "member_multi_count": None,
            "effective_price": price,
            "offer_price": None,
            "offer_label": None,
            "offer_valid_until": None,
        }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/prices"
        assert request.url.params["stores"] == "willys:2354"
        assert request.url.params["limit"] == "1000"
        cursor = request.url.params.get("cursor")
        seen_cursors.append(cursor)
        if cursor is None:
            return _json_response(
                request,
                {
                    "data": [flat_row("pasta", "Garant Pasta 500 g", 18.9)],
                    "next_cursor": "opaque-1",
                },
            )
        assert cursor == "opaque-1"
        return _json_response(
            request,
            {
                "data": [flat_row("rice", "Garant Ris 1 kg", 24.9)],
                # A broken upstream page must not create an infinite loop.
                "next_cursor": "opaque-1",
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.get_store_products("willys:2354")
    finally:
        await client.aclose()

    assert seen_cursors == [None, "opaque-1"]
    assert {product.product_id for product in products} == {"pasta", "rice"}
    packages = {product.product_id: product.package_quantity for product in products}
    # Flat rows carry name hints only, not authoritative package fields.
    assert packages == {"pasta": None, "rice": None}


@pytest.mark.asyncio
async def test_get_offers_uses_deals_endpoint_and_nested_product_rows() -> None:
    active_offer = {
        "price": 29.9,
        "label": "Veckans vara",
        "valid_from": "2025-01-01T00:00:00Z",
        "valid_until": "2030-12-31T23:59:59Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/deals"
        assert dict(request.url.params) == {
            "stores": "willys:2354",
            "limit": "500",
            "lookback_days": "14",
        }
        return _json_response(
            request,
            {
                "data": [
                    _product_row(
                        "deal",
                        name="Kycklinglårfilé",
                        amount=1,
                        unit="kg",
                        prices=_prices(regular=49.9, offer=active_offer) | {"previous": 59.9},
                    )
                ]
            },
        )

    provider, client = _provider(handler)
    try:
        products = await provider.get_offers("willys:2354")
    finally:
        await client.aclose()

    assert len(products) == 1
    assert products[0].product_id == "deal"
    assert products[0].effective_price == 29.9
    assert products[0].offers[0].kind == OfferKind.CAMPAIGN
