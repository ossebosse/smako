from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    PriceContextType,
    StoreContextRelationType,
    StoreIdentityMatchConfidence,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.services.closed_provider_cache import load_closed_provider_cache
from grocery_data.app.storage.models import (
    PhysicalStoreModel,
    ProviderStoreIdentityMappingModel,
    StoreContextLinkModel,
)

_STRONG_CONFIDENCE = frozenset(
    {
        StoreIdentityMatchConfidence.EXACT_ID.value,
        StoreIdentityMatchConfidence.EXACT_ADDRESS.value,
        StoreIdentityMatchConfidence.EXACT_NAME_AND_POSTAL.value,
        StoreIdentityMatchConfidence.STRONG_GEO.value,
    }
)


class ClosedPrimatProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    chain: Chain
    coverage: CoverageLevel
    price_context: PriceContextType
    provider_store_id: str = Field(min_length=1, max_length=255)
    source_channel: Literal["catalog"]
    source_observed_at: datetime
    source_provider: Literal["primat"]
    source_snapshot_id: str = Field(min_length=1, max_length=255)
    store_id: str = Field(min_length=1, max_length=255)

    @field_validator("source_observed_at")
    @classmethod
    def require_aware_observation(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("closed Primat observation timestamp must be timezone-aware")
        return value.astimezone(UTC)


class ClosedPrimatStoreEvidence(BaseModel):
    """Only identity and freshness fields needed to refresh an existing link."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    store_id: str = Field(min_length=1, max_length=255)
    chain: Chain
    source_store_id: str = Field(min_length=1, max_length=255)
    physical_store_external_id: str = Field(min_length=1, max_length=255)
    coverage: CoverageLevel
    tier: CoverageLevel
    price_context_type: PriceContextType
    source_provenance: ClosedPrimatProvenance

    @model_validator(mode="after")
    def require_exact_closed_identity(self) -> ClosedPrimatStoreEvidence:
        provenance = self.source_provenance
        if not is_complete_catalog_coverage(self.coverage):
            raise ValueError("closed Primat context lacks complete catalog coverage")
        if (
            self.tier != self.coverage
            or self.store_id != f"{self.chain.value}:{self.source_store_id}"
            or self.source_store_id != self.physical_store_external_id
            or provenance.chain != self.chain
            or provenance.store_id != self.store_id
            or provenance.provider_store_id != self.source_store_id
            or provenance.coverage != self.coverage
            or provenance.price_context != self.price_context_type
        ):
            raise ValueError("closed Primat store identity is internally inconsistent")
        return self


class ClosedProviderContextActivationItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    physical_store_id: str
    grocery_context_id: str | None = None
    provider_store_id: str
    status: Literal["activated", "rejected"]
    reason: str | None = None
    snapshot_id: str | None = None
    observed_at: datetime | None = None


class ClosedProviderContextActivationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["activated", "partially_activated", "rejected"]
    cache_stores: int = Field(ge=1)
    activated: int = Field(ge=0)
    rejected: int = Field(ge=0)
    snapshot_ids: tuple[str, ...] = ()
    items: tuple[ClosedProviderContextActivationItem, ...]
    provider_requests: int = 0
    mappings_created: int = 0


class _ActivationRejected(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _validate_product_scope(
    products: tuple[dict[str, Any], ...],
    stores: dict[str, ClosedPrimatStoreEvidence],
) -> None:
    represented: set[str] = set()
    for row in products:
        try:
            store_id = str(row["store_id"])
            chain = Chain(str(row["chain"]))
            provenance = ClosedPrimatProvenance.model_validate(row["source_provenance"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("closed Primat product provenance is invalid") from exc
        store = stores.get(store_id)
        if store is None:
            raise ValueError("closed Primat product references an unknown store scope")
        if (
            chain != store.chain
            or provenance.chain != store.chain
            or provenance.store_id != store.store_id
            or provenance.provider_store_id != store.source_store_id
            or provenance.source_snapshot_id
            != store.source_provenance.source_snapshot_id
            or provenance.source_observed_at
            != store.source_provenance.source_observed_at
            or provenance.coverage != store.coverage
            or provenance.price_context != store.price_context_type
        ):
            raise ValueError("closed Primat product scope conflicts with store evidence")
        represented.add(store_id)
    if represented != set(stores):
        raise ValueError("closed Primat cache has no products for one store scope")


def _store_evidence(path: Path) -> tuple[ClosedPrimatStoreEvidence, ...]:
    document, _size, _resolved = load_closed_provider_cache(path)
    stores: list[ClosedPrimatStoreEvidence] = []
    try:
        stores = [ClosedPrimatStoreEvidence.model_validate(row) for row in document.stores]
    except ValueError as exc:
        raise ValueError("closed Primat store evidence is invalid") from exc
    by_store_id = {row.store_id: row for row in stores}
    identity_keys = {
        (row.chain.value, row.source_store_id, row.physical_store_external_id)
        for row in stores
    }
    if len(by_store_id) != len(stores) or len(identity_keys) != len(stores):
        raise ValueError("closed Primat cache contains ambiguous store identities")
    oldest_observation = min(
        store.source_provenance.source_observed_at for store in stores
    )
    if document.captured_at != oldest_observation:
        raise ValueError("closed Primat cache envelope is not keyed to its oldest context")
    _validate_product_scope(document.products, by_store_id)
    return tuple(stores)


def _resolve_one(
    session: Session,
    evidence: ClosedPrimatStoreEvidence,
) -> tuple[PhysicalStoreModel, StoreContextLinkModel]:
    physical_rows = session.scalars(
        select(PhysicalStoreModel).where(
            PhysicalStoreModel.chain == evidence.chain.value,
            PhysicalStoreModel.external_store_id == evidence.physical_store_external_id,
            PhysicalStoreModel.is_active.is_(True),
        )
    ).all()
    if len(physical_rows) != 1:
        raise _ActivationRejected("physical_identity_not_exact")
    physical = physical_rows[0]

    mappings = session.scalars(
        select(ProviderStoreIdentityMappingModel).where(
            ProviderStoreIdentityMappingModel.physical_store_id == physical.id,
            ProviderStoreIdentityMappingModel.provider == SourceProvider.PRIMAT.value,
            ProviderStoreIdentityMappingModel.provider_store_id
            == evidence.source_store_id,
            ProviderStoreIdentityMappingModel.status == "verified",
            ProviderStoreIdentityMappingModel.is_active.is_(True),
        )
    ).all()
    if len(mappings) != 1:
        raise _ActivationRejected("verified_mapping_not_exact")
    mapping = mappings[0]
    if (
        mapping.confidence not in _STRONG_CONFIDENCE
        or not mapping.provider_context_id
        or not mapping.provider_context_id.startswith("primat:")
        or not mapping.verified_identity_fingerprint
        or mapping.drift_detected_at is not None
    ):
        raise _ActivationRejected("verified_mapping_not_strong")

    links = session.scalars(
        select(StoreContextLinkModel).where(
            StoreContextLinkModel.physical_store_id == physical.id,
            StoreContextLinkModel.source_provider == SourceProvider.PRIMAT.value,
            StoreContextLinkModel.grocery_context_id == mapping.provider_context_id,
            StoreContextLinkModel.source_channel == SourceChannel.CATALOG.value,
            StoreContextLinkModel.is_active.is_(True),
        )
    ).all()
    if len(links) != 1:
        raise _ActivationRejected("catalog_link_not_exact")
    link = links[0]
    if (
        link.relation_type
        != StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT.value
        or link.confidence != Confidence.EXACT.value
        or link.price_context_type != evidence.price_context_type.value
    ):
        raise _ActivationRejected("catalog_link_evidence_mismatch")

    return physical, link


def _activate_one(
    session: Session,
    evidence: ClosedPrimatStoreEvidence,
) -> tuple[PhysicalStoreModel, StoreContextLinkModel]:
    physical, link = _resolve_one(session, evidence)

    return _apply_one(session, evidence, physical, link)


def _apply_one(
    session: Session,
    evidence: ClosedPrimatStoreEvidence,
    physical: PhysicalStoreModel,
    link: StoreContextLinkModel,
) -> tuple[PhysicalStoreModel, StoreContextLinkModel]:
    """Apply already-resolved evidence inside the caller's transaction."""

    link.snapshot_id = evidence.source_provenance.source_snapshot_id
    link.observed_at = evidence.source_provenance.source_observed_at
    link.coverage = evidence.coverage.value
    link.basket_eligible = True
    link.offers_only = False
    session.flush()
    return physical, link


def validate_closed_primat_context_links(
    session: Session,
    cache_path: Path,
) -> ClosedProviderContextActivationReport:
    """Validate every cache identity without changing persisted context state."""

    stores = _store_evidence(cache_path)
    items: list[ClosedProviderContextActivationItem] = []
    snapshot_ids: set[str] = set()
    for evidence in stores:
        try:
            physical, link = _resolve_one(session, evidence)
        except _ActivationRejected as exc:
            items.append(
                ClosedProviderContextActivationItem(
                    physical_store_id=f"physical:{evidence.chain.value}:unresolved",
                    provider_store_id=evidence.source_store_id,
                    status="rejected",
                    reason=exc.reason,
                )
            )
            continue
        snapshot_id = evidence.source_provenance.source_snapshot_id
        snapshot_ids.add(snapshot_id)
        items.append(
            ClosedProviderContextActivationItem(
                physical_store_id=physical.id,
                grocery_context_id=link.grocery_context_id,
                provider_store_id=evidence.source_store_id,
                status="activated",
                snapshot_id=snapshot_id,
                observed_at=evidence.source_provenance.source_observed_at,
            )
        )
    activated = sum(item.status == "activated" for item in items)
    rejected = len(items) - activated
    status: Literal["activated", "partially_activated", "rejected"]
    if activated == len(items):
        status = "activated"
    elif activated:
        status = "partially_activated"
    else:
        status = "rejected"
    return ClosedProviderContextActivationReport(
        status=status,
        cache_stores=len(stores),
        activated=activated,
        rejected=rejected,
        snapshot_ids=tuple(sorted(snapshot_ids)),
        items=tuple(items),
    )


def activate_closed_primat_context_links(
    session: Session,
    cache_path: Path,
    *,
    require_complete: bool = False,
) -> ClosedProviderContextActivationReport:
    """Refresh only pre-existing exact Primat links from a closed local cache.

    This function has no provider or transport dependency. A rejected cache
    store is isolated in a savepoint; it can never create a physical store,
    identity mapping, or context link.
    """

    stores = _store_evidence(cache_path)
    if require_complete:
        # Managed refresh publishes one cache as one city-scoped unit. Resolve
        # every identity before the first write and avoid per-row savepoints:
        # on SQLite, releasing the outermost SAVEPOINT can otherwise persist a
        # successful early row even when the surrounding Session later rolls
        # back after a partial report.
        resolved: list[
            tuple[
                ClosedPrimatStoreEvidence,
                PhysicalStoreModel,
                StoreContextLinkModel,
            ]
        ] = []
        for evidence in stores:
            try:
                physical, link = _resolve_one(session, evidence)
            except _ActivationRejected as exc:
                raise ValueError(
                    "complete closed Primat context activation was rejected"
                ) from exc
            resolved.append((evidence, physical, link))

        items: list[ClosedProviderContextActivationItem] = []
        snapshot_ids: set[str] = set()
        for evidence, physical, link in resolved:
            physical, link = _apply_one(session, evidence, physical, link)
            snapshot_ids.add(str(link.snapshot_id))
            items.append(
                ClosedProviderContextActivationItem(
                    physical_store_id=physical.id,
                    grocery_context_id=link.grocery_context_id,
                    provider_store_id=evidence.source_store_id,
                    status="activated",
                    snapshot_id=link.snapshot_id,
                    observed_at=link.observed_at,
                )
            )
        return ClosedProviderContextActivationReport(
            status="activated",
            cache_stores=len(stores),
            activated=len(stores),
            rejected=0,
            snapshot_ids=tuple(sorted(snapshot_ids)),
            items=tuple(items),
        )

    items: list[ClosedProviderContextActivationItem] = []
    snapshot_ids: set[str] = set()
    for evidence in stores:
        try:
            with session.begin_nested():
                physical, link = _activate_one(session, evidence)
        except _ActivationRejected as exc:
            items.append(
                ClosedProviderContextActivationItem(
                    physical_store_id=f"physical:{evidence.chain.value}:unresolved",
                    provider_store_id=evidence.source_store_id,
                    status="rejected",
                    reason=exc.reason,
                )
            )
            continue
        snapshot_ids.add(str(link.snapshot_id))
        items.append(
            ClosedProviderContextActivationItem(
                physical_store_id=physical.id,
                grocery_context_id=link.grocery_context_id,
                provider_store_id=evidence.source_store_id,
                status="activated",
                snapshot_id=link.snapshot_id,
                observed_at=link.observed_at,
            )
        )
    activated = sum(item.status == "activated" for item in items)
    rejected = len(items) - activated
    status: Literal["activated", "partially_activated", "rejected"]
    if activated == len(items):
        status = "activated"
    elif activated:
        status = "partially_activated"
    else:
        status = "rejected"
    return ClosedProviderContextActivationReport(
        status=status,
        cache_stores=len(stores),
        activated=activated,
        rejected=rejected,
        snapshot_ids=tuple(sorted(snapshot_ids)),
        items=tuple(items),
    )


__all__ = [
    "ClosedProviderContextActivationItem",
    "ClosedProviderContextActivationReport",
    "activate_closed_primat_context_links",
    "validate_closed_primat_context_links",
]
