import pytest
from app.models import OfferKind
from app.models.product import QuantityConfidence
from app.providers import MockPriceProvider


@pytest.mark.asyncio
async def test_find_stores_uses_lund_fallback() -> None:
    provider = MockPriceProvider()

    stores = await provider.find_stores("999 99")

    assert len(stores) == 3
    assert {store.chain for store in stores} == {"Willys", "ICA", "Coop"}
    assert all(store.city == "Lund" for store in stores)


@pytest.mark.asyncio
async def test_catalog_has_canonical_packages_and_complete_staple_coverage() -> None:
    provider = MockPriceProvider()
    stores = await provider.find_stores("22350")

    required_staples = {
        "kycklinglårfilé",
        "falukorv",
        "ägg",
        "kidneybönor",
        "röda linser",
        "pasta",
        "ris",
        "potatis",
        "gul lök",
        "morot",
        "frysta grönsaker",
        "mjölk",
        "crème fraiche",
        "ost",
        "krossade tomater",
        "kokosmjölk",
        "tortillabröd",
    }
    for store in stores:
        products = await provider.get_store_products(store.store_id)
        assert required_staples <= {product.canonical_name for product in products}
        assert {product.package_unit for product in products} <= {"g", "ml", "st"}

    beans = await provider.search_products(
        "kidneybönor", ["willys-lund-norra-faladen"]
    )
    assert beans[0].package_quantity == 380
    assert beans[0].usable_quantity == 230
    assert beans[0].quantity_confidence == QuantityConfidence.EXACT


@pytest.mark.asyncio
async def test_member_prices_are_only_effective_when_enabled() -> None:
    store_id = "ica-maxi-gunnesbo"
    without_membership = await MockPriceProvider(
        use_member_prices=False
    ).search_products("nötfärs", [store_id])
    with_membership = await MockPriceProvider(
        use_member_prices=True
    ).search_products("nötfärs", [store_id])

    assert without_membership[0].price == 61.90
    assert without_membership[0].member_price == 49.90
    assert without_membership[0].effective_price == 61.90
    assert with_membership[0].effective_price == 49.90


@pytest.mark.asyncio
async def test_campaign_is_effective_but_multipack_remains_conditional() -> None:
    campaign = await MockPriceProvider().search_products(
        "kyckling", ["willys-lund-norra-faladen"]
    )
    multipack = await MockPriceProvider().search_products(
        "krossade tomater", ["coop-martenstorget"]
    )

    offered_chicken = next(product for product in campaign if product.package_quantity == 1000)
    assert offered_chicken.price == 94.90
    assert offered_chicken.effective_price == 69.90

    tomatoes = multipack[0]
    assert tomatoes.effective_price == tomatoes.price == 12.90
    assert tomatoes.offers[0].kind == OfferKind.MULTIPACK
    assert tomatoes.offers[0].required_packages == 3
    assert tomatoes.offers[0].price == 30.00
