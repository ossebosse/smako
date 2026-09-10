from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from grocery_data.app.domain.enums import Confidence, PromotionType, SaleModel
from grocery_data.app.domain.physical_price import (
    AccuracyBucket,
    DigitalPriceCandidate,
    PhysicalIdentificationEvidence,
    PhysicalPriceComparison,
    PhysicalPriceComparisonStatus,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    PhysicalSampleConfidence,
    PhysicalValidationSessionItem,
    PromotionComparisonStatus,
    SourceAccuracyReport,
    VerificationSuggestion,
)
from grocery_data.app.services.catalog_snapshot_quality import is_valid_gtin

_CENT = Decimal("0.01")
_PERCENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _normalized_name(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold().strip())


def _normalized_comparison_unit(value: str | None) -> str | None:
    normalized = re.sub(r"\s+", "", (value or "").casefold())
    return {
        "kg": "kg",
        "kr/kg": "kg",
        "sek/kg": "kg",
        "l": "l",
        "liter": "l",
        "lit": "l",
        "kr/l": "l",
        "kr/lit": "l",
        "sek/l": "l",
        "st": "st",
        "styck": "st",
        "kr/st": "st",
        "sek/st": "st",
    }.get(normalized, normalized or None)


def _percent(count: int, total: int) -> Decimal:
    if total == 0:
        return Decimal(0)
    return (Decimal(count) * 100 / Decimal(total)).quantize(_PERCENT)


def _hours_between(left: datetime, right: datetime) -> Decimal:
    seconds = abs(Decimal(str((left - right).total_seconds())))
    return (seconds / Decimal(3600)).quantize(_PERCENT)


def _observation_confidence(
    observation: PhysicalPriceObservation,
    *,
    match_method: str | None,
) -> Confidence:
    if observation.identity_status in {
        PhysicalProductIdentityStatus.GTIN_MISMATCH,
        PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN,
        PhysicalProductIdentityStatus.NO_MATCH,
    }:
        return Confidence.LOW
    if is_valid_gtin(observation.gtin):
        if match_method == "gtin":
            return Confidence.HIGH
        if (
            match_method == "verified_session_product"
            and observation.identity_status is PhysicalProductIdentityStatus.GTIN_MATCH
            and observation.identification_evidence
            is PhysicalIdentificationEvidence.GTIN_VERIFIED
        ):
            return Confidence.HIGH
    if match_method in {"exact_name", "verified_session_product"}:
        return Confidence.MEDIUM
    if observation.gtin is not None:
        return Confidence.MEDIUM
    return Confidence.LOW


def derived_observation_confidence(
    comparisons: Sequence[PhysicalPriceComparison],
    *,
    gtin: str | None,
    identity_status: PhysicalProductIdentityStatus | None = None,
    identification_evidence: PhysicalIdentificationEvidence | None = None,
) -> Confidence:
    """Derive stored manual confidence from an actually resolved product."""

    resolved_methods = {
        comparison.match_method
        for comparison in comparisons
        if comparison.digital_price is not None
    }
    if is_valid_gtin(gtin):
        if "gtin" in resolved_methods:
            return Confidence.HIGH
        if (
            "verified_session_product" in resolved_methods
            and identity_status is PhysicalProductIdentityStatus.GTIN_MATCH
            and identification_evidence is PhysicalIdentificationEvidence.GTIN_VERIFIED
        ):
            return Confidence.HIGH
    if resolved_methods.intersection({"exact_name", "verified_session_product"}):
        return Confidence.MEDIUM
    return Confidence.LOW


