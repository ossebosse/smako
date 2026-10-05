"""The common basket engine compares whole checkout after pooled demand."""

from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate
from app.models.store import Store
from app.services.basket_optimizer import BasketOptimizer


def test_smaller_and_larger_packs_compete_on_paid_packages():
    store = Store(store_id="shop", name="Butik", chain="coop", city="Lund")
    products = tuple(ProductCandidate(
        product_id=f"pack-{size}", product_name=f"Paprikapulver {size} g",
        canonical_name="paprikapulver", store_id="shop", store_name="Butik",
        package_quantity=size, package_unit="g", usable_quantity=size,
        usable_unit="g", price=price, effective_price=price, match_score=1,
        semantic_confidence="high", quantity_confidence="exact",
    ) for size, price in ((37, 25.50), (200, 74.50)))
    optimizer = BasketOptimizer()
    for required, expected, packages, total in ((14, "pack-37", 1, 25.50),
                                                (80, "pack-200", 1, 74.50)):
        basket = optimizer.optimize(
            [NormalizedIngredient(canonical_name="paprikapulver",
                                  required_quantity=required, unit="g")],
            {"paprikapulver": products}, [store], 1)
        item = basket.stores[0].items[0]
        assert (item.product_id, item.packages_needed, basket.total) == (expected, packages, total)
