from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.models.basket import BasketAuditStatus, OptimizedBasket
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    Product,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.provenance import SourceProvenance
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.price_universe import (
    BasketResultCache,
    PriceUniverse,
    PriceUniverseBuilder,
    PriceUniverseKey,
)
from app.services.price_universe_runtime import PricingProjectionCache
from app.services.user_pricing import (
    price_candidate_for_context,
    price_contracts_for_candidate,
)
from pydantic import ValidationError

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)

NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)
TODAY = date(2026, 8, 31)


def _member_offer(
    *,
    program: MembershipProgram = MembershipProgram.COOP_MEMBER,
    price: float = 10,
    required_packages: int = 1,
) -> OfferMetadata:
    mechanism = (
        PromotionMechanism.MULTIBUY
        if required_packages > 1
        else PromotionMechanism.SALE_PRICE
    )
    return OfferMetadata(
        kind=OfferKind.MULTIPACK if required_packages > 1 else OfferKind.MEMBER,
        description=(
            f"{program.consumer_label}: {required_packages} for {price}"
            if required_packages > 1
            else f"{program.consumer_label}: {price}"
        ),
        price=price,
        required_packages=required_packages,
        price_contract_id=(
            f"contract:{program.value.casefold()}:{required_packages}:{price}"
        ),
        eligibility=PromotionEligibility.MEMBER,
        mechanism=mechanism,
        membership_program=program,
        member_program=program.consumer_label,
    )


def _product(
    *,
    chain: str = "coop",
    price: float = 15,
    effective_price: float | None = None,
    member_price: float | None = None,
    offers: list[OfferMetadata] | None = None,
) -> Product:
    current_price = price if effective_price is None else effective_price
    store_id = f"own:{chain}:test"
    return Product(
        product_id=f"{chain}:rice",
        name="Basmatiris",
        canonical_name="ris",
        canonical_food="ris",
        category="Skafferi",
        store_id=store_id,
        store_name="Testbutik",
        chain=chain,
        price=price,
        effective_price=current_price,
        member_price=member_price,
        offers=offers or [],
        sale_price=current_price,
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=500,
        package_unit="g",
        usable_quantity=500,
        usable_unit="g",
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        source_provenance=SourceProvenance(
            source_provider="own",
            source_channel="catalog",
            source_snapshot_id="snapshot-membership-test",
            source_observed_at=NOW,
            chain=chain,
            store_id=store_id,
            store_name="Testbutik",
            price_context="online_store",
            coverage="full_catalog",
            semantic_confidence="high",
            quantity_confidence="exact",
        ),
    )


def _candidate(product: Product) -> ProductCandidate:
    return ProductCandidate.from_product(product, match_score=1).model_copy(
        update={"semantic_evidence": ["shared-membership-test"]}
    )


def _universe(product: Product) -> PriceUniverse:
    key = PriceUniverseKey.create(
        city="Lund",
        snapshot_ids=("snapshot-membership-test",),
        memberships={},
        source_strategy_version="strategy-shared-v1",
        normalizer_version="normalizer-v1",
        taxonomy_version="taxonomy-v1",
    )
    return PriceUniverseBuilder().build(key, [product], built_at=NOW)


def _require_packages(count: int) -> NormalizedIngredient:
    return NormalizedIngredient(
        canonical_name="ris",
        required_quantity=count * 500,
        unit="g",
    )


def test_shared_universe_retains_member_contract_without_flattening_public_price() -> None:
    product = _product(
        price=15,
        member_price=10,
        offers=[_member_offer(price=10)],
    )

    universe = _universe(product)
    stored = universe.products[0]

    assert stored.price == 15
    assert stored.effective_price == 15
    assert stored.sale_price == 15
    assert stored.member_price == 10
    assert stored.offers == product.offers
    assert stored.offers[0].eligibility is PromotionEligibility.MEMBER
    assert stored.offers[0].membership_program is MembershipProgram.COOP_MEMBER