def _matching_candidates(
    observation: PhysicalPriceObservation,
    candidates: Sequence[DigitalPriceCandidate],
    *,
    verified_session_product_identity: tuple[str, str, str] | None = None,
    verified_session_gtin: str | None = None,
) -> tuple[list[DigitalPriceCandidate], str | None]:
    if observation.identity_status in {
        PhysicalProductIdentityStatus.NO_MATCH,
        PhysicalProductIdentityStatus.GTIN_MISMATCH,
        PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN,
    }:
        return [], None
    same_store = [
        candidate
        for candidate in candidates
        if candidate.physical_store_id == observation.physical_store_id
    ]
    if verified_session_product_identity is not None:
        if (
            observation.identity_status is PhysicalProductIdentityStatus.GTIN_MATCH
            and (
                observation.gtin is None
                or observation.gtin != verified_session_gtin
            )
        ):
            # A GTIN_MATCH observation may only use this exact-product bridge
            # when the session's separately verified GTIN is the scanned GTIN.
            return [], None
        provider, context_id, product_id = verified_session_product_identity
        exact_session_target = [
            candidate
            for candidate in same_store
            if (
                candidate.source_provider == provider
                and candidate.grocery_context_id == context_id
                and candidate.product_id == product_id
                # Identifier enrichment must not override a conflicting GTIN
                # already present on the immutable digital row.
                and (
                    observation.gtin is None
                    or candidate.gtin is None
                    or candidate.gtin == observation.gtin
                )
            )
        ]
        return exact_session_target, "verified_session_product"
    if observation.gtin is not None and observation.identity_status in {
        None,
        PhysicalProductIdentityStatus.EXACT,
        PhysicalProductIdentityStatus.GTIN_MATCH,
    }:
        return (
            [candidate for candidate in same_store if candidate.gtin == observation.gtin],
            "gtin",
        )
    expected_name = _normalized_name(observation.product_name)
    if expected_name:
        return (
            [
                candidate
                for candidate in same_store
                if _normalized_name(candidate.product_name) == expected_name
            ],
            "exact_name",
        )
    return [], None


def _comparison_prices(
    observation: PhysicalPriceObservation,
    candidate: DigitalPriceCandidate,
) -> tuple[Decimal, Decimal]:
    if (
        observation.price_semantics is PhysicalPriceSemantics.WEIGHT
        and candidate.comparison_price is not None
    ):
        return (
            observation.comparison_price or observation.shelf_price,
            candidate.comparison_price,
        )
    if (
        observation.price_semantics is PhysicalPriceSemantics.MULTIBUY
        or observation.price_semantics is None
    ) and (
        observation.multibuy_total_price is not None
        and candidate.multibuy_total_price is not None
        and observation.multibuy_quantity == candidate.multibuy_quantity
    ):
        return observation.multibuy_total_price, candidate.multibuy_total_price
    if (
        observation.price_semantics is PhysicalPriceSemantics.MEMBER
        or observation.member_only
    ) and candidate.member_price is not None:
        return observation.shelf_price, candidate.member_price
    if (
        observation.price_semantics is PhysicalPriceSemantics.REGULAR
        or (
            observation.price_semantics is None
            and observation.promotion_type is None
            and not observation.member_only
        )
    ) and (
        (candidate.promotion_type is not None or candidate.member_only)
        and candidate.regular_price is not None
    ):
        # A regular shelf-label sample must be compared with the digital
        # ordinary price, not an active campaign/member rate. Promotion
        # agreement is reported independently below.
        return observation.shelf_price, candidate.regular_price
    return observation.shelf_price, candidate.current_price


def _promotion_comparison(
    observation: PhysicalPriceObservation,
    candidate: DigitalPriceCandidate,
    *,
    exact_tolerance: Decimal,
) -> tuple[PromotionComparisonStatus, bool, bool | None, bool, bool]:
    type_match = observation.promotion_type == candidate.promotion_type
    member_match = (
        None
        if observation.member_only is None
        else observation.member_only == candidate.member_only
    )
    physical_multibuy = (
        observation.multibuy_quantity,
        observation.multibuy_total_price,
    )
    digital_multibuy = (
        candidate.multibuy_quantity,
        candidate.multibuy_total_price,
    )
    multibuy_match = physical_multibuy == digital_multibuy
    physical_comparison_price = observation.comparison_price
    if (
        observation.price_semantics is PhysicalPriceSemantics.WEIGHT
        and physical_comparison_price is None
    ):
        physical_comparison_price = observation.shelf_price
    if physical_comparison_price is None and candidate.comparison_price is None:
        comparison_price_match = True
    elif physical_comparison_price is None or candidate.comparison_price is None:
        comparison_price_match = False
    else:
        comparison_price_match = (
            abs(physical_comparison_price - candidate.comparison_price) <= exact_tolerance
            and _normalized_comparison_unit(observation.comparison_unit)
            == _normalized_comparison_unit(candidate.comparison_unit)
        )
    status = (
        PromotionComparisonStatus.MATCH
        if type_match and member_match is not False and multibuy_match
        else PromotionComparisonStatus.DIFFERENT
    )
    return status, type_match, member_match, multibuy_match, comparison_price_match


