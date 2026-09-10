from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.enums import (
    Chain,
    CoverageLevel,
    PriceContextState,
    PriceContextType,
    ProviderStoreMappingStatus,
    SnapshotState,
    StoreIdentityMatchConfidence,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.source_strategy import SourceProvider, source_strategy_for
from grocery_data.app.services.store_coverage import ContextCoverageItem, StoreCoverageAuditor
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    ProviderStoreIdentityMappingModel,
    SourceProductModel,
    StoreModel,
)

_STRONG_EXTERNAL_CONFIDENCE = frozenset(
    {
        StoreIdentityMatchConfidence.EXACT_ID.value,
        StoreIdentityMatchConfidence.EXACT_ADDRESS.value,
        StoreIdentityMatchConfidence.EXACT_NAME_AND_POSTAL.value,
        StoreIdentityMatchConfidence.STRONG_GEO.value,
    }
)


class PriceContextMappingEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    status: str
    confidence: str
    provider_context_id: str | None = None
    candidate_context_id: str | None = None
    evidence: str | None = None
    verified_at: datetime | None = None
    last_checked_at: datetime
    drift_detected_at: datetime | None = None


class PriceContextAuditItem(BaseModel):
    """Closed explanation for exactly one active physical store."""

    model_config = ConfigDict(frozen=True)

    physical_store_id: str
    chain: Chain
    name: str
    address: str | None = None
    postal_code: str | None = None
    physical_status: Literal["active"] = "active"
    state: PriceContextState
    price_source: str | None = None
    grocery_context_id: str | None = None
    context_name: str | None = None
    context_scope: Literal[
        "store_specific",
        "regional",
        "regional_online",
        "none",
    ] = "none"
    coverage: str | None = None
    snapshot_id: str | None = None
    observed_at: datetime | None = None
    age_hours: float | None = None
    fresh: bool = False
    basket_eligible: bool = False
    reason: str
    mappings: tuple[PriceContextMappingEvidence, ...] = ()
    contexts: tuple[ContextCoverageItem, ...] = ()

    @model_validator(mode="after")
    def validate_closed_state(self) -> PriceContextAuditItem:
        full_states = {
            PriceContextState.OWN_FULL_CONTEXT,
            PriceContextState.EXTERNAL_FULL_CONTEXT,
        }
        offer_states = {
            PriceContextState.OWN_OFFERS_ONLY,
            PriceContextState.REGIONAL_OFFERS_ONLY,
        }
        if self.state in full_states:
            if not (
                self.basket_eligible
                and self.fresh
                and self.price_source
                and self.grocery_context_id
                and self.snapshot_id
            ):
                raise ValueError("full context state requires fresh basket-eligible provenance")
        elif self.basket_eligible:
            raise ValueError("only full context states may be basket eligible")
        if self.state in offer_states and not self.fresh:
            raise ValueError("offer-only state requires fresh offer evidence")
        if (
            self.state == PriceContextState.OWN_FULL_CONTEXT
            and self.price_source != SourceProvider.OWN.value
        ):
            raise ValueError("OWN full context must use OWN provenance")
        if self.state == PriceContextState.EXTERNAL_FULL_CONTEXT and self.price_source in {
            None,
            SourceProvider.OWN.value,
        }:
            raise ValueError("external full context must use external provenance")
        if self.state == PriceContextState.REGIONAL_OFFERS_ONLY:
            if self.context_scope != "regional":
                raise ValueError("regional offers must retain regional scope")
        elif self.context_scope == "regional" and self.state != PriceContextState.STALE_CONTEXT:
            raise ValueError("regional scope is exclusive to regional or stale offer evidence")
        if self.context_scope == "regional_online" and self.state not in {
            *full_states,
            PriceContextState.STALE_CONTEXT,
        }:
            raise ValueError("regional online scope requires full or stale catalog evidence")
        return self


class ChainPriceContextSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    physical_stores: int = Field(ge=0)
    explained_stores: int = Field(ge=0)
    full_basket_contexts: int = Field(ge=0)
    offers_only: int = Field(ge=0)
    stale: int = Field(ge=0)
    mapping_unresolved: int = Field(ge=0)
    no_price_context: int = Field(ge=0)
    state_counts: dict[str, int]
    chain_reason: str | None = None
    stores: tuple[PriceContextAuditItem, ...]


class PriceContextAuditReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str
    generated_at: datetime
    max_price_age_hours: float = Field(gt=0)
    physical_stores: int = Field(ge=0)
    explained_states: int = Field(ge=0)
    unknown: int = Field(ge=0)
    basket_capable: int = Field(ge=0)
    offers_only: int = Field(ge=0)
    stale: int = Field(ge=0)
    mapping_unresolved: int = Field(ge=0)
    no_price_context: int = Field(ge=0)
    state_counts: dict[str, int]
    chains: dict[str, ChainPriceContextSummary]
    live_provider_requests: Literal[0] = 0
    physical_validation_required: Literal[False] = False

    @model_validator(mode="after")
    def validate_complete_explanation(self) -> PriceContextAuditReport:
        items = [store for chain in self.chains.values() for store in chain.stores]
        ids = [store.physical_store_id for store in items]
        if len(ids) != len(set(ids)):
            raise ValueError("each physical store must appear exactly once")
        if len(items) != self.physical_stores:
            raise ValueError("physical store total must equal the closed state rows")
        if self.explained_states != self.physical_stores or self.unknown != 0:
            raise ValueError("every physical store must have one explained state")
        if sum(self.state_counts.values()) != self.physical_stores:
            raise ValueError("state counts must cover every physical store exactly once")
        return self


class _RegionalOfferEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    grocery_context_id: str
    context_name: str
    coverage: CoverageLevel
    snapshot_id: str
    observed_at: datetime
    age_hours: float
    stale: bool


