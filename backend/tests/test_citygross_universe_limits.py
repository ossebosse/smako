from datetime import UTC, datetime

from app.models.product import Product
from app.models.provenance import SourceProvenance
from app.services.price_universe import _dominance_prune


def product(identity, price, cap):
    return Product(product_id=identity, name="Basmatiris 1 kg", canonical_name="ris", category="Skafferi",
        canonical_food="ris", store_id="citygross:test", store_name="Test", chain="citygross",
        price=price, effective_price=price, sale_price=price, sale_unit="st",
        sale_model="fixed_package", package_quantity=1000, package_unit="g",
        usable_quantity=1000, usable_unit="g", quantity_confidence="exact",
        source_provenance=SourceProvenance(source_provider="own", source_channel="online_price",
            source_snapshot_id="test", source_observed_at=datetime(2026, 9, 23, tzinfo=UTC),
            maximum_purchase_units=cap))


def test_cheap_limited_product_does_not_dominate_larger_purchase_capacity():
    products = [product("cheap-one", 10, 1), product("larger-limit", 15, 25),
                product("no-limit", 20, None), product("expensive-one", 11, 1)]
    retained, pruned = _dominance_prune(products, "ris", range(len(products)))
    assert {products[i].product_id for i in retained} == {"cheap-one", "larger-limit", "no-limit"}
    assert pruned == 1
