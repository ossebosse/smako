import pytest
from app.models.basket import (
    BasketAuditStatus,
    BasketItem,
    BasketVerificationStatus,
    OptimizedBasket,
    OptimizedStoreGroup,
    StoreBasket,
)
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver


def requirement(quantity: float = 350, unit: str = "g") -> NormalizedIngredient:
    return NormalizedIngredient(
        canonical_name="paprika",
        required_quantity=quantity,
        unit=unit,
    )


def candidate(**overrides: object) -> ProductCandidate:
    values: dict[str, object] = {
        "product_id": "pepper",
        "product_name": "Paprika röd",
        "canonical_name": "paprika",
        "canonical_food": "red_pepper",
        "food_family": "vegetable",
        "product_role": "whole_vegetable",
        "store_id": "store",
        "store_name": "Butik",
        "sale_model": SaleModel.FIXED_PACKAGE,
        "package_quantity": 500,
        "package_unit": "g",
        "usable_quantity": 500,
        "usable_unit": "g",
        "quantity_confidence": QuantityConfidence.EXACT,
        "semantic_confidence": SemanticConfidence.HIGH,
        "price": 20,
        "effective_price": 20,
        "match_score": 1,
    }
    values.update(overrides)
    return ProductCandidate(**values)


def test_calculator_and_auditor_can_share_the_authoritative_resolver_instance() -> None:
    resolver = PurchaseQuantityResolver()
    calculator = BasketCalculator(resolver=resolver)
    auditor = BasketAuditor(resolver=resolver)

    assert calculator.resolver is resolver
    assert auditor.resolver is resolver

    required = requirement()
    item = calculator.calculate_item(required, candidate())
    audit = auditor.audit([required], [item])

    assert audit.status == BasketAuditStatus.PASS
    assert audit.items[0].quantity_reconciled
    assert audit.items[0].cost_reconciled


def test_sold_by_weight_is_a_derived_cost_not_a_one_kilo_package() -> None:
    item = BasketCalculator().calculate_item(
        requirement(),
        candidate(
            sale_model=SaleModel.SOLD_BY_WEIGHT,
            package_quantity=None,
            package_unit=None,
            usable_quantity=None,
            usable_unit=None,
            sale_price=10.79,
            sale_unit=None,
            comparison_price=39.90,
            comparison_unit="kg",
            quantity_confidence=QuantityConfidence.DERIVED,
            variable_weight=True,
            price=10.79,
            effective_price=10.79,
        ),
    )

    assert item.sale_model == SaleModel.SOLD_BY_WEIGHT
    assert item.package_quantity is None
    assert item.packages_needed == 1
    assert item.purchased_quantity == 350
    assert item.total_price == 13.97
    assert item.verification_status == BasketVerificationStatus.VERIFIED


def test_piece_purchase_exposes_estimated_weight_and_status() -> None:
    item = BasketCalculator().calculate_item(
        requirement(500),
        candidate(
            sale_model=SaleModel.SOLD_BY_PIECE,
            package_quantity=None,
            package_unit=None,
            usable_quantity=None,
            usable_unit=None,
            sale_price=3,
            sale_unit="st",
            piece_price=3,
            estimated_piece_weight=175,
            quantity_confidence=QuantityConfidence.ESTIMATED,
            price=3,
            effective_price=3,
        ),
    )

    assert item.packages_needed == 3
    assert item.purchased_quantity == 3
    assert item.purchased_unit == "st"
    assert item.purchased_usable_quantity == 525
    assert item.total_price == 9
    assert item.verification_status == BasketVerificationStatus.VERIFIED_WITH_ESTIMATES


def test_piece_checkout_uses_piece_price_instead_of_legacy_effective_price() -> None:
    item = BasketCalculator().calculate_item(
        requirement(500),
        candidate(
            sale_model=SaleModel.SOLD_BY_PIECE,
            package_quantity=None,
            package_unit=None,
            usable_quantity=None,
            usable_unit=None,
            sale_price=3,
            sale_unit="st",
            piece_price=3,
            estimated_piece_weight=175,
            quantity_confidence=QuantityConfidence.ESTIMATED,
            price=5,
            effective_price=5,
        ),
    )

    assert item.packages_needed == 3
    assert item.unit_price == 3
    assert item.total_price == 9
    assert item.regular_total_price == 15
    audit = BasketAuditor().audit([requirement(500)], [item])
    assert audit.status == BasketAuditStatus.PASS
    assert audit.items[0].cost_reconciled
    assert audit.items[0].selected_products[0].cost_reconciled