class PhysicalPriceValidationService:
    """Compares manual evidence with immutable digital observations.

    The service has no catalog repository dependency and therefore cannot turn a
    manual sample into a current catalog price.
    """

    def __init__(
        self,
        *,
        exact_tolerance: Decimal = Decimal("0.00"),
        minor_tolerance: Decimal = Decimal("1.00"),
        max_digital_age_hours: Decimal = Decimal(48),
        anomaly_ratio: Decimal = Decimal(5),
    ) -> None:
        if exact_tolerance < 0:
            raise ValueError("exact_tolerance must not be negative")
        if minor_tolerance < exact_tolerance:
            raise ValueError("minor_tolerance must be at least exact_tolerance")
        if max_digital_age_hours <= 0:
            raise ValueError("max_digital_age_hours must be positive")
        if anomaly_ratio <= 1:
            raise ValueError("anomaly_ratio must be greater than one")
        self.exact_tolerance = exact_tolerance
        self.minor_tolerance = minor_tolerance
        self.max_digital_age_hours = max_digital_age_hours
        self.anomaly_ratio = anomaly_ratio

    def compare_observation(
        self,
        observation: PhysicalPriceObservation,
        candidates: Sequence[DigitalPriceCandidate],
        *,
        expected_providers: Iterable[str] | None = None,
        verified_session_product_identity: tuple[str, str, str] | None = None,
        verified_session_gtin: str | None = None,
    ) -> tuple[PhysicalPriceComparison, ...]:
        matches, match_method = _matching_candidates(
            observation,
            candidates,
            verified_session_product_identity=verified_session_product_identity,
            verified_session_gtin=verified_session_gtin,
        )
        candidates_by_provider: dict[str, list[DigitalPriceCandidate]] = defaultdict(list)
        for candidate in matches:
            candidates_by_provider[candidate.source_provider].append(candidate)

        provider_names = list(dict.fromkeys(expected_providers or candidates_by_provider))
        if not provider_names:
            provider_names = [""]

        comparisons: list[PhysicalPriceComparison] = []
        for provider in provider_names:
            provider_matches = candidates_by_provider.get(provider, [])
            candidate = min(
                provider_matches,
                key=lambda row: (
                    abs((row.observed_at - observation.observed_at).total_seconds()),
                    row.source_snapshot_id,
                    row.product_id,
                ),
                default=None,
            )
            confidence = _observation_confidence(
                observation,
                match_method=match_method if candidate is not None else None,
            )
            if candidate is None:
                comparisons.append(
                    PhysicalPriceComparison(
                        observation_id=observation.id,
                        physical_store_id=observation.physical_store_id,
                        source_provider=provider or None,
                        gtin=observation.gtin,
                        product_name=observation.product_name,
                        physical_price=observation.shelf_price,
                        physical_promotion_type=observation.promotion_type,
                        status=PhysicalPriceComparisonStatus.NO_DIGITAL_MATCH,
                        observation_confidence=confidence,
                    )
                )
                continue

            physical_price, digital_price = _comparison_prices(observation, candidate)
            signed = _money(physical_price - digital_price)
            absolute = abs(signed)
            percentage = (signed * 100 / digital_price).quantize(_PERCENT)
            exact = absolute <= self.exact_tolerance
            within_050 = absolute <= Decimal("0.50")
            within_100 = absolute <= Decimal("1.00")
            age = _hours_between(observation.observed_at, candidate.observed_at)
            if age > self.max_digital_age_hours:
                status = PhysicalPriceComparisonStatus.STALE_DIGITAL_PRICE
            elif exact:
                status = PhysicalPriceComparisonStatus.MATCH
            elif absolute <= self.minor_tolerance:
                status = PhysicalPriceComparisonStatus.MINOR_DIFFERENCE
            else:
                status = PhysicalPriceComparisonStatus.MAJOR_DIFFERENCE

            promotion = _promotion_comparison(
                observation,
                candidate,
                exact_tolerance=self.exact_tolerance,
            )
            smaller = min(physical_price, digital_price)
            larger = max(physical_price, digital_price)
            anomaly = larger / smaller >= self.anomaly_ratio
            comparisons.append(
                PhysicalPriceComparison(
                    observation_id=observation.id,
                    physical_store_id=observation.physical_store_id,
                    source_provider=candidate.source_provider,
                    grocery_context_id=candidate.grocery_context_id,
                    source_snapshot_id=candidate.source_snapshot_id,
                    product_id=candidate.product_id,
                    gtin=observation.gtin or candidate.gtin,
                    product_name=observation.product_name or candidate.product_name,
                    sale_model=candidate.sale_model,
                    physical_promotion_type=observation.promotion_type,
                    digital_promotion_type=candidate.promotion_type,
                    physical_price=_money(physical_price),
                    digital_price=_money(digital_price),
                    digital_observed_at=candidate.observed_at,
                    digital_age_hours=age,
                    signed_difference=signed,
                    absolute_difference=absolute,
                    percentage_difference=percentage,
                    exact_match=exact,
                    within_050=within_050,
                    within_100=within_100,
                    status=status,
                    promotion_status=promotion[0],
                    promotion_type_match=promotion[1],
                    member_restriction_match=promotion[2],
                    multibuy_match=promotion[3],
                    comparison_price_match=promotion[4],
                    input_anomaly_suspected=anomaly,
                    match_method=match_method,
                    observation_confidence=confidence,
                )
            )
        return tuple(comparisons)


