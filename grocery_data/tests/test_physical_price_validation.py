from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from grocery_data.app.domain.enums import Confidence, PromotionType, SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalPriceComparisonStatus,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PromotionComparisonStatus,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
    PhysicalVerificationSuggestionSampler,
    build_accuracy_report,
)

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def _observation(**overrides: object) -> PhysicalPriceObservation:
    values: dict[str, object] = {
        "id": "observation-1",
        "physical_store_id": "physical-hemkop-karhogstorg",
        "gtin": "7310865004703",
        "product_name": "Mjölk 1 l",
        "shelf_price": Decimal("31.90"),
        "observed_at": NOW,
        "confidence": Confidence.UNKNOWN,
    }
    values.update(overrides)
    return PhysicalPriceObservation.model_validate(values)


def _candidate(**overrides: object) -> DigitalPriceCandidate:
    values: dict[str, object] = {
        "physical_store_id": "physical-hemkop-karhogstorg",
        "grocery_context_id": "hemkop-online-karhogstorg",
        "source_provider": "own",
        "source_snapshot_id": "snapshot-own-1",
        "observed_at": NOW - timedelta(hours=2),
        "product_id": "product-milk",
        "product_name": "Mjölk 1 l",
        "gtin": "7310865004703",
        "current_price": Decimal("29.90"),
        "regular_price": Decimal("31.90"),
        "sale_model": SaleModel.FIXED_PACKAGE,
        "common_product_score": Decimal(4),
    }
    values.update(overrides)
    return DigitalPriceCandidate.model_validate(values)


def _stratified_candidate(
    index: int,
    semantics: PhysicalPriceSemantics,
) -> DigitalPriceCandidate:
    promotion_type = {
        PhysicalPriceSemantics.SALE: PromotionType.SALE_PRICE,
        PhysicalPriceSemantics.MEMBER: PromotionType.MEMBER_PRICE,
        PhysicalPriceSemantics.MULTIBUY: PromotionType.MULTIBUY,
    }.get(semantics)
    return _candidate(
        product_id=f"stratified-{semantics.value}-{index:02d}",
        product_name=f"{semantics.value.title()} product {index:02d}",
        gtin=None,
        brand=f"Brand {index % 4}",
        category=f"Category {index % 6}",
        package_description=f"{index + 1}00 g",
        current_price=Decimal(10 + index),
        regular_price=Decimal(15 + index),
        promotion_type=promotion_type,
        member_only=semantics is PhysicalPriceSemantics.MEMBER,
        member_price=(
            Decimal(10 + index)
            if semantics is PhysicalPriceSemantics.MEMBER
            else None
        ),
        multibuy_quantity=(
            2 if semantics is PhysicalPriceSemantics.MULTIBUY else None
        ),
        multibuy_total_price=(
            Decimal(30)
            if semantics is PhysicalPriceSemantics.MULTIBUY
            else None
        ),
        comparison_price=(
            Decimal(10 + index)
            if semantics is PhysicalPriceSemantics.WEIGHT
            else None
        ),
        comparison_unit=(
            "kg" if semantics is PhysicalPriceSemantics.WEIGHT else None
        ),
        sale_model=(
            SaleModel.SOLD_BY_WEIGHT
            if semantics is PhysicalPriceSemantics.WEIGHT
            else SaleModel.FIXED_PACKAGE
        ),
        common_product_score=Decimal(4),
    )


