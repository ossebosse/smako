from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain import (
    RECIPE_RELEVANT_INGREDIENTS,
    RecipeRelevantIngredient,
)
from grocery_data.app.domain.recipe import RECIPE_QUERY_ALIASES as _RECIPE_QUERY_ALIASES
from grocery_data.app.storage.models import (
    IcaDiscoveryEventModel,
    IcaProductRegistryModel,
    IcaStoreProductObservationModel,
)

# Backwards-compatible service-level export; the authoritative vocabulary now
# lives in the domain layer and is shared with ProductNormalizer.
RECIPE_QUERY_ALIASES = _RECIPE_QUERY_ALIASES


class CoverageFailureReason(StrEnum):
    NO_PRODUCT_IDS = "no_product_ids"
    STALE_PRICE = "stale_price"
    UNKNOWN_QUANTITY = "unknown_quantity"
    SEMANTIC_REJECTION = "semantic_rejection"
    NO_STORE_PRICE = "no_store_price"
    UNKNOWN_PURCHASE_MODEL = "unknown_purchase_model"
    QUARANTINED = "quarantined"
    CHALLENGE_BEFORE_ENRICHMENT = "challenge_before_enrichment"


class IngredientCoverageRow(BaseModel):
    ingredient: str
    known_candidates: int
    fresh_candidates: int
    usable_candidates: int
    coverage_level: int = Field(ge=0, le=3)
    failure_reasons: list[CoverageFailureReason] = Field(default_factory=list)


class RecipeCoverageReport(BaseModel):
    store_id: str
    max_price_age_days: int
    ingredients: list[IngredientCoverageRow]
    at_least_one: int
    at_least_three: int
    at_least_five: int
    coverage_ratio: float


class RouteYieldReport(BaseModel):
    route_type: str
    pages: int
    product_ids: int
    full_products: int
    priced_products: int
    gtin_products: int = 0
    package_products: int = 0
    challenge_encountered: bool = False

    @property
    def ids_per_page(self) -> float:
        return self.product_ids / self.pages if self.pages else 0.0

    @property
    def priced_products_per_page(self) -> float:
        return self.priced_products / self.pages if self.pages else 0.0


class RecipeQueryCoverageBenchmark:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        store_id: str,
        *,
        ingredients: tuple[RecipeRelevantIngredient, ...] = RECIPE_RELEVANT_INGREDIENTS,
        max_price_age_days: int = 7,
        now: datetime | None = None,
    ) -> RecipeCoverageReport:
        now = now or datetime.now(tz=UTC)
        cutoff = now - timedelta(days=max_price_age_days)
        safe_semantic = {"exact", "high", "medium"}
        safe_quantity = {"exact", "derived", "estimated"}
        result: list[IngredientCoverageRow] = []
        for ingredient in ingredients:
            product_ids = list(
                self.session.scalars(
                    select(IcaProductRegistryModel.id)
                    .join(
                        IcaDiscoveryEventModel,
                        IcaDiscoveryEventModel.registry_product_id == IcaProductRegistryModel.id,
                    )
                    .where(
                        IcaDiscoveryEventModel.store_id == store_id,
                        IcaProductRegistryModel.canonical_food == ingredient.canonical,
                    )
                    .distinct()
                )
            )
            observation_rows = list(
                self.session.execute(
                    select(
                        IcaStoreProductObservationModel.registry_product_id,
                        IcaStoreProductObservationModel.sale_price,
                        IcaStoreProductObservationModel.observed_at,
                        IcaStoreProductObservationModel.semantic_confidence,
                        IcaStoreProductObservationModel.quantity_confidence,
                    )
                    .join(
                        IcaProductRegistryModel,
                        IcaProductRegistryModel.id
                        == IcaStoreProductObservationModel.registry_product_id,
                    )
                    .where(
                        IcaStoreProductObservationModel.store_id == store_id,
                        IcaStoreProductObservationModel.registry_product_id.in_(product_ids),
                    )
                    .order_by(IcaStoreProductObservationModel.observed_at.desc())
                )
            )
            latest_by_product = {}
            for row in observation_rows:
                latest_by_product.setdefault(row.registry_product_id, row)
            observations = list(latest_by_product.values())
            known = len(product_ids)
            fresh_rows = [
                row for row in observations if row.sale_price and row.observed_at >= cutoff
            ]
            usable = [
                row
                for row in fresh_rows
                if row.semantic_confidence in safe_semantic
                and row.quantity_confidence in safe_quantity
            ]
            reasons: list[CoverageFailureReason] = []
            if not known:
                reasons.append(CoverageFailureReason.NO_PRODUCT_IDS)
            elif not fresh_rows:
                reasons.append(CoverageFailureReason.STALE_PRICE)
            elif not any(row.quantity_confidence in safe_quantity for row in fresh_rows):
                reasons.append(CoverageFailureReason.UNKNOWN_QUANTITY)
            elif not any(row.semantic_confidence in safe_semantic for row in fresh_rows):
                reasons.append(CoverageFailureReason.SEMANTIC_REJECTION)
            usable_count = len(usable)
            level = 3 if usable_count >= 5 else 2 if usable_count >= 3 else 1 if usable_count else 0
            result.append(
                IngredientCoverageRow(
                    ingredient=ingredient.canonical,
                    known_candidates=known,
                    fresh_candidates=len(fresh_rows),
                    usable_candidates=usable_count,
                    coverage_level=level,
                    failure_reasons=reasons,
                )
            )
        one = sum(row.usable_candidates >= 1 for row in result)
        return RecipeCoverageReport(
            store_id=store_id,
            max_price_age_days=max_price_age_days,
            ingredients=result,
            at_least_one=one,
            at_least_three=sum(row.usable_candidates >= 3 for row in result),
            at_least_five=sum(row.usable_candidates >= 5 for row in result),
            coverage_ratio=one / len(result) if result else 1.0,
        )


def route_yields(session: Session, store_id: str) -> list[RouteYieldReport]:
    rows = session.execute(
        select(
            IcaDiscoveryEventModel.source,
            func.count(func.distinct(IcaDiscoveryEventModel.source_page)),
            func.count(func.distinct(IcaDiscoveryEventModel.registry_product_id)),
        )
        .where(IcaDiscoveryEventModel.store_id == store_id)
        .group_by(IcaDiscoveryEventModel.source)
    )
    reports = []
    for source, pages, product_ids in rows:
        reports.append(
            RouteYieldReport(
                route_type=source,
                pages=pages,
                product_ids=product_ids,
                full_products=0,
                priced_products=0,
            )
        )
    return reports
