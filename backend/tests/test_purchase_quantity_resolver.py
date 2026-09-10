from decimal import Decimal

import pytest
from app.models.product import (
    OfferKind,
    OfferMetadata,
    Product,
    ProductCandidate,
    ProductSemantics,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver


def semantics(**overrides: object) -> ProductSemantics:
    values: dict[str, object] = {
        "product_id": "product-1",
        "canonical_food": "pasta",
        "sale_price": 40,
        "semantic_confidence": SemanticConfidence.HIGH,
        "quantity_confidence": QuantityConfidence.EXACT,
    }
    values.update(overrides)
    return ProductSemantics(**values)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    ("field", "companions"),
    [
        ("sale_price", {}),
        ("package_quantity", {"package_unit": "g"}),
        ("usable_quantity", {"usable_unit": "g"}),
        ("comparison_price", {"comparison_unit": "kg"}),
        ("piece_price", {}),
        ("estimated_piece_weight", {}),
    ],
)
def test_product_semantics_rejects_non_finite_money_and_quantities(
    field: str,
    companions: dict[str, object],
    value: float,
) -> None:
    with pytest.raises(ValueError):
        semantics(**companions, **{field: value})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_offer_metadata_rejects_non_finite_price(value: float) -> None:
    with pytest.raises(ValueError):
        OfferMetadata(
            kind=OfferKind.CAMPAIGN,
            description="Veckans pris",
            price=value,
        )


@pytest.mark.parametrize("field", ["price", "effective_price", "member_price"])
def test_product_rejects_non_finite_checkout_prices(field: str) -> None:
    values: dict[str, object] = {
        "product_id": "pasta",
        "name": "Pasta 500 g",
        "canonical_name": "pasta",
        "category": "skafferi",
        "store_id": "store",
        "store_name": "Butik",
        "package_quantity": 500,
        "package_unit": "g",
        "price": 20,
        "effective_price": 20,
    }
    values[field] = float("inf")

    with pytest.raises(ValueError):
        Product(**values)


def test_legacy_fixed_package_payload_remains_compatible() -> None:
    product = Product(
        product_id="pasta-1kg",
        name="Pasta 1 kg",
        canonical_name="pasta",
        category="skafferi",
        store_id="store",
        store_name="Butik",
        package_quantity=1000,
        package_unit="g",
        price=19.90,
    )

    assert product.sale_model == SaleModel.FIXED_PACKAGE
    assert product.sale_price == 19.90
    assert product.package_quantity == product.usable_quantity == 1000
    assert product.package_unit == product.usable_unit == "g"
    assert product.canonical_food == "pasta"

    candidate = ProductCandidate.from_product(product, match_score=0.9)
    assert candidate.sale_model == SaleModel.FIXED_PACKAGE
    assert candidate.sale_price == 19.90
    assert candidate.package_quantity == 1000


def test_legacy_variable_weight_maps_to_sold_by_weight() -> None:
    product = semantics(
        package_quantity=1000,
        package_unit="g",
        variable_weight=True,
        sale_price=39.90,
        sale_unit="kg",
    )

    assert product.sale_model == SaleModel.SOLD_BY_WEIGHT
    assert product.variable_weight
    assert product.usable_quantity == 1000


def test_explicit_variable_weight_package_is_not_overridden_by_legacy_flag() -> None:
    product = semantics(
        sale_model=SaleModel.VARIABLE_WEIGHT_PACKAGE,
        package_quantity=850,
        package_unit="g",
        variable_weight=True,
    )

    assert product.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE


def test_comparison_price_does_not_create_a_package_quantity() -> None:
    pepper = semantics(
        canonical_food="red_pepper",
        sale_price=10.79,
        comparison_price=39.90,
        comparison_unit="kg",
        quantity_confidence=QuantityConfidence.UNKNOWN,
    )

    assert pepper.sale_model == SaleModel.UNKNOWN
    assert pepper.package_quantity is None
    assert pepper.package_unit is None
    assert pepper.usable_quantity is None

    resolution = PurchaseQuantityResolver().resolve(
        pepper, required_quantity=350, required_unit="g"
    )
    assert not resolution.resolved
    assert resolution.total_price is None
    assert resolution.quantity_confidence == QuantityConfidence.UNKNOWN


def test_fixed_package_rounds_up_whole_packages() -> None:
    pasta = semantics(
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=500,
        package_unit="g",
        sale_price=40,
    )

    result = PurchaseQuantityResolver().resolve(pasta, required_quantity=1200, required_unit="g")

    assert result.resolved
    assert result.packages_needed == 3
    assert result.purchased_quantity == Decimal(1500)
    assert result.purchased_usable_quantity == Decimal(1500)
    assert result.waste_quantity == Decimal(300)
    assert result.total_price == Decimal("120.00")


def test_package_usable_quantity_cannot_exceed_gross_quantity() -> None:
    with pytest.raises(ValueError, match="cannot exceed gross"):
        semantics(
            sale_model=SaleModel.FIXED_PACKAGE,
            package_quantity=500,
            package_unit="g",
            usable_quantity=800,
            usable_unit="g",
        )

    # The resolver remains fail-closed even if an internal model_copy bypasses
    # normal Pydantic construction validation.
    valid = semantics(
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=500,
        package_unit="g",
    )
    impossible = valid.model_copy(update={"usable_quantity": 800, "usable_unit": "g"})
    result = PurchaseQuantityResolver().resolve(
        impossible,
        required_quantity=400,
        required_unit="g",
    )
    assert not result.resolved
    assert "cannot exceed gross" in str(result.error)


