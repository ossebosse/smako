from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from grocery_data.app.domain.enums import SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalValidationSession,
    PhysicalValidationSessionItem,
    SessionItemIdentifierStatus,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalVerificationSuggestionSampler,
)
from grocery_data.app.storage.repositories import (
    digital_candidate_set_sha256,
    validation_session_suggestion_sha256,
)


def _normalized_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _frozen_candidates_for_suggestion(
    suggestion_gtin: str | None,
    suggestion_product_name: str,
    candidates: Sequence[DigitalPriceCandidate],
) -> tuple[DigitalPriceCandidate, ...]:
    if suggestion_gtin:
        matching = [candidate for candidate in candidates if candidate.gtin == suggestion_gtin]
    else:
        normalized_name = _normalized_name(suggestion_product_name)
        matching = [
            candidate
            for candidate in candidates
            if _normalized_name(candidate.product_name) == normalized_name
        ]
    unique: dict[tuple[str, str, str, str], DigitalPriceCandidate] = {}
    for candidate in matching:
        identity = (
            candidate.source_provider,
            candidate.grocery_context_id,
            candidate.source_snapshot_id,
            candidate.product_id,
        )
        existing = unique.get(identity)
        if existing is None or candidate.observed_at > existing.observed_at:
            unique[identity] = candidate
    return tuple(
        sorted(
            unique.values(),
            key=lambda row: (
                row.source_provider,
                row.grocery_context_id,
                row.product_id,
            ),
        )
    )


def build_physical_validation_session(
    candidates: Sequence[DigitalPriceCandidate],
    *,
    physical_store_id: str,
    chain: str,
    store_name: str,
    target_count: int = 20,
    blind_capture: bool = True,
    sampling_strategy: str = "stratified",
    notes: str | None = None,
    started_at: datetime | None = None,
) -> tuple[PhysicalValidationSession, tuple[PhysicalValidationSessionItem, ...]]:
    """Freeze a deterministic optional sample without any live provider access."""

    if not 1 <= target_count <= 100:
        raise ValueError("target_count must be 1..100")
    if sampling_strategy != "stratified":
        raise ValueError("only the stratified sampling strategy is currently supported")
    timestamp = started_at or datetime.now(tz=UTC)
    if timestamp.tzinfo is None:
        raise ValueError("started_at must be timezone-aware")
    suggestions = PhysicalVerificationSuggestionSampler().suggest_stratified(
        candidates,
        physical_store_id=physical_store_id,
        limit=target_count,
    )
    if not suggestions:
        raise ValueError("no persisted digital candidates are available for this store")

    session_id = uuid4().hex
    items: list[PhysicalValidationSessionItem] = []
    for ordinal, suggestion in enumerate(suggestions, start=1):
        frozen_candidates = _frozen_candidates_for_suggestion(
            suggestion.gtin,
            suggestion.product_name,
            candidates,
        )
        if not frozen_candidates:
            raise ValueError("suggestion has no immutable digital evidence")
        items.append(
            PhysicalValidationSessionItem(
                id=uuid4().hex,
                session_id=session_id,
                ordinal=ordinal,
                stratum=suggestion.stratum,
                target_gtin=suggestion.gtin,
                target_product_name=suggestion.product_name,
                target_brand=suggestion.brand,
                target_category=suggestion.category,
                target_package_description=suggestion.package_description,
                target_product_id=suggestion.product_id,
                target_source_provider=suggestion.source_provider,
                target_grocery_context_id=suggestion.grocery_context_id,
                target_sale_model=suggestion.sale_model,
                identifier_status=(
                    SessionItemIdentifierStatus.NOT_REQUIRED_WEIGHT
                    if suggestion.sale_model
                    in {
                        SaleModel.SOLD_BY_WEIGHT,
                        SaleModel.VARIABLE_WEIGHT_PACKAGE,
                    }
                    else SessionItemIdentifierStatus.KNOWN_GTIN
                    if suggestion.gtin is not None
                    else SessionItemIdentifierStatus.UNKNOWN_GTIN
                ),
                reasons=suggestion.reasons,
                candidate_set_sha256=digital_candidate_set_sha256(frozen_candidates),
                candidates=frozen_candidates,
            )
        )
    item_tuple = tuple(items)
    validation_session = PhysicalValidationSession(
        id=session_id,
        physical_store_id=physical_store_id,
        chain=chain,
        store_name=store_name,
        blind_capture=blind_capture,
        target_count=target_count,
        sampling_strategy=sampling_strategy,
        notes=notes,
        suggestion_set_sha256=validation_session_suggestion_sha256(item_tuple),
        started_at=timestamp,
    )
    return validation_session, item_tuple


__all__ = ["build_physical_validation_session"]
