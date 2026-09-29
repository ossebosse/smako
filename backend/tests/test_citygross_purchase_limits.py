from datetime import UTC, datetime

import pytest
from app.models.basket import BasketAuditStatus
from app.models.ingredient import NormalizedIngredient
from app.models.product import OfferMetadata, ProductCandidate
from app.models.provenance import SourceProvenance
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator


def provenance(limit=25):
    return SourceProvenance(source_provider="own", source_channel="online_price",
        source_snapshot_id="retained-citygross-fixture", source_observed_at=datetime(2026, 9, 23, tzinfo=UTC),
        chain="citygross", maximum_purchase_units=limit,
        official_product_url="https://www.citygross.se/matvaror/pasta",
        quantity_limit_source_url="https://www.citygross.se/static/js/main.07a64bf6.js")


def candidate(*, limit=25, offers=None):
    return ProductCandidate(product_id="pasta", product_name="Pasta 500 g",
        canonical_name="pasta", canonical_food="pasta", semantic_confidence="high",
        store_id="own:citygross:3211", store_name="Malmö Hyllie", chain="citygross",
        price=20, effective_price=20, sale_price=20, sale_unit="st", sale_model="fixed_package",
        package_quantity=500, package_unit="g", usable_quantity=500, usable_unit="g",
        quantity_confidence="exact", match_score=1, offers=offers or [],
        source_provenance=provenance(limit))


def requirement(packages):
    return NormalizedIngredient(canonical_name="pasta", required_quantity=packages * 500, unit="g")


def test_source_purchase_cap_25_preserves_price_and_rejects_26():
    calculator = BasketCalculator()
    item = calculator.calculate_item(requirement(25), candidate())
    assert item.total_price == 500 and item.packages_needed == 25
    assert item.source_provenance.maximum_purchase_units == 25
    assert BasketAuditor().audit([requirement(25)], [item]).status == BasketAuditStatus.PASS
    with pytest.raises(ValueError, match="purchase-unit limit exceeded"):
        calculator.calculate_item(requirement(26), candidate())


def test_purchase_cap_is_distinct_from_discounted_multibuy_groups():
    offer = OfferMetadata(kind="multipack", price=30, description="2 för 30, max 2 köp",
                          required_packages=2, max_quantity=2)
    calculator = BasketCalculator()
    item = calculator.calculate_item(requirement(25), candidate(offers=[offer]))
    assert item.total_price == 480  # Two groups at 30, 21 regular packages at 20.
    assert item.applied_offer.max_quantity == 2
    assert item.source_provenance.maximum_purchase_units == 25
    with pytest.raises(ValueError, match="purchase-unit limit exceeded"):
        calculator.calculate_item(requirement(26), candidate(offers=[offer]))


def test_conditional_multibuy_has_its_own_package_groups_under_purchase_cap():
    offer = OfferMetadata(kind="multipack", price=30, description="2 för 30", required_packages=2)
    product = candidate(offers=[offer]).model_copy(update={"price": None, "sale_price": None,
                                                          "effective_price": 15})
    calculator = BasketCalculator()
    assert calculator.calculate_item(requirement(24), product).total_price == 360
    with pytest.raises(ValueError, match="purchase-unit limit exceeded"):
        calculator.calculate_item(requirement(26), product)


def test_same_product_aliases_share_purchase_cap_and_audit_independently_rejects():
    calculator = BasketCalculator()
    items = [calculator.calculate_item(requirement(13), candidate()) for _ in range(2)]
    with pytest.raises(ValueError, match="purchase-unit limit exceeded"):
        calculator.quote_group_basket(items)
    audit = BasketAuditor().audit([requirement(26)], items)
    assert audit.status == BasketAuditStatus.FAIL
    assert any("purchase-unit limit" in e for e in audit.total_reconciliation_errors)


def test_forged_over_cap_basket_fails_audit_without_repricing():
    uncapped = BasketCalculator().calculate_item(requirement(26), candidate(limit=None))
    forged = uncapped.model_copy(update={"source_provenance": provenance(25)})
    assert BasketAuditor().audit([requirement(26)], [forged]).status == BasketAuditStatus.FAIL


def test_weight_price_never_assumes_one_kilogram_is_one_sales_unit():
    product = candidate().model_copy(update={"sale_model": "sold_by_weight", "sale_unit": "kg",
        "package_quantity": None, "package_unit": None, "usable_quantity": None,
        "usable_unit": None})
    with pytest.raises(ValueError, match="verified count of sales units"):
        BasketCalculator().calculate_item(requirement(1), product)


def test_absent_fields_do_not_change_legacy_provenance_json():
    original = {"source_provider": "own", "source_channel": "catalog",
        "source_snapshot_id": "old", "source_observed_at": "2026-09-21T10:00:00Z"}
    serialized = SourceProvenance.model_validate(original).model_dump(mode="json")
    assert "maximum_purchase_units" not in serialized
    assert "official_product_url" not in serialized
    assert "quantity_limit_source_url" not in serialized
