from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, exists, false, func, or_, select
from sqlalchemy.orm import Session

from grocery_data.app.api.common import (
    active_snapshot_for_store,
    collection_metadata,
    decimal_number,
    freshness_for_snapshot,
    freshness_for_store,
)
from grocery_data.app.api.dependencies import get_session
from grocery_data.app.api.geography import resolve_postal_scope
from grocery_data.app.domain.enums import (
    Chain,
    CoverageLevel,
    PriceContextType,
    StoreContextRelationType,
)
from grocery_data.app.domain.source_strategy import SourceProvider
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
)

router = APIRouter(tags=["catalog"])
SessionDep = Annotated[Session, Depends(get_session)]


def _source_channel_for_store(store: StoreModel | None) -> str:
    if store is not None and store.coverage == CoverageLevel.OFFERS_ONLY.value:
        return "offers"
    return "catalog"


def _effective_store_context(store: StoreModel | None) -> tuple[str | None, str | None]:
    """Return persisted context facts with one evidence-backed legacy bridge.

    Willys snapshots created before the context migration still retain the
    exact activated store and ``online_shopping=true``. That combination is an
    online-store price context, never evidence of a physical shelf price.
    """

    if store is None:
        return None, None
    price_context = store.price_context_type
    physical_external_id = store.physical_store_external_id
    if (
        store.chain == Chain.WILLYS.value
        and price_context is None
        and store.online_shopping is True
        and store.coverage == CoverageLevel.FULL_CATALOG.value
    ):
        price_context = PriceContextType.ONLINE_STORE.value
        physical_external_id = physical_external_id or store.external_id
    return price_context, physical_external_id


def _source_metadata(
    *,
    channel: str,
    snapshot_id: str | None,
    observed_at: datetime | None,
    coverage: str | None,
    price_context: str | None,
    chain: str | None = None,
    store_id: str | None = None,
    store_name: str | None = None,
) -> dict[str, Any]:
    """Return an additive, consumer-safe provenance envelope.

    Flat legacy fields remain in every response. The envelope gives new
    federated consumers one stable shape without exposing source payloads,
    URLs, headers or session state.
    """

    return {
        "provider": "own",
        "channel": channel,
        "snapshot_id": snapshot_id,
        "observed_at": observed_at,
        "coverage": coverage,
        "price_context": price_context,
        "fallback_used": False,
        "chain": chain,
        "store_id": store_id,
        "store_name": store_name,
    }


class BulkPriceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_ids: list[str] = Field(default_factory=list, max_length=200)
    product_ids: list[str] = Field(default_factory=list, max_length=500)
    canonical_foods: list[str] = Field(default_factory=list, max_length=200)
    chains: list[Chain] = Field(default_factory=list, max_length=6)
    limit: int = Field(default=1000, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_filter(self) -> BulkPriceQuery:
        if not (self.store_ids or self.product_ids or self.canonical_foods or self.chains):
            raise ValueError("at least one bulk price filter is required")
        return self


def _store_or_404(session: Session, store_id: str) -> StoreModel:
    store = session.get(StoreModel, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="store not found")
    return store


def _split_values(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or ():
        result.extend(part.strip() for part in value.split(",") if part.strip())
    return list(dict.fromkeys(result))


def _chains_for_stores(session: Session, store_ids: list[str]) -> set[str]:
    if not store_ids:
        return set()
    return set(session.scalars(select(StoreModel.chain).where(StoreModel.id.in_(store_ids))))


def _snapshot_ids_for_stores(session: Session, store_ids: list[str]) -> set[str]:
    if not store_ids:
        return set()
    stores = session.scalars(select(StoreModel).where(StoreModel.id.in_(store_ids)))
    return {
        snapshot.id
        for store in stores
        if (snapshot := active_snapshot_for_store(session, store)) is not None
    }


def _active_snapshot_or_503(session: Session, store: StoreModel) -> CatalogSnapshotModel:
    snapshot = active_snapshot_for_store(session, store)
    if snapshot is None:
        raise HTTPException(
            status_code=503,
            detail=f"no active snapshot for {store.chain}",
        )
    return snapshot


def _pickup_links_for_store(
    session: Session,
    store: StoreModel,
    *,
    service_city: str | None = None,
    service_postal_code: str | None = None,
) -> list[tuple[StoreContextLinkModel, PhysicalStoreModel]]:
    """Return verified active pickup destinations for one local price context.

    A pickup point is relation metadata, not another price context.  The query
    therefore returns link/physical-store pairs while callers keep serializing
    the local ``StoreModel`` exactly once.  An optional city/postcode narrows
    the options to the geographic scope that admitted the context.
    """

    statement = (
        select(StoreContextLinkModel, PhysicalStoreModel)
        .join(
            PhysicalStoreModel,
            PhysicalStoreModel.id == StoreContextLinkModel.physical_store_id,
        )
        .where(
            StoreContextLinkModel.local_store_id == store.id,
            StoreContextLinkModel.source_provider == SourceProvider.OWN.value,
            StoreContextLinkModel.relation_type == StoreContextRelationType.PICKUP_CONTEXT.value,
            StoreContextLinkModel.confidence == "exact",
            StoreContextLinkModel.pickup_point_external_id.is_not(None),
            StoreContextLinkModel.is_active.is_(True),
            PhysicalStoreModel.is_active.is_(True),
        )
    )
    if service_city:
        statement = statement.where(
            func.lower(func.trim(PhysicalStoreModel.city)) == service_city.casefold().strip()
        )
    if service_postal_code:
        statement = statement.where(
            func.replace(PhysicalStoreModel.postal_code, " ", "") == service_postal_code
        )
    return list(
        session.execute(
            statement.order_by(
                PhysicalStoreModel.name,
                StoreContextLinkModel.pickup_point_external_id,
                StoreContextLinkModel.id,
            )
        ).all()
    )


def _store_item(
    session: Session,
    store: StoreModel,
    *,
    service_city: str | None = None,
    requested_postal_code: str | None = None,
    exact_service_postal: bool = False,
) -> dict[str, Any]:
    freshness = freshness_for_store(session, store)
    channel = _source_channel_for_store(store)
    price_context, physical_external_id = _effective_store_context(store)
    pickup_rows = _pickup_links_for_store(
        session,
        store,
        service_city=service_city,
        service_postal_code=requested_postal_code if exact_service_postal else None,
    )
    pickup_options = [
        {
            "physical_store_id": physical.id,
            "physical_store_external_id": physical.external_store_id,
            "pickup_point_external_id": link.pickup_point_external_id,
            "name": physical.name,
            "address": physical.address,
            "postal_code": physical.postal_code,
            "city": physical.city,
            "latitude": decimal_number(physical.latitude),
            "longitude": decimal_number(physical.longitude),
            "relation_type": link.relation_type,
            "confidence": link.confidence,
        }
        for link, physical in pickup_rows
    ]
    service_area = None
    if pickup_options:
        service_area = {
            "cities": sorted(
                {
                    str(option["city"]).strip()
                    for option in pickup_options
                    if option["city"] is not None and str(option["city"]).strip()
                },
                key=str.casefold,
            ),
            "postal_codes": sorted(
                {
                    "".join(
                        character for character in str(option["postal_code"]) if character.isdigit()
                    )
                    for option in pickup_options
                    if option["postal_code"] is not None
                }
                - {""}
            ),
            "availability_basis": "verified_pickup_context",
            "requested_postal_code": requested_postal_code,
        }
    is_online_price = price_context in {
        PriceContextType.ONLINE_STORE.value,
        PriceContextType.ONLINE_FULFILLMENT.value,
        PriceContextType.REGIONAL.value,
    }
    return {
        "id": store.id,
        "chain": store.chain,
        "external_id": store.external_id,
        "name": store.name,
        "address": store.address,
        "postal_code": store.postal_code,
        # ``service_city`` is an eligibility scope, not a claim that a
        # regional online context has a physical address there.
        "city": store.city or (service_city if pickup_options else None),
        "latitude": decimal_number(store.latitude),
        "longitude": decimal_number(store.longitude),
        "online_shopping": store.online_shopping,
        "coverage": store.coverage,
        "price_context_type": price_context,
        "physical_store_external_id": physical_external_id,
        "price_semantics": "online_price" if is_online_price else None,
        "price_label": (
            {
                Chain.COOP.value: "Coop onlinepris",
                Chain.ICA.value: "ICA onlinepris",
            }.get(store.chain, "Onlinepris")
            if is_online_price
            else None
        ),
        "service_area": service_area,
        "pickup_options": pickup_options,
        "active": store.is_active,
        "snapshot_id": freshness["snapshot_id"],
        "observed_at": freshness["observed_at"],
        "data_age_hours": freshness["data_age_hours"],
        "connector_status": freshness["connector_status"],
        "source_provider": "own",
        "source_channel": channel,
        "source_observed_at": freshness["observed_at"],
        "source_snapshot_id": freshness["snapshot_id"],
        "fallback_used": False,
        "source": _source_metadata(
            channel=channel,
            snapshot_id=freshness["snapshot_id"],
            observed_at=freshness["observed_at"],
            coverage=store.coverage,
            price_context=price_context,
            chain=store.chain,
            store_id=store.id,
            store_name=store.name,
        ),
    }


def _product_item(
    product: ProductModel,
    source: SourceProductModel,
    price: PriceObservationModel | None,
    store: StoreModel | None,
) -> dict[str, Any]:
    observed_at = price.observed_at if price is not None else product.observed_at
    channel = _source_channel_for_store(store)
    coverage = store.coverage if store is not None else None
    price_context, _ = _effective_store_context(store)
    return {
        "id": product.id,
        "chain": product.chain,
        "external_product_id": product.external_product_id,
        "gtin": product.gtin,
        "name": product.name,
        "brand": product.brand,
        "category_path": product.category_path,
        "canonical_food": product.canonical_food,
        "product_role": product.product_role,
        "product_form": product.product_form,
        "semantic_confidence": product.semantic_confidence,
        "sale_model": product.sale_model,
        "quantity_confidence": product.quantity_confidence,
        "package_quantity": decimal_number(product.package_quantity),
        "package_unit": product.package_unit,
        "package_text": source.package_text,
        "drained_quantity": decimal_number(source.drained_quantity),
        "usable_quantity": decimal_number(product.usable_quantity),
        "usable_unit": product.usable_unit,
        "average_weight_kg": decimal_number(source.average_weight_kg),
        "increment_value": decimal_number(source.increment_value),
        "basket_type": source.basket_type,
        "sale_unit": price.sale_unit if price is not None else source.sale_unit,
        "availability": source.availability or product.availability,
        "store_id": store.id if store is not None else source.store_id,
        "store_name": store.name if store is not None else None,
        "sale_price": decimal_number(price.sale_price if price is not None else source.sale_price),
        "regular_price": decimal_number(
            price.regular_price if price is not None else source.regular_price
        ),
        "member_price": decimal_number(
            price.member_price if price is not None else source.member_price
        ),
        "comparison_price": decimal_number(
            price.comparison_price if price is not None else source.comparison_price
        ),
        "comparison_unit": (price.comparison_unit if price is not None else source.comparison_unit),
        "observed_at": observed_at,
        "snapshot_id": source.catalog_snapshot_id,
        "source_provider": "own",
        "source_channel": channel,
        "source_observed_at": observed_at,
        "source_snapshot_id": source.catalog_snapshot_id,
        "coverage": coverage,
        "price_context": price_context,
        "fallback_used": False,
        "source": _source_metadata(
            channel=channel,
            snapshot_id=source.catalog_snapshot_id,
            observed_at=observed_at,
            coverage=coverage,
            price_context=price_context,
            chain=product.chain,
            store_id=store.id if store is not None else source.store_id,
            store_name=store.name if store is not None else None,
        ),
        # Only opaque database identifiers and version/timestamp metadata are
        # exposed here. Raw URLs, request query strings, source fields and
        # payload locations remain internal so lineage cannot leak credentials.
        "lineage": {
            "source_snapshot_id": source.catalog_snapshot_id,
            "raw_snapshot_id": source.raw_snapshot_id,
            "parser_version": product.parser_version,
            "normalizer_version": product.normalizer_version,
            "observed_at": observed_at,
        },
        "promotions": [],
        # A narrow validated contract flag, never raw document/source fields.
        "lidl_document_count_contract": bool(
            (source.source_fields or {}).get('lidl_offer_policy') == 'lidl-national-qualified-document-text-v2'
            and source.source_fields.get('lidl_purchase_qualified') is True
            and (source.source_fields.get('document_product_binding') or {}).get('explicit_piece_purchase') is True
            and not source.source_fields.get('purchase_blockers')
            and store and source.store_external_id == store.external_id
            and channel == 'offers' and coverage == 'offers_only'
            and product.package_quantity == product.usable_quantity == 1
            and product.package_unit == product.usable_unit == 'st'
        ),
        "willys_document_count_contract": bool(
            (source.source_fields or {}).get("willys_flyer_policy") == "willys-flyer-validated-text-v2"
            and source.source_fields.get("willys_flyer_purchase_qualified") is True
            and source.source_fields.get("document_product_binding")
            and not source.source_fields.get("purchase_blockers")
            and product.parser_version == "willys-flyer-text-v2"
            and store and source.store_external_id == store.external_id
            and channel == "offers" and coverage == "offers_only"
            and product.package_quantity == 1 and product.package_unit == "st"
            and product.usable_quantity == 1 and product.usable_unit == "st"
        ),
        **({"physical_offer_qualified": source.source_fields.get("coop_purchase_qualified") is True,
            "external_store_id": store.external_id if store else None,
            "price_context_type": price_context}
           if (source.source_fields or {}).get("coop_physical_policy") else {}),
    }


def _promotion_item(
    promotion: PromotionModel,
    *,
    product: ProductModel | None = None,
    source: SourceProductModel | None = None,
    store: StoreModel | None = None,
) -> dict[str, Any]:
    price_context, _ = _effective_store_context(store)
    item = {
        "id": promotion.id,
        "snapshot_id": promotion.catalog_snapshot_id,
        "external_id": promotion.external_id,
        "type": promotion.type,
        "valid_from": promotion.valid_from,
        "valid_to": promotion.valid_to,
        "price": decimal_number(promotion.price),
        "quantity": promotion.quantity,
        "member_only": promotion.member_only,
        "max_quantity": promotion.max_quantity,
        "description": promotion.description,
        "product_id": product.id if product is not None else promotion.product_id,
        "external_product_id": source.external_product_id if source is not None else None,
        "product_name": (
            product.name if product is not None else source.name if source is not None else None
        ),
        "store_id": store.id if store is not None else promotion.store_id,
        "store_external_id": store.external_id if store is not None else None,
        "store_name": store.name if store is not None else None,
        "store_coverage": store.coverage if store is not None else None,
        "chain": store.chain if store is not None else None,
        "source_provider": "own",
        "source_channel": "offers",
        "source_observed_at": source.fetched_at if source is not None else None,
        "source_snapshot_id": promotion.catalog_snapshot_id,
        "coverage": store.coverage if store is not None else None,
        "price_context": price_context,
        "fallback_used": False,
        "source": _source_metadata(
            channel="offers",
            snapshot_id=promotion.catalog_snapshot_id,
            observed_at=source.fetched_at if source is not None else None,
            coverage=store.coverage if store is not None else None,
            price_context=price_context,
            chain=store.chain if store is not None else None,
            store_id=store.id if store is not None else promotion.store_id,
            store_name=store.name if store is not None else None,
        ),
    }
    if product is not None and source is not None:
        # An offer carries enough normalized product data for explicit offer
        # diagnostics. Consumers must not fetch /catalog for an OFFERS_ONLY
        # store merely to attach package/price semantics to this promotion.
        item["product"] = _product_item(product, source, None, store)
    deposit = (promotion.source_payload or {}).get("reviewedDeposit")
    if (promotion.source_payload or {}).get("policy") in {"coop-physical-structured-v1", "coop-xtra-pdf-text-v1", "lidl-national-reviewed-document-text-v1", "lidl-national-qualified-document-text-v2", "willys-flyer-reviewed-text-v1", "willys-flyer-validated-text-v2"}:
        # Safe opaque contract identity; preserve caps across concrete variants.
        item["price_contract_id"] = promotion.source_payload.get("price_contract_id")
        if promotion.source_payload.get('price_basis_unit') == 'kg':
            item['price_basis_unit'] = 'kg'
    if (promotion.source_payload or {}).get("purchase_terms"):
        from grocery_data.app.domain.purchase_terms import PurchaseTerms
        item["purchase_terms"] = PurchaseTerms.model_validate(promotion.source_payload["purchase_terms"]).model_dump(mode="json")
        if promotion.source_payload.get('price_basis_unit') == 'kg':
            item['price_basis_unit'] = 'kg'
        if promotion.source_payload.get('price_contract_id'):
            item['price_contract_id'] = promotion.source_payload['price_contract_id']
    campaign = (promotion.source_payload or {}).get("campaign_evidence")
    if campaign is not None:
        from grocery_data.app.domain.campaign_validity import CampaignEvidence
        item["campaign_evidence"] = CampaignEvidence.model_validate(campaign).model_dump(mode="json")
    if deposit is not None:
        from grocery_data.app.domain.promotion_pricing import DepositContract
        item["deposit"] = DepositContract.model_validate(deposit).model_dump(mode="json")
    return item


def _product_items(session: Session, rows: list[Any]) -> list[dict[str, Any]]:
    items = [_product_item(*row) for row in rows]
    source_ids = [row[1].id for row in rows]
    if not source_ids:
        return items
    promotion_rows = session.scalars(
        select(PromotionModel)
        .where(PromotionModel.source_product_id.in_(source_ids))
        .order_by(PromotionModel.valid_from, PromotionModel.id)
    )
    contexts = {row[1].id: (row[0], row[1], row[3]) for row in rows}
    promotions_by_source: dict[str, list[dict[str, Any]]] = {}
    for promotion in promotion_rows:
        product, source, store = contexts[promotion.source_product_id]
        promotions_by_source.setdefault(promotion.source_product_id, []).append(
            _promotion_item(
                promotion,
                product=product,
                source=source,
                store=store,
            )
        )
    for item, row in zip(items, rows, strict=True):
        item["promotions"] = promotions_by_source.get(row[1].id, [])
    # Transport is snapshot lineage, not a new retailer/provider or a price
    # fact. One lookup per page avoids changing raw product records or hashes.
    snapshot_ids = {row[1].catalog_snapshot_id for row in rows if row[1].chain == "willys"}
    if not snapshot_ids:
        return items
    relay_ids = {
        snapshot.id
        for snapshot in session.scalars(
            select(CatalogSnapshotModel).where(CatalogSnapshotModel.id.in_(snapshot_ids))
        )
        if (
            (snapshot.metrics or {}).get("source_artifact")
            or (snapshot.metrics or {}).get("source_artifact_lineage")
            or {}
        ).get("collection_location")
        == "LOCAL_RELAY"
    }
    for item, row in zip(items, rows, strict=True):
        if row[1].catalog_snapshot_id not in relay_ids:
            continue
        for value in (item, *item["promotions"]):
            value["collection_location"] = "LOCAL_RELAY"
            value["source"]["collection_location"] = "LOCAL_RELAY"
            if "product" in value:
                value["product"]["collection_location"] = "LOCAL_RELAY"
                value["product"]["source"]["collection_location"] = "LOCAL_RELAY"
        item["lineage"]["collection_location"] = "LOCAL_RELAY"
    return items


def _price_item(
    observation: PriceObservationModel,
    product: ProductModel,
    store: StoreModel,
) -> dict[str, Any]:
    channel = _source_channel_for_store(store)
    return {
        "id": observation.id,
        "snapshot_id": observation.catalog_snapshot_id,
        "product_id": product.id,
        "external_product_id": product.external_product_id,
        "gtin": product.gtin,
        "product_name": product.name,
        "canonical_food": product.canonical_food,
        "store_id": store.id,
        "store_external_id": store.external_id,
        "store_name": store.name,
        "chain": product.chain,
        "observed_at": observation.observed_at,
        "currency": observation.currency,
        "sale_price": decimal_number(observation.sale_price),
        "regular_price": decimal_number(observation.regular_price),
        "member_price": decimal_number(observation.member_price),
        "comparison_price": decimal_number(observation.comparison_price),
        "comparison_unit": observation.comparison_unit,
        "sale_unit": observation.sale_unit,
        "sale_model": product.sale_model,
        "quantity_confidence": product.quantity_confidence,
        "semantic_confidence": product.semantic_confidence,
        "source_provider": "own",
        "source_channel": channel,
        "source_observed_at": observation.observed_at,
        "source_snapshot_id": observation.catalog_snapshot_id,
        "coverage": store.coverage,
        "price_context": store.price_context_type,
        "fallback_used": False,
        "source": _source_metadata(
            channel=channel,
            snapshot_id=observation.catalog_snapshot_id,
            observed_at=observation.observed_at,
            coverage=store.coverage,
            price_context=store.price_context_type,
            chain=product.chain,
            store_id=store.id,
            store_name=store.name,
        ),
    }


def _product_rows_statement():
    return (
        select(ProductModel, SourceProductModel, PriceObservationModel, StoreModel)
        .join(
            SourceProductModel,
            ProductModel.source_product_id == SourceProductModel.id,
        )
        .join(
            CatalogSnapshotModel,
            SourceProductModel.catalog_snapshot_id == CatalogSnapshotModel.id,
        )
        .outerjoin(
            PriceObservationModel,
            and_(
                PriceObservationModel.product_id == ProductModel.id,
                PriceObservationModel.catalog_snapshot_id == CatalogSnapshotModel.id,
            ),
        )
        .outerjoin(StoreModel, SourceProductModel.store_id == StoreModel.id)
        .where(
            CatalogSnapshotModel.is_active.is_(True),
            ProductModel.catalog_snapshot_id == CatalogSnapshotModel.id,
        )
    )


def _price_rows_statement():
    return (
        select(PriceObservationModel, ProductModel, StoreModel)
        .join(ProductModel, PriceObservationModel.product_id == ProductModel.id)
        .join(StoreModel, PriceObservationModel.store_id == StoreModel.id)
        .join(
            CatalogSnapshotModel,
            PriceObservationModel.catalog_snapshot_id == CatalogSnapshotModel.id,
        )
        .where(CatalogSnapshotModel.is_active.is_(True))
    )


def _price_response(
    session: Session,
    statement,
    *,
    limit: int,
    offset: int,
) -> dict:
    rows = session.execute(
        statement.order_by(ProductModel.name, StoreModel.name).offset(offset).limit(limit)
    ).all()
    items = [_price_item(*row) for row in rows]
    chains = {item["chain"] for item in items}
    snapshot_ids = {item["snapshot_id"] for item in items}
    metadata = collection_metadata(session, chains, snapshot_ids=snapshot_ids)
    return {
        "items": items,
        "prices": items,
        "count": len(items),
        "offset": offset,
        **metadata,
    }


@router.get("/stores")
def stores(
    session: SessionDep,
    chain: Chain | None = None,
    city: str | None = None,
    postal_code: str | None = None,
    online_shopping: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    statement = select(StoreModel).where(StoreModel.is_active.is_(True))
    geography = None
    if chain is not None:
        statement = statement.where(StoreModel.chain == chain.value)
    service_city = city.strip() if city and city.strip() else None
    exact_service_postal = False
    if postal_code:
        geography = resolve_postal_scope(postal_code)
        if geography.resolution == "invalid":
            raise HTTPException(status_code=422, detail="postal_code must contain five digits")
        if service_city:
            exact_service_postal = True
        elif geography.resolved_city is not None:
            service_city = geography.resolved_city
        else:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "postal_code is outside the current Lund/Malmö scope",
                    "geography": geography.as_dict(),
                },
            )
    if service_city:
        direct_area = func.lower(func.trim(StoreModel.city)) == service_city.casefold()
        linked_area_conditions = [
            StoreContextLinkModel.local_store_id == StoreModel.id,
            StoreContextLinkModel.source_provider == SourceProvider.OWN.value,
            StoreContextLinkModel.relation_type == StoreContextRelationType.PICKUP_CONTEXT.value,
            StoreContextLinkModel.confidence == "exact",
            StoreContextLinkModel.pickup_point_external_id.is_not(None),
            StoreContextLinkModel.basket_eligible.is_(True),
            StoreContextLinkModel.coverage.in_(
                (
                    CoverageLevel.FULL_CATALOG.value,
                    CoverageLevel.FULL_ONLINE_CATALOG.value,
                )
            ),
            StoreContextLinkModel.snapshot_id.is_not(None),
            StoreContextLinkModel.is_active.is_(True),
            PhysicalStoreModel.is_active.is_(True),
            func.lower(func.trim(PhysicalStoreModel.city)) == service_city.casefold(),
        ]
        if exact_service_postal and geography is not None:
            direct_area = and_(
                direct_area,
                func.replace(StoreModel.postal_code, " ", "") == geography.normalized_postal_code,
            )
            linked_area_conditions.append(
                func.replace(PhysicalStoreModel.postal_code, " ", "")
                == geography.normalized_postal_code
            )
        linked_area = exists(
            select(1)
            .select_from(StoreContextLinkModel)
            .join(
                PhysicalStoreModel,
                PhysicalStoreModel.id == StoreContextLinkModel.physical_store_id,
            )
            .where(*linked_area_conditions)
        )
        statement = statement.where(or_(direct_area, linked_area))
    if online_shopping is not None:
        statement = statement.where(StoreModel.online_shopping.is_(online_shopping))
    rows = list(
        session.scalars(
            statement.order_by(StoreModel.chain, StoreModel.name).offset(offset).limit(limit)
        )
    )
    items = [
        _store_item(
            session,
            store,
            service_city=service_city,
            requested_postal_code=(
                geography.normalized_postal_code if geography is not None else None
            ),
            exact_service_postal=exact_service_postal,
        )
        for store in rows
    ]
    chains = {store.chain for store in rows}
    if chain is not None:
        chains.add(chain.value)
    snapshot_ids = {item["snapshot_id"] for item in items if item["snapshot_id"] is not None}
    snapshot_ids.update(_snapshot_ids_for_stores(session, [store.id for store in rows]))
    metadata = collection_metadata(session, chains, snapshot_ids=snapshot_ids)
    return {
        "items": items,
        "stores": items,
        "count": len(items),
        "offset": offset,
        "geography": geography.as_dict() if geography is not None else None,
        **metadata,
    }


@router.get("/stores/{store_id}")
def store_detail(store_id: str, session: SessionDep) -> dict:
    store = _store_or_404(session, store_id)
    return _store_item(session, store)


@router.get("/products/search")
def product_search(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    session: SessionDep,
    store_id: Annotated[list[str] | None, Query()] = None,
    chain: Chain | None = None,
    canonical_food: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    statement = _product_rows_statement()
    pattern = f"%{q.casefold().replace('%', r'\%').replace('_', r'\_')}%"
    statement = statement.where(
        or_(
            func.lower(ProductModel.name).like(pattern, escape="\\"),
            func.lower(func.coalesce(ProductModel.brand, "")).like(pattern, escape="\\"),
            func.lower(func.coalesce(ProductModel.canonical_food, "")).like(pattern, escape="\\"),
        )
    )
    store_ids = _split_values(store_id)
    if store_ids:
        stores_by_id = {
            store.id: store
            for store in session.scalars(select(StoreModel).where(StoreModel.id.in_(store_ids)))
        }
        if set(stores_by_id) != set(store_ids):
            raise HTTPException(status_code=404, detail="one or more stores were not found")
        # ProductModel carries the normalized store lineage and has a covering
        # snapshot/store/name index. Filtering through SourceProductModel here
        # made SQLite choose a quadratic nested-loop plan on real catalogs.
        #
        # Promotion is scoped, so a legacy and a canonical scope name may both
        # remain active while referring to the same logical price context. The
        # store/catalog surface deliberately resolves exactly one authoritative
        # snapshot in that case. Keep search on the identical pairwise lineage;
        # selecting every globally active row would merge two observations for
        # one context and can make a prepared PriceUniverse internally
        # inconsistent with /catalog/{store_id}.
        active_contexts = [
            (store.id, snapshot.id)
            for store in stores_by_id.values()
            if (snapshot := active_snapshot_for_store(session, store)) is not None
        ]
        statement = statement.where(
            or_(
                *(
                    and_(
                        ProductModel.store_id == requested_store_id,
                        ProductModel.catalog_snapshot_id == snapshot_id,
                    )
                    for requested_store_id, snapshot_id in active_contexts
                )
            )
            if active_contexts
            else false()
        )
    if chain is not None:
        statement = statement.where(ProductModel.chain == chain.value)
    if canonical_food is not None:
        statement = statement.where(ProductModel.canonical_food == canonical_food)
    rows = session.execute(
        statement.order_by(ProductModel.name, StoreModel.name).offset(offset).limit(limit)
    ).all()
    items = _product_items(session, rows)
    chains = {item["chain"] for item in items} | _chains_for_stores(session, store_ids)
    if chain is not None:
        chains.add(chain.value)
    snapshot_ids = {item["snapshot_id"] for item in items if item["snapshot_id"] is not None}
    snapshot_ids.update(_snapshot_ids_for_stores(session, store_ids))
    metadata = collection_metadata(session, chains, snapshot_ids=snapshot_ids)
    return {
        "items": items,
        "products": items,
        "count": len(items),
        "offset": offset,
        **metadata,
    }


@router.get("/products/{product_id}")
def product_detail(product_id: str, session: SessionDep) -> dict:
    row = session.execute(
        _product_rows_statement().where(ProductModel.id == product_id).limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="product not found in active snapshot")
    item = _product_items(session, [row])[0]
    snapshot = session.get(CatalogSnapshotModel, item["snapshot_id"])
    if snapshot is None:  # pragma: no cover - protected by the active-snapshot join
        raise HTTPException(status_code=503, detail="active product snapshot disappeared")
    freshness = freshness_for_snapshot(session, snapshot)
    # Keep legacy top-level freshness fields while letting the product row's
    # exact price observation and context provenance win every collision.
    # Snapshot-wide freshness remains explicit for clients that need the
    # conservative oldest-observation eligibility clock.
    return {**freshness, **item, "snapshot_freshness": freshness}


@router.get("/prices")
def prices(
    session: SessionDep,
    store_id: Annotated[list[str] | None, Query()] = None,
    product_id: Annotated[list[str] | None, Query()] = None,
    chain: Chain | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    statement = _price_rows_statement()
    store_ids = _split_values(store_id)
    product_ids = _split_values(product_id)
    if store_ids:
        statement = statement.where(PriceObservationModel.store_id.in_(store_ids))
    if product_ids:
        statement = statement.where(PriceObservationModel.product_id.in_(product_ids))
    if chain is not None:
        statement = statement.where(ProductModel.chain == chain.value)
    response = _price_response(session, statement, limit=limit, offset=offset)
    metadata_chains = _chains_for_stores(session, store_ids)
    if chain is not None:
        metadata_chains.add(chain.value)
    if metadata_chains:
        snapshot_ids = {
            item["snapshot_id"] for item in response["freshness"] if item["snapshot_id"] is not None
        }
        snapshot_ids.update(_snapshot_ids_for_stores(session, store_ids))
        response.update(
            collection_metadata(
                session,
                metadata_chains,
                snapshot_ids=snapshot_ids or None,
            )
        )
    return response


@router.post("/prices/query")
def bulk_prices(
    query: BulkPriceQuery,
    session: SessionDep,
) -> dict:
    statement = _price_rows_statement()
    if query.store_ids:
        statement = statement.where(PriceObservationModel.store_id.in_(query.store_ids))
    if query.product_ids:
        statement = statement.where(PriceObservationModel.product_id.in_(query.product_ids))
    if query.canonical_foods:
        statement = statement.where(ProductModel.canonical_food.in_(query.canonical_foods))
    if query.chains:
        statement = statement.where(ProductModel.chain.in_([item.value for item in query.chains]))
    response = _price_response(session, statement, limit=query.limit, offset=query.offset)
    metadata_chains = _chains_for_stores(session, query.store_ids)
    metadata_chains.update(item.value for item in query.chains)
    if metadata_chains:
        snapshot_ids = {
            item["snapshot_id"] for item in response["freshness"] if item["snapshot_id"] is not None
        }
        snapshot_ids.update(_snapshot_ids_for_stores(session, query.store_ids))
        response.update(
            collection_metadata(
                session,
                metadata_chains,
                snapshot_ids=snapshot_ids or None,
            )
        )
    return response


@router.get("/catalog/{store_id}")
def catalog(
    store_id: str,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    store = _store_or_404(session, store_id)
    if store.coverage == CoverageLevel.OFFERS_ONLY.value:
        raise HTTPException(
            status_code=409,
            detail=(
                "offers-only store has no verified catalog; use /offers for "
                "explicit offer diagnostics"
            ),
        )
    snapshot = _active_snapshot_or_503(session, store)
    statement = _product_rows_statement().where(
        ProductModel.store_id == store.id,
        ProductModel.catalog_snapshot_id == snapshot.id,
        SourceProductModel.store_id == store.id,
        SourceProductModel.catalog_snapshot_id == snapshot.id,
    )
    rows = session.execute(statement.order_by(ProductModel.name).offset(offset).limit(limit)).all()
    items = _product_items(session, rows)
    freshness = freshness_for_snapshot(session, snapshot)
    return {
        "store": _store_item(session, store),
        "items": items,
        "products": items,
        "count": len(items),
        "offset": offset,
        **freshness,
    }


@router.get("/offers")
def offers(
    session: SessionDep,
    store_id: Annotated[list[str] | None, Query()] = None,
    chain: Chain | None = None,
    active_only: bool = True,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    statement = (
        select(PromotionModel, ProductModel, SourceProductModel, StoreModel)
        .join(
            CatalogSnapshotModel,
            PromotionModel.catalog_snapshot_id == CatalogSnapshotModel.id,
        )
        .outerjoin(ProductModel, PromotionModel.product_id == ProductModel.id)
        .join(SourceProductModel, PromotionModel.source_product_id == SourceProductModel.id)
        .join(StoreModel, PromotionModel.store_id == StoreModel.id)
        .where(CatalogSnapshotModel.is_active.is_(True))
    )
    store_ids = _split_values(store_id)
    if store_ids:
        statement = statement.where(PromotionModel.store_id.in_(store_ids))
    if chain is not None:
        statement = statement.where(StoreModel.chain == chain.value)
    if active_only:
        today = datetime.now(tz=ZoneInfo("Europe/Stockholm")).date()
        statement = statement.where(
            or_(PromotionModel.valid_from.is_(None), PromotionModel.valid_from <= today),
            or_(PromotionModel.valid_to.is_(None), PromotionModel.valid_to >= today),
        )
    rows = session.execute(
        statement.order_by(PromotionModel.valid_to, SourceProductModel.name)
        .offset(offset)
        .limit(limit)
    ).all()
    items = [
        _promotion_item(promotion, product=product, source=source, store=store)
        for promotion, product, source, store in rows
    ]
    chains = {item["chain"] for item in items} | _chains_for_stores(session, store_ids)
    if chain is not None:
        chains.add(chain.value)
    snapshot_ids = {item["snapshot_id"] for item in items if item["snapshot_id"] is not None}
    snapshot_ids.update(_snapshot_ids_for_stores(session, store_ids))
    metadata = collection_metadata(session, chains, snapshot_ids=snapshot_ids)
    return {
        "items": items,
        "offers": items,
        "count": len(items),
        "offset": offset,
        **metadata,
    }
