from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, object_session

from grocery_data.app.domain.enums import (
    Confidence,
    PromotionType,
    SaleModel,
    SnapshotState,
    StoreContextRelationType,
)
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalIdentificationEvidence,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    PhysicalValidationSessionItem,
    WeightPriceType,
)
from grocery_data.app.domain.source_strategy import SourceProvider
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    ExternalPriceCandidateModel,
    PhysicalObservationV2EvidenceModel,
    PhysicalPriceObservationModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    StoreContextLinkModel,
)
from grocery_data.app.storage.repositories import ExternalPriceCandidateRepository


class ExternalPhysicalPriceCandidateReader(Protocol):
    """Read provider-neutral candidates from already persisted external data.

    Implementations must not make live provider requests while serving a manual
    validation page or report.
    """

    def for_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> Sequence[DigitalPriceCandidate]: ...

    def for_store(
        self,
        physical_store_id: str,
        *,
        limit: int,
    ) -> Sequence[DigitalPriceCandidate]: ...

    def current_for_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> Sequence[DigitalPriceCandidate]: ...


def external_candidate_from_row(row: ExternalPriceCandidateModel) -> DigitalPriceCandidate:
    return DigitalPriceCandidate(
        physical_store_id=row.physical_store_id,
        grocery_context_id=row.grocery_context_id,
        source_provider=row.source_provider,
        source_snapshot_id=row.source_snapshot_id,
        observed_at=row.observed_at,
        product_id=row.product_id,
        product_name=row.product_name,
        gtin=row.gtin,
        current_price=row.current_price,
        regular_price=row.regular_price,
        member_price=row.member_price,
        comparison_price=row.comparison_price,
        comparison_unit=row.comparison_unit,
        promotion_type=(PromotionType(row.promotion_type) if row.promotion_type else None),
        member_only=row.member_only,
        multibuy_quantity=row.multibuy_quantity,
        multibuy_total_price=row.multibuy_total_price,
        sale_model=_sale_model(row.sale_model),
        common_product_score=row.common_product_score,
    )


def _package_description(product: ProductModel) -> str | None:
    if product.package_quantity is None or not product.package_unit:
        return None
    quantity = format(product.package_quantity.normalize(), "f")
    return f"{quantity} {product.package_unit}"


class PersistedExternalPhysicalPriceCandidateReader:
    """Read a local licensed/provider cache; never performs a provider request."""

    def __init__(self, session: Session) -> None:
        self.repository = ExternalPriceCandidateRepository(session)

    def for_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> tuple[DigitalPriceCandidate, ...]:
        return tuple(
            external_candidate_from_row(row)
            for row in self.repository.matching_observation(observation)
        )

    def for_store(
        self,
        physical_store_id: str,
        *,
        limit: int,
    ) -> tuple[DigitalPriceCandidate, ...]:
        return tuple(
            external_candidate_from_row(row)
            for row in self.repository.active_for_store(
                physical_store_id,
                limit=limit,
            )
        )

    def current_for_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> tuple[DigitalPriceCandidate, ...]:
        """Read only rows marked current in the persisted licensed cache."""

        return tuple(
            external_candidate_from_row(row)
            for row in self.repository.matching_observation(observation)
            if row.is_active
        )