def test_physical_observation_is_manual_evidence_with_validated_pairs() -> None:
    observation = _observation(
        gtin="7310 8650-0470 3",
        comparison_price=Decimal("31.90"),
        comparison_unit="l",
        photo_reference="  shelf-label://local-reference  ",
    )

    assert observation.gtin == "7310865004703"
    assert observation.source == "manual"
    assert observation.photo_reference == "shelf-label://local-reference"

    with pytest.raises(ValidationError, match="gtin or product_name"):
        _observation(gtin=None, product_name=None)
    with pytest.raises(ValidationError, match="comparison price and unit"):
        _observation(comparison_price=Decimal(10))
    with pytest.raises(ValidationError, match="multibuy quantity and total"):
        _observation(
            promotion_type=PromotionType.MULTIBUY,
            multibuy_quantity=2,
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        _observation(observed_at=datetime(2026, 8, 23, 12))  # noqa: DTZ001


def test_compare_gtin_reports_signed_and_tolerance_differences_per_provider() -> None:
    service = PhysicalPriceValidationService()
    own = _candidate()
    primat = _candidate(
        source_provider="primat",
        source_snapshot_id="snapshot-primat-1",
        current_price=Decimal("31.40"),
    )

    own_result, primat_result = service.compare_observation(
        _observation(),
        [own, primat],
        expected_providers=("own", "primat"),
    )

    assert own_result.status is PhysicalPriceComparisonStatus.MAJOR_DIFFERENCE
    assert own_result.signed_difference == Decimal("2.00")
    assert own_result.absolute_difference == Decimal("2.00")
    assert own_result.percentage_difference == Decimal("6.69")
    assert own_result.exact_match is False
    assert own_result.within_050 is False
    assert own_result.within_100 is False
    assert own_result.observation_confidence is Confidence.HIGH
    assert primat_result.status is PhysicalPriceComparisonStatus.MINOR_DIFFERENCE
    assert primat_result.absolute_difference == Decimal("0.50")
    assert primat_result.within_050 is True
    assert primat_result.within_100 is True


def test_absent_licensed_candidate_is_no_match_not_a_false_primat_comparison() -> None:
    [own, primat] = PhysicalPriceValidationService().compare_observation(
        _observation(shelf_price=Decimal("29.90")),
        [_candidate()],
        expected_providers=("own", "primat"),
    )

    assert own.status is PhysicalPriceComparisonStatus.MATCH
    assert own.source_provider == "own"
    assert primat.status is PhysicalPriceComparisonStatus.NO_DIGITAL_MATCH
    assert primat.source_provider == "primat"
    assert primat.digital_price is None
    assert primat.source_snapshot_id is None


def test_comparison_uses_same_physical_store_and_closest_digital_observation() -> None:
    candidates = [
        _candidate(
            source_snapshot_id="older",
            observed_at=NOW - timedelta(hours=8),
            current_price=Decimal("31.90"),
        ),
        _candidate(
            source_snapshot_id="closest",
            observed_at=NOW - timedelta(minutes=10),
            current_price=Decimal("30.90"),
        ),
        _candidate(
            physical_store_id="some-other-store",
            source_snapshot_id="wrong-store",
            observed_at=NOW,
            current_price=Decimal("31.90"),
        ),
    ]

    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(),
        candidates,
    )

    assert comparison.source_snapshot_id == "closest"
    assert comparison.status is PhysicalPriceComparisonStatus.MINOR_DIFFERENCE


def test_stale_digital_price_is_reported_separately_even_when_price_matches() -> None:
    [comparison] = PhysicalPriceValidationService(
        max_digital_age_hours=Decimal(48)
    ).compare_observation(
        _observation(shelf_price=Decimal("29.90")),
        [_candidate(observed_at=NOW - timedelta(hours=49))],
    )

    assert comparison.status is PhysicalPriceComparisonStatus.STALE_DIGITAL_PRICE
    assert comparison.exact_match is True
    assert comparison.digital_age_hours == Decimal("49.00")


def test_exact_name_match_is_lower_confidence_and_never_fuzzy() -> None:
    observation = _observation(gtin=None, product_name="  Mjölk   1 L ")
    [resolved] = PhysicalPriceValidationService().compare_observation(
        observation,
        [_candidate(gtin=None, product_name="mjölk 1 l")],
    )
    [unresolved] = PhysicalPriceValidationService().compare_observation(
        _observation(gtin=None, product_name="Mjölk ekologisk 1 l"),
        [_candidate(gtin=None, product_name="Mjölk 1 l")],
        expected_providers=("own",),
    )

    assert resolved.match_method == "exact_name"
    assert resolved.observation_confidence is Confidence.MEDIUM
    assert unresolved.status is PhysicalPriceComparisonStatus.NO_DIGITAL_MATCH
    assert unresolved.observation_confidence is Confidence.LOW


def test_checksum_invalid_gtin_match_is_not_high_confidence() -> None:
    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(gtin="7310000000001"),
        [_candidate(gtin="7310000000001")],
    )

    assert comparison.match_method == "gtin"
    assert comparison.observation_confidence is Confidence.MEDIUM