def test_auditor_rejects_non_package_cost_disagreement() -> None:
    valid = BasketCalculator().calculate_item(
        requirement(),
        candidate(
            sale_model=SaleModel.SOLD_BY_WEIGHT,
            package_quantity=None,
            package_unit=None,
            usable_quantity=None,
            usable_unit=None,
            sale_price=39.90,
            sale_unit="kg",
            quantity_confidence=QuantityConfidence.DERIVED,
        ),
    )
    tampered = valid.model_copy(update={"total_price": 39.90, "unit_price": 39.90})

    audit = BasketAuditor().audit([requirement()], [tampered])

    assert audit.status == BasketAuditStatus.FAIL
    assert audit.verification_status == BasketVerificationStatus.INVALID
    assert not audit.items[0].cost_reconciled
    assert not audit.items[0].selected_products[0].cost_reconciled
    assert "cost differs" in str(audit.items[0].selected_products[0].reconciliation_error)


def test_auditor_independently_reconciles_fixed_campaign_checkout() -> None:
    offer = OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description="Kampanjpris",
        price=15,
    )
    required = requirement(1200)
    valid = BasketCalculator().calculate_item(
        required,
        candidate(price=20, effective_price=15, offers=[offer]),
    )

    assert valid.base_checkout_unit_price == 15
    assert valid.packages_needed == 3
    assert valid.total_price == 45
    assert BasketAuditor().audit([required], [valid]).status == BasketAuditStatus.PASS

    tampered = valid.model_copy(update={"total_price": 0.01})
    audit = BasketAuditor().audit([required], [tampered])
    assert audit.status == BasketAuditStatus.FAIL
    assert audit.verification_status == BasketVerificationStatus.INVALID
    assert not audit.items[0].cost_reconciled


def test_auditor_rejects_tampered_fixed_checkout_unit_price() -> None:
    required = requirement(1200)
    valid = BasketCalculator().calculate_item(
        required,
        candidate(price=20, effective_price=20),
    )

    assert valid.packages_needed == 3
    assert valid.unit_price == 20
    assert valid.total_price == 60

    # Pydantic's model_copy deliberately bypasses validation.  The independent
    # audit must therefore reconcile both the checkout total and the displayed
    # package price against the shared fixed-checkout resolver.
    tampered = valid.model_copy(update={"unit_price": 1})
    audit = BasketAuditor().audit([required], [tampered])

    assert audit.status == BasketAuditStatus.FAIL
    assert audit.verification_status == BasketVerificationStatus.INVALID
    assert not audit.items[0].cost_reconciled
    assert not audit.items[0].selected_products[0].cost_reconciled
    assert "fixed checkout" in str(audit.items[0].selected_products[0].reconciliation_error)


def test_auditor_independently_reconciles_fixed_multipack_with_remainder() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="3 för 45 kr",
        price=45,
        required_packages=3,
    )
    required = requirement(1700)
    valid = BasketCalculator().calculate_item(
        required,
        candidate(price=20, effective_price=20, offers=[offer]),
    )

    assert valid.base_checkout_unit_price == 20
    assert valid.packages_needed == 4
    assert valid.total_price == 65
    assert BasketAuditor().audit([required], [valid]).status == BasketAuditStatus.PASS

    tampered = valid.model_copy(update={"total_price": 64})
    audit = BasketAuditor().audit([required], [tampered])
    assert audit.status == BasketAuditStatus.FAIL
    assert not audit.items[0].cost_reconciled


def test_unknown_purchase_model_cannot_create_an_exact_basket_item() -> None:
    with pytest.raises(ValueError, match="Unresolved purchase quantity"):
        BasketCalculator().calculate_item(
            requirement(),
            candidate(
                sale_model=SaleModel.UNKNOWN,
                package_quantity=None,
                package_unit=None,
                usable_quantity=None,
                usable_unit=None,
                quantity_confidence=QuantityConfidence.UNKNOWN,
            ),
        )


def test_unknown_sale_model_is_never_reported_as_verified() -> None:
    item = BasketItem(
        ingredient="avokado",
        product_id="ambiguous",
        product_name="Avokado",
        store_id="store",
        store_name="Butik",
        required_quantity=1,
        unit="st",
        canonical_food="avocado",
        semantic_confidence=SemanticConfidence.HIGH,
        sale_model=SaleModel.UNKNOWN,
        sale_price=12.90,
        quantity_confidence=QuantityConfidence.DERIVED,
        packages_needed=1,
        purchased_quantity=1,
        purchased_unit="st",
        purchased_usable_quantity=1,
        waste_quantity=0,
        unit_price=12.90,
        total_price=12.90,
    )

    assert item.verification_status == BasketVerificationStatus.UNVERIFIED


def test_unknown_confidence_is_mathematically_auditable_but_unverified() -> None:
    item = BasketCalculator().calculate_item(
        requirement(),
        candidate(quantity_confidence=QuantityConfidence.UNKNOWN),
    )

    audit = BasketAuditor().audit([requirement()], [item])

    assert audit.status == BasketAuditStatus.PASS
    assert audit.verification_status == BasketVerificationStatus.UNVERIFIED
    assert audit.unknown_quantities == 1


