from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from grocery_data.app.api.dependencies import get_session
from grocery_data.app.services.ica_recipe_coverage import (
    RecipeQueryCoverageBenchmark,
    route_yields,
)
from grocery_data.app.services.ica_registry import IcaProductRegistry
from grocery_data.app.storage.models import (
    IcaDiscoveryEventModel,
    IcaEnrichmentRunModel,
    IcaProductRegistryModel,
    IcaStoreProductObservationModel,
    StoreModel,
)

router = APIRouter(prefix="/registry/ica", tags=["ica-registry"])
SessionDep = Annotated[Session, Depends(get_session)]


class BasketCoverageRequest(BaseModel):
    canonical_foods: list[str] = Field(min_length=1, max_length=100)
    max_price_age_days: int = Field(default=7, ge=0, le=90)


def _ica_store(session: SessionDep, store_id: str) -> StoreModel:
    store = session.get(StoreModel, store_id)
    if store is None or store.chain != "ica":
        raise HTTPException(status_code=404, detail="ICA store not found")
    return store


@router.get("/stores/{store_id}/stats")
def registry_stats(store_id: str, session: SessionDep) -> dict:
    store = _ica_store(session, store_id)
    enrichment = session.scalar(
        select(IcaEnrichmentRunModel)
        .where(IcaEnrichmentRunModel.store_id == store.id)
        .order_by(IcaEnrichmentRunModel.finished_at.desc())
        .limit(1)
    )
    return {
        "store_id": store.id,
        "store_external_id": store.external_id,
        "coverage": store.coverage,
        "registry": IcaProductRegistry(session).stats(store.id),
        "ssr_enrichment": None
        if enrichment is None
        else {
            "status": enrichment.status,
            "challenge_encountered": enrichment.challenge_encountered,
            "pages_visited": enrichment.pages_visited,
            "product_ids_seen": enrichment.product_ids_seen,
            "price_observations": enrichment.price_observations,
            "finished_at": enrichment.finished_at,
        },
    }


@router.post("/stores/{store_id}/basket-coverage")
def basket_coverage(
    store_id: str,
    request: BasketCoverageRequest,
    session: SessionDep,
) -> dict:
    store = _ica_store(session, store_id)
    result = IcaProductRegistry(session).basket_coverage(
        store.id,
        request.canonical_foods,
        max_price_age_days=request.max_price_age_days,
    )
    return result.model_dump()


@router.get("/stores/{store_id}/recipe-coverage")
def recipe_coverage(
    store_id: str,
    session: SessionDep,
    max_price_age_days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> dict:
    store = _ica_store(session, store_id)
    report = RecipeQueryCoverageBenchmark(session).run(
        store.id,
        max_price_age_days=max_price_age_days,
    )
    return {
        **report.model_dump(mode="json"),
        "global_coverage": store.coverage,
        "capability": "query_complete_capable" if report.coverage_ratio >= 0.95 else "incremental",
        "route_yields": [
            {
                **item.model_dump(mode="json"),
                "ids_per_page": item.ids_per_page,
                "priced_products_per_page": item.priced_products_per_page,
            }
            for item in route_yields(session, store.id)
        ],
    }


@router.get("/products/{product_id}")
def registry_product(product_id: str, session: SessionDep) -> dict:
    product = session.scalar(
        select(IcaProductRegistryModel).where(
            IcaProductRegistryModel.external_product_id == product_id
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="ICA registry product not found")
    events = list(
        session.scalars(
            select(IcaDiscoveryEventModel)
            .where(IcaDiscoveryEventModel.registry_product_id == product.id)
            .order_by(IcaDiscoveryEventModel.observed_at)
        )
    )
    observations = list(
        session.scalars(
            select(IcaStoreProductObservationModel)
            .where(IcaStoreProductObservationModel.registry_product_id == product.id)
            .order_by(IcaStoreProductObservationModel.observed_at.desc())
            .limit(100)
        )
    )
    now = datetime.now(tz=UTC)
    return {
        "external_product_id": product.external_product_id,
        "gtin": product.gtin,
        "name": product.name,
        "brand": product.brand,
        "package_text": product.package_text,
        "category_path": product.category_path,
        "canonical_food": product.canonical_food,
        "metadata_level": product.metadata_level,
        "active_state": product.active_state,
        "first_seen_at": product.first_seen_at,
        "last_seen_at": product.last_seen_at,
        "metadata_age_days": (now - product.last_seen_at).total_seconds() / 86400,
        "discovery_history": [
            {
                "source": event.source,
                "source_page": event.source_page,
                "observed_at": event.observed_at,
                "raw_snapshot_id": event.raw_snapshot_id,
            }
            for event in events
        ],
        "price_observations": [
            {
                "store_id": row.store_id,
                "sale_price": float(row.sale_price) if row.sale_price is not None else None,
                "comparison_price": (
                    float(row.comparison_price) if row.comparison_price is not None else None
                ),
                "comparison_unit": row.comparison_unit,
                "observed_at": row.observed_at,
                "price_age_days": (now - row.observed_at).total_seconds() / 86400,
                "sale_model": row.sale_model,
                "quantity_confidence": row.quantity_confidence,
            }
            for row in observations
        ],
    }
