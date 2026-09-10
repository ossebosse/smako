from __future__ import annotations

import pytest
from app.models import Product, Store
from app.services.cheap_products import CheapProductsService

STORE = Store(
    store_id="willys:1",
    name="Willys Test",
    chain="Willys",
    city="Lund",
    postal_code="22350",
)


def _product(
    product_id: str,
    name: str,
    canonical_name: str,
    *,
    price: float = 20,
) -> Product:
    return Product(
        product_id=product_id,
        name=name,
        canonical_name=canonical_name,
        category="Testkategori",
        store_id=STORE.store_id,
        store_name=STORE.name,
        package_quantity=500,
        package_unit="g",
        price=price,
    )


class _SearchProvider:
    def __init__(self, rows: dict[str, list[Product]]) -> None:
        self.rows = rows

    async def search_products(
        self, query: str, _store_ids: list[str]
    ) -> list[Product]:
        return self.rows.get(query, [])


class _CheapProvider(_SearchProvider):
    def __init__(self, cheap_rows: list[Product]) -> None:
        super().__init__({})
        self.cheap_rows = cheap_rows

    async def get_cheap_products(
        self, _store_ids: list[str], limit: int = 100
    ) -> list[Product]:
        return self.cheap_rows[:limit]


@pytest.mark.asyncio
async def test_targeted_search_filters_category_neighbours_before_price_sorting() -> None:
    provider = _SearchProvider(
        {
            "korv": [
                _product("bread", "Glutenfritt Korvbröd", "glutenfritt korvbröd", price=5),
                _product("sausage", "Falukorv 800 g", "falukorv", price=30),
            ],
            "linser": [
                _product("peas", "Ärter Gula 500 g", "ärter gula", price=5),
                _product("lentils", "Röda Linser 500 g", "linser", price=20),
            ],
            "bönor": [
                _product("green-beans", "Gröna Bönor 500 g", "bönor", price=5),
                _product("kidney", "Kidneybönor 380 g", "kidneybönor", price=15),
                _product("white", "Bönor Vita 380 g", "bönor", price=16),
            ],
            # Unrelated queries retain Primat's broader search semantics.
            "pasta": [_product("spaghetti", "Glutenfri Spaghetti", "pasta")],
        }
    )

    signals = await CheapProductsService().find(provider, [STORE], limit_per_group=10)
    selected_ids = {signal.product_id for signal in signals}

    assert {"sausage", "lentils", "kidney", "white", "spaghetti"} <= selected_ids
    assert {"bread", "peas", "green-beans"}.isdisjoint(selected_ids)


@pytest.mark.asyncio
async def test_unscoped_cheap_rows_use_the_same_ingredient_quality_filters() -> None:
    provider = _CheapProvider(
        [
            _product("bread", "Korvbröd Glutenfritt", "glutenfritt korvbröd", price=5),
            _product("sausage", "Grillkorv 500 g", "korv", price=25),
            _product("peas", "Gula Ärter 500 g", "gula ärter", price=5),
            _product("lentils", "Belugalinser 400 g", "linser", price=20),
            _product("green-beans", "Bönor Gröna Frysta", "bönor", price=5),
            _product("kidney", "Kidneybönor 380 g", "kidneybönor", price=15),
        ]
    )

    signals = await CheapProductsService().find(provider, [STORE], limit_per_group=10)
    selected_ids = {signal.product_id for signal in signals}

    assert {"sausage", "lentils", "kidney"} <= selected_ids
    assert {"bread", "peas", "green-beans"}.isdisjoint(selected_ids)
