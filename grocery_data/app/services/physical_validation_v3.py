from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from statistics import median

from sqlalchemy.orm import Session

from grocery_data.app.domain.enums import SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalPriceComparison,
    PhysicalPriceComparisonStatus,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    PhysicalValidationSessionItem,
    PhysicalValidationSessionStatus,
    PromotionComparisonStatus,
)
from grocery_data.app.services.physical_price_candidates import (
    PersistedPhysicalPriceCandidateReader,
    physical_observation_from_row,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
    compare_frozen_session_observation,
)
from grocery_data.app.services.physical_source_price_evidence import (
    PhysicalSourceSemanticPriceAdapter,
    SemanticPriceDiagnostic,
)
from grocery_data.app.storage.repositories import (
    PhysicalPriceObservationRepository,
    PhysicalValidationComparisonVersion,
    PhysicalValidationSessionRepository,
    PhysicalValidationSnapshotLock,
    digital_candidate_sha256,
)

OFFICIAL_VERSION_KIND = "official_snapshot_lock"
POST_VISIT_DIAGNOSTIC_VERSION_KIND = "post_visit_diagnostic"
AMENDED_PHYSICAL_EVIDENCE_VERSION_KIND = "amended_physical_evidence"
DEFAULT_OFFICIAL_FRESHNESS_HOURS = Decimal(2)
DEFAULT_MINIMUM_COMPARABLE_SAMPLE = 20


class ComparisonExclusionReason(StrEnum):
    NO_DIGITAL_MATCH = "no_digital_match"
    STALE_DIGITAL = "stale_digital"
    PROMOTION_SEMANTICS_INCOMPLETE = "promotion_semantics_incomplete"
    MEMBERSHIP_NOT_COMPARABLE = "membership_not_comparable"
    QUANTITY_NOT_COMPARABLE = "quantity_not_comparable"
    PRICE_BASIS_NOT_COMPARABLE = "price_basis_not_comparable"
    IDENTITY_UNCERTAIN = "identity_uncertain"
    INPUT_ANOMALY_SUSPECTED = "input_anomaly_suspected"
    POST_VISIT_DIAGNOSTIC_ONLY = "post_visit_diagnostic_only"