def physical_observation_from_row(
    row: PhysicalPriceObservationModel,
) -> PhysicalPriceObservation:
    database_session = object_session(row)
    v2 = (
        database_session.get(PhysicalObservationV2EvidenceModel, row.id)
        if database_session is not None
        else None
    )
    return PhysicalPriceObservation(
        id=row.id,
        physical_store_id=row.physical_store_id,
        gtin=row.gtin,
        product_name=row.product_name,
        shelf_price=row.shelf_price,
        comparison_price=row.comparison_price,
        comparison_unit=row.comparison_unit,
        promotion_type=(PromotionType(row.promotion_type) if row.promotion_type else None),
        member_only=row.member_only,
        multibuy_quantity=row.multibuy_quantity,
        multibuy_total_price=row.multibuy_total_price,
        promotion_text=row.promotion_text,
        observed_at=row.observed_at,
        source="manual",
        confidence=Confidence(row.confidence),
        notes=row.notes,
        photo_reference=row.photo_reference,
        validation_session_id=row.validation_session_id,
        validation_session_item_id=row.validation_session_item_id,
        price_semantics=(
            PhysicalPriceSemantics(row.price_semantics) if row.price_semantics else None
        ),
        identity_status=(
            PhysicalProductIdentityStatus(row.identity_status) if row.identity_status else None
        ),
        identification_evidence=(
            PhysicalIdentificationEvidence(v2.identification_evidence)
            if v2 is not None
            else None
        ),
        regular_shelf_price=(v2.regular_shelf_price if v2 is not None else None),
        weight_price_type=(
            WeightPriceType(v2.weight_price_type)
            if v2 is not None and v2.weight_price_type
            else None
        ),
        immutable_candidate_set_sha256=row.immutable_candidate_set_sha256,
    )


def expected_providers_for_store(
    session: Session,
    physical_store_id: str,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            session.scalars(
                select(StoreContextLinkModel.source_provider)
                .where(
                    StoreContextLinkModel.physical_store_id == physical_store_id,
                    StoreContextLinkModel.is_active.is_(True),
                )
                .order_by(StoreContextLinkModel.source_provider)
            )
        )
    )


def _sale_model(value: str) -> SaleModel:
    try:
        return SaleModel(value)
    except ValueError:
        return SaleModel.UNKNOWN


def _promotion_type(value: str) -> PromotionType:
    try:
        return PromotionType(value)
    except ValueError:
        return PromotionType.OTHER


def _promotion_for(
    session: Session,
    *,
    product_id: str,
    store_id: str,
    snapshot_id: str,
    as_of: date,
) -> PromotionModel | None:
    rows = list(
        session.scalars(
            select(PromotionModel)
            .where(
                PromotionModel.product_id == product_id,
                PromotionModel.store_id == store_id,
                PromotionModel.catalog_snapshot_id == snapshot_id,
                or_(PromotionModel.valid_from.is_(None), PromotionModel.valid_from <= as_of),
                or_(PromotionModel.valid_to.is_(None), PromotionModel.valid_to >= as_of),
            )
            .order_by(PromotionModel.id)
        )
    )
    if not rows:
        return None
    priority = {
        PromotionType.MULTIBUY.value: 0,
        PromotionType.MEMBER_PRICE.value: 1,
        PromotionType.SALE_PRICE.value: 2,
        PromotionType.PERCENT_DISCOUNT.value: 3,
        PromotionType.OTHER.value: 4,
    }
    return min(rows, key=lambda row: (priority.get(row.type, 9), row.id))