def test_member_multibuy_and_comparison_price_are_compared_as_conditions() -> None:
    observation = _observation(
        shelf_price=Decimal(15),
        comparison_price=Decimal(15),
        comparison_unit="st",
        promotion_type=PromotionType.MEMBER_PRICE,
        member_only=True,
        multibuy_quantity=2,
        multibuy_total_price=Decimal(30),
    )
    candidate = _candidate(
        current_price=Decimal(17),
        member_price=Decimal(15),
        comparison_price=Decimal(15),
        comparison_unit="st",
        promotion_type=PromotionType.MEMBER_PRICE,
        member_only=True,
        multibuy_quantity=2,
        multibuy_total_price=Decimal(30),
    )

    [comparison] = PhysicalPriceValidationService().compare_observation(
        observation,
        [candidate],
    )

    assert comparison.physical_price == Decimal("30.00")
    assert comparison.digital_price == Decimal("30.00")
    assert comparison.status is PhysicalPriceComparisonStatus.MATCH
    assert comparison.promotion_status is PromotionComparisonStatus.MATCH
    assert comparison.member_restriction_match is True
    assert comparison.multibuy_match is True
    assert comparison.comparison_price_match is True


def test_regular_shelf_sample_uses_regular_price_when_digital_campaign_is_active() -> None:
    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(shelf_price=Decimal("31.90"), promotion_type=None),
        [
            _candidate(
                current_price=Decimal("29.90"),
                regular_price=Decimal("31.90"),
                promotion_type=PromotionType.SALE_PRICE,
            )
        ],
    )

    assert comparison.digital_price == Decimal("31.90")
    assert comparison.status is PhysicalPriceComparisonStatus.MATCH
    assert comparison.promotion_status is PromotionComparisonStatus.DIFFERENT


def test_unknown_member_restriction_is_not_reported_as_a_false_disagreement() -> None:
    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(shelf_price=Decimal("29.90"), member_only=None),
        [_candidate(member_only=False)],
    )

    assert comparison.member_restriction_match is None
    assert comparison.promotion_status is PromotionComparisonStatus.MATCH


def test_obvious_tenfold_manual_price_is_flagged_as_possible_input_error() -> None:
    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(shelf_price=Decimal("169.50")),
        [_candidate(current_price=Decimal("16.95"))],
    )

    assert comparison.status is PhysicalPriceComparisonStatus.MAJOR_DIFFERENCE
    assert comparison.input_anomaly_suspected is True


def test_accuracy_report_is_explicitly_sampled_and_has_temporal_segments() -> None:
    regular = _observation(
        id="regular",
        shelf_price=Decimal("29.90"),
        observed_at=NOW - timedelta(days=7),
    )
    campaign = _observation(
        id="campaign",
        shelf_price=Decimal(25),
        promotion_type=PromotionType.SALE_PRICE,
        observed_at=NOW,
    )
    service = PhysicalPriceValidationService()
    comparisons = (
        *service.compare_observation(
            regular,
            [
                _candidate(
                    current_price=Decimal("29.90"),
                    observed_at=regular.observed_at - timedelta(hours=2),
                )
            ],
            expected_providers=("own", "primat"),
        ),
        *service.compare_observation(
            campaign,
            [
                _candidate(
                    current_price=Decimal(25),
                    promotion_type=PromotionType.SALE_PRICE,
                    sale_model=SaleModel.SOLD_BY_WEIGHT,
                )
            ],
            expected_providers=("own", "primat"),
        ),
    )

    report = build_accuracy_report(
        [regular, campaign],
        comparisons,
        scope_label="Hemköp Karhögstorg, Lund",
    )

    assert report.scope_label == "Hemköp Karhögstorg, Lund — sampled observations"
    assert "stickprov" in report.sampled_observations_note
    assert report.observation_count == 2
    assert report.days_sampled == 2
    assert report.campaign_weeks_sampled == 1
    assert report.providers["own"].comparisons == 2
    assert report.providers["own"].exact_matches == 2
    assert report.providers["own"].exact_percent == Decimal("100.00")
    assert report.providers["primat"].no_digital_match == 2
    assert report.segments["regular_products"].comparisons == 2
    assert report.segments["campaigns"].comparisons == 2
    assert report.segments["weight_products"].comparisons == 1


