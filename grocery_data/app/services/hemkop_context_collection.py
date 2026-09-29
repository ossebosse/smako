from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from grocery_data.app.connectors.hemkop import HemkopOperatorCrawlPolicy
from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    PhysicalStoreLifecycleState,
    PriceContextType,
    SnapshotState,
    StoreContextLink,
    StoreContextRelationType,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.storage import (
    PhysicalStoreRepository,
    StoreContextLinkRepository,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    ProductModel,
    StoreModel,
)


class HemkopContextActivationError(ValueError):
    """A promoted exact Hemköp snapshot cannot prove its context lineage."""


class HemkopContextActivationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    physical_store_id: str
    grocery_context_id: str
    local_store_id: str
    observed_at: datetime


class HemkopContextCollectionTarget(BaseModel):
    """One exact physical-store-backed Hemköp online price context."""

    model_config = ConfigDict(frozen=True)

    physical_store_id: str = Field(min_length=1)
    store_external_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    grocery_context_id: str = Field(min_length=1)
    scope_key: str = Field(min_length=1)
    roles: tuple[str, ...] = ("basket", "offers")
    evidence: str = Field(min_length=1)


class HemkopContextCollectionSkip(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_external_id: str | None = None
    physical_store_id: str | None = None
    grocery_context_id: str | None = None
    reason: str


class HemkopContextCollectionPlan(BaseModel):
    """Auditable plan; constructing it performs no network operation."""

    model_config = ConfigDict(frozen=True)

    city: str
    source_policy: str = "review"
    operator_opt_in: bool
    configured_allowlist_size: int = Field(ge=0)
    eligible_contexts: int = Field(ge=0)
    targets: tuple[HemkopContextCollectionTarget, ...] = ()
    skipped: tuple[HemkopContextCollectionSkip, ...] = ()
    unmatched_allowlist_ids: tuple[str, ...] = ()


class HemkopMultiContextCollectionPlanner:
    """Plan exact, isolated Hemköp collection from persisted official evidence.

    A physical store alone is never sufficient.  A target must also have an
    active OWN catalog link proving the exact Hemköp online-store context.  The
    operator REVIEW flag and allowlist are then intersected with those proven
    contexts; allowlisting an arbitrary identifier cannot create work.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def scope_key(city: str, store_external_id: str) -> str:
        city_key = city.casefold().strip()
        store_id = store_external_id.strip()
        if not city_key or not store_id:
            raise ValueError("city and store_external_id must not be blank")
        return f"{city_key}:{Chain.HEMKOP.value}:{store_id}"

    def plan(
        self,
        city: str,
        *,
        policy: HemkopOperatorCrawlPolicy | None = None,
    ) -> HemkopContextCollectionPlan:
        city_name = city.strip()
        if not city_name:
            raise ValueError("city must not be blank")
        effective_policy = policy or HemkopOperatorCrawlPolicy.from_environment()
        physical_repository = PhysicalStoreRepository(self.session)
        link_repository = StoreContextLinkRepository(self.session)
        from grocery_data.app.services.hemkop_municipal_job import configuration, read
        area, municipal_root, municipal_enabled = configuration(city_name)
        municipal = None
        if municipal_enabled:
            from grocery_data.app.services.area_membership import approved_municipal_stores
            state = read(municipal_root / 'source-state.json')
            if state.get('inventory', {}).get('area') != area.model_dump(mode='json'):
                raise ValueError('current Hemkop municipal inventory required before catalog selection')
            municipal = approved_municipal_stores(state['inventory'])
        localities = {s.city for s in municipal.values() if s.city} if municipal is not None else {city_name}
        physical_rows = physical_repository.list_for_city(
            city_name,
            chain=Chain.HEMKOP,
            active_only=True,
        )
        if municipal is not None:
            physical_rows = [r for locality in sorted(localities)
                for r in physical_repository.list_for_city(locality, chain=Chain.HEMKOP, active_only=True)
                if r.external_store_id in municipal
                and r.address == municipal[r.external_store_id].address
                and r.postal_code == ''.join((municipal[r.external_store_id].postal_code or '').split())]
        physical_by_id = {row.id: row for row in physical_rows}
        proven: list[HemkopContextCollectionTarget] = []
        rejected: list[HemkopContextCollectionSkip] = []
        by_external_id: dict[str, list[HemkopContextCollectionTarget]] = defaultdict(list)

        for link in [link for locality in sorted(localities) for link in link_repository.list_for_city(locality, active_only=True)]:
            physical = physical_by_id.get(link.physical_store_id)
            if physical is None or physical.chain != Chain.HEMKOP.value:
                continue
            external_id = (physical.external_store_id or "").strip()
            expected_context_id = f"own:{Chain.HEMKOP.value}:{external_id}"
            exact_capability = (
                physical.is_active
                and physical.lifecycle_state == PhysicalStoreLifecycleState.ACTIVE.value
                and bool(external_id)
                and link.source_provider == SourceProvider.OWN.value
                and link.source_channel == SourceChannel.CATALOG.value
                and link.coverage == CoverageLevel.FULL_ONLINE_CATALOG.value
                and link.price_context_type == PriceContextType.ONLINE_STORE.value
                and link.relation_type == StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT.value
                and link.confidence == Confidence.EXACT.value
                and link.grocery_context_id == expected_context_id
                and not link.offers_only
                and bool((link.evidence or "").strip())
            )
            if not exact_capability:
                continue
            target = HemkopContextCollectionTarget(
                physical_store_id=physical.id,
                store_external_id=external_id,
                store_name=physical.name,
                city=physical.city if municipal is not None else city_name,
                grocery_context_id=link.grocery_context_id,
                scope_key=self.scope_key(physical.city if municipal is not None else city_name, external_id),
                evidence=str(link.evidence),
            )
            by_external_id[external_id].append(target)

        for external_id, matches in sorted(by_external_id.items()):
            if len(matches) != 1:
                rejected.extend(
                    HemkopContextCollectionSkip(
                        store_external_id=external_id,
                        physical_store_id=match.physical_store_id,
                        grocery_context_id=match.grocery_context_id,
                        reason="ambiguous exact physical-store context evidence",
                    )
                    for match in matches
                )
                continue
            proven.append(matches[0])

        targets: list[HemkopContextCollectionTarget] = []
        for candidate in sorted(proven, key=lambda row: row.store_external_id):
            if not effective_policy.allow_full_crawl:
                rejected.append(
                    HemkopContextCollectionSkip(
                        store_external_id=candidate.store_external_id,
                        physical_store_id=candidate.physical_store_id,
                        grocery_context_id=candidate.grocery_context_id,
                        reason="REVIEW source requires HEMKOP_ALLOW_FULL_CRAWL=true",
                    )
                )
            elif candidate.store_external_id not in effective_policy.allowed_store_ids:
                rejected.append(
                    HemkopContextCollectionSkip(
                        store_external_id=candidate.store_external_id,
                        physical_store_id=candidate.physical_store_id,
                        grocery_context_id=candidate.grocery_context_id,
                        reason="exact store is not in HEMKOP_STORE_EXTERNAL_IDS",
                    )
                )
            else:
                targets.append(candidate)

        proven_ids = {candidate.store_external_id for candidate in proven}
        return HemkopContextCollectionPlan(
            city=city_name,
            operator_opt_in=effective_policy.allow_full_crawl,
            configured_allowlist_size=len(effective_policy.allowed_store_ids),
            eligible_contexts=len(proven),
            targets=tuple(targets),
            skipped=tuple(rejected),
            unmatched_allowlist_ids=tuple(sorted(effective_policy.allowed_store_ids - proven_ids)),
        )


def activate_promoted_hemkop_online_context(
    session: Session,
    snapshot: CatalogSnapshotModel,
) -> HemkopContextActivationResult | None:
    """Advance one already-proven exact Hemköp link with snapshot lineage.

    This is deliberately a promotion hook, not store discovery. It only updates
    a pre-existing exact official physical-store -> online-context relation and
    fails closed if the promoted snapshot cannot prove one store, complete
    product/price lineage, and the exact collection scope. The caller keeps this
    in the snapshot-promotion transaction so the LKG snapshot and link remain
    paired if activation fails.
    """

    if (
        snapshot.chain != Chain.HEMKOP.value
        or snapshot.coverage != CoverageLevel.FULL_ONLINE_CATALOG.value
    ):
        return None
    if snapshot.state != SnapshotState.PROMOTED.value or not snapshot.is_active:
        raise HemkopContextActivationError(
            "Hemköp context activation requires the active promoted snapshot"
        )
    if snapshot.promoted_at is None:
        raise HemkopContextActivationError("promoted Hemköp snapshot lacks promoted_at")

    store_ids = tuple(
        session.scalars(
            select(ProductModel.store_id)
            .where(ProductModel.catalog_snapshot_id == snapshot.id)
            .distinct()
        )
    )
    if len(store_ids) != 1:
        raise HemkopContextActivationError(
            "Hemköp exact snapshot must contain exactly one local price context"
        )
    local_store = session.get(StoreModel, store_ids[0])
    if local_store is None or local_store.chain != Chain.HEMKOP.value:
        raise HemkopContextActivationError("Hemköp snapshot local context is missing")
    external_id = local_store.external_id.strip()
    if (
        not external_id
        or not local_store.is_active
        or local_store.coverage != CoverageLevel.FULL_ONLINE_CATALOG.value
        or local_store.price_context_type != PriceContextType.ONLINE_STORE.value
        or local_store.online_shopping is not True
    ):
        raise HemkopContextActivationError("Hemköp snapshot local context is not full online")

    physical_id = f"physical:{Chain.HEMKOP.value}:{external_id}"
    physical = session.get(PhysicalStoreModel, physical_id)
    if (
        physical is None
        or physical.chain != Chain.HEMKOP.value
        or physical.external_store_id != external_id
        or not physical.is_active
        or physical.lifecycle_state != PhysicalStoreLifecycleState.ACTIVE.value
        or not (physical.city or "").strip()
    ):
        raise HemkopContextActivationError(
            "Hemköp snapshot has no exact active official physical-store identity"
        )
    expected_scope = HemkopMultiContextCollectionPlanner.scope_key(
        str(physical.city), external_id
    )
    if snapshot.scope_key != expected_scope:
        raise HemkopContextActivationError("Hemköp snapshot scope does not match exact store")

    context_id = f"own:{Chain.HEMKOP.value}:{external_id}"
    links = StoreContextLinkRepository(session)
    current = links.get(
        physical_id,
        source_provider=SourceProvider.OWN.value,
        grocery_context_id=context_id,
    )
    if (
        current is None
        or not current.is_active
        or current.source_channel != SourceChannel.CATALOG.value
        or current.coverage != CoverageLevel.FULL_ONLINE_CATALOG.value
        or current.price_context_type != PriceContextType.ONLINE_STORE.value
        or current.relation_type
        != StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT.value
        or current.confidence != Confidence.EXACT.value
        or not (current.evidence or "").strip()
    ):
        raise HemkopContextActivationError(
            "Hemköp exact official online-context evidence is missing or ambiguous"
        )

    product_count = int(
        session.scalar(
            select(func.count(ProductModel.id)).where(
                ProductModel.catalog_snapshot_id == snapshot.id,
                ProductModel.store_id == local_store.id,
            )
        )
        or 0
    )
    price_count, observed_at = session.execute(
        select(
            func.count(PriceObservationModel.id),
            func.min(PriceObservationModel.observed_at),
        ).where(
            PriceObservationModel.catalog_snapshot_id == snapshot.id,
            PriceObservationModel.store_id == local_store.id,
            or_(
                PriceObservationModel.sale_price.is_not(None),
                PriceObservationModel.regular_price.is_not(None),
            ),
        )
    ).one()
    if product_count <= 0 or int(price_count or 0) != product_count or observed_at is None:
        raise HemkopContextActivationError(
            "Hemköp exact snapshot product/price lineage is incomplete"
        )

    persisted = links.upsert(
        StoreContextLink(
            physical_store_id=physical_id,
            grocery_context_id=context_id,
            source_provider=SourceProvider.OWN,
            source_channel=SourceChannel.CATALOG,
            local_store_id=local_store.id,
            grocery_context_name=current.grocery_context_name or local_store.name,
            price_context_type=PriceContextType.ONLINE_STORE,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
            relation_type=StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT,
            confidence=Confidence.EXACT,
            evidence=str(current.evidence),
            basket_eligible=True,
            offers_only=False,
            snapshot_id=snapshot.id,
            observed_at=observed_at,
            linked_at=current.linked_at,
            last_verified_at=snapshot.promoted_at,
            active=True,
        )
    )
    if (
        persisted.snapshot_id != snapshot.id
        or persisted.local_store_id != local_store.id
        or not persisted.basket_eligible
    ):
        raise HemkopContextActivationError(
            "persisted Hemköp context link failed snapshot reconciliation"
        )
    return HemkopContextActivationResult(
        snapshot_id=snapshot.id,
        physical_store_id=physical_id,
        grocery_context_id=context_id,
        local_store_id=local_store.id,
        observed_at=observed_at,
    )


__all__ = [
    "HemkopContextActivationError",
    "HemkopContextActivationResult",
    "HemkopContextCollectionPlan",
    "HemkopContextCollectionSkip",
    "HemkopContextCollectionTarget",
    "HemkopMultiContextCollectionPlanner",
    "activate_promoted_hemkop_online_context",
]