def compare_frozen_session_observation(
    observation: PhysicalPriceObservation,
    candidates: Sequence[DigitalPriceCandidate],
    *,
    item: PhysicalValidationSessionItem | None,
) -> tuple[PhysicalPriceComparison, ...]:
    """Compare against one immutable session target without rewriting its row.

    Product-detail enrichment is stored separately from the frozen price
    candidate.  When that later evidence verifies a GTIN, the exact selected
    provider/context/product tuple is the safe join key; the scanned GTIN stays
    identity evidence and never gets injected into the old snapshot row.
    """

    candidate_tuple = tuple(candidates)
    providers = tuple(
        dict.fromkeys(candidate.source_provider for candidate in candidate_tuple)
    )
    verified_identity: tuple[str, str, str] | None = None
    verified_gtin: str | None = None
    if (
        item is not None
        and observation.identity_status
        not in {
            PhysicalProductIdentityStatus.GTIN_MISMATCH,
            PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN,
            PhysicalProductIdentityStatus.NO_MATCH,
        }
        and observation.validation_session_id == item.session_id
        and observation.validation_session_item_id == item.id
        and observation.immutable_candidate_set_sha256 == item.candidate_set_sha256
        and item.target_source_provider is not None
        and item.target_grocery_context_id is not None
        and item.target_product_id is not None
    ):
        target_identity = (
            item.target_source_provider,
            item.target_grocery_context_id,
            item.target_product_id,
        )
        target_candidates = tuple(
            candidate
            for candidate in candidate_tuple
            if (
                candidate.source_provider == target_identity[0]
                and candidate.grocery_context_id == target_identity[1]
                and candidate.product_id == target_identity[2]
            )
        )
        # Keep the ordinary GTIN path when the immutable target already had
        # that code. The bridge exists only for later identifier evidence and
        # exact manual/weight selection.
        target_has_scanned_gtin = bool(
            observation.gtin
            and any(candidate.gtin == observation.gtin for candidate in target_candidates)
        )
        if target_candidates and not target_has_scanned_gtin:
            verified_identity = target_identity
            verified_gtin = item.target_gtin
    return PhysicalPriceValidationService().compare_observation(
        observation,
        candidate_tuple,
        expected_providers=providers,
        verified_session_product_identity=verified_identity,
        verified_session_gtin=verified_gtin,
    )


def _sample_confidence(count: int, minimum_sample: int) -> PhysicalSampleConfidence:
    if count == 0:
        return PhysicalSampleConfidence.NO_PHYSICAL_SAMPLE
    if count < minimum_sample:
        return PhysicalSampleConfidence.LIMITED_SAMPLE
    return PhysicalSampleConfidence.GOOD_SAMPLE