def test_auditor_recomputes_with_resolver_and_rejects_quantity_disagreement() -> None:
    item = BasketItem(
        ingredient="paprika",
        product_id="pepper",
        product_name="Paprika röd",
        store_id="store",
        store_name="Butik",
        canonical_food="red_pepper",
        product_role="whole_vegetable",
        semantic_confidence=SemanticConfidence.HIGH,
        sale_model=SaleModel.SOLD_BY_WEIGHT,
        sale_price=10.79,
        comparison_price=39.90,
        comparison_unit="kg",
        required_quantity=350,
        unit="g",
        quantity_confidence=QuantityConfidence.DERIVED,
        variable_weight=True,
        packages_needed=1,
        purchased_quantity=400,
        purchased_unit="g",
        purchased_usable_quantity=400,
        waste_quantity=50,
        unit_price=13.97,
        total_price=13.97,
    )

    audit = BasketAuditor().audit([requirement()], [item])

    assert audit.status == BasketAuditStatus.FAIL
    assert audit.verification_status == BasketVerificationStatus.INVALID
    assert not audit.items[0].quantity_reconciled
    assert not audit.items[0].selected_products[0].quantity_reconciled
    assert "PurchaseQuantityResolver" in str(
        audit.items[0].selected_products[0].reconciliation_error
    )


def test_store_and_optimized_totals_must_reconcile_with_item_costs() -> None:
    required = requirement(350)
    item = BasketCalculator().calculate_item(required, candidate(price=20, effective_price=20))
    assert item.total_price == 20

    store = StoreBasket(
        store_id="store",
        store_name="Butik",
        total=1,
        items=[item],
    )
    assert not store.total_reconciled
    assert store.verification_status == BasketVerificationStatus.INVALID
    store_audit = BasketAuditor().audit([required], store)
    assert store_audit.status == BasketAuditStatus.FAIL
    assert not store_audit.totals_reconciled
    assert store_audit.calculated_total == 20
    assert store_audit.reported_total == 1

    group = OptimizedStoreGroup(
        store_id="store",
        store_name="Butik",
        items=[item],
        subtotal=1,
    )
    basket = OptimizedBasket(total=1, stores=[group], max_stores=1)
    assert not group.subtotal_reconciled
    assert not basket.total_reconciled
    assert basket.verification_status == BasketVerificationStatus.INVALID
    audit = BasketAuditor().audit([required], basket)
    assert audit.status == BasketAuditStatus.FAIL
    assert audit.verification_status == BasketVerificationStatus.INVALID
    assert not audit.totals_reconciled
    assert "store subtotal" in " ".join(audit.total_reconciliation_errors)


def test_auditor_detects_total_tampering_after_model_validation() -> None:
    required = requirement(350)
    item = BasketCalculator().calculate_item(required, candidate(price=20, effective_price=20))
    valid = OptimizedBasket(
        total=20,
        stores=[
            OptimizedStoreGroup(
                store_id="store",
                store_name="Butik",
                items=[item],
                subtotal=20,
            )
        ],
        max_stores=1,
    )
    assert valid.total_reconciled
    assert valid.verification_status == BasketVerificationStatus.VERIFIED

    tampered = valid.model_copy(update={"total": 0.01})
    audit = BasketAuditor().audit([required], tampered)
    assert audit.status == BasketAuditStatus.FAIL
    assert audit.verification_status == BasketVerificationStatus.INVALID
    assert not audit.totals_reconciled


@pytest.mark.parametrize("basket_kind", ["store", "optimized"])
def test_auditor_preserves_an_invalid_container_status(basket_kind: str) -> None:
    required = requirement(350)
    item = BasketCalculator().calculate_item(required, candidate(price=20, effective_price=20))
    if basket_kind == "store":
        basket: StoreBasket | OptimizedBasket = StoreBasket(
            store_id="store",
            store_name="Butik",
            total=20,
            items=[item],
            verification_status=BasketVerificationStatus.INVALID,
        )
    else:
        basket = OptimizedBasket(
            total=20,
            stores=[
                OptimizedStoreGroup(
                    store_id="store",
                    store_name="Butik",
                    items=[item],
                    subtotal=20,
                )
            ],
            max_stores=1,
            verification_status=BasketVerificationStatus.INVALID,
        )

    assert basket.total_reconciled
    assert basket.verification_status == BasketVerificationStatus.INVALID

    audit = BasketAuditor().audit([required], basket)

    assert audit.totals_reconciled
    assert audit.status == BasketAuditStatus.FAIL
    assert audit.verification_status == BasketVerificationStatus.INVALID
