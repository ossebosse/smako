from __future__ import annotations

from datetime import date

from app.models import (
    NormalizedIngredient,
    OfferKind,
    OfferMetadata,
    OptimizedBasket,
    OptimizedStoreGroup,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.services.basket_calculator import BasketCalculator
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.membership_reporting import (
    fixed_basket_membership_savings,
    membership_coverage,
)
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)

TODAY = date(2026, 8, 31)


def _candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="coop-pasta",
        product_name="Pasta 500 g",
        canonical_name="pasta",
        store_id="own:coop:730400",
        store_name="Coop Online Syd",
        chain="coop",
        price=15,
        effective_price=15,
        member_price=10,
        match_score=1,
        offers=[
            OfferMetadata(
                kind=OfferKind.MEMBER,
                description="Coop-medlem 10 kr",
                price=10,
                required_packages=1,
                price_contract_id="contract:coop-pasta:member",
                eligibility=PromotionEligibility.MEMBER,
                mechanism=PromotionMechanism.SALE_PRICE,
                membership_program=MembershipProgram.COOP_MEMBER,
                member_program="Coop medlem",
            )
        ],
        sale_model=SaleModel.FIXED_PACKAGE,
        sale_price=15,
        package_quantity=500,
        package_unit="g",
        usable_quantity=500,
        usable_unit="g",
        quantity_confidence=QuantityConfidence.EXACT,
        semantic_confidence=SemanticConfidence.HIGH,
    )


def _pool(candidate: ProductCandidate) -> EconomicIngredientPool:
    return EconomicIngredientPool(
        candidates_by_name={"pasta": [candidate]},
        semantic_candidates_by_name={"pasta": [candidate]},
        matched_candidates_by_name={"pasta": [candidate]},
    )


def test_coverage_explains_available_and_unavailable_selected_programmes() -> None:
    pool = _pool(_candidate())
    context = UserPricingContext(
        memberships={MembershipProgram.COOP_MEMBER, MembershipProgram.ICA_STAMMIS}
    )

    by_program = {
        row.membership_program: row
        for row in membership_coverage(pool, context, on_date=TODAY)
    }

    assert by_program[MembershipProgram.COOP_MEMBER].active_contracts == 1
    assert by_program[MembershipProgram.COOP_MEMBER].status == "available"
    assert by_program[MembershipProgram.COOP_MEMBER].contexts == ("Coop Online Syd",)
    assert by_program[MembershipProgram.ICA_STAMMIS].active_contracts == 0
    assert by_program[MembershipProgram.ICA_STAMMIS].status == "no_verified_contracts"
    assert "inga verifierade Stammispriser" in by_program[
        MembershipProgram.ICA_STAMMIS
    ].message


def test_membership_savings_reprices_same_exact_product_and_quantity() -> None:
    shared = _candidate()
    member = price_candidate_for_context(
        shared,
        UserPricingContext(memberships={MembershipProgram.COOP_MEMBER}),
        on_date=TODAY,
    )
    requirement = NormalizedIngredient(
        canonical_name="pasta",
        required_quantity=500,
        unit="g",
    )
    item = BasketCalculator().calculate_item(requirement, member)
    basket = OptimizedBasket(
        total=item.total_price,
        max_stores=1,
        stores=[
            OptimizedStoreGroup(
                store_id=item.store_id,
                store_name=item.store_name,
                items=[item],
                subtotal=item.total_price,
            )
        ],
    )

    result = fixed_basket_membership_savings(basket, _pool(shared), on_date=TODAY)

    assert result.basket_total_with_memberships == 10
    assert result.same_basket_public_total == 15
    assert result.amount == 5
    assert result.member_price_lines == 1
