from datetime import UTC, datetime

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
)
from app.models.provenance import SourceProvenance
from app.services.basket_calculator import (
    BasketCalculator,
    BasketItemQuote,
    calculate_packages,
)


def candidate(
    *,
    package_quantity: float = 500,
    price: float = 40,
    effective_price: float | None = None,
    offers: list[OfferMetadata] | None = None,
) -> ProductCandidate:
    return ProductCandidate(
        product_id="product-1",
        product_name="Testprodukt",
        canonical_name="kyckling",
        store_id="store-1",
        store_name="Testbutik",
        package_quantity=package_quantity,
        package_unit="g",
        price=price,
        effective_price=price if effective_price is None else effective_price,
        match_score=1,
        offers=offers or [],
    )


def test_exact_required_package_example_from_specification() -> None:
    # Behov 1200 g, förpackning 500 g, pris 40 kr => 3 paket och 120 kr.
    ingredient = NormalizedIngredient(canonical_name="kyckling", required_quantity=1200, unit="g")

    item = BasketCalculator().calculate_item(ingredient, candidate())

    assert item.packages_needed == 3
    assert item.total_price == 120.00
    assert item.purchased_quantity == 1500
    assert item.waste_quantity == 300
    assert item.regular_total_price == 120.00


def test_ceil_at_package_boundary() -> None:
    assert calculate_packages(500, 500) == 1
    assert calculate_packages(500.001, 500) == 2


def test_public_multipack_only_applies_at_required_count() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="3 för 90 kr",
        price=90,
        required_packages=3,
    )
    calculator = BasketCalculator()

    below = calculator.calculate_item(
        NormalizedIngredient(canonical_name="kyckling", required_quantity=900, unit="g"),
        candidate(price=40, offers=[offer]),
    )
    qualified = calculator.calculate_item(
        NormalizedIngredient(canonical_name="kyckling", required_quantity=1200, unit="g"),
        candidate(price=40, offers=[offer]),
    )

    assert below.packages_needed == 2
    assert below.total_price == 80
    assert below.applied_offer is None
    assert qualified.packages_needed == 3
    assert qualified.total_price == 90
    assert qualified.applied_offer == offer
    assert qualified.offer_description == "3 för 90 kr"


def test_lightweight_quote_materializes_exact_checkout_result() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="3 för 90 kr",
        price=90,
        required_packages=3,
    )
    ingredient = NormalizedIngredient(canonical_name="kyckling", required_quantity=1700, unit="g")
    calculator = BasketCalculator()

    quote = calculator.quote_item(
        ingredient,
        candidate(price=40, offers=[offer]),
    )
    item = quote.to_basket_item()

    assert isinstance(quote, BasketItemQuote)
    assert item.packages_needed == 4
    assert item.purchased_quantity == 2000
    assert item.waste_quantity == 300
    assert item.unit_price == 32.50
    assert item.total_price == 130
    assert item.regular_total_price == 160
    assert item.applied_offer == offer
    assert item.offer_description == "3 för 90 kr"


def test_selected_basket_item_preserves_source_snapshot_lineage() -> None:
    provenance = SourceProvenance(
        source_provider="own",
        source_channel="catalog",
        source_snapshot_id="snapshot-citygross-1",
        source_observed_at=datetime.now(tz=UTC),
    )
    source_candidate = candidate().model_copy(update={"source_provenance": provenance})

    quote = BasketCalculator().quote_item(
        NormalizedIngredient(canonical_name="kyckling", required_quantity=500, unit="g"),
        source_candidate,
    )

    assert quote.source_provenance == provenance
    assert quote.to_basket_item().source_provenance == provenance


def test_single_member_price_cap_charges_regular_price_after_two_packages() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MEMBER,
        description="Medlemspris 39 kr, max 2 styck",
        price=39,
        max_quantity=2,
        member_program="Coop medlem",
    )

    item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="smör", required_quantity=1500, unit="g"),
        candidate(
            package_quantity=500,
            price=59.57,
            effective_price=39,
            offers=[offer],
        ),
    )

    assert item.packages_needed == 3
    assert item.total_price == 137.57
    assert item.applied_offer == offer