class PersistedPhysicalPriceCandidateReader:
    """Read OWN candidates from local immutable snapshots only."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _own_links(self, physical_store_id: str) -> list[StoreContextLinkModel]:
        rows = list(
            self.session.scalars(
                select(StoreContextLinkModel)
                .where(
                    StoreContextLinkModel.physical_store_id == physical_store_id,
                    StoreContextLinkModel.source_provider == SourceProvider.OWN.value,
                    StoreContextLinkModel.local_store_id.is_not(None),
                    StoreContextLinkModel.is_active.is_(True),
                )
                .order_by(StoreContextLinkModel.grocery_context_id)
            )
        )
        relation_priority = {
            StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT.value: 0,
            StoreContextRelationType.PICKUP_CONTEXT.value: 1,
            StoreContextRelationType.DELIVERY_CONTEXT.value: 2,
            StoreContextRelationType.REGIONAL_CONTEXT.value: 3,
            StoreContextRelationType.UNKNOWN.value: 4,
        }
        if not rows:
            return []
        best_priority = min(relation_priority.get(row.relation_type, 9) for row in rows)
        return [row for row in rows if relation_priority.get(row.relation_type, 9) == best_priority]

    def for_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> tuple[DigitalPriceCandidate, ...]:
        links = self._own_links(observation.physical_store_id)
        rows: list[tuple[ProductModel, PriceObservationModel, CatalogSnapshotModel, str]] = []
        for link in links:
            statement = (
                select(ProductModel, PriceObservationModel, CatalogSnapshotModel)
                .join(
                    PriceObservationModel,
                    PriceObservationModel.product_id == ProductModel.id,
                )
                .join(
                    CatalogSnapshotModel,
                    CatalogSnapshotModel.id == PriceObservationModel.catalog_snapshot_id,
                )
                .where(
                    PriceObservationModel.store_id == link.local_store_id,
                    CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
                )
            )
            if observation.gtin is not None:
                statement = statement.where(ProductModel.gtin == observation.gtin)
            else:
                statement = statement.where(
                    func.lower(func.trim(ProductModel.name))
                    == (observation.product_name or "").casefold().strip()
                )
            rows.extend(
                (product, price, snapshot, link.grocery_context_id)
                for product, price, snapshot in self.session.execute(statement).all()
            )
        return tuple(
            candidate
            for product, price, snapshot, grocery_context_id in rows
            if (
                candidate := self._candidate(
                    observation.physical_store_id,
                    grocery_context_id,
                    product,
                    price,
                    snapshot,
                )
            )
            is not None
        )

    def for_store(
        self,
        physical_store_id: str,
        *,
        limit: int = 1000,
    ) -> tuple[DigitalPriceCandidate, ...]:
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be 1..5000")
        links = self._own_links(physical_store_id)
        candidates: list[DigitalPriceCandidate] = []
        per_link_limit = max(1, limit // max(len(links), 1))
        for link in links:
            rows = self.session.execute(
                select(ProductModel, PriceObservationModel, CatalogSnapshotModel)
                .join(
                    PriceObservationModel,
                    PriceObservationModel.product_id == ProductModel.id,
                )
                .join(
                    CatalogSnapshotModel,
                    CatalogSnapshotModel.id == PriceObservationModel.catalog_snapshot_id,
                )
                .where(
                    PriceObservationModel.store_id == link.local_store_id,
                    CatalogSnapshotModel.is_active.is_(True),
                    CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
                    ProductModel.canonical_food.is_not(None),
                )
                .order_by(
                    case(
                        (
                            ProductModel.sale_model.in_(
                                (
                                    SaleModel.SOLD_BY_WEIGHT.value,
                                    SaleModel.VARIABLE_WEIGHT_PACKAGE.value,
                                )
                            ),
                            0,
                        ),
                        else_=1,
                    ),
                    ProductModel.name,
                    ProductModel.id,
                )
                .limit(per_link_limit)
            ).all()
            prior_by_key: dict[str, Decimal] = {}
            current_keys = tuple({product.source_product_key for product, _price, _snapshot in rows})
            current_snapshot_ids = tuple({snapshot.id for _product, _price, snapshot in rows})
            if current_keys:
                history = self.session.execute(
                    select(ProductModel.source_product_key, PriceObservationModel)
                    .join(
                        PriceObservationModel,
                        PriceObservationModel.product_id == ProductModel.id,
                    )
                    .join(
                        CatalogSnapshotModel,
                        CatalogSnapshotModel.id == PriceObservationModel.catalog_snapshot_id,
                    )
                    .where(
                        PriceObservationModel.store_id == link.local_store_id,
                        CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
                        CatalogSnapshotModel.id.not_in(current_snapshot_ids),
                        ProductModel.source_product_key.in_(current_keys),
                    )
                    .order_by(
                        ProductModel.source_product_key,
                        PriceObservationModel.observed_at.desc(),
                    )
                ).all()
                for source_key, prior in history:
                    prior_price = prior.sale_price or prior.regular_price
                    if source_key not in prior_by_key and prior_price is not None:
                        prior_by_key[source_key] = prior_price
            for product, price, snapshot in rows:
                candidate = self._candidate(
                    physical_store_id,
                    link.grocery_context_id,
                    product,
                    price,
                    snapshot,
                )
                if candidate is None:
                    continue
                prior_price = prior_by_key.get(product.source_product_key)
                if prior_price is not None:
                    candidate = candidate.model_copy(
                        update={
                            "recent_price_change": abs(candidate.current_price - prior_price)
                        }
                    )
                candidates.append(candidate)
        return tuple(candidates[:limit])

    def current_for_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> tuple[DigitalPriceCandidate, ...]:
        """Read the active promoted OWN snapshot for a digital-price preview."""

        links = self._own_links(observation.physical_store_id)
        rows: list[tuple[ProductModel, PriceObservationModel, CatalogSnapshotModel, str]] = []
        for link in links:
            statement = (
                select(ProductModel, PriceObservationModel, CatalogSnapshotModel)
                .join(
                    PriceObservationModel,
                    PriceObservationModel.product_id == ProductModel.id,
                )
                .join(
                    CatalogSnapshotModel,
                    CatalogSnapshotModel.id == PriceObservationModel.catalog_snapshot_id,
                )
                .where(
                    PriceObservationModel.store_id == link.local_store_id,
                    CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
                    CatalogSnapshotModel.is_active.is_(True),
                )
            )
            if observation.gtin is not None:
                statement = statement.where(ProductModel.gtin == observation.gtin)
            else:
                statement = statement.where(
                    func.lower(func.trim(ProductModel.name))
                    == (observation.product_name or "").casefold().strip()
                )
            rows.extend(
                (product, price, snapshot, link.grocery_context_id)
                for product, price, snapshot in self.session.execute(statement).all()
            )
        return tuple(
            candidate
            for product, price, snapshot, grocery_context_id in rows
            if (
                candidate := self._candidate(
                    observation.physical_store_id,
                    grocery_context_id,
                    product,
                    price,
                    snapshot,
                )
            )
            is not None
        )

    def current_for_known_detail_identity(
        self,
        observation: PhysicalPriceObservation,
    ) -> tuple[DigitalPriceCandidate, ...]:
        """Resolve a scanned GTIN through already persisted stable identities.

        Some broad catalog rows omit GTIN while an older/detail-enriched row for
        the same chain and stable external product ID contains it. This method
        uses only that local evidence and the selected store's active promoted
        snapshot. It never requests a product detail or performs fuzzy matching.
        """

        if observation.gtin is None:
            return ()
        identities = tuple(
            (str(chain), str(external_id))
            for chain, external_id in self.session.execute(
                select(ProductModel.chain, ProductModel.external_product_id)
                .where(
                    ProductModel.gtin == observation.gtin,
                    ProductModel.external_product_id.is_not(None),
                )
                .distinct()
            )
            if external_id
        )
        if not identities:
            return ()
        identity_filter = or_(
            *(
                and_(
                    ProductModel.chain == chain,
                    ProductModel.external_product_id == external_id,
                )
                for chain, external_id in identities
            )
        )
        rows: list[tuple[ProductModel, PriceObservationModel, CatalogSnapshotModel, str]] = []
        for link in self._own_links(observation.physical_store_id):
            rows.extend(
                (product, price, snapshot, link.grocery_context_id)
                for product, price, snapshot in self.session.execute(
                    select(ProductModel, PriceObservationModel, CatalogSnapshotModel)
                    .join(
                        PriceObservationModel,
                        PriceObservationModel.product_id == ProductModel.id,
                    )
                    .join(
                        CatalogSnapshotModel,
                        CatalogSnapshotModel.id == PriceObservationModel.catalog_snapshot_id,
                    )
                    .where(
                        PriceObservationModel.store_id == link.local_store_id,
                        CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
                        CatalogSnapshotModel.is_active.is_(True),
                        identity_filter,
                    )
                ).all()
            )
        return tuple(
            candidate
            for product, price, snapshot, grocery_context_id in rows
            if (
                candidate := self._candidate(
                    observation.physical_store_id,
                    grocery_context_id,
                    product,
                    price,
                    snapshot,
                )
            )
            is not None
        )

    def for_exact_session_item_snapshot(
        self,
        *,
        physical_store_id: str,
        chain: str,
        item: PhysicalValidationSessionItem,
        snapshot_id: str,
        require_active: bool = False,
    ) -> tuple[DigitalPriceCandidate, ...]:
        """Resolve one immutable target in one explicitly selected OWN snapshot.

        This is deliberately narrower than the ordinary observation lookup. It
        uses the stable source external product ID saved with the field-session
        item and never falls back to GTIN, name or fuzzy matching.
        """

        if item.target_source_provider != SourceProvider.OWN.value:
            return ()
        if (
            item.target_grocery_context_id is None
            or item.target_external_product_id is None
            or item.target_store_external_id is None
        ):
            return ()
        snapshot = self.session.get(CatalogSnapshotModel, snapshot_id)
        if (
            snapshot is None
            or snapshot.chain != chain
            or snapshot.state != SnapshotState.PROMOTED.value
            or (require_active and not snapshot.is_active)
        ):
            return ()
        links = [
            link
            for link in self._own_links(physical_store_id)
            if link.grocery_context_id == item.target_grocery_context_id
            and link.local_store_id is not None
        ]
        if len(links) != 1:
            return ()
        link = links[0]
        rows = self.session.execute(
            select(ProductModel, PriceObservationModel)
            .join(
                PriceObservationModel,
                PriceObservationModel.product_id == ProductModel.id,
            )
            .where(
                ProductModel.catalog_snapshot_id == snapshot.id,
                ProductModel.store_id == link.local_store_id,
                ProductModel.chain == chain,
                ProductModel.external_product_id == item.target_external_product_id,
                ProductModel.store_external_id == item.target_store_external_id,
                PriceObservationModel.catalog_snapshot_id == snapshot.id,
                PriceObservationModel.store_id == link.local_store_id,
            )
        ).all()
        candidates = tuple(
            candidate
            for product, price in rows
            if (
                candidate := self._candidate(
                    physical_store_id,
                    item.target_grocery_context_id,
                    product,
                    price,
                    snapshot,
                )
            )
            is not None
        )
        # Exact external identity must be unique within one context/snapshot.
        # Returning multiple candidates would make the operator binding unsafe.
        if len(candidates) > 1:
            raise ValueError(
                "reconciliation snapshot contains conflicting exact product identities"
            )
        return candidates

    def _candidate(
        self,
        physical_store_id: str,
        grocery_context_id: str,
        product: ProductModel,
        price: PriceObservationModel,
        snapshot: CatalogSnapshotModel,
    ) -> DigitalPriceCandidate | None:
        promotion = _promotion_for(
            self.session,
            product_id=product.id,
            store_id=price.store_id,
            snapshot_id=snapshot.id,
            as_of=price.observed_at.date(),
        )
        promotion_type = _promotion_type(promotion.type) if promotion is not None else None
        promotion_price = promotion.price if promotion is not None else None

        # Some connectors persist the ordinary price on the price observation
        # and the effective campaign/member amount on the explicit promotion
        # row.  Project that verified semantic split faithfully instead of
        # comparing a physical campaign label with the ordinary digital price.
        sale_price = price.sale_price
        if promotion_type is PromotionType.SALE_PRICE and promotion_price is not None:
            sale_price = sale_price or promotion_price
        member_price = price.member_price
        if promotion_type is PromotionType.MEMBER_PRICE and promotion_price is not None:
            member_price = member_price or promotion_price
        current_price = sale_price or price.regular_price or member_price
        if current_price is None:
            return None

        # Quantity=1 is present on some ordinary sale/member promotions.  It
        # must not turn those rows into a conditional multibuy observation.
        multibuy = (
            promotion_type is PromotionType.MULTIBUY
            and promotion is not None
            and promotion.quantity is not None
            and promotion.price is not None
        )
        return DigitalPriceCandidate(
            physical_store_id=physical_store_id,
            grocery_context_id=grocery_context_id,
            source_provider=SourceProvider.OWN.value,
            source_snapshot_id=snapshot.id,
            observed_at=price.observed_at,
            product_id=product.id,
            product_name=product.name,
            brand=product.brand,
            category=(product.category_path[-1] if product.category_path else None),
            package_description=_package_description(product),
            gtin=product.gtin,
            current_price=current_price,
            regular_price=price.regular_price,
            member_price=member_price,
            comparison_price=price.comparison_price,
            comparison_unit=price.comparison_unit,
            promotion_type=promotion_type,
            member_only=promotion.member_only if promotion is not None else False,
            multibuy_quantity=promotion.quantity if multibuy else None,
            multibuy_total_price=promotion.price if multibuy else None,
            sale_model=_sale_model(product.sale_model),
            common_product_score=Decimal(1),
        )


def combined_candidates_for_observation(
    observation: PhysicalPriceObservation,
    *,
    persisted_reader: PersistedPhysicalPriceCandidateReader,
    external_reader: ExternalPhysicalPriceCandidateReader | None = None,
) -> tuple[DigitalPriceCandidate, ...]:
    candidates = list(persisted_reader.for_observation(observation))
    if external_reader is not None:
        candidates.extend(external_reader.for_observation(observation))
    return tuple(candidates)


def combined_candidates_for_store(
    physical_store_id: str,
    *,
    persisted_reader: PersistedPhysicalPriceCandidateReader,
    external_reader: ExternalPhysicalPriceCandidateReader | None = None,
    limit: int = 1000,
) -> tuple[DigitalPriceCandidate, ...]:
    candidates = list(persisted_reader.for_store(physical_store_id, limit=limit))
    if external_reader is not None:
        candidates.extend(external_reader.for_store(physical_store_id, limit=limit))
    return tuple(candidates)


def current_candidates_for_observation(
    observation: PhysicalPriceObservation,
    *,
    persisted_reader: PersistedPhysicalPriceCandidateReader,
    external_reader: ExternalPhysicalPriceCandidateReader | None = None,
) -> tuple[DigitalPriceCandidate, ...]:
    """Return current persisted prices only; never performs a provider call.

    Injected legacy readers may not yet expose ``current_for_observation``. In
    that case their observation result is treated as a closed local snapshot
    and reduced deterministically to the newest row per product/context.
    """

    candidates = list(persisted_reader.current_for_observation(observation))
    if external_reader is not None:
        current_reader = getattr(external_reader, "current_for_observation", None)
        external = (
            list(current_reader(observation))
            if callable(current_reader)
            else list(external_reader.for_observation(observation))
        )
        candidates.extend(external)
    newest: dict[tuple[str, str, str], DigitalPriceCandidate] = {}
    for candidate in candidates:
        key = (
            candidate.source_provider,
            candidate.grocery_context_id,
            candidate.product_id,
        )
        previous = newest.get(key)
        if previous is None or candidate.observed_at > previous.observed_at:
            newest[key] = candidate
    return tuple(
        sorted(
            newest.values(),
            key=lambda row: (
                row.source_provider,
                row.grocery_context_id,
                row.product_name,
                row.product_id,
            ),
        )
    )


__all__ = [
    "ExternalPhysicalPriceCandidateReader",
    "PersistedExternalPhysicalPriceCandidateReader",
    "PersistedPhysicalPriceCandidateReader",
    "combined_candidates_for_observation",
    "combined_candidates_for_store",
    "current_candidates_for_observation",
    "expected_providers_for_store",
    "external_candidate_from_row",
    "physical_observation_from_row",
]
