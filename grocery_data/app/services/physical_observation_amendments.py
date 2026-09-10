from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from grocery_data.app.domain.physical_price import (
    PhysicalObservationAmendment,
    PhysicalPriceObservation,
    physical_observation_payload_sha256,
)
from grocery_data.app.services.physical_price_candidates import (
    physical_observation_from_row,
)
from grocery_data.app.services.physical_validation_v3 import (
    AMENDED_PHYSICAL_EVIDENCE_VERSION_KIND,
    DEFAULT_MINIMUM_COMPARABLE_SAMPLE,
    DEFAULT_OFFICIAL_FRESHNESS_HOURS,
    PhysicalValidationV3Service,
)
from grocery_data.app.storage.repositories import (
    PhysicalObservationAmendmentRepository,
    PhysicalPriceObservationRepository,
    PhysicalValidationComparisonVersion,
    PhysicalValidationSessionRepository,
)


@dataclass(frozen=True, slots=True)
class PhysicalObservationAmendmentResult:
    amendment: PhysicalObservationAmendment
    idempotent_replay: bool
    effective_observations: tuple[PhysicalPriceObservation, ...]
    effective_evidence_sha256: str
    version: PhysicalValidationComparisonVersion


@dataclass(frozen=True, slots=True)
class PhysicalObservationAmendedState:
    amendments: tuple[PhysicalObservationAmendment, ...]
    effective_observations: tuple[PhysicalPriceObservation, ...]
    effective_evidence_sha256: str


class PhysicalObservationAmendmentService:
    """Append corrections without changing original physical observation rows."""

    def __init__(
        self,
        session: Session,
        *,
        official_freshness_hours: Decimal = DEFAULT_OFFICIAL_FRESHNESS_HOURS,
        minimum_comparable_sample: int = DEFAULT_MINIMUM_COMPARABLE_SAMPLE,
    ) -> None:
        self.session = session
        self.repository = PhysicalObservationAmendmentRepository(session)
        self.session_repository = PhysicalValidationSessionRepository(session)
        self.observation_repository = PhysicalPriceObservationRepository(session)
        self.v3 = PhysicalValidationV3Service(
            session,
            official_freshness_hours=official_freshness_hours,
            minimum_comparable_sample=minimum_comparable_sample,
        )

    def append(
        self,
        amendment: PhysicalObservationAmendment,
    ) -> PhysicalObservationAmendmentResult:
        existing = self.repository.idempotency_lookup(
            amendment.validation_session_id,
            amendment.validation_session_item_id,
            amendment.client_request_id,
        )
        persisted = self.repository.add_amendment(amendment)
        state = self.amended_state(amendment.validation_session_id)
        if state is None:  # pragma: no cover - append necessarily creates one row
            raise RuntimeError("persisted amendment is missing from its session state")

        if existing is None:
            try:
                official = self.v3.official_report(amendment.validation_session_id)
            except LookupError:
                official = self.v3.lock_official(amendment.validation_session_id)
            version = self.session_repository.add_comparison_version(
                session_id=amendment.validation_session_id,
                version_kind=AMENDED_PHYSICAL_EVIDENCE_VERSION_KIND,
                source_snapshot_ids=official.version.source_snapshot_ids,
                evidence_sha256=state.effective_evidence_sha256,
                freshness_threshold_hours=official.version.freshness_threshold_hours,
                reason=(
                    "append-only physical evidence amendment "
                    f"{persisted.id}: {persisted.reason}"
                ),
                created_at=persisted.created_at or persisted.observed_at,
            )
        else:
            versions = tuple(
                row
                for row in self.session_repository.comparison_versions(
                    amendment.validation_session_id
                )
                if row.version_kind == AMENDED_PHYSICAL_EVIDENCE_VERSION_KIND
            )
            if not versions:
                raise RuntimeError("idempotent amendment lacks its evidence version")
            version = versions[-1]
            if version.evidence_sha256 != state.effective_evidence_sha256:
                raise RuntimeError("latest amendment version does not match effective evidence")

        return PhysicalObservationAmendmentResult(
            amendment=persisted,
            idempotent_replay=existing is not None,
            effective_observations=state.effective_observations,
            effective_evidence_sha256=state.effective_evidence_sha256,
            version=version,
        )

    def amended_state(
        self,
        validation_session_id: str,
    ) -> PhysicalObservationAmendedState | None:
        amendments = self.repository.amendments_for_session(validation_session_id)
        if not amendments:
            return None
        items = self.session_repository.items(validation_session_id)
        base_by_item = {
            row.validation_session_item_id: physical_observation_from_row(row)
            for row in self.observation_repository.list_for_session(
                validation_session_id
            )
        }
        head_by_item = {
            item.id: head
            for item in items
            if (head := self.repository.head_for_item(item.id)) is not None
        }
        effective: list[PhysicalPriceObservation] = []
        evidence_rows: list[dict[str, str | None]] = []
        for item in items:
            head = head_by_item.get(item.id)
            observation = head.payload if head is not None else base_by_item.get(item.id)
            if observation is None:
                continue
            effective.append(observation)
            evidence_rows.append(
                {
                    "validation_session_item_id": item.id,
                    "physical_observation_payload_sha256": (
                        physical_observation_payload_sha256(observation)
                    ),
                    "amendment_id": head.id if head is not None else None,
                    "base_observation_id": (
                        head.base_observation_id
                        if head is not None
                        else observation.id
                    ),
                }
            )
        evidence_sha256 = hashlib.sha256(
            json.dumps(
                evidence_rows,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return PhysicalObservationAmendedState(
            amendments=amendments,
            effective_observations=tuple(effective),
            effective_evidence_sha256=evidence_sha256,
        )


__all__ = [
    "PhysicalObservationAmendedState",
    "PhysicalObservationAmendmentResult",
    "PhysicalObservationAmendmentService",
]