def test_multibuy_cap_limits_discounted_groups() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 för 105 kr, max 1 köp",
        price=105,
        required_packages=2,
        max_quantity=1,
        member_program="Coop medlem",
    )

    item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="kaffe", required_quantity=2000, unit="g"),
        candidate(package_quantity=500, price=74.65, offers=[offer]),
    )

    assert item.packages_needed == 4
    assert item.total_price == 254.30
    assert item.applied_offer == offer


def test_money_is_rounded_to_integer_cents() -> None:
    item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="kyckling", required_quantity=501, unit="g"),
        candidate(price=19.995),
    )

    assert item.unit_price == 20.00
    assert item.total_price == 40.00


def test_incompatible_dimensions_are_rejected() -> None:
    ingredient = NormalizedIngredient(canonical_name="ägg", required_quantity=4, unit="st")

    try:
        BasketCalculator().calculate_item(ingredient, candidate())
    except ValueError as error:
        assert "Incompatible units" in str(error)
    else:
        raise AssertionError("Expected incompatible units to fail")


def test_piece_quote_projects_resolved_usable_unit_into_basket_item() -> None:
    ingredient = NormalizedIngredient(canonical_name="ägg", required_quantity=8, unit="st")
    source_candidate = ProductCandidate(
        product_id="piece-with-weight-metadata",
        product_name="Piece product with source weight",
        canonical_name="ägg",
        store_id="store-1",
        store_name="Testbutik",
        price=30,
        effective_price=30,
        sale_model=SaleModel.SOLD_BY_PIECE,
        sale_price=30,
        sale_unit="st",
        piece_price=30,
        package_quantity=1,
        package_unit="st",
        usable_quantity=285,
        usable_unit="g",
        estimated_piece_weight=285,
        estimated_piece_weight_unit="g",
        quantity_confidence=QuantityConfidence.ESTIMATED,
        match_score=1,
    )

    item = BasketCalculator().calculate_item(ingredient, source_candidate)

    assert item.usable_quantity == 1
    assert item.usable_unit == "st"
    assert item.purchased_usable_quantity == 8
    assert item.purchased_unit == "st"
    assert item.packages_needed == 8


@pytest.mark.parametrize("offer_kind", [OfferKind.CAMPAIGN, OfferKind.MEMBER])
@pytest.mark.parametrize(
    ("sale_model", "ingredient", "candidate_updates", "expected_total"),
    [
        (
            SaleModel.SOLD_BY_WEIGHT,
            NormalizedIngredient(canonical_name="kött", required_quantity=4000, unit="g"),
            {
                "sale_unit": "kg",
                "comparison_price": 100,
                "comparison_unit": "kg",
                "variable_weight": True,
            },
            400,
        ),
        (
            SaleModel.SOLD_BY_PIECE,
            NormalizedIngredient(canonical_name="frukt", required_quantity=5, unit="st"),
            {
                "sale_unit": "st",
                "piece_price": 50,
                "package_quantity": 1,
                "package_unit": "st",
                "usable_quantity": 1,
                "usable_unit": "st",
            },
            500,
        ),
        (
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
            NormalizedIngredient(canonical_name="ost", required_quantity=1500, unit="g"),
            {
                "sale_unit": "kg",
                "comparison_price": 50,
                "comparison_unit": "kg",
                "package_quantity": 500,
                "package_unit": "g",
                "usable_quantity": 500,
                "usable_unit": "g",
                "variable_weight": True,
            },
            300,
        ),
    ],
)
def test_capped_non_fixed_single_offer_is_metadata_only_when_cap_unit_is_unknown(
    offer_kind: OfferKind,
    sale_model: SaleModel,
    ingredient: NormalizedIngredient,
    candidate_updates: dict[str, object],
    expected_total: float,
) -> None:
    member_program = "Testklubb" if offer_kind is OfferKind.MEMBER else None
    offer = OfferMetadata(
        kind=offer_kind,
        description="Capped source price",
        price=50,
        max_quantity=2,
        member_program=member_program,
    )
    source_candidate = ProductCandidate(
        product_id=f"capped-{sale_model.value}-{offer_kind.value}",
        product_name="Capped test product",
        canonical_name=ingredient.canonical_name,
        store_id="store-1",
        store_name="Testbutik",
        price=100,
        effective_price=50,
        sale_model=sale_model,
        sale_price=50,
        match_score=1,
        offers=[offer],
        quantity_confidence=QuantityConfidence.EXACT,
        **candidate_updates,
    )

    item = BasketCalculator().calculate_item(ingredient, source_candidate)

    assert item.total_price == expected_total
    assert item.sale_price == 100
    assert item.piece_price == (100 if sale_model is SaleModel.SOLD_BY_PIECE else None)
    assert item.applied_offer is None
    assert item.purchase_warning is not None
    assert "capped non-fixed offer" in item.purchase_warning
    # Fail-close must not mutate or erase source promotion provenance.
    assert source_candidate.offers == [offer]


