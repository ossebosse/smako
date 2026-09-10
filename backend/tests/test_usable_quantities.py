import pytest
from app.models.basket import BasketItem
from app.models.ingredient import NormalizedIngredient
from app.models.product import Product, ProductCandidate, QuantityConfidence
from app.services.basket_calculator import BasketCalculator


def candidate(
    *,
    package_quantity: float,
    package_unit: str,
    usable_quantity: float | None = None,
    usable_unit: str | None = None,
    confidence: QuantityConfidence = QuantityConfidence.UNKNOWN,
    variable_weight: bool = False,
    price: float = 10,
) -> ProductCandidate:
    return ProductCandidate(
        product_id="p",
        product_name="Produkt",
        canonical_name="råvara",
        store_id="s",
        store_name="Butik",
        package_quantity=package_quantity,
        package_unit=package_unit,
        usable_quantity=usable_quantity,
        usable_unit=usable_unit,
        quantity_confidence=confidence,
        variable_weight=variable_weight,
        price=price,
        effective_price=price,
        match_score=1,
    )


def test_old_product_payload_gets_honest_backward_compatible_fallback() -> None:
    product = Product(
        product_id="old",
        name="Pasta 1 kg",
        canonical_name="pasta",
        category="skafferi",
        store_id="s",
        store_name="Butik",
        package_quantity=1000,
        package_unit="g",
        price=20,
    )

    assert product.usable_quantity == 1000
    assert product.usable_unit == "g"
    assert product.quantity_confidence == QuantityConfidence.UNKNOWN
    assert product.normalized_unit_price == 20

    old_basket_payload = BasketItem(
        ingredient="pasta",
        product_id="old",
        product_name="Pasta 1 kg",
        store_id="s",
        store_name="Butik",
        required_quantity=700,
        unit="g",
        package_quantity=1000,
        packages_needed=1,
        purchased_quantity=1000,
        waste_quantity=300,
        unit_price=20,
        total_price=20,
    )
    assert old_basket_payload.package_unit == "g"
    assert old_basket_payload.usable_quantity == 1000
    assert old_basket_payload.purchased_usable_quantity == 1000
    assert old_basket_payload.quantity_confidence == QuantityConfidence.UNKNOWN


@pytest.mark.parametrize(
    ("required", "package_quantity", "unit", "expected_packages"),
    [
        (1200, 1000, "g", 2),
        (1200, 1000, "ml", 2),
        (13, 12, "st", 2),
    ],
)
def test_dry_liquid_and_egg_packages_use_usable_quantity(
    required: float,
    package_quantity: float,
    unit: str,
    expected_packages: int,
) -> None:
    item = BasketCalculator().calculate_item(
        NormalizedIngredient(
            canonical_name="råvara", required_quantity=required, unit=unit
        ),
        candidate(
            package_quantity=package_quantity,
            package_unit=unit,
            usable_quantity=package_quantity,
            usable_unit=unit,
            confidence=QuantityConfidence.EXACT,
        ),
    )

    assert item.packages_needed == expected_packages
    assert item.purchased_usable_quantity == package_quantity * expected_packages
    assert item.quantity_confidence == QuantityConfidence.EXACT


def test_drained_weight_controls_package_count_and_surplus() -> None:
    drained = candidate(
        package_quantity=380,
        package_unit="g",
        usable_quantity=230,
        usable_unit="g",
        confidence=QuantityConfidence.EXACT,
        price=12.90,
    )
    item = BasketCalculator().calculate_item(
        NormalizedIngredient(
            canonical_name="kidneybönor", required_quantity=350, unit="g"
        ),
        drained,
    )

    assert item.packages_needed == 2
    assert item.package_quantity == 380
    assert item.purchased_quantity == 760
    assert item.usable_quantity == 230
    assert item.purchased_usable_quantity == 460
    assert item.waste_quantity == 110
    assert item.total_price == 25.80


def test_estimated_weight_per_piece_buys_four_onions() -> None:
    onion = candidate(
        package_quantity=1,
        package_unit="st",
        usable_quantity=175,
        usable_unit="g",
        confidence=QuantityConfidence.ESTIMATED,
        price=1.91,
    )
    item = BasketCalculator().calculate_item(
        NormalizedIngredient(
            canonical_name="gul lök", required_quantity=600, unit="g"
        ),
        onion,
    )

    assert item.packages_needed == 4
    assert item.purchased_quantity == 4
    assert item.package_unit == "st"
    assert item.purchased_usable_quantity == 700
    assert item.waste_quantity == 100
    assert item.quantity_confidence == QuantityConfidence.ESTIMATED


def test_variable_per_kilo_product_is_prorated_to_requested_weight() -> None:
    item = BasketCalculator().calculate_item(
        NormalizedIngredient(
            canonical_name="potatis", required_quantity=700, unit="g"
        ),
        candidate(
            package_quantity=1000,
            package_unit="g",
            usable_quantity=1000,
            usable_unit="g",
            confidence=QuantityConfidence.EXACT,
            variable_weight=True,
            price=69.90,
        ),
    )

    assert item.packages_needed == 1
    assert item.purchased_quantity == 700
    assert item.purchased_usable_quantity == 700
    assert item.waste_quantity == 0
    assert item.total_price == 48.93
    assert item.variable_weight


def test_legacy_waste_semantics_remain_for_equal_gross_and_usable_weight() -> None:
    item = BasketCalculator().calculate_item(
        NormalizedIngredient(
            canonical_name="kyckling", required_quantity=1200, unit="g"
        ),
        candidate(package_quantity=500, package_unit="g", price=40),
    )

    assert item.packages_needed == 3
    assert item.purchased_quantity == item.purchased_usable_quantity == 1500
    assert item.waste_quantity == 300