def test_sold_by_weight_prorates_rate_instead_of_buying_one_kilo() -> None:
    pepper = semantics(
        canonical_food="red_pepper",
        sale_model=SaleModel.SOLD_BY_WEIGHT,
        sale_price=10.79,
        comparison_price=39.90,
        comparison_unit="kg",
        quantity_confidence=QuantityConfidence.DERIVED,
    )

    result = PurchaseQuantityResolver().resolve(pepper, required_quantity=350, required_unit="g")

    assert result.resolved
    assert result.packages_needed == 1
    assert result.purchased_quantity == Decimal(350)
    assert result.purchased_usable_quantity == Decimal(350)
    assert result.waste_quantity == 0
    assert result.total_price == Decimal("13.97")
    assert result.quantity_confidence == QuantityConfidence.DERIVED
    assert pepper.package_quantity is None


def test_explicit_sale_rate_takes_precedence_over_comparison_rate() -> None:
    product = semantics(
        sale_model=SaleModel.SOLD_BY_WEIGHT,
        sale_price=35,
        sale_unit="kg",
        comparison_price=39.90,
        comparison_unit="kg",
        quantity_confidence=QuantityConfidence.DERIVED,
    )

    result = PurchaseQuantityResolver().resolve(product, required_quantity=200, required_unit="g")

    assert result.total_price == Decimal("7.00")


def test_tiny_positive_weight_purchase_rounds_to_one_cent_without_validation_failure() -> None:
    product = semantics(
        sale_model=SaleModel.SOLD_BY_WEIGHT,
        sale_price=10,
        sale_unit="kg",
        quantity_confidence=QuantityConfidence.DERIVED,
    )

    result = PurchaseQuantityResolver().resolve(
        product,
        required_quantity=0.1,
        required_unit="g",
    )

    assert result.resolved
    assert result.unit_price == result.total_price == Decimal("0.01")


def test_sold_by_piece_uses_estimated_piece_weight_for_weight_need() -> None:
    onion = semantics(
        canonical_food="yellow_onion",
        sale_model=SaleModel.SOLD_BY_PIECE,
        sale_price=3,
        sale_unit="st",
        piece_price=3,
        estimated_piece_weight=175,
        estimated_piece_weight_unit="g",
    )

    result = PurchaseQuantityResolver().resolve(onion, required_quantity=500, required_unit="g")

    assert result.resolved
    assert result.packages_needed == 3
    assert result.purchased_quantity == Decimal(3)
    assert result.purchased_unit == "st"
    assert result.purchased_usable_quantity == Decimal(525)
    assert result.waste_quantity == Decimal(25)
    assert result.total_price == Decimal("9.00")
    assert result.quantity_confidence == QuantityConfidence.ESTIMATED
    assert result.uses_estimate


def test_variable_weight_package_is_explicitly_estimated() -> None:
    meat = semantics(
        canonical_food="beef_meat",
        sale_model=SaleModel.VARIABLE_WEIGHT_PACKAGE,
        package_quantity=500,
        package_unit="g",
        sale_price=39.90,
        sale_unit="kg",
        comparison_price=39.90,
        comparison_unit="kg",
        quantity_confidence=QuantityConfidence.ESTIMATED,
    )

    result = PurchaseQuantityResolver().resolve(meat, required_quantity=700, required_unit="g")

    assert result.resolved
    assert result.packages_needed == 2
    assert result.purchased_quantity == Decimal(1000)
    assert result.purchased_usable_quantity == Decimal(1000)
    assert result.total_price == Decimal("39.90")
    assert result.quantity_confidence == QuantityConfidence.ESTIMATED
    assert result.warning == "variable package weight and total are estimates"


def test_variable_weight_package_without_rate_uses_representative_package_price() -> None:
    product = semantics(
        canonical_food="beef_meat",
        sale_model=SaleModel.VARIABLE_WEIGHT_PACKAGE,
        package_quantity=500,
        package_unit="g",
        sale_price=50,
        sale_unit="package",
        quantity_confidence=QuantityConfidence.ESTIMATED,
    )

    result = PurchaseQuantityResolver().resolve(
        product,
        required_quantity=700,
        required_unit="g",
    )

    assert result.resolved
    assert result.packages_needed == 2
    assert result.purchased_quantity == Decimal(1000)
    assert result.total_price == Decimal("100.00")
    assert result.unit_price == Decimal("50.00")


def test_variable_weight_package_does_not_upgrade_unknown_source_confidence() -> None:
    ambiguous = semantics(
        canonical_food="beef_meat",
        sale_model=SaleModel.VARIABLE_WEIGHT_PACKAGE,
        package_quantity=500,
        package_unit="g",
        sale_price=39.90,
        sale_unit="kg",
        quantity_confidence=QuantityConfidence.UNKNOWN,
    )

    result = PurchaseQuantityResolver().resolve(
        ambiguous,
        required_quantity=400,
        required_unit="g",
    )

    assert not result.resolved
    assert result.quantity_confidence == QuantityConfidence.UNKNOWN
    assert "confidence is unknown" in str(result.error)


def test_unknown_purchase_model_is_never_an_exact_resolution() -> None:
    unknown = semantics(
        sale_model=SaleModel.UNKNOWN,
        sale_price=10.79,
        quantity_confidence=QuantityConfidence.UNKNOWN,
    )

    result = PurchaseQuantityResolver().resolve(unknown, required_quantity=350, required_unit="g")

    assert not result.resolved
    assert result.packages_needed is None
    assert result.purchased_quantity is None
    assert result.total_price is None
    assert result.error == "purchase model is unknown"


def test_fixed_package_without_package_metadata_is_unresolved() -> None:
    incomplete = semantics(sale_model=SaleModel.FIXED_PACKAGE)

    result = PurchaseQuantityResolver().resolve(
        incomplete, required_quantity=100, required_unit="g"
    )

    assert not result.resolved
    assert "explicit package" in str(result.error)