@dataclass(frozen=True, slots=True)
class PhysicalComparisonAssessment:
    comparison: PhysicalPriceComparison
    comparable: bool
    exclusion_reasons: tuple[ComparisonExclusionReason, ...]
    semantic_diagnostic: SemanticPriceDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class PhysicalValidationV3Report:
    validation_session_id: str
    version: PhysicalValidationComparisonVersion
    official: bool
    diagnostic_only: bool
    observations: tuple[PhysicalPriceObservation, ...]
    comparisons: tuple[PhysicalPriceComparison, ...]
    assessments: tuple[PhysicalComparisonAssessment, ...]
    snapshot_locks: tuple[PhysicalValidationSnapshotLock, ...]
    minimum_comparable_sample: int
    amended_physical_evidence: bool = False

    @property
    def comparable_comparisons(self) -> tuple[PhysicalPriceComparison, ...]:
        return tuple(
            row.comparison for row in self.assessments if row.comparable
        )

    @property
    def comparable_denominator(self) -> int:
        return len(self.comparable_comparisons)

    @property
    def score_eligible(self) -> bool:
        return (
            (self.official or self.amended_physical_evidence)
            and self.comparable_denominator >= self.minimum_comparable_sample
        )

    def metadata(self) -> dict[str, object]:
        comparable = self.comparable_comparisons
        denominator = len(comparable)

        def percent(count: int) -> Decimal:
            if denominator == 0:
                return Decimal(0)
            return (Decimal(count) * 100 / Decimal(denominator)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        exact = sum(row.exact_match for row in comparable)
        within_050 = sum(row.within_050 for row in comparable)
        within_100 = sum(row.within_100 for row in comparable)
        signed_errors = tuple(
            row.signed_difference
            for row in comparable
            if row.signed_difference is not None
        )
        absolute_errors = tuple(abs(value) for value in signed_errors)

        def money(value: Decimal) -> Decimal:
            return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        exclusions = Counter(
            reason.value
            for assessment in self.assessments
            for reason in assessment.exclusion_reasons
        )
        semantic_assessments = tuple(
            (assessment, diagnostic)
            for assessment in self.assessments
            if (diagnostic := assessment.semantic_diagnostic) is not None
        )
        semantic_rows = tuple(row for _assessment, row in semantic_assessments)

        def amount_summary_eligible(
            assessment: PhysicalComparisonAssessment,
            row: SemanticPriceDiagnostic,
        ) -> bool:
            return (
                row.comparable
                and assessment.comparison.status
                is not PhysicalPriceComparisonStatus.NO_DIGITAL_MATCH
                and ComparisonExclusionReason.IDENTITY_UNCERTAIN
                not in assessment.exclusion_reasons
            )

        semantic_comparable_assessments = tuple(
            (assessment, row)
            for assessment, row in semantic_assessments
            if amount_summary_eligible(assessment, row)
        )
        semantic_change_reasons = Counter(
            reason.value
            for row in semantic_rows
            for reason in row.change_reasons
        )
        semantic_mismatches = Counter(
            dimension for row in semantic_rows for dimension in row.mismatch_dimensions
        )
        semantic_signed_differences = tuple(
            difference
            for _assessment, row in semantic_comparable_assessments
            if (difference := row.signed_difference) is not None
        )
        semantic_absolute_differences = tuple(
            abs(value) for value in semantic_signed_differences
        )
        return {
            "validation_session_id": self.validation_session_id,
            "version": {
                "id": self.version.id,
                "number": self.version.version_number,
                "kind": self.version.version_kind,
                "source_snapshot_ids": list(self.version.source_snapshot_ids),
                "evidence_sha256": self.version.evidence_sha256,
                "freshness_threshold_hours": self.version.freshness_threshold_hours,
                "reason": self.version.reason,
                "created_at": self.version.created_at,
            },
            "official": self.official,
            "diagnostic_only": self.diagnostic_only,
            "amended_physical_evidence": self.amended_physical_evidence,
            "official_replaced_by_amendment": False,
            "sampled_only": True,
            "physical_observation_count": len(self.observations),
            "comparison_count": len(self.comparisons),
            "comparable_denominator": denominator,
            "excluded_comparisons": len(self.assessments) - denominator,
            "minimum_comparable_sample": self.minimum_comparable_sample,
            "score_eligible": self.score_eligible,
            "accuracy_display": (
                "AVAILABLE" if self.score_eligible else "INSUFFICIENT_COMPARABLE_SAMPLE"
            ),
            "exact_matches": exact,
            "within_050": within_050,
            "within_100": within_100,
            "exact_percent": percent(exact),
            "within_050_percent": percent(within_050),
            "within_100_percent": percent(within_100),
            "priced_comparable_count": len(signed_errors),
            "mean_absolute_error": (
                money(sum(absolute_errors, Decimal(0)) / len(absolute_errors))
                if absolute_errors
                else None
            ),
            "median_absolute_error": (
                money(Decimal(median(absolute_errors)))
                if absolute_errors
                else None
            ),
            "mean_signed_error": (
                money(sum(signed_errors, Decimal(0)) / len(signed_errors))
                if signed_errors
                else None
            ),
            "signed_error_definition": (
                "physical_price_minus_digital_price_sek; "
                "positive means the digital price is lower than the shelf price"
            ),
            "status_counts": dict(
                sorted(Counter(row.status.value for row in self.comparisons).items())
            ),
            "comparable_status_counts": dict(
                sorted(Counter(row.status.value for row in comparable).items())
            ),
            "exclusion_reason_counts": dict(sorted(exclusions.items())),
            "semantic_price_diagnostics": {
                "comparison_count": len(semantic_rows),
                "contract_comparable_count": sum(row.comparable for row in semantic_rows),
                "comparable_count": len(semantic_comparable_assessments),
                "exact_amount_match_count": sum(
                    row.exact_amount_match
                    for _assessment, row in semantic_comparable_assessments
                ),
                "source_promotion_rows": sum(
                    row.source_promotion_rows for row in semantic_rows
                ),
                "normalized_promotions": sum(
                    row.normalized_promotions for row in semantic_rows
                ),
                "invalid_promotion_rows": sum(
                    row.invalid_promotion_rows for row in semantic_rows
                ),
                "temporal_neutral_amount_summary": {
                    "priced_comparable_count": len(semantic_signed_differences),
                    "exact_matches": sum(
                        value == 0 for value in semantic_absolute_differences
                    ),
                    "within_050": sum(
                        value <= Decimal("0.50")
                        for value in semantic_absolute_differences
                    ),
                    "within_100": sum(
                        value <= Decimal("1.00")
                        for value in semantic_absolute_differences
                    ),
                    "major_difference": sum(
                        value > Decimal("1.00")
                        for value in semantic_absolute_differences
                    ),
                    "mean_absolute_error": (
                        money(
                            sum(semantic_absolute_differences, Decimal(0))
                            / len(semantic_absolute_differences)
                        )
                        if semantic_absolute_differences
                        else None
                    ),
                    "median_absolute_error": (
                        money(Decimal(median(semantic_absolute_differences)))
                        if semantic_absolute_differences
                        else None
                    ),
                    "mean_signed_error": (
                        money(
                            sum(semantic_signed_differences, Decimal(0))
                            / len(semantic_signed_differences)
                        )
                        if semantic_signed_differences
                        else None
                    ),
                    "signed_error_definition": (
                        "physical_semantic_price_minus_digital_semantic_price_sek; "
                        "independent of freshness/diagnostic-only score eligibility"
                    ),
                },
                "change_reason_counts": dict(sorted(semantic_change_reasons.items())),
                "mismatch_dimension_counts": dict(sorted(semantic_mismatches.items())),
                "rows": [
                    {
                        "observation_id": assessment.comparison.observation_id,
                        "contract_comparable": row.comparable,
                        "comparable": amount_summary_eligible(assessment, row),
                        "exact_amount_match": (
                            row.exact_amount_match
                            if amount_summary_eligible(assessment, row)
                            else False
                        ),
                        "physical": (
                            row.physical.model_dump(mode="json")
                            if row.physical is not None
                            else None
                        ),
                        "digital": (
                            row.digital.model_dump(mode="json")
                            if row.digital is not None
                            else None
                        ),
                        "source_promotion_rows": row.source_promotion_rows,
                        "normalized_promotions": row.normalized_promotions,
                        "invalid_promotion_rows": row.invalid_promotion_rows,
                        "change_reasons": [value.value for value in row.change_reasons],
                        "mismatch_dimensions": list(row.mismatch_dimensions),
                        "comparison_status": assessment.comparison.status.value,
                        "exclusion_reasons": [
                            value.value for value in assessment.exclusion_reasons
                        ],
                        "amount_summary_eligible": amount_summary_eligible(
                            assessment,
                            row,
                        ),
                        "signed_difference": (
                            row.signed_difference
                            if amount_summary_eligible(assessment, row)
                            else None
                        ),
                        "absolute_difference": (
                            row.absolute_difference
                            if amount_summary_eligible(assessment, row)
                            else None
                        ),
                        "semantic_result": (
                            row.semantic_result
                            if amount_summary_eligible(assessment, row)
                            else "excluded_from_amount_summary"
                        ),
                    }
                    for assessment in self.assessments
                    if (row := assessment.semantic_diagnostic) is not None
                ],
            },
            "snapshot_locks": [
                {
                    "source_provider": row.source_provider,
                    "grocery_context_id": row.grocery_context_id,
                    "source_snapshot_id": row.source_snapshot_id,
                    "candidate_count": row.candidate_count,
                    "evidence_sha256": row.evidence_sha256,
                    "locked_at": row.locked_at,
                }
                for row in self.snapshot_locks
            ],
            "immutable_session_evidence_preserved": True,
            "physical_observations_modified": False,
        }


class PhysicalValidationV3Service:
    """Versioned, fail-closed validation without rewriting field evidence."""

    def __init__(
        self,
        session: Session,
        *,
        official_freshness_hours: Decimal = DEFAULT_OFFICIAL_FRESHNESS_HOURS,
        minimum_comparable_sample: int = DEFAULT_MINIMUM_COMPARABLE_SAMPLE,
    ) -> None:
        threshold = Decimal(official_freshness_hours)
        if not threshold.is_finite() or threshold <= 0:
            raise ValueError("official freshness threshold must be positive")
        if minimum_comparable_sample <= 0:
            raise ValueError("minimum comparable sample must be positive")
        self.session = session
        self.repository = PhysicalValidationSessionRepository(session)
        self.reader = PersistedPhysicalPriceCandidateReader(session)
        # Legacy comparison status keeps its historical 48 h behavior.  The
        # stricter V3 2 h official gate is applied independently below.
        self.validator = PhysicalPriceValidationService()
        self.semantic_price_adapter = PhysicalSourceSemanticPriceAdapter(session)
        self.official_freshness_hours = threshold
        self.minimum_comparable_sample = minimum_comparable_sample

    def lock_session_start(
        self,
        validation_session_id: str,
    ) -> tuple[PhysicalValidationSnapshotLock, ...]:
        """Persist/verify the official snapshot boundary for ACTIVE or completed sessions."""

        if self.repository.get(validation_session_id) is None:
            raise LookupError("validation session does not exist")
        return self.repository.ensure_snapshot_locks(validation_session_id)

    def lock_official(
        self,
        validation_session_id: str,
        *,
        created_at: datetime | None = None,
    ) -> PhysicalValidationV3Report:
        validation_session = self._completed_session(validation_session_id)
        locks = self.lock_session_start(validation_session_id)
        evidence_sha256 = self._lock_set_sha256(locks)
        version = self.repository.add_comparison_version(
            session_id=validation_session_id,
            version_kind=OFFICIAL_VERSION_KIND,
            source_snapshot_ids=tuple(row.source_snapshot_id for row in locks),
            evidence_sha256=evidence_sha256,
            freshness_threshold_hours=self.official_freshness_hours,
            reason="immutable session-start digital snapshot lock",
            created_at=created_at or validation_session.completed_at or datetime.now(tz=UTC),
        )
        return self._official_report(version, locks)

    def amended_report(
        self,
        validation_session_id: str,
        *,
        observations: tuple[PhysicalPriceObservation, ...],
        evidence_sha256: str,
    ) -> PhysicalValidationV3Report:
        """Report an explicit append-only physical-evidence amendment version."""

        self._completed_session(validation_session_id)
        versions = tuple(
            row
            for row in self.repository.comparison_versions(validation_session_id)
            if row.version_kind == AMENDED_PHYSICAL_EVIDENCE_VERSION_KIND
        )
        if not versions:
            raise LookupError("amended physical evidence version is not locked")
        version = versions[-1]
        if version.evidence_sha256 != evidence_sha256:
            raise ValueError("amended physical evidence does not match its version")
        locks = self.repository.preview_snapshot_locks(validation_session_id)
        locked_snapshot_ids = tuple(
            sorted({row.source_snapshot_id for row in locks})
        )
        if version.source_snapshot_ids != locked_snapshot_ids:
            raise ValueError("amended physical evidence changed the digital snapshot boundary")
        items = {row.id: row for row in self.repository.items(validation_session_id)}
        if not observations or any(
            (row.validation_session_item_id or "") not in items
            for row in observations
        ):
            raise ValueError("amended physical evidence has invalid session items")
        return self._locked_physical_report(
            version,
            locks,
            observations=observations,
            items=items,
            amended_physical_evidence=True,
        )

    def official_report(self, validation_session_id: str) -> PhysicalValidationV3Report:
        versions = self.repository.comparison_versions(validation_session_id)
        version = next(
            (row for row in versions if row.version_kind == OFFICIAL_VERSION_KIND),
            None,
        )
        if version is None:
            raise LookupError("official physical comparison version is not locked")
        locks = self.repository.snapshot_locks(validation_session_id)
        if not locks or self._lock_set_sha256(locks) != version.evidence_sha256:
            raise ValueError("official snapshot lock evidence does not match its version")
        return self._official_report(version, locks)

    def preview_official(
        self,
        validation_session_id: str,
    ) -> PhysicalValidationV3Report:
        """Build the official report contract without persisting legacy locks."""

        validation_session = self._completed_session(validation_session_id)
        locks = self.repository.preview_snapshot_locks(validation_session_id)
        evidence_sha256 = self._lock_set_sha256(locks)
        existing = next(
            (
                row
                for row in self.repository.comparison_versions(validation_session_id)
                if row.version_kind == OFFICIAL_VERSION_KIND
            ),
            None,
        )
        if existing is not None:
            if existing.evidence_sha256 != evidence_sha256:
                raise ValueError(
                    "official snapshot lock evidence does not match its version"
                )
            version = existing
        else:
            version = PhysicalValidationComparisonVersion(
                id=f"preview-{evidence_sha256[:24]}",
                validation_session_id=validation_session_id,
                version_number=1,
                version_kind=OFFICIAL_VERSION_KIND,
                source_snapshot_ids=tuple(
                    sorted({row.source_snapshot_id for row in locks})
                ),
                evidence_sha256=evidence_sha256,
                freshness_threshold_hours=self.official_freshness_hours,
                reason="unpersisted immutable session-start snapshot preview",
                created_at=(
                    validation_session.completed_at
                    or validation_session.started_at
                ),
            )
        return self._official_report(version, locks)

    def register_post_visit_diagnostic(
        self,
        validation_session_id: str,
        *,
        snapshot_id: str,
        reason: str,
        created_at: datetime | None = None,
    ) -> PhysicalValidationV3Report:
        validation_session = self._completed_session(validation_session_id)
        # An official version must exist first so a diagnostic can never become
        # the de-facto baseline merely because it was registered earlier.
        try:
            self.official_report(validation_session_id)
        except LookupError:
            self.lock_official(validation_session_id, created_at=created_at)
        observations, items = self._observations_and_items(validation_session_id)
        candidates_by_observation = self._diagnostic_candidates(
            validation_session_id,
            snapshot_id=snapshot_id,
            observations=observations,
            items=items,
            physical_store_id=validation_session.physical_store_id,
            chain=validation_session.chain,
            require_active=True,
        )
        evidence_payload = [
            f"{observation.id}:{digital_candidate_sha256(candidate)}"
            for observation, candidate in zip(
                observations,
                candidates_by_observation,
                strict=True,
            )
        ]
        evidence_sha256 = hashlib.sha256(
            "\n".join(sorted(evidence_payload)).encode()
        ).hexdigest()
        version = self.repository.add_comparison_version(
            session_id=validation_session_id,
            version_kind=POST_VISIT_DIAGNOSTIC_VERSION_KIND,
            source_snapshot_ids=(snapshot_id,),
            evidence_sha256=evidence_sha256,
            freshness_threshold_hours=self.official_freshness_hours,
            reason=reason,
            created_at=created_at or datetime.now(tz=UTC),
        )
        return self._diagnostic_report(
            version,
            observations=observations,
            items=items,
            candidates=candidates_by_observation,
        )

    def diagnostic_reports(
        self,
        validation_session_id: str,
    ) -> tuple[PhysicalValidationV3Report, ...]:
        validation_session = self._completed_session(validation_session_id)
        observations, items = self._observations_and_items(validation_session_id)
        reports: list[PhysicalValidationV3Report] = []
        for version in self.repository.comparison_versions(validation_session_id):
            if version.version_kind != POST_VISIT_DIAGNOSTIC_VERSION_KIND:
                continue
            if len(version.source_snapshot_ids) != 1:
                raise ValueError("post-visit diagnostic must reference one snapshot")
            candidates = self._diagnostic_candidates(
                validation_session_id,
                snapshot_id=version.source_snapshot_ids[0],
                observations=observations,
                items=items,
                physical_store_id=validation_session.physical_store_id,
                chain=validation_session.chain,
                require_active=False,
            )
            reports.append(
                self._diagnostic_report(
                    version,
                    observations=observations,
                    items=items,
                    candidates=candidates,
                )
            )
        return tuple(reports)

    def report(self, validation_session_id: str) -> dict[str, object]:
        versions = self.repository.comparison_versions(validation_session_id)
        official_version_persisted = any(
            row.version_kind == OFFICIAL_VERSION_KIND for row in versions
        )
        official = self.preview_official(validation_session_id)
        diagnostics = self.diagnostic_reports(validation_session_id)
        return {
            "official": official.metadata(),
            "official_version_persisted": official_version_persisted,
            "post_visit_diagnostics": [row.metadata() for row in diagnostics],
            "official_replaced_by_diagnostic": False,
            "immutable_session_evidence_preserved": True,
        }

    def _official_report(
        self,
        version: PhysicalValidationComparisonVersion,
        locks: tuple[PhysicalValidationSnapshotLock, ...],
    ) -> PhysicalValidationV3Report:
        observations, items = self._observations_and_items(
            version.validation_session_id
        )
        return self._locked_physical_report(
            version,
            locks,
            observations=observations,
            items=items,
            amended_physical_evidence=False,
        )

    def _locked_physical_report(
        self,
        version: PhysicalValidationComparisonVersion,
        locks: tuple[PhysicalValidationSnapshotLock, ...],
        *,
        observations: tuple[PhysicalPriceObservation, ...],
        items: dict[str, PhysicalValidationSessionItem],
        amended_physical_evidence: bool,
    ) -> PhysicalValidationV3Report:
        locked_identities = {
            (row.source_provider, row.grocery_context_id, row.source_snapshot_id)
            for row in locks
        }
        comparisons: list[PhysicalPriceComparison] = []
        assessments: list[PhysicalComparisonAssessment] = []
        for observation in observations:
            item = items[observation.validation_session_item_id or ""]
            frozen = self.repository.candidates_for_item(item.id)
            target = tuple(
                candidate
                for candidate in frozen
                if (
                    candidate.source_provider == item.target_source_provider
                    and candidate.grocery_context_id == item.target_grocery_context_id
                    and candidate.product_id == item.target_product_id
                )
            )
            if target and any(
                (
                    candidate.source_provider,
                    candidate.grocery_context_id,
                    candidate.source_snapshot_id,
                )
                not in locked_identities
                for candidate in target
            ):
                raise ValueError("official candidate is outside the locked snapshot set")
            semantic = (
                self.semantic_price_adapter.compare(observation, target[0])
                if len(target) == 1
                else None
            )
            rows = compare_frozen_session_observation(
                observation,
                (semantic.adjusted_candidate,) if semantic is not None else target,
                item=item,
            )
            if len(rows) != 1:
                raise ValueError("locked comparison must resolve exactly one provider row")
            comparison = rows[0]
            comparisons.append(comparison)
            assessments.append(
                self._assess(
                    observation,
                    comparison,
                    freshness_hours=version.freshness_threshold_hours,
                    diagnostic_only=False,
                    semantic_diagnostic=semantic,
                )
            )
        return PhysicalValidationV3Report(
            validation_session_id=version.validation_session_id,
            version=version,
            official=not amended_physical_evidence,
            diagnostic_only=False,
            observations=observations,
            comparisons=tuple(comparisons),
            assessments=tuple(assessments),
            snapshot_locks=locks,
            minimum_comparable_sample=self.minimum_comparable_sample,
            amended_physical_evidence=amended_physical_evidence,
        )

    def _diagnostic_report(
        self,
        version: PhysicalValidationComparisonVersion,
        *,
        observations: tuple[PhysicalPriceObservation, ...],
        items: dict[str, PhysicalValidationSessionItem],
        candidates: tuple[DigitalPriceCandidate, ...],
    ) -> PhysicalValidationV3Report:
        comparisons: list[PhysicalPriceComparison] = []
        assessments: list[PhysicalComparisonAssessment] = []
        for observation, candidate_object in zip(
            observations,
            candidates,
            strict=True,
        ):
            candidate = candidate_object
            item = items[observation.validation_session_item_id or ""]
            semantic = self.semantic_price_adapter.compare(observation, candidate)
            rows = self.validator.compare_observation(
                observation,
                (semantic.adjusted_candidate,),
                expected_providers=(candidate.source_provider,),
                verified_session_product_identity=(
                    candidate.source_provider,
                    candidate.grocery_context_id,
                    candidate.product_id,
                ),
                verified_session_gtin=item.target_gtin,
            )
            if len(rows) != 1:
                raise ValueError("diagnostic comparison must resolve exactly one row")
            comparison = rows[0]
            comparisons.append(comparison)
            assessments.append(
                self._assess(
                    observation,
                    comparison,
                    freshness_hours=version.freshness_threshold_hours,
                    diagnostic_only=True,
                    semantic_diagnostic=semantic,
                )
            )
        return PhysicalValidationV3Report(
            validation_session_id=version.validation_session_id,
            version=version,
            official=False,
            diagnostic_only=True,
            observations=observations,
            comparisons=tuple(comparisons),
            assessments=tuple(assessments),
            snapshot_locks=self.repository.snapshot_locks(
                version.validation_session_id
            ),
            minimum_comparable_sample=self.minimum_comparable_sample,
        )

    def _diagnostic_candidates(
        self,
        validation_session_id: str,
        *,
        snapshot_id: str,
        observations: tuple[PhysicalPriceObservation, ...],
        items: dict[str, PhysicalValidationSessionItem],
        physical_store_id: str,
        chain: str,
        require_active: bool,
    ) -> tuple[DigitalPriceCandidate, ...]:
        del validation_session_id
        candidates: list[DigitalPriceCandidate] = []
        for observation in observations:
            item = items[observation.validation_session_item_id or ""]
            exact = self.reader.for_exact_session_item_snapshot(
                physical_store_id=physical_store_id,
                chain=chain,
                item=item,
                snapshot_id=snapshot_id,
                require_active=require_active,
            )
            if len(exact) != 1:
                raise ValueError(
                    "post-visit diagnostic lacks one exact stable product match"
                )
            candidates.append(exact[0])
        return tuple(candidates)

    def _observations_and_items(
        self,
        validation_session_id: str,
    ) -> tuple[
        tuple[PhysicalPriceObservation, ...],
        dict[str, PhysicalValidationSessionItem],
    ]:
        observations = tuple(
            physical_observation_from_row(row)
            for row in PhysicalPriceObservationRepository(self.session).list_for_session(
                validation_session_id
            )
        )
        if not observations:
            raise ValueError("validation session has no physical observations")
        items = {row.id: row for row in self.repository.items(validation_session_id)}
        if any(
            (row.validation_session_item_id or "") not in items for row in observations
        ):
            raise ValueError("physical observation is missing its immutable session item")
        return observations, items

    def _completed_session(self, validation_session_id: str):  # type: ignore[no-untyped-def]
        validation_session = self.repository.get(validation_session_id)
        if validation_session is None:
            raise LookupError("validation session does not exist")
        if validation_session.status is not PhysicalValidationSessionStatus.COMPLETED:
            raise ValueError("only a completed validation session can be reported")
        return validation_session

    @staticmethod
    def _lock_set_sha256(
        locks: tuple[PhysicalValidationSnapshotLock, ...],
    ) -> str:
        payload = [
            {
                "source_provider": row.source_provider,
                "grocery_context_id": row.grocery_context_id,
                "source_snapshot_id": row.source_snapshot_id,
                "candidate_count": row.candidate_count,
                "evidence_sha256": row.evidence_sha256,
            }
            for row in locks
        ]
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()

    @staticmethod
    def _assess(
        observation: PhysicalPriceObservation,
        comparison: PhysicalPriceComparison,
        *,
        freshness_hours: Decimal,
        diagnostic_only: bool,
        semantic_diagnostic: SemanticPriceDiagnostic | None = None,
    ) -> PhysicalComparisonAssessment:
        reasons: list[ComparisonExclusionReason] = []
        if comparison.status is PhysicalPriceComparisonStatus.NO_DIGITAL_MATCH:
            reasons.append(ComparisonExclusionReason.NO_DIGITAL_MATCH)
        if observation.identity_status in {
            PhysicalProductIdentityStatus.GTIN_MISMATCH,
            PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN,
            PhysicalProductIdentityStatus.NO_MATCH,
        }:
            reasons.append(ComparisonExclusionReason.IDENTITY_UNCERTAIN)
        if (
            comparison.digital_age_hours is not None
            and comparison.digital_age_hours > freshness_hours
        ):
            reasons.append(ComparisonExclusionReason.STALE_DIGITAL)
        if semantic_diagnostic is not None:
            mismatch_dimensions = set(semantic_diagnostic.mismatch_dimensions)
            if {
                "physical_semantics_unknown",
                "basis",
                "comparison_unit",
            }.intersection(mismatch_dimensions):
                reasons.append(ComparisonExclusionReason.PRICE_BASIS_NOT_COMPARABLE)
            if "eligibility" in mismatch_dimensions:
                reasons.append(ComparisonExclusionReason.MEMBERSHIP_NOT_COMPARABLE)
            if {
                "package_count",
                "condition_required_packages",
            }.intersection(mismatch_dimensions):
                reasons.append(ComparisonExclusionReason.QUANTITY_NOT_COMPARABLE)
            if {
                "digital_semantics_unavailable",
                "mechanism",
                "invalid_source_promotion_rows",
            }.intersection(mismatch_dimensions):
                reasons.append(
                    ComparisonExclusionReason.PROMOTION_SEMANTICS_INCOMPLETE
                )
        elif observation.price_semantics in {None, PhysicalPriceSemantics.UNKNOWN}:
            reasons.append(ComparisonExclusionReason.PRICE_BASIS_NOT_COMPARABLE)
        elif observation.price_semantics is PhysicalPriceSemantics.SALE:
            if comparison.promotion_status is not PromotionComparisonStatus.MATCH:
                reasons.append(
                    ComparisonExclusionReason.PROMOTION_SEMANTICS_INCOMPLETE
                )
        elif observation.price_semantics is PhysicalPriceSemantics.MEMBER:
            if (
                comparison.promotion_status is not PromotionComparisonStatus.MATCH
                or comparison.member_restriction_match is not True
            ):
                reasons.append(ComparisonExclusionReason.MEMBERSHIP_NOT_COMPARABLE)
        elif observation.price_semantics is PhysicalPriceSemantics.MULTIBUY:
            if (
                comparison.promotion_status is not PromotionComparisonStatus.MATCH
                or comparison.multibuy_match is not True
            ):
                reasons.append(ComparisonExclusionReason.QUANTITY_NOT_COMPARABLE)
        elif observation.price_semantics is PhysicalPriceSemantics.WEIGHT and (
            comparison.sale_model
            not in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}
            or comparison.comparison_price_match is not True
        ):
            reasons.append(ComparisonExclusionReason.PRICE_BASIS_NOT_COMPARABLE)
        if comparison.input_anomaly_suspected:
            reasons.append(ComparisonExclusionReason.INPUT_ANOMALY_SUSPECTED)
        if diagnostic_only:
            reasons.append(ComparisonExclusionReason.POST_VISIT_DIAGNOSTIC_ONLY)
        return PhysicalComparisonAssessment(
            comparison=comparison,
            comparable=not reasons,
            exclusion_reasons=tuple(dict.fromkeys(reasons)),
            semantic_diagnostic=semantic_diagnostic,
        )


__all__ = [
    "AMENDED_PHYSICAL_EVIDENCE_VERSION_KIND",
    "DEFAULT_MINIMUM_COMPARABLE_SAMPLE",
    "DEFAULT_OFFICIAL_FRESHNESS_HOURS",
    "OFFICIAL_VERSION_KIND",
    "POST_VISIT_DIAGNOSTIC_VERSION_KIND",
    "ComparisonExclusionReason",
    "PhysicalComparisonAssessment",
    "PhysicalValidationV3Report",
    "PhysicalValidationV3Service",
]
