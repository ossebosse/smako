from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain import (
    BasketDataCoverage,
    IcaRegistryObservation,
    MetadataLevel,
    ProductActiveState,
    SourceProduct,
)
from grocery_data.app.storage.models import (
    IcaDiscoveryEventModel,
    IcaProductRegistryModel,
    IcaStoreProductObservationModel,
    StoreModel,
)

_LEVEL_ORDER = {
    MetadataLevel.DISCOVERED_ID_ONLY: 0,
    MetadataLevel.BASIC_METADATA: 1,
    MetadataLevel.PRICED: 2,
    MetadataLevel.FULL_METADATA: 3,
}


def metadata_level(value: IcaRegistryObservation) -> MetadataLevel:
    has_basic = bool(value.name and (value.brand or value.package_text or value.category_path))
    if value.sale_price is not None:
        if has_basic and value.comparison_price is not None and value.sale_model:
            return MetadataLevel.FULL_METADATA
        return MetadataLevel.PRICED
    return MetadataLevel.BASIC_METADATA if has_basic else MetadataLevel.DISCOVERED_ID_ONLY


def active_state(last_seen_at: datetime, now: datetime) -> ProductActiveState:
    age = now - last_seen_at
    if age <= timedelta(days=7):
        return ProductActiveState.ACTIVE
    if age <= timedelta(days=30):
        return ProductActiveState.STALE
    if age <= timedelta(days=90):
        return ProductActiveState.NOT_SEEN_RECENTLY
    return ProductActiveState.UNKNOWN


