from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from grocery_data.app.connectors.coop.online_context import (
    CoopOnlineContextEvidenceBundle,
)
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    PhysicalStore,
    PhysicalStoreLifecycleState,
    PriceContextType,
    SnapshotState,
)
from grocery_data.app.storage import StoreContextLinkRepository
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    ProductModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreModel,
)

COOP_SYD_CONTEXT_EXTERNAL_ID = "730400"
COOP_SYD_GROCERY_CONTEXT_ID = "own:coop:730400"
STORA_COOP_LUND_PHYSICAL_STORE_ID = "physical:coop:2696"
STORA_COOP_LUND_PICKUP_POINT_ID = "257611"
_DEFAULT_EVIDENCE_PATH = (
    Path(__file__).parents[1]
    / "connectors"
    / "coop"
    / "fixtures"
    / "online_contexts_2026_08_25.json"
)


class CoopOnlineContextActivationError(RuntimeError):
    """A promoted online snapshot lacks evidence required for pickup activation."""


@dataclass(frozen=True, slots=True)
class CoopOnlineContextActivationResult:
    snapshot_id: str
    grocery_context_id: str
    local_store_id: str
    observed_at: datetime
    linked_physical_store_ids: tuple[str, ...]
    pickup_point_external_ids: tuple[str, ...]

    @property
    def links_activated(self) -> int:
        return len(self.linked_physical_store_ids)


@lru_cache(maxsize=1)
def default_coop_online_context_evidence() -> CoopOnlineContextEvidenceBundle:
    """Load the sanitized, immutable public fulfillment evidence bundle."""

    return CoopOnlineContextEvidenceBundle.from_path(_DEFAULT_EVIDENCE_PATH)


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


