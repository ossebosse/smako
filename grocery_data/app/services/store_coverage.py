from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.enums import (
    DEFAULT_SOURCE_CHAINS,
    Chain,
    Confidence,
    ConnectorStatus,
    CoverageLevel,
    PhysicalStoreCoverageState,
    PhysicalStoreLifecycleState,
    PriceContextType,
    SnapshotState,
    StoreContextRelationType,
    StoreDiscoveryErrorCode,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.domain.store import PhysicalStore, StoreContextLink
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
)
from grocery_data.app.storage.repositories import (
    PhysicalStoreDiscoveryHealthRepository,
    PhysicalStoreRepository,
    StoreContextLinkRepository,
)


def _normalized_text(value: str | None) -> str:
    return re.sub(r"[^0-9a-zåäö]+", " ", (value or "").casefold()).strip()


def _postal(value: str | None) -> str:
    return "".join(character for character in (value or "") if character.isdigit())


class GroceryContextEvidence(BaseModel):
    """Credential-free projection of an OWN or external federated context."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    grocery_context_id: str = Field(min_length=1, max_length=255)
    chain: Chain
    name: str = Field(min_length=1, max_length=500)
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    external_store_id: str | None = None
    physical_store_external_id: str | None = None
    price_context_type: PriceContextType | None = None
    source_provider: SourceProvider
    source_channel: SourceChannel = SourceChannel.CATALOG
    coverage: CoverageLevel | None = None
    basket_eligible: bool = False
    offers_only: bool = False
    snapshot_id: str | None = None
    observed_at: datetime | None = None
    active: bool = True
    local_store_id: str | None = None


class ExactStoreContextMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    context: GroceryContextEvidence
    relation_type: StoreContextRelationType
    confidence: Confidence
    evidence: str

    def as_link(self, physical_store_id: str, *, verified_at: datetime) -> StoreContextLink:
        return StoreContextLink(
            physical_store_id=physical_store_id,
            grocery_context_id=self.context.grocery_context_id,
            source_provider=self.context.source_provider,
            source_channel=self.context.source_channel,
            local_store_id=self.context.local_store_id,
            grocery_context_name=self.context.name,
            price_context_type=self.context.price_context_type,
            coverage=self.context.coverage,
            relation_type=self.relation_type,
            confidence=self.confidence,
            evidence=self.evidence,
            basket_eligible=self.context.basket_eligible,
            offers_only=self.context.offers_only,
            snapshot_id=self.context.snapshot_id,
            observed_at=self.context.observed_at,
            linked_at=verified_at,
            last_verified_at=verified_at,
            active=self.context.active,
        )


class ExactStoreIdentityMatcher:
    """Exact identity hooks; deliberately no fuzzy store-name fallback."""

    @staticmethod
    def external_identities(
        physical: PhysicalStore | PhysicalStoreModel,
    ) -> frozenset[str]:
        primary = getattr(physical, "external_store_id", None)
        aliases = getattr(physical, "external_store_aliases", ()) or ()
        return frozenset(
            identity for identity in (primary, *aliases) if isinstance(identity, str) and identity
        )

    @staticmethod
    def official_to_registry(
        official: PhysicalStore,
        registry: Sequence[PhysicalStoreModel],
    ) -> tuple[PhysicalStoreModel | None, str | None]:
        same_chain = [row for row in registry if row.chain == official.chain.value]
        if rows := [row for row in same_chain if row.id == official.id]:
            return rows[0], "registry_id"
        official_identities = ExactStoreIdentityMatcher.external_identities(official)
        if official_identities:
            rows = [
                row
                for row in same_chain
                if official_identities & ExactStoreIdentityMatcher.external_identities(row)
            ]
            if len(rows) == 1:
                return rows[0], "official_external_store_identity"
        address = _normalized_text(official.address)
        postal_code = _postal(official.postal_code)
        if address and postal_code:
            rows = [
                row
                for row in same_chain
                if _normalized_text(row.address) == address
                and _postal(row.postal_code) == postal_code
            ]
            if len(rows) == 1:
                return rows[0], "exact_address_postal_code"
        if official.latitude is not None and official.longitude is not None:
            rows = [
                row
                for row in same_chain
                if row.latitude == official.latitude and row.longitude == official.longitude
            ]
            if len(rows) == 1:
                return rows[0], "exact_coordinates"
        return None, None

    @staticmethod
    def physical_to_context(
        physical: PhysicalStore | PhysicalStoreModel,
        contexts: Iterable[GroceryContextEvidence],
    ) -> list[ExactStoreContextMatch]:
        matches: list[ExactStoreContextMatch] = []
        for context in contexts:
            chain = physical.chain.value if isinstance(physical.chain, Chain) else physical.chain
            if context.chain.value != chain or not context.active:
                continue
            external_ids = ExactStoreIdentityMatcher.external_identities(physical)
            if (
                context.physical_store_external_id
                and context.physical_store_external_id in external_ids
            ):
                matches.append(
                    ExactStoreContextMatch(
                        context=context,
                        relation_type=_relation_for_context(context.price_context_type),
                        confidence=Confidence.EXACT,
                        evidence="official primary/alias store identity exact match",
                    )
                )
                continue
            if (
                context.external_store_id in external_ids
                and context.price_context_type == PriceContextType.PHYSICAL_STORE
            ):
                matches.append(
                    ExactStoreContextMatch(
                        context=context,
                        relation_type=StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT,
                        confidence=Confidence.EXACT,
                        evidence="official primary/alias context identity exact match",
                    )
                )
                continue
            physical_address = _normalized_text(getattr(physical, "address", None))
            context_address = _normalized_text(context.address)
            physical_postal = _postal(getattr(physical, "postal_code", None))
            context_postal = _postal(context.postal_code)
            if (
                physical_address
                and physical_postal
                and physical_address == context_address
                and physical_postal == context_postal
            ):
                matches.append(
                    ExactStoreContextMatch(
                        context=context,
                        relation_type=_relation_for_context(context.price_context_type),
                        confidence=Confidence.HIGH,
                        evidence="official address and postal code exact match",
                    )
                )
                continue
            latitude = getattr(physical, "latitude", None)
            longitude = getattr(physical, "longitude", None)
            if (
                latitude is not None
                and longitude is not None
                and latitude == context.latitude
                and longitude == context.longitude
            ):
                matches.append(
                    ExactStoreContextMatch(
                        context=context,
                        relation_type=_relation_for_context(context.price_context_type),
                        confidence=Confidence.HIGH,
                        evidence="official coordinates exact match",
                    )
                )
        return matches


def _relation_for_context(value: PriceContextType | None) -> StoreContextRelationType:
    if value in {PriceContextType.PHYSICAL_STORE, PriceContextType.ONLINE_STORE}:
        return StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT
    if value == PriceContextType.ONLINE_FULFILLMENT:
        return StoreContextRelationType.DELIVERY_CONTEXT
    if value == PriceContextType.REGIONAL:
        return StoreContextRelationType.REGIONAL_CONTEXT
    return StoreContextRelationType.UNKNOWN


class ContextCoverageItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    grocery_context_id: str
    context_name: str | None = None
    pickup_point_external_id: str | None = None
    source_provider: str
    source_channel: str
    relation_type: str
    confidence: str
    price_context_type: str | None = None
    coverage: str | None = None
    active: bool
    basket_eligible: bool
    offers_only: bool
    stale: bool
    snapshot_id: str | None = None
    observed_at: datetime | None = None


class PhysicalStoreCoverageItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    physical_store_id: str
    chain: Chain
    external_store_id: str | None = None
    external_store_aliases: tuple[str, ...] = ()
    name: str
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    official_source: str
    registry_known: bool
    physical_active: bool
    lifecycle_state: str
    coverage_state: PhysicalStoreCoverageState
    identity_evidence: str | None = None
    contexts: tuple[ContextCoverageItem, ...] = ()
    missing_reason: str | None = None


class ChainStoreCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    official_physical_stores: int
    known_physical_stores: int
    mapped_physical_stores: int
    mapped_contexts: int
    basket_capable_contexts: int
    offers_only_contexts: int
    stale_physical_stores: int
    missing_physical_stores: int
    missing_mappings: int
    stores: tuple[PhysicalStoreCoverageItem, ...]


class StoreDiscoveryHealthItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    city: str
    status: ConnectorStatus
    complete: bool
    discovered_count: int = Field(ge=0)
    previous_count: int | None = Field(default=None, ge=0)
    observed_at: datetime
    error_code: StoreDiscoveryErrorCode | None = None


class StoreCoverageReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str
    generated_at: datetime
    official_evidence: Literal["fresh_discovery", "persisted_registry"]
    official_last_seen_at: datetime | None = None
    physical_stores: int
    known_physical_stores: int
    mapped_contexts: int
    basket_capable: int
    offers_only: int
    stale: int
    missing: int
    chains: dict[str, ChainStoreCoverage]
    discovery_health: dict[str, StoreDiscoveryHealthItem] = Field(default_factory=dict)


class StoreCoverageAuditor:
    """Reconcile official physical sites with explicit federated context links."""

    def __init__(self, session: Session, *, max_price_age_hours: float = 48.0) -> None:
        if max_price_age_hours <= 0:
            raise ValueError("max_price_age_hours must be greater than zero")
        self.session = session
        self.max_price_age_hours = max_price_age_hours

    def audit(
        self,
        city: str,
        *,
        official_stores: Sequence[PhysicalStore] | None = None,
        now: datetime | None = None,
    ) -> StoreCoverageReport:
        city_key = city.strip()
        if not city_key:
            raise ValueError("city must not be blank")
        generated_at = now or datetime.now(tz=UTC)
        if generated_at.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        generated_at = generated_at.astimezone(UTC)

        repository = PhysicalStoreRepository(self.session)
        registry = repository.list_for_city(city_key, active_only=False)
        current_official = (
            list(official_stores)
            if official_stores is not None
            else [_physical_domain(row) for row in registry if row.is_active]
        )
        official_by_chain: dict[Chain, list[PhysicalStore]] = defaultdict(list)
        registry_by_chain: dict[Chain, list[PhysicalStoreModel]] = defaultdict(list)
        for store in current_official:
            if (store.city or "").casefold().strip() == city_key.casefold():
                official_by_chain[store.chain].append(store)
        for row in registry:
            registry_by_chain[Chain(row.chain)].append(row)

        chain_reports: dict[str, ChainStoreCoverage] = {}
        for chain in DEFAULT_SOURCE_CHAINS:
            entries, matched = self._entries_for_chain(
                chain=chain,
                official=official_by_chain[chain],
                registry=registry_by_chain[chain],
                official_was_supplied=official_stores is not None,
                now=generated_at,
            )
            active_context_keys = {
                (context.source_provider, context.grocery_context_id)
                for entry in entries
                for context in entry.contexts
                if entry.physical_active and context.active and (not context.stale or context.basket_eligible)
            }
            basket_keys = {
                (context.source_provider, context.grocery_context_id)
                for entry in entries
                for context in entry.contexts
                if (
                    entry.physical_active
                    and context.active
                    and context.basket_eligible
                )
            }
            offer_keys = {
                (context.source_provider, context.grocery_context_id)
                for entry in entries
                for context in entry.contexts
                if (
                    entry.physical_active
                    and context.active
                    and not context.stale
                    and context.offers_only
                )
            }
            report = ChainStoreCoverage(
                chain=chain,
                official_physical_stores=len(official_by_chain[chain]),
                known_physical_stores=len(matched),
                mapped_physical_stores=sum(
                    item.physical_active
                    and any(context.active and (not context.stale or context.basket_eligible) for context in item.contexts)
                    for item in entries
                ),
                mapped_contexts=len(active_context_keys),
                basket_capable_contexts=len(basket_keys),
                offers_only_contexts=len(offer_keys),
                stale_physical_stores=sum(
                    item.coverage_state == PhysicalStoreCoverageState.STALE for item in entries
                ),
                missing_physical_stores=sum(
                    item.coverage_state == PhysicalStoreCoverageState.MISSING for item in entries
                ),
                missing_mappings=sum(
                    item.coverage_state
                    in {
                        PhysicalStoreCoverageState.MISSING,
                        PhysicalStoreCoverageState.NO_PRICE_CONTEXT,
                    }
                    for item in entries
                ),
                stores=tuple(entries),
            )
            chain_reports[chain.value] = report

        discovery_health = {
            row.chain: StoreDiscoveryHealthItem(
                chain=Chain(row.chain),
                city=row.city,
                status=ConnectorStatus(row.status),
                complete=row.complete,
                discovered_count=row.discovered_count,
                previous_count=row.previous_count,
                observed_at=row.observed_at,
                error_code=(
                    StoreDiscoveryErrorCode(row.error_code) if row.error_code is not None else None
                ),
            )
            for row in PhysicalStoreDiscoveryHealthRepository(self.session).list_for_city(city_key)
        }
        return StoreCoverageReport(
            city=city_key,
            generated_at=generated_at,
            official_evidence=(
                "fresh_discovery" if official_stores is not None else "persisted_registry"
            ),
            official_last_seen_at=max(
                (store.last_seen_at for store in current_official),
                default=None,
            ),
            physical_stores=sum(item.official_physical_stores for item in chain_reports.values()),
            known_physical_stores=sum(
                item.known_physical_stores for item in chain_reports.values()
            ),
            mapped_contexts=sum(item.mapped_contexts for item in chain_reports.values()),
            basket_capable=sum(item.basket_capable_contexts for item in chain_reports.values()),
            offers_only=sum(item.offers_only_contexts for item in chain_reports.values()),
            stale=sum(item.stale_physical_stores for item in chain_reports.values()),
            missing=sum(item.missing_mappings for item in chain_reports.values()),
            chains=chain_reports,
            discovery_health=discovery_health,
        )

    def _entries_for_chain(
        self,
        *,
        chain: Chain,
        official: Sequence[PhysicalStore],
        registry: Sequence[PhysicalStoreModel],
        official_was_supplied: bool,
        now: datetime,
    ) -> tuple[list[PhysicalStoreCoverageItem], set[str]]:
        result: list[PhysicalStoreCoverageItem] = []
        matched: set[str] = set()
        for source in official:
            row, identity = ExactStoreIdentityMatcher.official_to_registry(
                source,
                [candidate for candidate in registry if candidate.id not in matched],
            )
            if row is None:
                result.append(
                    PhysicalStoreCoverageItem(
                        physical_store_id=source.id,
                        chain=chain,
                        external_store_id=source.external_store_id,
                        name=source.name,
                        address=source.address,
                        postal_code=source.postal_code,
                        city=source.city,
                        official_source=source.official_source,
                        registry_known=False,
                        physical_active=source.active,
                        lifecycle_state=source.lifecycle_state.value,
                        coverage_state=PhysicalStoreCoverageState.MISSING,
                        missing_reason="official physical store is absent from registry",
                    )
                )
                continue
            matched.add(row.id)
            result.append(self._coverage_item(row, identity_evidence=identity, now=now))

        # Historical registry rows remain visible as NOT_SEEN evidence. They
        # are neither deleted nor counted as current official physical stores.
        for row in registry:
            if row.id in matched:
                continue
            item = self._coverage_item(row, identity_evidence=None, now=now)
            result.append(
                item.model_copy(
                    update={
                        "physical_active": False,
                        "lifecycle_state": PhysicalStoreLifecycleState.NOT_SEEN.value,
                        "coverage_state": PhysicalStoreCoverageState.STALE,
                        "missing_reason": (
                            "registry store not present in current official discovery"
                            if official_was_supplied
                            else "registry store retained as NOT_SEEN"
                        ),
                    }
                )
            )
        return sorted(result, key=lambda item: (item.name, item.physical_store_id)), matched

    def _coverage_item(
        self,
        physical: PhysicalStoreModel,
        *,
        identity_evidence: str | None,
        now: datetime,
    ) -> PhysicalStoreCoverageItem:
        links = StoreContextLinkRepository(self.session).list_for_physical_store(
            physical.id,
            active_only=False,
        )
        contexts = tuple(self._context_item(link, now=now) for link in links)
        active_contexts = tuple(item for item in contexts if item.active)
        if (
            not physical.is_active
            or physical.lifecycle_state == PhysicalStoreLifecycleState.NOT_SEEN.value
        ):
            state = PhysicalStoreCoverageState.STALE
            reason = "physical store is retained as NOT_SEEN"
        elif active_contexts and all(item.stale and not item.basket_eligible for item in active_contexts):
            state = PhysicalStoreCoverageState.STALE
            reason = "all linked price contexts are stale"
        elif any(item.basket_eligible for item in active_contexts):
            state = PhysicalStoreCoverageState.BASKET_CAPABLE
            reason = None
        elif any(item.offers_only for item in active_contexts):
            state = PhysicalStoreCoverageState.OFFERS_ONLY
            reason = None
        elif active_contexts:
            state = PhysicalStoreCoverageState.MAPPED
            reason = "mapped contexts are not basket eligible"
        else:
            state = PhysicalStoreCoverageState.NO_PRICE_CONTEXT
            reason = "no active price context link"
        return PhysicalStoreCoverageItem(
            physical_store_id=physical.id,
            chain=Chain(physical.chain),
            external_store_id=physical.external_store_id,
            external_store_aliases=tuple(physical.external_store_aliases or ()),
            name=physical.name,
            address=physical.address,
            postal_code=physical.postal_code,
            city=physical.city,
            official_source=physical.official_source,
            registry_known=True,
            physical_active=physical.is_active,
            lifecycle_state=physical.lifecycle_state,
            coverage_state=state,
            identity_evidence=identity_evidence,
            contexts=contexts,
            missing_reason=reason,
        )

    def _context_item(
        self,
        link: StoreContextLinkModel,
        *,
        now: datetime,
    ) -> ContextCoverageItem:
        coverage = link.coverage
        observed_at = link.observed_at
        snapshot_id = link.snapshot_id
        active = link.is_active
        basket_eligible = link.basket_eligible
        offers_only = link.offers_only or coverage == CoverageLevel.OFFERS_ONLY.value

        if link.local_store_id is not None:
            local = self.session.get(StoreModel, link.local_store_id)
            if local is None:
                active = False
                basket_eligible = False
                offers_only = False
            else:
                active = active and local.is_active
                coverage = local.coverage
                snapshot, observed_at = self._local_snapshot(local)
                snapshot_id = snapshot.id if snapshot is not None else None
                basket_eligible = bool(
                    active and snapshot is not None and is_complete_catalog_coverage(coverage)
                )
                offers_only = bool(active and coverage == CoverageLevel.OFFERS_ONLY.value)

        stale = False
        valid_observation = False
        if observed_at is not None:
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=UTC)
            age_hours = (now - observed_at.astimezone(UTC)).total_seconds() / 3600
            stale = age_hours < -1 or age_hours > self.max_price_age_hours
            valid_observation = age_hours >= -1
        elif basket_eligible or offers_only:
            # A price-bearing eligibility claim without timestamp provenance
            # fails closed for both basket catalogs and offer feeds.
            stale = True
        if not valid_observation:
            basket_eligible = False
            offers_only = False
        elif stale:
            # This coverage report has no contract dates. Only the runtime
            # that evaluates individual offers can assert campaign usability.
            offers_only = False
        if not active:
            basket_eligible = False
            offers_only = False
        if basket_eligible and (
            snapshot_id is None or not is_complete_catalog_coverage(coverage or "")
        ):
            basket_eligible = False

        return ContextCoverageItem(
            grocery_context_id=link.grocery_context_id,
            context_name=link.grocery_context_name,
            pickup_point_external_id=link.pickup_point_external_id,
            source_provider=link.source_provider,
            source_channel=link.source_channel,
            relation_type=link.relation_type,
            confidence=link.confidence,
            price_context_type=link.price_context_type,
            coverage=coverage,
            active=active,
            basket_eligible=basket_eligible,
            offers_only=offers_only,
            stale=stale,
            snapshot_id=snapshot_id,
            observed_at=observed_at,
        )

    def _local_snapshot(
        self,
        store: StoreModel,
    ) -> tuple[CatalogSnapshotModel | None, datetime | None]:
        contains_store = exists(
            select(1).where(
                SourceProductModel.catalog_snapshot_id == CatalogSnapshotModel.id,
                SourceProductModel.store_id == store.id,
            )
        )
        snapshot = self.session.scalar(
            select(CatalogSnapshotModel)
            .where(
                CatalogSnapshotModel.chain == store.chain,
                CatalogSnapshotModel.is_active.is_(True),
                CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
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
            return None, None
        observed_at = self.session.scalar(
            select(func.min(PriceObservationModel.observed_at)).where(
                PriceObservationModel.catalog_snapshot_id == snapshot.id,
                PriceObservationModel.store_id == store.id,
            )
        )
        return snapshot, observed_at or snapshot.created_at


def _physical_domain(row: PhysicalStoreModel) -> PhysicalStore:
    return PhysicalStore(
        id=row.id,
        chain=Chain(row.chain),
        external_store_id=row.external_store_id,
        external_store_aliases=tuple(row.external_store_aliases or ()),
        name=row.name,
        address=row.address,
        postal_code=row.postal_code,
        city=row.city,
        latitude=row.latitude,
        longitude=row.longitude,
        official_source=row.official_source,
        discovered_at=row.discovered_at,
        last_seen_at=row.last_seen_at,
        active=row.is_active,
        lifecycle_state=PhysicalStoreLifecycleState(row.lifecycle_state),
        not_seen_at=row.not_seen_at,
    )


__all__ = [
    "ChainStoreCoverage",
    "ContextCoverageItem",
    "ExactStoreContextMatch",
    "ExactStoreIdentityMatcher",
    "GroceryContextEvidence",
    "PhysicalStoreCoverageItem",
    "StoreCoverageAuditor",
    "StoreCoverageReport",
    "StoreDiscoveryHealthItem",
]