def test_wrong_chain_member_offer_is_rejected_at_request_projection() -> None:
    candidate = _candidate(
        _product(
            chain="coop",
            offers=[_member_offer(program=MembershipProgram.ICA_STAMMIS)],
        )
    )

    with pytest.raises(ValueError, match="membership program does not match product chain"):
        price_candidate_for_context(
            candidate,
            UserPricingContext(memberships={MembershipProgram.ICA_STAMMIS}),
            on_date=TODAY,
        )


def test_legacy_flattened_public_effective_price_survives_request_projection() -> None:
    stored = _universe(_product(price=20, effective_price=15)).products[0]
    projected = price_candidate_for_context(
        _candidate(stored),
        UserPricingContext(),
        on_date=TODAY,
    )

    assert stored.effective_price == 15
    assert projected.effective_price == 15
    assert projected.sale_price == 15
    assert projected.selected_price_eligibility is PromotionEligibility.PUBLIC
    assert projected.selected_price_mechanism is PromotionMechanism.SALE_PRICE
    assert any(
        contract.eligibility is PromotionEligibility.PUBLIC
        and contract.mechanism is PromotionMechanism.SALE_PRICE
        and contract.price == 15
        for contract in price_contracts_for_candidate(_candidate(stored))
    )


def test_price_contract_projection_normalizes_binary_float_round_trip_noise() -> None:
    candidate = _candidate(
        _product(
            price=24.990000000000002,
            effective_price=24.990000000000002,
        )
    )

    contracts = price_contracts_for_candidate(candidate)

    assert contracts[0].mechanism is PromotionMechanism.REGULAR
    assert contracts[0].price == Decimal("24.99")


def test_request_time_member_unit_price_requires_the_exact_program() -> None:
    stored = _universe(
        _product(price=15, member_price=10, offers=[_member_offer(price=10)])
    ).products[0]
    shared_candidate = _candidate(stored)

    public = price_candidate_for_context(
        shared_candidate,
        UserPricingContext(),
        on_date=TODAY,
    )
    wrong_program = price_candidate_for_context(
        shared_candidate,
        UserPricingContext(memberships={MembershipProgram.ICA_STAMMIS}),
        on_date=TODAY,
    )
    coop_member = price_candidate_for_context(
        shared_candidate,
        UserPricingContext(memberships={MembershipProgram.COOP_MEMBER}),
        on_date=TODAY,
    )

    assert public.effective_price == 15
    assert wrong_program.effective_price == 15
    assert public.offers == []
    assert wrong_program.offers == []
    assert coop_member.effective_price == 10
    assert coop_member.selected_price_eligibility is PromotionEligibility.MEMBER
    assert coop_member.selected_membership_program is MembershipProgram.COOP_MEMBER
    # Request projection must not mutate the shared artifact candidate.
    assert shared_candidate.effective_price == 15
    assert shared_candidate.offers == stored.offers


@pytest.mark.parametrize(
    ("package_count", "expected_total", "promotion_applied"),
    ((2, 30, False), (3, 30, True), (4, 45, True)),
)
def test_member_multibuy_checkout_for_two_three_and_four_packages(
    package_count: int,
    expected_total: float,
    promotion_applied: bool,
) -> None:
    shared_candidate = _candidate(
        _universe(
            _product(
                price=15,
                offers=[_member_offer(price=30, required_packages=3)],
            )
        ).products[0]
    )
    member_candidate = price_candidate_for_context(
        shared_candidate,
        UserPricingContext(memberships={MembershipProgram.COOP_MEMBER}),
        on_date=TODAY,
    )

    item = BasketCalculator().calculate_item(
        _require_packages(package_count),
        member_candidate,
    )

    assert item.packages_needed == package_count
    assert item.total_price == expected_total
    assert (item.applied_offer is not None) is promotion_applied
    if promotion_applied:
        assert item.price_mechanism is PromotionMechanism.MULTIBUY
        assert item.eligibility is PromotionEligibility.MEMBER
        assert item.membership_program is MembershipProgram.COOP_MEMBER
    else:
        assert item.price_mechanism is PromotionMechanism.REGULAR
        assert item.eligibility is PromotionEligibility.PUBLIC


