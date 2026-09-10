from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from grocery_data.app.domain.physical_price import (
    PhysicalPriceComparison,
    PhysicalPriceObservation,
    PhysicalValidationSessionStatus,
)
from grocery_data.app.services.physical_price_candidates import (
    PersistedPhysicalPriceCandidateReader,
    physical_observation_from_row,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
    compare_frozen_session_observation,
)
from grocery_data.app.storage.repositories import (
    PhysicalPriceObservationRepository,
    PhysicalValidationSessionReconciliation,
    PhysicalValidationSessionRepository,
)

FROZEN_COMPARISON_BASIS = "frozen_session_evidence"
RECONCILED_COMPARISON_BASIS = "explicit_post_visit_snapshot_reconciliation"


@dataclass(frozen=True, slots=True)
class PhysicalSessionComparisonBundle:
    validation_session_id: str
    comparison_basis: str
    observations: tuple[PhysicalPriceObservation, ...]
    comparisons: tuple[PhysicalPriceComparison, ...]
    original_comparisons: tuple[PhysicalPriceComparison, ...]
    diagnostic_comparisons: tuple[PhysicalPriceComparison, ...]
    original_snapshot_ids: tuple[str, ...]
    reconciliation: PhysicalValidationSessionReconciliation | None
    max_digital_age_hours: Decimal | None
    min_signed_offset_hours: Decimal | None
    max_signed_offset_hours: Decimal | None
    temporal_relation: str | None

    def metadata(self) -> dict[str, object]:
        return {
            "comparison_basis": self.comparison_basis,
            "post_visit_diagnostic_basis": (
                RECONCILED_COMPARISON_BASIS
                if self.reconciliation is not None
                else None
            ),
            "original_snapshot_ids": list(self.original_snapshot_ids),
            "reconciliation": (
                {
                    "id": self.reconciliation.id,
                    "source_provider": self.reconciliation.source_provider,
                    "grocery_context_id": self.reconciliation.grocery_context_id,
                    "source_snapshot_id": self.reconciliation.source_snapshot_id,
                    "reason": self.reconciliation.reason,
                    "reconciled_at": self.reconciliation.reconciled_at,
                }
                if self.reconciliation is not None
                else None
            ),
            "max_digital_age_hours": self.max_digital_age_hours,
            "min_signed_offset_hours": self.min_signed_offset_hours,
            "max_signed_offset_hours": self.max_signed_offset_hours,
            "temporal_relation": self.temporal_relation,
            "original_status_counts": dict(
                sorted(Counter(row.status.value for row in self.original_comparisons).items())
            ),
            "effective_status_counts": dict(
                sorted(Counter(row.status.value for row in self.comparisons).items())
            ),
            "diagnostic_status_counts": dict(
                sorted(
                    Counter(
                        row.status.value for row in self.diagnostic_comparisons
                    ).items()
                )
            ),
            "post_visit_diagnostic_replaces_official": False,
            "immutable_session_evidence_preserved": True,
            "physical_observations_modified": False,
        }