def test_suggestions_prioritize_disagreements_promotions_and_sale_model_diversity() -> None:
    candidates = [
        _candidate(
            product_id="disputed-own",
            gtin="7310000000002",
            product_name="Disputed rice",
            current_price=Decimal(20),
            common_product_score=Decimal(5),
        ),
        _candidate(
            source_provider="primat",
            source_snapshot_id="primat",
            product_id="disputed-primat",
            gtin="7310000000002",
            product_name="Disputed rice",
            current_price=Decimal(25),
            common_product_score=Decimal(5),
        ),
        _candidate(
            product_id="weight-campaign",
            gtin="7310000000003",
            product_name="Potatis lösvikt",
            current_price=Decimal("12.90"),
            promotion_type=PromotionType.SALE_PRICE,
            sale_model=SaleModel.SOLD_BY_WEIGHT,
        ),
        _candidate(
            product_id="ordinary",
            gtin="7310000000004",
            product_name="Ordinary pasta",
            current_price=Decimal(18),
            common_product_score=Decimal(1),
        ),
    ]

    suggestions = PhysicalVerificationSuggestionSampler().suggest(
        candidates,
        physical_store_id="physical-hemkop-karhogstorg",
        limit=3,
    )

    assert len(suggestions) == 3
    assert len({row.product_id for row in suggestions}) == 3
    disputed = next(row for row in suggestions if row.product_name == "Disputed rice")
    weighted = next(row for row in suggestions if row.product_name == "Potatis lösvikt")
    assert "large_source_disagreement" in disputed.reasons
    assert "weight_product" in weighted.reasons
    assert "promotion" in weighted.reasons


def test_suggestion_sampler_never_crosses_physical_store_boundary() -> None:
    suggestions = PhysicalVerificationSuggestionSampler().suggest(
        [
            _candidate(),
            _candidate(
                physical_store_id="different-store",
                product_id="wrong-store-product",
            ),
        ],
        physical_store_id="physical-hemkop-karhogstorg",
        limit=10,
    )

    assert [suggestion.product_id for suggestion in suggestions] == ["product-milk"]


def test_stratified_25_uses_five_truthful_strata_and_deterministic_backfill() -> None:
    available = {
        PhysicalPriceSemantics.REGULAR: 12,
        PhysicalPriceSemantics.SALE: 10,
        PhysicalPriceSemantics.MEMBER: 1,
        PhysicalPriceSemantics.MULTIBUY: 1,
        PhysicalPriceSemantics.WEIGHT: 2,
    }
    candidates = tuple(
        _stratified_candidate(index, semantics)
        for semantics, count in available.items()
        for index in range(count)
    )
    sampler = PhysicalVerificationSuggestionSampler()

    forward = sampler.suggest_stratified(
        candidates,
        physical_store_id="physical-hemkop-karhogstorg",
        limit=25,
    )
    reversed_input = sampler.suggest_stratified(
        tuple(reversed(candidates)),
        physical_store_id="physical-hemkop-karhogstorg",
        limit=25,
    )

    assert len(forward) == 25
    assert [row.product_id for row in forward] == [
        row.product_id for row in reversed_input
    ]
    assert len({(row.grocery_context_id, row.product_id) for row in forward}) == 25
    assert {row.stratum for row in forward} == set(available)
    assert all(row.stratum is not PhysicalPriceSemantics.UNKNOWN for row in forward)

    # MEMBER/MULTIBUY/WEIGHT are deliberately undersupplied relative to their
    # nominal quota of five. Backfill may use only real remaining candidates;
    # it must not relabel REGULAR/SALE rows to make the quota look complete.
    selected_counts = {
        semantics: sum(row.stratum is semantics for row in forward)
        for semantics in available
    }
    assert selected_counts == {
        PhysicalPriceSemantics.REGULAR: 11,
        PhysicalPriceSemantics.SALE: 10,
        PhysicalPriceSemantics.MEMBER: 1,
        PhysicalPriceSemantics.MULTIBUY: 1,
        PhysicalPriceSemantics.WEIGHT: 2,
    }
    expected_by_id = {
        candidate.product_id: (
            PhysicalPriceSemantics.WEIGHT
            if candidate.sale_model is SaleModel.SOLD_BY_WEIGHT
            else PhysicalPriceSemantics.MEMBER
            if candidate.member_only
            else PhysicalPriceSemantics.MULTIBUY
            if candidate.multibuy_quantity is not None
            else PhysicalPriceSemantics.SALE
            if candidate.promotion_type is not None
            else PhysicalPriceSemantics.REGULAR
        )
        for candidate in candidates
    }
    assert all(
        row.stratum is expected_by_id[row.product_id]
        for row in forward
    )
