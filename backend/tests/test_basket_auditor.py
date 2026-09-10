from app.models.basket import BasketAuditStatus
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    ProductCandidate,
    QuantityConfidence,
    SemanticConfidence,
)
from app.services.basket_auditor import DEFAULT_PANTRY_ITEMS, BasketAuditor
from app.services.basket_calculator import BasketCalculator


def requirement(name: str, quantity: float, unit: str = "g") -> NormalizedIngredient:
    return NormalizedIngredient(
        canonical_name=name,
        required_quantity=quantity,
        unit=unit,
    )


def purchased_item(
    name: str,
    required: float,
    package: float,
    *,
    unit: str = "g",
    price: float = 10,
):
    candidate = ProductCandidate(
        product_id=f"product-{name}",
        product_name=f"{name} {package} {unit}",
        canonical_name=name,
        store_id="store",
        store_name="Butik",
        package_quantity=package,
        package_unit=unit,
        usable_quantity=package,
        usable_unit=unit,
        quantity_confidence=QuantityConfidence.EXACT,
        semantic_confidence=SemanticConfidence.HIGH,
        price=price,
        effective_price=price,
        match_score=1,
    )
    return BasketCalculator().calculate_item(requirement(name, required, unit), candidate)


def test_700_required_and_1000_purchased_passes_with_surplus_value() -> None:
    result = BasketAuditor().audit(
        [requirement("potatis", 700)],
        [purchased_item("potatis", 700, 1000, price=20)],
    )

    row = result.items[0]
    assert result.status == BasketAuditStatus.PASS
    assert result.passed
    assert row.status == BasketAuditStatus.PASS
    assert row.purchased_usable_quantity == 1000
    assert row.surplus_quantity == 300
    assert row.surplus_percent == 42.86
    assert row.estimated_surplus_value == 6
    assert row.selected_products[0].product_id == "product-potatis"
    assert row.selected_products[0].packages_needed == 1
    assert result.unit_totals[0].surplus_quantity == 300
    assert result.estimated_surplus_value_total == 6
    assert result.ingredients_checked == 1
    assert result.unknown_quantities == 0


def test_1200_required_and_only_1000_purchased_is_blocking_failure() -> None:
    # The selected product came from an earlier 700 g calculation. The auditor
    # independently checks it against the complete 1200 g weekly requirement.
    result = BasketAuditor().audit(
        [requirement("potatis", 1200)],
        [purchased_item("potatis", 700, 1000)],
    )

    assert result.status == BasketAuditStatus.FAIL
    assert not result.passed
    assert len(result.deficits) == 1
    assert result.deficits[0].canonical_name == "potatis"
    assert result.deficits[0].deficit_quantity == 200


def test_pantry_policy_uses_canonical_ids_and_does_not_exempt_creme_fraiche() -> None:
    assert DEFAULT_PANTRY_ITEMS == {
        "salt",
        "black_pepper",
        "water",
        "neutral_cooking_oil",
    }
    auditor = BasketAuditor()
    assert auditor.is_pantry("svartpeppar")
    assert auditor.is_pantry(requirement("vatten", 500, "ml"))
    assert not auditor.is_pantry("crème fraiche")

    result = auditor.audit(
        [
            requirement("salt", 5),
            requirement("svartpeppar", 2),
            requirement("vatten", 500, "ml"),
            requirement("neutral matolja", 20, "ml"),
            requirement("crème fraiche", 200),
        ],
        [],
    )

    assert {item.canonical_name for item in result.pantry_items} == {
        "salt",
        "black_pepper",
        "water",
        "neutral_cooking_oil",
    }
    assert [row.canonical_name for row in result.deficits] == ["crème fraiche"]
    assert result.unknown_quantities == 1


def test_shared_weekly_package_is_audited_after_requirement_aggregation() -> None:
    result = BasketAuditor().audit(
        [requirement("potatis", 600), requirement("potatis", 700)],
        [purchased_item("potatis", 1300, 2000, price=19.90)],
    )

    assert result.passed
    assert len(result.items) == 1
    assert result.items[0].required_quantity == 1300
    assert result.items[0].purchased_usable_quantity == 2000
    assert result.items[0].surplus_quantity == 700