def test_equivalent_uncapped_non_fixed_offer_keeps_the_checkout_rate() -> None:
    capped = OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description="Max 2",
        price=50,
        max_quantity=2,
    )
    uncapped = OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description="Uncapped equivalent",
        price=50,
    )
    source_candidate = ProductCandidate(
        product_id="uncapped-weight",
        product_name="Uncapped weight product",
        canonical_name="kött",
        store_id="store-1",
        store_name="Testbutik",
        price=100,
        effective_price=50,
        sale_model=SaleModel.SOLD_BY_WEIGHT,
        sale_price=50,
        sale_unit="kg",
        comparison_price=100,
        comparison_unit="kg",
        variable_weight=True,
        match_score=1,
        offers=[capped, uncapped],
        quantity_confidence=QuantityConfidence.EXACT,
    )

    item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="kött", required_quantity=4000, unit="g"),
        source_candidate,
    )

    assert item.total_price == 200
    assert item.sale_price == 50
    assert item.purchase_warning == "cost is derived from actual purchased weight"


def test_capped_comparison_only_weight_rate_fails_closed() -> None:
    offer = OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description="Max 2",
        price=50,
        max_quantity=2,
    )
    source_candidate = ProductCandidate(
        product_id="capped-comparison-weight",
        product_name="Comparison-only weight product",
        canonical_name="kött",
        store_id="store-1",
        store_name="Testbutik",
        price=100,
        effective_price=50,
        sale_model=SaleModel.SOLD_BY_WEIGHT,
        sale_price=50,
        comparison_price=50,
        comparison_unit="kg",
        variable_weight=True,
        match_score=1,
        offers=[offer],
        quantity_confidence=QuantityConfidence.EXACT,
    )

    with pytest.raises(ValueError, match="Unresolved purchase quantity"):
        BasketCalculator().calculate_item(
            NormalizedIngredient(canonical_name="kött", required_quantity=4000, unit="g"),
            source_candidate,
        )


def test_capped_variable_rate_above_package_total_uses_ordinary_comparison_rate() -> None:
    """A kg rate cannot be compared numerically with a representative package total."""

    offer = OfferMetadata(
        kind=OfferKind.MEMBER,
        description="Capped member kg rate",
        price=105,
        max_quantity=3,
        member_program="Testklubb",
    )
    source_candidate = ProductCandidate(
        product_id="capped-variable-cross-unit",
        product_name="Variable package",
        canonical_name="kyckling",
        store_id="store-1",
        store_name="Testbutik",
        # Representative ordinary package total: 850 g * 119 kr/kg.
        price=101.15,
        effective_price=101.15,
        sale_model=SaleModel.VARIABLE_WEIGHT_PACKAGE,
        sale_price=105,
        sale_unit="kg",
        comparison_price=119,
        comparison_unit="kg",
        package_quantity=850,
        package_unit="g",
        usable_quantity=850,
        usable_unit="g",
        variable_weight=True,
        match_score=1,
        offers=[offer],
        quantity_confidence=QuantityConfidence.ESTIMATED,
    )

    item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="kyckling", required_quantity=850, unit="g"),
        source_candidate,
    )

    assert item.total_price == 101.15
    assert item.sale_unit is None
    assert item.comparison_price == 119
    assert item.applied_offer is None
    assert item.purchase_warning is not None
    assert "capped non-fixed offer" in item.purchase_warning