def _bucket(
    comparisons: Sequence[PhysicalPriceComparison],
    *,
    minimum_sample: int,
) -> AccuracyBucket:
    total = len(comparisons)
    usable = [
        comparison
        for comparison in comparisons
        if comparison.status
        not in {
            PhysicalPriceComparisonStatus.NO_DIGITAL_MATCH,
            PhysicalPriceComparisonStatus.STALE_DIGITAL_PRICE,
        }
    ]
    exact = sum(comparison.exact_match for comparison in usable)
    within_050 = sum(comparison.within_050 for comparison in usable)
    within_100 = sum(comparison.within_100 for comparison in usable)
    exact_percent = _percent(exact, total)
    within_050_percent = _percent(within_050, total)
    within_100_percent = _percent(within_100, total)
    eligible = total >= minimum_sample
    signed_errors = [
        comparison.signed_difference
        for comparison in usable
        if comparison.signed_difference is not None
    ]
    absolute_errors = [abs(error) for error in signed_errors]
    mean_absolute_error = (
        _money(sum(absolute_errors, Decimal(0)) / len(absolute_errors))
        if absolute_errors
        else None
    )
    median_absolute_error = (
        _money(Decimal(median(absolute_errors))) if absolute_errors else None
    )
    mean_signed_error = (
        _money(sum(signed_errors, Decimal(0)) / len(signed_errors))
        if signed_errors
        else None
    )
    return AccuracyBucket(
        comparisons=total,
        exact_matches=exact,
        within_050=within_050,
        within_100=within_100,
        minor_differences=sum(
            comparison.status is PhysicalPriceComparisonStatus.MINOR_DIFFERENCE
            for comparison in comparisons
        ),
        major_differences=sum(
            comparison.status is PhysicalPriceComparisonStatus.MAJOR_DIFFERENCE
            for comparison in comparisons
        ),
        no_digital_match=sum(
            comparison.status is PhysicalPriceComparisonStatus.NO_DIGITAL_MATCH
            for comparison in comparisons
        ),
        stale_digital_price=sum(
            comparison.status is PhysicalPriceComparisonStatus.STALE_DIGITAL_PRICE
            for comparison in comparisons
        ),
        exact_percent=exact_percent,
        within_050_percent=within_050_percent,
        within_100_percent=within_100_percent,
        minimum_sample_for_score=minimum_sample,
        score_eligible=eligible,
        sample_confidence=_sample_confidence(total, minimum_sample),
        display_exact_percent=exact_percent if eligible else None,
        display_within_050_percent=within_050_percent if eligible else None,
        display_within_100_percent=within_100_percent if eligible else None,
        priced_comparisons=len(signed_errors),
        mean_absolute_error=mean_absolute_error,
        median_absolute_error=median_absolute_error,
        mean_signed_error=mean_signed_error,
        digital_lower_than_shelf_count=sum(error > 0 for error in signed_errors),
        digital_higher_than_shelf_count=sum(error < 0 for error in signed_errors),
    )


def build_accuracy_report(
    observations: Sequence[PhysicalPriceObservation],
    comparisons: Sequence[PhysicalPriceComparison],
    *,
    scope_label: str,
    minimum_sample: int = 20,
) -> SourceAccuracyReport:
    if minimum_sample <= 0:
        raise ValueError("minimum_sample must be greater than zero")
    observation_by_id = {observation.id: observation for observation in observations}
    if len(observation_by_id) != len(observations):
        raise ValueError("observation IDs must be unique")
    unknown = {row.observation_id for row in comparisons} - observation_by_id.keys()
    if unknown:
        raise ValueError("comparisons must refer to supplied observations")

    provider_groups: dict[str, list[PhysicalPriceComparison]] = defaultdict(list)
    for comparison in comparisons:
        provider_groups[comparison.source_provider or "unknown"].append(comparison)

    segment_groups: dict[str, list[PhysicalPriceComparison]] = defaultdict(list)
    for comparison in comparisons:
        observation = observation_by_id[comparison.observation_id]
        if observation.promotion_type is None:
            segment_groups["regular_products"].append(comparison)
        else:
            segment_groups["campaigns"].append(comparison)
        if observation.member_only or observation.promotion_type is PromotionType.MEMBER_PRICE:
            segment_groups["member_prices"].append(comparison)
        if (
            observation.multibuy_quantity is not None
            or observation.promotion_type is PromotionType.MULTIBUY
        ):
            segment_groups["multibuy"].append(comparison)
        if comparison.sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }:
            segment_groups["weight_products"].append(comparison)

    dates = {observation.observed_at.date() for observation in observations}
    campaign_weeks = {
        (observation.observed_at.isocalendar().year, observation.observed_at.isocalendar().week)
        for observation in observations
        if observation.promotion_type is not None
    }
    normalized_scope = scope_label.strip()
    if not normalized_scope:
        raise ValueError("scope_label is required")
    return SourceAccuracyReport(
        scope_label=f"{normalized_scope} — sampled observations",
        observation_count=len(observations),
        days_sampled=len(dates),
        campaign_weeks_sampled=len(campaign_weeks),
        minimum_sample_for_score=minimum_sample,
        score_eligible=len(observations) >= minimum_sample,
        sample_confidence=_sample_confidence(len(observations), minimum_sample),
        providers={
            name: _bucket(rows, minimum_sample=minimum_sample)
            for name, rows in sorted(provider_groups.items())
        },
        segments={
            name: _bucket(rows, minimum_sample=minimum_sample)
            for name, rows in sorted(segment_groups.items())
        },
        identity_status_breakdown=dict(
            sorted(
                Counter(
                    observation.identity_status.value
                    if observation.identity_status
                    else "legacy"
                    for observation in observations
                ).items()
            )
        ),
        identification_evidence_breakdown=dict(
            sorted(
                Counter(
                    observation.identification_evidence.value
                    if observation.identification_evidence
                    else "legacy"
                    for observation in observations
                ).items()
            )
        ),
    )