class IcaProductRegistry:
    def __init__(self, session: Session):
        self.session = session

    def ingest(self, observation: IcaRegistryObservation) -> IcaProductRegistryModel:
        store = self.session.scalar(
            select(StoreModel).where(
                StoreModel.chain == "ica",
                StoreModel.external_id == observation.store_external_id,
            )
        )
        if store is None:
            raise ValueError("ICA registry observation references an unknown store")
        product = self.session.scalar(
            select(IcaProductRegistryModel).where(
                IcaProductRegistryModel.external_product_id == observation.external_product_id
            )
        )
        incoming_level = metadata_level(observation)
        if product is None:
            product = IcaProductRegistryModel(
                external_product_id=observation.external_product_id,
                first_seen_at=observation.observed_at,
                last_seen_at=observation.observed_at,
                metadata_level=incoming_level.value,
                active_state=ProductActiveState.ACTIVE.value,
                metadata_confidence="unknown",
            )
            self.session.add(product)
            self.session.flush()
        else:
            product.last_seen_at = max(product.last_seen_at, observation.observed_at)
        current_level = MetadataLevel(product.metadata_level)
        if _LEVEL_ORDER[incoming_level] >= _LEVEL_ORDER[current_level]:
            for field in ("gtin", "name", "brand", "package_text", "canonical_food"):
                value = getattr(observation, field)
                if value is not None:
                    setattr(product, field, value)
            if observation.category_path:
                product.category_path = observation.category_path
            product.metadata_level = incoming_level.value
            if incoming_level is MetadataLevel.FULL_METADATA:
                product.last_full_metadata_at = observation.observed_at
        product.active_state = active_state(product.last_seen_at, observation.observed_at).value

        fingerprint_source = (
            f"{product.id}|{store.id}|{observation.source.value}|"
            f"{observation.source_page}|{observation.observed_at.isoformat()}"
        )
        fingerprint = hashlib.sha256(fingerprint_source.encode()).hexdigest()
        exists = self.session.scalar(
            select(IcaDiscoveryEventModel.id).where(
                IcaDiscoveryEventModel.event_fingerprint == fingerprint
            )
        )
        if exists is None:
            self.session.add(
                IcaDiscoveryEventModel(
                    registry_product_id=product.id,
                    store_id=store.id,
                    source=observation.source.value,
                    source_page=observation.source_page,
                    raw_snapshot_id=observation.raw_snapshot_id,
                    observed_at=observation.observed_at,
                    event_fingerprint=fingerprint,
                )
            )
        if observation.sale_price is not None or observation.availability is not None:
            self.session.add(
                IcaStoreProductObservationModel(
                    registry_product_id=product.id,
                    store_id=store.id,
                    raw_snapshot_id=observation.raw_snapshot_id,
                    observed_at=observation.observed_at,
                    sale_price=observation.sale_price,
                    comparison_price=observation.comparison_price,
                    comparison_unit=observation.comparison_unit,
                    availability=observation.availability,
                    promotion=observation.promotion,
                    sale_model=observation.sale_model,
                    semantic_confidence=observation.semantic_confidence,
                    quantity_confidence=observation.quantity_confidence,
                    metadata_level=incoming_level.value,
                )
            )
        self.session.flush()
        return product

    def ingest_many(self, observations: Iterable[IcaRegistryObservation]) -> int:
        ids = {self.ingest(item).id for item in observations}
        return len(ids)

    def ingest_offer_product(
        self,
        product: SourceProduct,
        *,
        raw_snapshot_id: str | None = None,
        canonical_food: str | None = None,
        sale_model: str | None = None,
        semantic_confidence: str | None = None,
        quantity_confidence: str | None = None,
    ) -> IcaProductRegistryModel | None:
        """Merge an already fetched ICA offer into the registry at zero request cost."""

        if product.chain.value != "ica" or not product.external_product_id:
            return None
        promotion = product.offers[0].model_dump(mode="json") if product.offers else None
        return self.ingest(
            IcaRegistryObservation(
                external_product_id=product.external_product_id,
                store_external_id=product.store_external_id,
                source="offers_page",
                source_page=product.raw_reference.split("#", 1)[0],
                observed_at=product.fetched_at,
                raw_snapshot_id=raw_snapshot_id,
                name=product.name,
                brand=product.brand,
                gtin=product.gtin,
                category_path=product.category_path,
                package_text=product.package_text,
                sale_price=product.sale_price,
                comparison_price=product.comparison_price,
                comparison_unit=product.comparison_unit,
                availability=product.availability,
                promotion=promotion,
                canonical_food=canonical_food,
                sale_model=sale_model,
                semantic_confidence=semantic_confidence,
                quantity_confidence=quantity_confidence,
            )
        )

    def stats(self, store_id: str, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(tz=UTC)
        products = list(
            self.session.scalars(
                select(IcaProductRegistryModel)
                .join(
                    IcaDiscoveryEventModel,
                    IcaDiscoveryEventModel.registry_product_id == IcaProductRegistryModel.id,
                )
                .where(IcaDiscoveryEventModel.store_id == store_id)
                .distinct()
            )
        )
        fresh_cutoff = now - timedelta(days=7)
        fresh_prices = (
            self.session.scalar(
                select(
                    func.count(func.distinct(IcaStoreProductObservationModel.registry_product_id))
                ).where(
                    IcaStoreProductObservationModel.store_id == store_id,
                    IcaStoreProductObservationModel.sale_price.is_not(None),
                    IcaStoreProductObservationModel.observed_at >= fresh_cutoff,
                )
            )
            or 0
        )
        return {
            "known_products": len(products),
            "basic_metadata": sum(
                _LEVEL_ORDER[MetadataLevel(row.metadata_level)] >= 1 for row in products
            ),
            "priced": sum(_LEVEL_ORDER[MetadataLevel(row.metadata_level)] >= 2 for row in products),
            "full_metadata": sum(
                MetadataLevel(row.metadata_level) is MetadataLevel.FULL_METADATA for row in products
            ),
            "fresh_prices": fresh_prices,
            "new_last_7_days": sum(row.first_seen_at >= fresh_cutoff for row in products),
            "new_last_30_days": sum(
                row.first_seen_at >= now - timedelta(days=30) for row in products
            ),
        }

    def basket_coverage(
        self,
        store_id: str,
        canonical_foods: list[str],
        *,
        now: datetime | None = None,
        max_price_age_days: int = 7,
    ) -> BasketDataCoverage:
        now = now or datetime.now(tz=UTC)
        requested = list(dict.fromkeys(canonical_foods))
        safe_confidences = {"exact", "high", "derived", "estimated"}
        rows = self.session.execute(
            select(
                IcaProductRegistryModel.canonical_food,
                IcaStoreProductObservationModel.semantic_confidence,
                IcaStoreProductObservationModel.quantity_confidence,
            )
            .join(
                IcaStoreProductObservationModel,
                IcaStoreProductObservationModel.registry_product_id == IcaProductRegistryModel.id,
            )
            .where(
                IcaStoreProductObservationModel.store_id == store_id,
                IcaProductRegistryModel.canonical_food.in_(requested),
                IcaStoreProductObservationModel.sale_price.is_not(None),
                IcaStoreProductObservationModel.observed_at
                >= now - timedelta(days=max_price_age_days),
            )
        )
        found = {
            food
            for food, semantic, quantity in rows
            if food and semantic in safe_confidences and quantity in safe_confidences
        }
        missing = [item for item in requested if item not in found]
        count = len(requested)
        return BasketDataCoverage(
            requested_ingredients=count,
            safely_priced_ingredients=count - len(missing),
            coverage_ratio=(count - len(missing)) / count if count else 1.0,
            complete_for_request=not missing,
            missing_ingredients=missing,
        )