def test_no_membership_cannot_use_member_multibuy() -> None:
    shared_candidate = _candidate(
        _universe(
            _product(
                price=15,
                offers=[_member_offer(price=30, required_packages=3)],
            )
        ).products[0]
    )
    public_candidate = price_candidate_for_context(
        shared_candidate,
        UserPricingContext(),
        on_date=TODAY,
    )

    item = BasketCalculator().calculate_item(_require_packages(3), public_candidate)

    assert item.total_price == 45
    assert item.applied_offer is None
    assert item.eligibility is PromotionEligibility.PUBLIC


def test_basket_auditor_rejects_member_price_without_authorization() -> None:
    member_context = UserPricingContext(
        memberships={MembershipProgram.COOP_MEMBER}
    )
    candidate = price_candidate_for_context(
        _candidate(
            _universe(
                _product(price=15, member_price=10, offers=[_member_offer(price=10)])
            ).products[0]
        ),
        member_context,
        on_date=TODAY,
    )
    requirement = _require_packages(1)
    item = BasketCalculator().calculate_item(requirement, candidate)

    rejected = BasketAuditor().audit(
        [requirement],
        [item],
        user_pricing_context=UserPricingContext(),
    )
    rejected_without_context = BasketAuditor().audit([requirement], [item])
    accepted = BasketAuditor().audit(
        [requirement],
        [item],
        user_pricing_context=member_context,
    )

    assert item.eligibility is PromotionEligibility.MEMBER
    assert rejected.status is BasketAuditStatus.FAIL
    assert rejected_without_context.status is BasketAuditStatus.FAIL
    assert any(
        "unauthorized member price" in error
        for error in rejected.total_reconciliation_errors
    )
    assert accepted.status is BasketAuditStatus.PASS


def test_basket_result_cache_isolated_by_pricing_context_id() -> None:
    universe = _universe(_product())
    cache = BasketResultCache()
    calls = 0

    def load() -> OptimizedBasket:
        nonlocal calls
        calls += 1
        return OptimizedBasket(total=0, stores=[], max_stores=1)

    public_context = UserPricingContext()
    coop_context = UserPricingContext(
        memberships={MembershipProgram.COOP_MEMBER}
    )
    common = {
        "allowed_context_ids": ("own:coop:test",),
        "max_stores": 1,
        "optimizer_version": "optimizer-v1",
        "factory": load,
    }

    first = cache.get_or_compute(
        universe,
        [("ris", 500, "g")],
        pricing_context_id=public_context.cache_identity,
        **common,
    )
    repeated = cache.get_or_compute(
        universe,
        [("ris", 500, "g")],
        pricing_context_id=public_context.cache_identity,
        **common,
    )
    membership_specific = cache.get_or_compute(
        universe,
        [("ris", 500, "g")],
        pricing_context_id=coop_context.cache_identity,
        **common,
    )

    assert first is repeated
    assert membership_specific is not first
    assert calls == 2
    assert cache.stats.hits == 1
    assert cache.stats.misses == 2
    assert cache.stats.entries == 2


def test_pricing_projection_cache_reuses_only_exact_context_and_date() -> None:
    cache = PricingProjectionCache()
    pool = EconomicIngredientPool()
    calls = 0

    def build() -> EconomicIngredientPool:
        nonlocal calls
        calls += 1
        return pool

    public_key = f"{UserPricingContext().cache_identity}:2026-08-31"
    coop_key = (
        f"{UserPricingContext(memberships={MembershipProgram.COOP_MEMBER}).cache_identity}"
        ":2026-08-31"
    )

    assert cache.get_or_compute(public_key, build) is pool
    assert cache.get_or_compute(public_key, build) is pool
    assert cache.get_or_compute(coop_key, build) is pool
    assert calls == 2
    assert cache.stats.hits == 1
    assert cache.stats.misses == 2
    assert cache.stats.entries == 2


def test_shared_offer_metadata_rejects_user_specific_contract() -> None:
    with pytest.raises(
        ValidationError,
        match="user-specific contracts cannot enter shared product offers",
    ):
        OfferMetadata(
            kind=OfferKind.CAMPAIGN,
            description="Personlig kupong",
            price=5,
            eligibility=PromotionEligibility.USER_SPECIFIC,
            mechanism=PromotionMechanism.SALE_PRICE,
        )