class PhysicalSessionReconciliationService:
    """Explicitly re-evaluate one completed visit against one exact snapshot.

    The operation never changes the field observations or the candidates that
    were frozen when the session began.  It records only an additive binding to
    a promoted snapshot, resolved by stable source external product identity.
    """

    def __init__(
        self,
        session: Session,
        *,
        max_digital_age_hours: Decimal = Decimal(48),
    ) -> None:
        if max_digital_age_hours <= 0:
            raise ValueError("max_digital_age_hours must be positive")
        self.session = session
        self.repository = PhysicalValidationSessionRepository(session)
        self.reader = PersistedPhysicalPriceCandidateReader(session)
        self.validator = PhysicalPriceValidationService(
            max_digital_age_hours=max_digital_age_hours
        )
        self.max_digital_age_hours = max_digital_age_hours

    def current_report(self, validation_session_id: str) -> PhysicalSessionComparisonBundle:
        binding = self.repository.reconciliation(validation_session_id)
        return self._build(
            validation_session_id,
            binding=binding,
            require_active=False,
        )

    def preview(
        self,
        validation_session_id: str,
        *,
        snapshot_id: str,
    ) -> PhysicalSessionComparisonBundle:
        validation_session = self.repository.get(validation_session_id)
        if validation_session is None:
            raise LookupError("validation session does not exist")
        if validation_session.status is not PhysicalValidationSessionStatus.COMPLETED:
            raise ValueError("only a completed validation session can be reconciled")
        items = self.repository.items(validation_session_id)
        identities = {
            (item.target_source_provider, item.target_grocery_context_id)
            for item in items
            if item.captured_observation_id is not None
        }
        if len(identities) != 1:
            raise ValueError(
                "reconciliation requires one exact provider/context across captured items"
            )
        provider, context_id = next(iter(identities))
        if provider is None or context_id is None:
            raise ValueError("captured items lack exact source/context identity")
        provisional = PhysicalValidationSessionReconciliation(
            id="preview",
            validation_session_id=validation_session_id,
            source_provider=provider,
            grocery_context_id=context_id,
            source_snapshot_id=snapshot_id,
            reason="preview",
            reconciled_at=datetime.now(tz=UTC),
        )
        return self._build(
            validation_session_id,
            binding=provisional,
            require_active=True,
        )

    def bind(
        self,
        validation_session_id: str,
        *,
        snapshot_id: str,
        reason: str,
        reconciled_at: datetime | None = None,
    ) -> PhysicalSessionComparisonBundle:
        preview = self.preview(validation_session_id, snapshot_id=snapshot_id)
        binding = preview.reconciliation
        assert binding is not None
        persisted = self.repository.add_reconciliation(
            session_id=validation_session_id,
            source_provider=binding.source_provider,
            grocery_context_id=binding.grocery_context_id,
            source_snapshot_id=snapshot_id,
            reason=reason,
            reconciled_at=reconciled_at or datetime.now(tz=UTC),
        )
        return self._build(
            validation_session_id,
            binding=persisted,
            require_active=False,
        )

    def _build(
        self,
        validation_session_id: str,
        *,
        binding: PhysicalValidationSessionReconciliation | None,
        require_active: bool,
    ) -> PhysicalSessionComparisonBundle:
        validation_session = self.repository.get(validation_session_id)
        if validation_session is None:
            raise LookupError("validation session does not exist")
        if (
            binding is not None
            and validation_session.status is not PhysicalValidationSessionStatus.COMPLETED
        ):
            raise ValueError("only a completed validation session can be reconciled")
        items = {item.id: item for item in self.repository.items(validation_session_id)}
        observations = tuple(
            physical_observation_from_row(row)
            for row in PhysicalPriceObservationRepository(self.session).list_for_session(
                validation_session_id
            )
        )
        if not observations:
            raise ValueError("validation session has no physical observations")

        original: list[PhysicalPriceComparison] = []
        diagnostic: list[PhysicalPriceComparison] = []
        original_snapshot_ids: set[str] = set()
        ages: list[Decimal] = []
        signed_offsets: list[Decimal] = []
        for observation in observations:
            item = items.get(observation.validation_session_item_id or "")
            if item is None:
                raise ValueError("physical observation is missing its immutable session item")
            frozen = self.repository.candidates_for_item(item.id)
            original_snapshot_ids.update(row.source_snapshot_id for row in frozen)
            original.extend(
                compare_frozen_session_observation(
                    observation,
                    frozen,
                    item=item,
                )
            )
            if binding is None:
                continue
            if (
                item.target_source_provider != binding.source_provider
                or item.target_grocery_context_id != binding.grocery_context_id
            ):
                raise ValueError(
                    "reconciliation binding does not match immutable session target"
                )
            candidates = self.reader.for_exact_session_item_snapshot(
                physical_store_id=validation_session.physical_store_id,
                chain=validation_session.chain,
                item=item,
                snapshot_id=binding.source_snapshot_id,
                require_active=require_active,
            )
            if len(candidates) != 1:
                raise ValueError(
                    "reconciliation snapshot lacks one exact stable product match"
                )
            candidate = candidates[0]
            age_hours = Decimal(
                str(abs((candidate.observed_at - observation.observed_at).total_seconds()))
            ) / Decimal(3600)
            signed_offset = Decimal(
                str((candidate.observed_at - observation.observed_at).total_seconds())
            ) / Decimal(3600)
            if age_hours > self.max_digital_age_hours:
                raise ValueError(
                    "reconciliation snapshot is too far from the physical observation"
                )
            ages.append(age_hours)
            signed_offsets.append(signed_offset)
            diagnostic.extend(
                self.validator.compare_observation(
                    observation,
                    candidates,
                    expected_providers=(binding.source_provider,),
                    verified_session_product_identity=(
                        candidate.source_provider,
                        candidate.grocery_context_id,
                        candidate.product_id,
                    ),
                    verified_session_gtin=item.target_gtin,
                )
            )
        temporal_relation: str | None = None
        if signed_offsets:
            if all(offset > 0 for offset in signed_offsets):
                temporal_relation = "post_visit"
            elif all(offset < 0 for offset in signed_offsets):
                temporal_relation = "pre_visit"
            elif all(offset == 0 for offset in signed_offsets):
                temporal_relation = "same_time"
            else:
                temporal_relation = "mixed"
        precision = Decimal("0.01")
        return PhysicalSessionComparisonBundle(
            validation_session_id=validation_session_id,
            comparison_basis=FROZEN_COMPARISON_BASIS,
            observations=observations,
            comparisons=tuple(original),
            original_comparisons=tuple(original),
            diagnostic_comparisons=tuple(diagnostic),
            original_snapshot_ids=tuple(sorted(original_snapshot_ids)),
            reconciliation=binding,
            max_digital_age_hours=(
                max(ages).quantize(precision) if ages else None
            ),
            min_signed_offset_hours=(
                min(signed_offsets).quantize(precision) if signed_offsets else None
            ),
            max_signed_offset_hours=(
                max(signed_offsets).quantize(precision) if signed_offsets else None
            ),
            temporal_relation=temporal_relation,
        )


__all__ = [
    "FROZEN_COMPARISON_BASIS",
    "RECONCILED_COMPARISON_BASIS",
    "PhysicalSessionComparisonBundle",
    "PhysicalSessionReconciliationService",
]