class CoopOnlineContextActivationService:
    """Atomically attach a verified Coop pickup to one promoted online context.

    The catalog context and the physical pickup point deliberately retain
    separate identities.  A link is written only after both the static public
    fulfillment evidence and the promoted snapshot's local raw/product/price
    lineage reconcile.  Callers must keep this operation in the same database
    transaction as snapshot promotion so a failed activation leaves the LKG
    snapshot and its link untouched.
    """

    def __init__(
        self,
        session: Session,
        *,
        evidence: CoopOnlineContextEvidenceBundle | None = None,
    ) -> None:
        self.session = session
        self.evidence = evidence or default_coop_online_context_evidence()

    def activate(self, snapshot_id: str) -> CoopOnlineContextActivationResult:
        snapshot = self.session.get(CatalogSnapshotModel, snapshot_id)
        if snapshot is None:
            raise CoopOnlineContextActivationError("Coop snapshot does not exist")
        self._validate_snapshot(snapshot)

        context = self.evidence.context(COOP_SYD_CONTEXT_EXTERNAL_ID)
        local_store = self.session.scalar(
            select(StoreModel).where(
                StoreModel.chain == Chain.COOP.value,
                StoreModel.external_id == context.external_context_id,
            )
        )
        if local_store is None:
            raise CoopOnlineContextActivationError(
                "promoted Coop snapshot has no local 730400 price context"
            )
        self._validate_local_context(local_store, context.display_name)
        observed_at = self._validated_observation_lineage(snapshot, local_store)

        relations = tuple(
            relation
            for relation in self.evidence.pickup_relations
            if relation.online_context_external_id == context.external_context_id
            and relation.evidence_kind == "public_fulfillment_response"
        )
        required = [
            relation
            for relation in relations
            if relation.physical_store_external_id == "2696"
            and relation.pickup_point_external_id == STORA_COOP_LUND_PICKUP_POINT_ID
        ]
        if len(required) != 1:
            raise CoopOnlineContextActivationError(
                "exact public Stora Coop Lund pickup evidence is missing or ambiguous"
            )

        physical_rows: list[PhysicalStoreModel] = []
        for relation in relations:
            matches = list(
                self.session.scalars(
                    select(PhysicalStoreModel).where(
                        PhysicalStoreModel.chain == Chain.COOP.value,
                        or_(
                            PhysicalStoreModel.external_store_id
                            == relation.physical_store_external_id,
                            PhysicalStoreModel.id
                            == f"physical:coop:{relation.physical_store_external_id}",
                        ),
                    )
                )
            )
            unique = {row.id: row for row in matches}
            if len(unique) != 1:
                raise CoopOnlineContextActivationError(
                    "public Coop pickup evidence has no unique physical-store identity"
                )
            physical = next(iter(unique.values()))
            self._validate_physical_store(
                physical,
                expected_external_id=relation.physical_store_external_id,
                expected_name=relation.physical_store_name,
            )
            physical_rows.append(physical)

        if not physical_rows:
            raise CoopOnlineContextActivationError(
                "Coop online context has no public fulfillment relation"
            )

        verified_at = snapshot.promoted_at
        if verified_at is None:  # pragma: no cover - guarded by _validate_snapshot
            raise CoopOnlineContextActivationError("promoted Coop snapshot lacks timestamp")
        links = StoreContextLinkRepository(self.session)
        linked_ids: list[str] = []
        pickup_ids: list[str] = []
        for physical in physical_rows:
            link = self.evidence.as_pickup_link(
                _physical_domain(physical),
                verified_at=verified_at,
                coverage=CoverageLevel.FULL_ONLINE_CATALOG,
                basket_eligible=True,
                snapshot_id=snapshot.id,
                observed_at=observed_at,
                local_store_id=local_store.id,
            )
            persisted = links.upsert(link)
            if (
                persisted.local_store_id != local_store.id
                or persisted.snapshot_id != snapshot.id
                or persisted.pickup_point_external_id is None
            ):
                raise CoopOnlineContextActivationError(
                    "persisted Coop pickup link failed identity reconciliation"
                )
            linked_ids.append(physical.id)
            pickup_ids.append(persisted.pickup_point_external_id)

        # Keep cardinality visible: many physical pickup links still resolve to
        # exactly one purchase/price context and never become duplicate stores.
        context_links = links.list_for_context(
            source_provider="own",
            grocery_context_id=context.grocery_context_id,
        )
        if any(row.local_store_id != local_store.id for row in context_links):
            raise CoopOnlineContextActivationError(
                "Coop pickup links disagree about the local online price context"
            )

        return CoopOnlineContextActivationResult(
            snapshot_id=snapshot.id,
            grocery_context_id=context.grocery_context_id,
            local_store_id=local_store.id,
            observed_at=observed_at,
            linked_physical_store_ids=tuple(sorted(linked_ids)),
            pickup_point_external_ids=tuple(sorted(pickup_ids)),
        )

    @staticmethod
    def _validate_snapshot(snapshot: CatalogSnapshotModel) -> None:
        if snapshot.chain != Chain.COOP.value:
            raise CoopOnlineContextActivationError("snapshot is not a Coop snapshot")
        if snapshot.coverage != CoverageLevel.FULL_ONLINE_CATALOG.value:
            raise CoopOnlineContextActivationError(
                "Coop pickup activation requires FULL_ONLINE_CATALOG"
            )
        if snapshot.state != SnapshotState.PROMOTED.value or not snapshot.is_active:
            raise CoopOnlineContextActivationError(
                "Coop pickup activation requires the active promoted snapshot"
            )
        if snapshot.promoted_at is None:
            raise CoopOnlineContextActivationError("promoted Coop snapshot lacks promoted_at")

    @staticmethod
    def _validate_local_context(store: StoreModel, expected_name: str) -> None:
        if not store.is_active:
            raise CoopOnlineContextActivationError("Coop 730400 local context is inactive")
        if store.name != expected_name:
            raise CoopOnlineContextActivationError(
                "Coop 730400 must retain its neutral online context name"
            )
        if store.coverage != CoverageLevel.FULL_ONLINE_CATALOG.value:
            raise CoopOnlineContextActivationError(
                "Coop 730400 local context is not full-online coverage"
            )
        if store.price_context_type != PriceContextType.ONLINE_FULFILLMENT.value:
            raise CoopOnlineContextActivationError(
                "Coop 730400 is not an online-fulfillment context"
            )
        if store.online_shopping is not True or store.physical_store_external_id is not None:
            raise CoopOnlineContextActivationError(
                "Coop 730400 must not impersonate a physical store"
            )

    @staticmethod
    def _validate_physical_store(
        row: PhysicalStoreModel,
        *,
        expected_external_id: str,
        expected_name: str,
    ) -> None:
        if row.id != f"physical:coop:{expected_external_id}":
            raise CoopOnlineContextActivationError(
                "Coop physical registry identity does not match public pickup evidence"
            )
        if (
            row.external_store_id != expected_external_id
            or row.name.casefold() != expected_name.casefold()
        ):
            raise CoopOnlineContextActivationError(
                "Coop physical identity does not match public pickup evidence"
            )
        if (
            not row.is_active
            or row.lifecycle_state != PhysicalStoreLifecycleState.ACTIVE.value
        ):
            raise CoopOnlineContextActivationError(
                "Coop pickup physical store is not active in the registry"
            )
        if (
            expected_external_id == "2696"
            and (row.city or "").casefold().strip() != "lund"
        ):
            raise CoopOnlineContextActivationError(
                "Stora Coop Lund physical identity is outside Lund"
            )

    def _validated_observation_lineage(
        self,
        snapshot: CatalogSnapshotModel,
        store: StoreModel,
    ) -> datetime:
        product_count = int(
            self.session.scalar(
                select(func.count(ProductModel.id)).where(
                    ProductModel.catalog_snapshot_id == snapshot.id,
                    ProductModel.store_id == store.id,
                )
            )
            or 0
        )
        price_count = int(
            self.session.scalar(
                select(func.count(PriceObservationModel.id)).where(
                    PriceObservationModel.catalog_snapshot_id == snapshot.id,
                    PriceObservationModel.store_id == store.id,
                )
            )
            or 0
        )
        valid_count, observed_at = self.session.execute(
            select(
                func.count(PriceObservationModel.id),
                func.min(PriceObservationModel.observed_at),
            )
            .join(ProductModel, ProductModel.id == PriceObservationModel.product_id)
            .join(
                SourceProductModel,
                SourceProductModel.id == PriceObservationModel.source_product_id,
            )
            .join(RawSnapshotModel, RawSnapshotModel.id == PriceObservationModel.raw_snapshot_id)
            .where(
                PriceObservationModel.catalog_snapshot_id == snapshot.id,
                PriceObservationModel.store_id == store.id,
                ProductModel.catalog_snapshot_id == snapshot.id,
                ProductModel.store_id == store.id,
                ProductModel.source_product_id == SourceProductModel.id,
                ProductModel.raw_snapshot_id == RawSnapshotModel.id,
                SourceProductModel.catalog_snapshot_id == snapshot.id,
                SourceProductModel.store_id == store.id,
                SourceProductModel.raw_snapshot_id == RawSnapshotModel.id,
                RawSnapshotModel.catalog_snapshot_id == snapshot.id,
                RawSnapshotModel.chain == Chain.COOP.value,
                or_(
                    PriceObservationModel.sale_price.is_not(None),
                    PriceObservationModel.regular_price.is_not(None),
                ),
            )
        ).one()
        valid_count = int(valid_count or 0)
        if product_count <= 0 or price_count != product_count or valid_count != price_count:
            raise CoopOnlineContextActivationError(
                "Coop 730400 product/price/raw observation lineage is incomplete"
            )
        if observed_at is None:
            raise CoopOnlineContextActivationError(
                "Coop 730400 observations lack an observation timestamp"
            )
        return observed_at


def activate_promoted_coop_online_context(
    session: Session,
    snapshot: CatalogSnapshotModel,
) -> CoopOnlineContextActivationResult | None:
    """Promotion hook; unrelated snapshots retain their existing behavior."""

    if (
        snapshot.chain != Chain.COOP.value
        or snapshot.coverage != CoverageLevel.FULL_ONLINE_CATALOG.value
    ):
        return None
    return CoopOnlineContextActivationService(session).activate(snapshot.id)


__all__ = [
    "COOP_SYD_CONTEXT_EXTERNAL_ID",
    "COOP_SYD_GROCERY_CONTEXT_ID",
    "STORA_COOP_LUND_PHYSICAL_STORE_ID",
    "STORA_COOP_LUND_PICKUP_POINT_ID",
    "CoopOnlineContextActivationError",
    "CoopOnlineContextActivationResult",
    "CoopOnlineContextActivationService",
    "activate_promoted_coop_online_context",
    "default_coop_online_context_evidence",
]