class PhysicalVerificationSuggestionSampler:
    """Deterministic optional sampler; it never requests live chain data."""

    def suggest(
        self,
        candidates: Sequence[DigitalPriceCandidate],
        *,
        physical_store_id: str,
        limit: int = 10,
    ) -> tuple[VerificationSuggestion, ...]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        eligible = [
            candidate
            for candidate in candidates
            if candidate.physical_store_id == physical_store_id
        ]
        grouped: dict[str, list[DigitalPriceCandidate]] = defaultdict(list)
        for candidate in eligible:
            identity = candidate.gtin or f"name:{_normalized_name(candidate.product_name)}"
            grouped[identity].append(candidate)

        ranked: list[VerificationSuggestion] = []
        for identity, rows in grouped.items():
            representative = min(
                rows,
                key=lambda row: (
                    row.source_provider.casefold() != "own",
                    row.source_provider,
                    row.product_id,
                ),
            )
            score = min(representative.common_product_score, Decimal(10))
            reasons: list[str] = []
            if representative.common_product_score > 0:
                reasons.append("common_product")
            if representative.gtin:
                score += Decimal(1)
            if representative.sale_model in {
                SaleModel.SOLD_BY_WEIGHT,
                SaleModel.VARIABLE_WEIGHT_PACKAGE,
            }:
                score += Decimal(3)
                reasons.append("weight_product")
            if representative.promotion_type is not None:
                score += Decimal(3)
                reasons.append("promotion")
            if representative.member_only:
                score += Decimal(2)
                reasons.append("member_price")
            if representative.multibuy_quantity is not None:
                score += Decimal(2)
                reasons.append("multibuy")
            if representative.recent_price_change is not None:
                if representative.recent_price_change > Decimal(1):
                    score += Decimal(5)
                    reasons.append("large_recent_price_change")
                elif representative.recent_price_change > 0:
                    score += Decimal(2)
                    reasons.append("recent_price_change")
            provider_prices = {
                row.source_provider: row.current_price for row in rows if row.source_provider
            }
            if len(provider_prices) >= 2:
                disagreement = max(provider_prices.values()) - min(provider_prices.values())
                if disagreement > Decimal(1):
                    score += Decimal(6)
                    reasons.append("large_source_disagreement")
                elif disagreement > 0:
                    score += Decimal(3)
                    reasons.append("source_disagreement")
            if not reasons:
                reasons.append("random_diversity_sample")
            ranked.append(
                VerificationSuggestion(
                    physical_store_id=physical_store_id,
                    grocery_context_id=representative.grocery_context_id,
                    source_provider=representative.source_provider,
                    product_id=representative.product_id,
                    gtin=representative.gtin,
                    product_name=representative.product_name,
                    brand=representative.brand,
                    category=representative.category,
                    package_description=representative.package_description,
                    current_price=representative.current_price,
                    sale_model=representative.sale_model,
                    promotion_type=representative.promotion_type,
                    stratum=self._stratum(representative),
                    priority_score=score,
                    reasons=tuple(reasons),
                )
            )

        ranked.sort(
            key=lambda row: (
                -row.priority_score,
                row.product_name.casefold(),
                row.product_id,
            )
        )
        chosen: list[VerificationSuggestion] = []
        seen_models: set[SaleModel] = set()
        for suggestion in ranked:
            if suggestion.sale_model in seen_models:
                continue
            chosen.append(suggestion)
            seen_models.add(suggestion.sale_model)
            if len(chosen) == limit:
                return tuple(chosen)
        for suggestion in ranked:
            if suggestion in chosen:
                continue
            chosen.append(suggestion)
            if len(chosen) == limit:
                break
        return tuple(chosen)

    def suggest_stratified(
        self,
        candidates: Sequence[DigitalPriceCandidate],
        *,
        physical_store_id: str,
        limit: int = 20,
    ) -> tuple[VerificationSuggestion, ...]:
        """Return a deterministic five-stratum field set.

        The target is distributed only across REGULAR, SALE, MEMBER,
        MULTIBUY and WEIGHT rows.  UNKNOWN is an evidence state, not a useful
        sampling bucket.  A source that lacks one requested stratum is
        backfilled from the remaining ranked candidates; the returned stratum
        remains truthful and callers can expose the shortfall.
        """

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        ranked = self.suggest(
            candidates,
            physical_store_id=physical_store_id,
            limit=100,
        )
        strata = (
            PhysicalPriceSemantics.REGULAR,
            PhysicalPriceSemantics.SALE,
            PhysicalPriceSemantics.MEMBER,
            PhysicalPriceSemantics.MULTIBUY,
            PhysicalPriceSemantics.WEIGHT,
        )
        quota, remainder = divmod(limit, len(strata))
        selected: list[VerificationSuggestion] = []
        for index, stratum in enumerate(strata):
            target = quota + (1 if index < remainder else 0)
            selected.extend(
                self._pick_diverse(
                    [row for row in ranked if row.stratum is stratum],
                    limit=target,
                )
            )
        if len(selected) < limit:
            selected_ids = {(row.grocery_context_id, row.product_id) for row in selected}
            for row in ranked:
                identity = (row.grocery_context_id, row.product_id)
                if identity in selected_ids:
                    continue
                selected.append(row)
                selected_ids.add(identity)
                if len(selected) == limit:
                    break
        return tuple(selected[:limit])

    @staticmethod
    def _pick_diverse(
        rows: Sequence[VerificationSuggestion],
        *,
        limit: int,
    ) -> list[VerificationSuggestion]:
        """Greedily retain source priority while spreading cheap sample dimensions."""

        chosen: list[VerificationSuggestion] = []
        remaining = list(rows)
        seen_categories: set[str] = set()
        seen_brands: set[str] = set()
        seen_packages: set[str] = set()
        seen_price_bands: set[int] = set()
        while remaining and len(chosen) < limit:
            def diversity_rank(row: VerificationSuggestion) -> tuple[object, ...]:
                category = (row.category or "unknown").casefold()
                brand = (row.brand or "unknown").casefold()
                package = (row.package_description or "unknown").casefold()
                price_band = int(row.current_price // Decimal(25))
                novelty = sum(
                    (
                        category not in seen_categories,
                        brand not in seen_brands,
                        package not in seen_packages,
                        price_band not in seen_price_bands,
                    )
                )
                return (
                    -novelty,
                    -row.priority_score,
                    row.product_name.casefold(),
                    row.product_id,
                )

            selected = min(remaining, key=diversity_rank)
            remaining.remove(selected)
            chosen.append(selected)
            seen_categories.add((selected.category or "unknown").casefold())
            seen_brands.add((selected.brand or "unknown").casefold())
            seen_packages.add((selected.package_description or "unknown").casefold())
            seen_price_bands.add(int(selected.current_price // Decimal(25)))
        return chosen

    @staticmethod
    def _stratum(candidate: DigitalPriceCandidate) -> PhysicalPriceSemantics:
        if candidate.sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }:
            return PhysicalPriceSemantics.WEIGHT
        if candidate.member_only or candidate.promotion_type is PromotionType.MEMBER_PRICE:
            return PhysicalPriceSemantics.MEMBER
        if (
            candidate.multibuy_quantity is not None
            or candidate.promotion_type is PromotionType.MULTIBUY
        ):
            return PhysicalPriceSemantics.MULTIBUY
        if candidate.promotion_type is not None:
            return PhysicalPriceSemantics.SALE
        return PhysicalPriceSemantics.REGULAR


__all__ = [
    "PhysicalPriceValidationService",
    "PhysicalVerificationSuggestionSampler",
    "build_accuracy_report",
    "compare_frozen_session_observation",
    "derived_observation_confidence",
]