class PriceContextAuditor:
    """Explain price-context eligibility for every active physical site.

    The audit is read-only.  It consumes promoted local snapshots, persisted
    provider mappings and persisted context links; it never calls a chain or
    external provider.
    """

    def __init__(self, session: Session, *, max_price_age_hours: float = 48.0) -> None:
        if max_price_age_hours <= 0:
            raise ValueError("max_price_age_hours must be greater than zero")
        self.session = session
        self.max_price_age_hours = max_price_age_hours

    def audit(self, city: str, *, now: datetime | None = None) -> PriceContextAuditReport:
        city_key = city.strip()
        if not city_key:
            raise ValueError("city must not be blank")
        generated_at = now or datetime.now(tz=UTC)
        if generated_at.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        generated_at = generated_at.astimezone(UTC)

        coverage = StoreCoverageAuditor(
            self.session,
            max_price_age_hours=self.max_price_age_hours,
        ).audit(city_key, now=generated_at)
        coverage_by_id = {
            store.physical_store_id: store
            for chain in coverage.chains.values()
            for store in chain.stores
            if store.registry_known and store.physical_active
        }
        physical = list(
            self.session.scalars(
                select(PhysicalStoreModel)
                .where(
                    PhysicalStoreModel.is_active.is_(True),
                    func.lower(func.trim(PhysicalStoreModel.city)) == city_key.casefold(),
                )
                .order_by(
                    PhysicalStoreModel.chain,
                    PhysicalStoreModel.name,
                    PhysicalStoreModel.id,
                )
            )
        )
        physical_ids = [row.id for row in physical]
        mappings: dict[str, list[ProviderStoreIdentityMappingModel]] = defaultdict(list)
        if physical_ids:
            for row in self.session.scalars(
                select(ProviderStoreIdentityMappingModel)
                .where(
                    ProviderStoreIdentityMappingModel.physical_store_id.in_(physical_ids),
                    ProviderStoreIdentityMappingModel.is_active.is_(True),
                )
                .order_by(
                    ProviderStoreIdentityMappingModel.physical_store_id,
                    ProviderStoreIdentityMappingModel.provider,
                )
            ):
                mappings[row.physical_store_id].append(row)

        regional = self._regional_lidl_offer(generated_at)
        by_chain: dict[Chain, list[PriceContextAuditItem]] = defaultdict(list)
        for row in physical:
            coverage_item = coverage_by_id.get(row.id)
            contexts = coverage_item.contexts if coverage_item is not None else ()
            item = self._classify(
                row,
                contexts=contexts,
                mappings=mappings[row.id],
                regional_lidl=regional,
                now=generated_at,
            )
            by_chain[item.chain].append(item)

        chain_reports: dict[str, ChainPriceContextSummary] = {}
        all_items: list[PriceContextAuditItem] = []
        for chain in Chain:
            stores = tuple(
                sorted(by_chain[chain], key=lambda row: (row.name, row.physical_store_id))
            )
            all_items.extend(stores)
            counts = Counter(store.state.value for store in stores)
            chain_reports[chain.value] = ChainPriceContextSummary(
                chain=chain,
                physical_stores=len(stores),
                explained_stores=len(stores),
                full_basket_contexts=sum(store.basket_eligible for store in stores),
                offers_only=sum(
                    store.state
                    in {
                        PriceContextState.OWN_OFFERS_ONLY,
                        PriceContextState.REGIONAL_OFFERS_ONLY,
                    }
                    for store in stores
                ),
                stale=counts[PriceContextState.STALE_CONTEXT.value],
                mapping_unresolved=counts[PriceContextState.MAPPING_UNRESOLVED.value],
                no_price_context=counts[PriceContextState.NO_PRICE_CONTEXT.value],
                state_counts=dict(sorted(counts.items())),
                chain_reason=(
                    f"NO_{city_key.upper()}_CONTEXT: no active physical stores registered "
                    f"for {city_key}"
                    if not stores and chain == Chain.CITY_GROSS
                    else None
                ),
                stores=stores,
            )

        counts = Counter(store.state.value for store in all_items)
        return PriceContextAuditReport(
            city=city_key,
            generated_at=generated_at,
            max_price_age_hours=self.max_price_age_hours,
            physical_stores=len(all_items),
            explained_states=len(all_items),
            unknown=0,
            basket_capable=sum(store.basket_eligible for store in all_items),
            offers_only=sum(
                store.state
                in {
                    PriceContextState.OWN_OFFERS_ONLY,
                    PriceContextState.REGIONAL_OFFERS_ONLY,
                }
                for store in all_items
            ),
            stale=counts[PriceContextState.STALE_CONTEXT.value],
            mapping_unresolved=counts[PriceContextState.MAPPING_UNRESOLVED.value],
            no_price_context=counts[PriceContextState.NO_PRICE_CONTEXT.value],
            state_counts=dict(sorted(counts.items())),
            chains=chain_reports,
        )

    def _classify(
        self,
        physical: PhysicalStoreModel,
        *,
        contexts: tuple[ContextCoverageItem, ...],
        mappings: list[ProviderStoreIdentityMappingModel],
        regional_lidl: _RegionalOfferEvidence | None,
        now: datetime,
    ) -> PriceContextAuditItem:
        chain = Chain(physical.chain)
        mapping_evidence = tuple(self._mapping_evidence(row) for row in mappings)
        mapping_problem = self._external_mapping_problem(chain, contexts, mappings)

        own_full = self._newest(
            context
            for context in contexts
            if self._is_fresh_full(context) and context.source_provider == SourceProvider.OWN.value
        )
        if own_full is not None:
            return self._from_context(
                physical,
                own_full,
                state=PriceContextState.OWN_FULL_CONTEXT,
                reason="fresh promoted OWN full catalog is eligible for basket pricing",
                mappings=mapping_evidence,
                all_contexts=contexts,
                now=now,
            )

        external_full = self._newest(
            context
            for context in contexts
            if self._is_fresh_full(context)
            and context.source_provider != SourceProvider.OWN.value
            and self._external_mapping_verified(context, mappings)
        )
        if external_full is not None:
            return self._from_context(
                physical,
                external_full,
                state=PriceContextState.EXTERNAL_FULL_CONTEXT,
                reason="fresh full external context has a persisted strong verified identity",
                mappings=mapping_evidence,
                all_contexts=contexts,
                now=now,
            )

        own_offer = self._newest(
            context for context in contexts if self._is_fresh_own_nonbasket(context)
        )
        if own_offer is not None:
            reason = (
                "fresh store-specific OWN offers are available but never basket eligible"
                if own_offer.coverage == CoverageLevel.OFFERS_ONLY.value
                else "fresh partial OWN context is constrained to the non-basket offers role"
            )
            if mapping_problem is not None:
                reason += "; the configured external basket mapping remains unresolved"
            return self._from_context(
                physical,
                own_offer,
                state=PriceContextState.OWN_OFFERS_ONLY,
                reason=reason,
                mappings=mapping_evidence,
                all_contexts=contexts,
                now=now,
            )

        if chain == Chain.LIDL and regional_lidl is not None and not regional_lidl.stale:
            return PriceContextAuditItem(
                physical_store_id=physical.id,
                chain=chain,
                name=physical.name,
                address=physical.address,
                postal_code=physical.postal_code,
                state=PriceContextState.REGIONAL_OFFERS_ONLY,
                price_source=SourceProvider.OWN.value,
                grocery_context_id=regional_lidl.grocery_context_id,
                context_name=regional_lidl.context_name,
                context_scope="regional",
                coverage=regional_lidl.coverage.value,
                snapshot_id=regional_lidl.snapshot_id,
                observed_at=regional_lidl.observed_at,
                age_hours=regional_lidl.age_hours,
                fresh=True,
                basket_eligible=False,
                reason=(
                    "fresh Lidl public regional offers apply to the area but are not assigned "
                    "as a store-specific price context"
                ),
                mappings=mapping_evidence,
                contexts=contexts,
            )

        if chain == Chain.LIDL and regional_lidl is not None and regional_lidl.stale:
            return PriceContextAuditItem(
                physical_store_id=physical.id,
                chain=chain,
                name=physical.name,
                address=physical.address,
                postal_code=physical.postal_code,
                state=PriceContextState.STALE_CONTEXT,
                price_source=SourceProvider.OWN.value,
                grocery_context_id=regional_lidl.grocery_context_id,
                context_name=regional_lidl.context_name,
                coverage=regional_lidl.coverage.value,
                snapshot_id=regional_lidl.snapshot_id,
                observed_at=regional_lidl.observed_at,
                age_hours=regional_lidl.age_hours,
                context_scope="regional",
                reason=(
                    "Lidl regional offer snapshot exists but exceeds the freshness window; "
                    "it remains unassigned to either physical store"
                ),
                mappings=mapping_evidence,
                contexts=contexts,
            )

        primary_provider = source_strategy_for(chain).primary_source.provider.value
        stale_primary = self._newest(
            context
            for context in contexts
            if context.active
            and context.stale
            and context.source_provider == primary_provider
            and (
                primary_provider == SourceProvider.OWN.value
                or self._external_mapping_is_verified_or_lkg(context, mappings)
            )
        )
        if stale_primary is not None:
            return self._from_context(
                physical,
                stale_primary,
                state=PriceContextState.STALE_CONTEXT,
                reason="verified primary/LKG price context exceeds the freshness window",
                mappings=mapping_evidence,
                all_contexts=contexts,
                now=now,
            )

        if mapping_problem is not None:
            return PriceContextAuditItem(
                physical_store_id=physical.id,
                chain=chain,
                name=physical.name,
                address=physical.address,
                postal_code=physical.postal_code,
                state=PriceContextState.MAPPING_UNRESOLVED,
                reason=mapping_problem,
                mappings=mapping_evidence,
                contexts=contexts,
            )

        external_nonbasket = self._newest(
            context
            for context in contexts
            if context.active
            and not context.stale
            and not context.basket_eligible
            and context.source_provider != SourceProvider.OWN.value
            and self._external_mapping_verified(context, mappings)
        )
        stale_context = self._newest(
            context for context in contexts if context.active and context.stale
        )
        if stale_context is not None:
            reason = "linked price evidence exceeds the configured freshness window"
            if external_nonbasket is not None:
                reason = (
                    "verified external identity is fresh but its "
                    f"{external_nonbasket.coverage or 'unknown'} coverage is not basket "
                    "eligible; the remaining linked price evidence is stale"
                )
            return self._from_context(
                physical,
                stale_context,
                state=PriceContextState.STALE_CONTEXT,
                reason=reason,
                mappings=mapping_evidence,
                all_contexts=contexts,
                now=now,
            )

        if external_nonbasket is not None:
            return PriceContextAuditItem(
                physical_store_id=physical.id,
                chain=chain,
                name=physical.name,
                address=physical.address,
                postal_code=physical.postal_code,
                state=PriceContextState.NO_PRICE_CONTEXT,
                price_source=external_nonbasket.source_provider,
                grocery_context_id=external_nonbasket.grocery_context_id,
                context_name=external_nonbasket.context_name,
                context_scope="store_specific",
                coverage=external_nonbasket.coverage,
                snapshot_id=external_nonbasket.snapshot_id,
                observed_at=external_nonbasket.observed_at,
                age_hours=self._age_hours(external_nonbasket.observed_at, now),
                fresh=True,
                basket_eligible=False,
                reason=(
                    "verified external store identity has only "
                    f"{external_nonbasket.coverage or 'unknown'} non-basket coverage"
                ),
                mappings=mapping_evidence,
                contexts=contexts,
            )

        partial = self._newest(
            context
            for context in contexts
            if context.active and context.coverage == CoverageLevel.PARTIAL_CATALOG.value
        )
        reason = (
            "OWN partial context has no current replayable price snapshot and is not basket eligible"
            if partial is not None
            else "no active fresh store-specific price context is available"
        )
        return PriceContextAuditItem(
            physical_store_id=physical.id,
            chain=chain,
            name=physical.name,
            address=physical.address,
            postal_code=physical.postal_code,
            state=PriceContextState.NO_PRICE_CONTEXT,
            reason=reason,
            mappings=mapping_evidence,
            contexts=contexts,
        )

    @staticmethod
    def _is_fresh_full(context: ContextCoverageItem) -> bool:
        return bool(
            context.active
            and not context.stale
            and context.basket_eligible
            and context.snapshot_id
            and context.observed_at
            and context.coverage is not None
            and is_complete_catalog_coverage(context.coverage)
        )

    @staticmethod
    def _is_fresh_own_nonbasket(context: ContextCoverageItem) -> bool:
        return bool(
            context.active
            and not context.stale
            and not context.basket_eligible
            and context.source_provider == SourceProvider.OWN.value
            and context.price_context_type != PriceContextType.REGIONAL.value
            and context.snapshot_id
            and context.observed_at
            and (
                context.offers_only
                or context.coverage
                in {
                    CoverageLevel.OFFERS_ONLY.value,
                    CoverageLevel.PARTIAL_CATALOG.value,
                }
            )
        )

    @staticmethod
    def _external_mapping_verified(
        context: ContextCoverageItem,
        mappings: list[ProviderStoreIdentityMappingModel],
    ) -> bool:
        return any(
            row.is_active
            and row.provider == context.source_provider
            and row.status == ProviderStoreMappingStatus.VERIFIED.value
            and row.confidence in _STRONG_EXTERNAL_CONFIDENCE
            and row.provider_context_id == context.grocery_context_id
            for row in mappings
        )

    @staticmethod
    def _external_mapping_is_verified_or_lkg(
        context: ContextCoverageItem,
        mappings: list[ProviderStoreIdentityMappingModel],
    ) -> bool:
        return any(
            row.is_active
            and row.provider == context.source_provider
            and row.status
            in {
                ProviderStoreMappingStatus.VERIFIED.value,
                ProviderStoreMappingStatus.MAPPING_DRIFT.value,
            }
            and row.confidence in _STRONG_EXTERNAL_CONFIDENCE
            and row.provider_context_id == context.grocery_context_id
            and row.verified_at is not None
            for row in mappings
        )

    @staticmethod
    def _external_mapping_problem(
        chain: Chain,
        contexts: tuple[ContextCoverageItem, ...],
        mappings: list[ProviderStoreIdentityMappingModel],
    ) -> str | None:
        primary = source_strategy_for(chain).primary_source.provider
        if primary == SourceProvider.OWN:
            return None
        rows = [row for row in mappings if row.is_active and row.provider == primary.value]
        verified = any(
            row.status == ProviderStoreMappingStatus.VERIFIED.value
            and row.confidence in _STRONG_EXTERNAL_CONFIDENCE
            and row.provider_context_id
            for row in rows
        )
        if verified:
            return None
        if any(row.status == ProviderStoreMappingStatus.MAPPING_DRIFT.value for row in rows):
            return "external store identity drift detected; LKG mapping retained for review"
        if rows:
            return "external provider mapping has no high-confidence unique identity match"
        if any(context.active and context.source_provider == primary.value for context in contexts):
            return "external context link lacks persisted verified mapping lineage"
        return "configured external basket provider has no verified physical-store mapping"

    @staticmethod
    def _newest(values: Iterable[ContextCoverageItem]) -> ContextCoverageItem | None:
        rows = list(values)
        if not rows:
            return None
        return max(
            rows,
            key=lambda row: (
                row.observed_at or datetime.min.replace(tzinfo=UTC),
                row.source_provider,
                row.grocery_context_id,
            ),
        )

    def _from_context(
        self,
        physical: PhysicalStoreModel,
        context: ContextCoverageItem,
        *,
        state: PriceContextState,
        reason: str,
        mappings: tuple[PriceContextMappingEvidence, ...],
        all_contexts: tuple[ContextCoverageItem, ...],
        now: datetime,
    ) -> PriceContextAuditItem:
        age_hours = self._age_hours(context.observed_at, now)
        context_scope = (
            "regional_online"
            if context.price_context_type == PriceContextType.ONLINE_FULFILLMENT.value
            else "store_specific"
        )
        return PriceContextAuditItem(
            physical_store_id=physical.id,
            chain=Chain(physical.chain),
            name=physical.name,
            address=physical.address,
            postal_code=physical.postal_code,
            state=state,
            price_source=context.source_provider,
            grocery_context_id=context.grocery_context_id,
            context_name=context.context_name,
            context_scope=context_scope,
            coverage=context.coverage,
            snapshot_id=context.snapshot_id,
            observed_at=context.observed_at,
            age_hours=age_hours,
            fresh=bool(context.observed_at is not None and not context.stale),
            basket_eligible=context.basket_eligible,
            reason=reason,
            mappings=mappings,
            contexts=all_contexts,
        )

    @staticmethod
    def _age_hours(observed_at: datetime | None, now: datetime) -> float | None:
        if observed_at is None:
            return None
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        return (now - observed_at.astimezone(UTC)).total_seconds() / 3600

    @staticmethod
    def _mapping_evidence(
        row: ProviderStoreIdentityMappingModel,
    ) -> PriceContextMappingEvidence:
        return PriceContextMappingEvidence(
            provider=row.provider,
            status=row.status,
            confidence=row.confidence,
            provider_context_id=row.provider_context_id,
            candidate_context_id=row.candidate_context_id,
            evidence=row.evidence,
            verified_at=row.verified_at,
            last_checked_at=row.last_checked_at,
            drift_detected_at=row.drift_detected_at,
        )

    def _regional_lidl_offer(self, now: datetime) -> _RegionalOfferEvidence | None:
        stores = list(
            self.session.scalars(
                select(StoreModel)
                .where(
                    StoreModel.chain == Chain.LIDL.value,
                    StoreModel.is_active.is_(True),
                    StoreModel.coverage == CoverageLevel.OFFERS_ONLY.value,
                    or_(
                        StoreModel.price_context_type == PriceContextType.REGIONAL.value,
                        StoreModel.external_id == "public-default-region",
                    ),
                )
                .order_by(StoreModel.id)
            )
        )
        candidates: list[_RegionalOfferEvidence] = []
        for store in stores:
            contains_store = exists(
                select(1).where(
                    SourceProductModel.catalog_snapshot_id == CatalogSnapshotModel.id,
                    SourceProductModel.store_id == store.id,
                )
            )
            snapshot = self.session.scalar(
                select(CatalogSnapshotModel)
                .where(
                    CatalogSnapshotModel.chain == Chain.LIDL.value,
                    CatalogSnapshotModel.coverage == CoverageLevel.OFFERS_ONLY.value,
                    CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
                    CatalogSnapshotModel.is_active.is_(True),
                    contains_store,
                )
                .order_by(
                    CatalogSnapshotModel.promoted_at.desc(),
                    CatalogSnapshotModel.created_at.desc(),
                    CatalogSnapshotModel.id,
                )
                .limit(1)
            )
            if snapshot is None:
                continue
            observed_at = (
                self.session.scalar(
                    select(func.min(PriceObservationModel.observed_at)).where(
                        PriceObservationModel.catalog_snapshot_id == snapshot.id,
                        PriceObservationModel.store_id == store.id,
                    )
                )
                or snapshot.created_at
            )
            age = self._age_hours(observed_at, now)
            assert age is not None
            candidates.append(
                _RegionalOfferEvidence(
                    grocery_context_id=f"own:{Chain.LIDL.value}:{store.external_id}",
                    context_name=store.name,
                    coverage=CoverageLevel.OFFERS_ONLY,
                    snapshot_id=snapshot.id,
                    observed_at=observed_at,
                    age_hours=age,
                    stale=age < -1 or age > self.max_price_age_hours,
                )
            )
        if not candidates:
            return None
        return min(candidates, key=lambda row: (row.stale, -row.observed_at.timestamp()))


__all__ = [
    "ChainPriceContextSummary",
    "PriceContextAuditItem",
    "PriceContextAuditReport",
    "PriceContextAuditor",
    "PriceContextMappingEvidence",
]
