from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from grocery_data.app.domain import Confidence, SaleModel
from grocery_data.app.services.ica_recipe_coverage import (
    RECIPE_QUERY_ALIASES,
    RECIPE_RELEVANT_INGREDIENTS,
    CoverageFailureReason,
    IngredientCoverageRow,
    RecipeRelevantIngredient,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    ParserFailureModel,
    PriceObservationModel,
    ProductModel,
    StoreModel,
)

ACCEPTED_SEMANTIC_CONFIDENCES = frozenset(
    {Confidence.EXACT.value, Confidence.HIGH.value, Confidence.MEDIUM.value}
)
ACCEPTED_QUANTITY_CONFIDENCES = frozenset(
    {Confidence.EXACT.value, Confidence.DERIVED.value, Confidence.ESTIMATED.value}
)

# This is a benchmark basket selected from the existing canonical ingredient set,
# not a second taxonomy. Keep the source names exactly aligned with that set.
REPRESENTATIVE_RECIPE_BASKET: tuple[str, ...] = (
    "milk",
    "eggs",
    "potato",
    "ris",
    "pasta",
    "chicken_meat",
    "minced_beef",
    "yellow_onion",
    "carrot",
    "red_lentils",
    "krossade_tomater",
    "cheese",
    "creme_fraiche",
)


class RepresentativeBasketCoverage(BaseModel):
    requested_ingredients: int
    safely_priced_ingredients: int
    coverage_ratio: float = Field(ge=0, le=1)
    complete_for_request: bool
    missing_ingredients: list[str] = Field(default_factory=list)
    failure_reasons: dict[str, list[CoverageFailureReason]] = Field(default_factory=dict)


class CatalogRecipeCoverageReport(BaseModel):
    snapshot_id: str
    store_id: str
    store_external_id: str
    chain: str
    max_price_age_days: int
    evaluated_at: datetime
    price_cutoff_at: datetime
    ingredients: list[IngredientCoverageRow]
    at_least_one: int
    at_least_three: int
    at_least_five: int
    coverage_ratio: float = Field(ge=0, le=1)
    representative_basket: RepresentativeBasketCoverage


@dataclass(frozen=True, slots=True)
class _Candidate:
    product: ProductModel
    price: PriceObservationModel | None
    quarantined: bool


def _positive_price(price: PriceObservationModel | None) -> bool:
    return price is not None and price.sale_price is not None and Decimal(price.sale_price) > 0


def _quarantined_product_ids(failures: list[ParserFailureModel]) -> set[str]:
    result: set[str] = set()
    for failure in failures:
        sample = failure.sample if isinstance(failure.sample, dict) else {}
        for key in ("external_product_id", "product_id", "id"):
            value = str(sample.get(key) or "").strip()
            if value:
                result.add(value)
    return result


class CatalogRecipeCoverageBenchmark:
    """Measure recipe usability from one persisted candidate catalog snapshot.

    Product identity and semantics come from normalized ``ProductModel`` rows,
    while freshness and positivity are checked only against the matching
    store-specific ``PriceObservationModel``. Candidate snapshots need not be
    active or promoted, which makes this suitable for pre-promotion validation.
    """

    ingredient_set = RECIPE_RELEVANT_INGREDIENTS
    query_aliases = RECIPE_QUERY_ALIASES
    representative_basket = REPRESENTATIVE_RECIPE_BASKET

    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        snapshot_id: str,
        store_id: str,
        *,
        ingredients: tuple[RecipeRelevantIngredient, ...] = RECIPE_RELEVANT_INGREDIENTS,
        representative_basket: tuple[str, ...] = REPRESENTATIVE_RECIPE_BASKET,
        max_price_age_days: int = 7,
        now: datetime | None = None,
        accepted_semantic_confidences: frozenset[str] = ACCEPTED_SEMANTIC_CONFIDENCES,
        accepted_quantity_confidences: frozenset[str] = ACCEPTED_QUANTITY_CONFIDENCES,
    ) -> CatalogRecipeCoverageReport:
        if max_price_age_days < 0:
            raise ValueError("max_price_age_days must be non-negative")
        evaluated_at = now or datetime.now(tz=UTC)
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        evaluated_at = evaluated_at.astimezone(UTC)
        cutoff = evaluated_at - timedelta(days=max_price_age_days)

        snapshot = self.session.get(CatalogSnapshotModel, snapshot_id)
        store = self.session.get(StoreModel, store_id)
        if snapshot is None:
            raise LookupError(f"catalog snapshot {snapshot_id!r} does not exist")
        if store is None:
            raise LookupError(f"store {store_id!r} does not exist")
        if snapshot.chain != store.chain:
            raise ValueError("candidate snapshot and store must belong to the same chain")

        requested = tuple(ingredients)
        requested_names = tuple(item.canonical for item in requested)
        benchmark_names = tuple(dict.fromkeys((*requested_names, *representative_basket)))
        unknown_names = set(benchmark_names).difference(RECIPE_QUERY_ALIASES)
        if unknown_names:
            raise ValueError(
                "benchmark ingredients must come from RECIPE_RELEVANT_INGREDIENTS: "
                + ", ".join(sorted(unknown_names))
            )

        rows = self.session.execute(
            select(ProductModel, PriceObservationModel)
            .outerjoin(
                PriceObservationModel,
                and_(
                    PriceObservationModel.product_id == ProductModel.id,
                    PriceObservationModel.catalog_snapshot_id == snapshot_id,
                    PriceObservationModel.store_id == store_id,
                ),
            )
            .where(
                ProductModel.catalog_snapshot_id == snapshot_id,
                ProductModel.store_id == store_id,
                ProductModel.chain == snapshot.chain,
                ProductModel.store_external_id == store.external_id,
                ProductModel.canonical_food.in_(benchmark_names),
            )
            .order_by(ProductModel.observed_at.desc(), ProductModel.id)
        ).all()
        failures = list(
            self.session.scalars(
                select(ParserFailureModel).where(
                    ParserFailureModel.catalog_snapshot_id == snapshot_id,
                    ParserFailureModel.store_external_id == store.external_id,
                )
            )
        )
        quarantined_references = {failure.raw_record_reference for failure in failures}
        quarantined_external_ids = _quarantined_product_ids(failures)

        by_ingredient: dict[str, dict[str, _Candidate]] = {name: {} for name in benchmark_names}
        for product, price in rows:
            canonical = product.canonical_food
            if canonical not in by_ingredient:
                continue
            identity = product.source_product_key or product.id
            # Rows are newest first, so replayed normalizer variants cannot
            # inflate candidate counts for one source identity.
            if identity in by_ingredient[canonical]:
                continue
            by_ingredient[canonical][identity] = _Candidate(
                product=product,
                price=price,
                quarantined=(
                    product.raw_reference in quarantined_references
                    or bool(
                        product.external_product_id
                        and product.external_product_id in quarantined_external_ids
                    )
                ),
            )

        coverage_by_name = {
            name: self._coverage_row(
                name,
                list(by_ingredient[name].values()),
                cutoff=cutoff,
                evaluated_at=evaluated_at,
                accepted_semantic_confidences=accepted_semantic_confidences,
                accepted_quantity_confidences=accepted_quantity_confidences,
            )
            for name in benchmark_names
        }
        ingredient_rows = [coverage_by_name[name] for name in requested_names]
        basket_rows = [coverage_by_name[name] for name in representative_basket]
        safely_priced = sum(row.usable_candidates >= 1 for row in basket_rows)
        missing = [row.ingredient for row in basket_rows if row.usable_candidates == 0]
        basket_failures = {
            row.ingredient: row.failure_reasons for row in basket_rows if row.failure_reasons
        }
        at_least_one = sum(row.usable_candidates >= 1 for row in ingredient_rows)
        return CatalogRecipeCoverageReport(
            snapshot_id=snapshot.id,
            store_id=store.id,
            store_external_id=store.external_id,
            chain=store.chain,
            max_price_age_days=max_price_age_days,
            evaluated_at=evaluated_at,
            price_cutoff_at=cutoff,
            ingredients=ingredient_rows,
            at_least_one=at_least_one,
            at_least_three=sum(row.usable_candidates >= 3 for row in ingredient_rows),
            at_least_five=sum(row.usable_candidates >= 5 for row in ingredient_rows),
            coverage_ratio=(at_least_one / len(ingredient_rows) if ingredient_rows else 1.0),
            representative_basket=RepresentativeBasketCoverage(
                requested_ingredients=len(basket_rows),
                safely_priced_ingredients=safely_priced,
                coverage_ratio=safely_priced / len(basket_rows) if basket_rows else 1.0,
                complete_for_request=safely_priced == len(basket_rows),
                missing_ingredients=missing,
                failure_reasons=basket_failures,
            ),
        )

    @staticmethod
    def _coverage_row(
        ingredient: str,
        candidates: list[_Candidate],
        *,
        cutoff: datetime,
        evaluated_at: datetime,
        accepted_semantic_confidences: frozenset[str],
        accepted_quantity_confidences: frozenset[str],
    ) -> IngredientCoverageRow:
        positive = [candidate for candidate in candidates if _positive_price(candidate.price)]
        fresh = [
            candidate
            for candidate in positive
            if candidate.price is not None and cutoff <= candidate.price.observed_at <= evaluated_at
        ]
        quality_candidates = [candidate for candidate in fresh if not candidate.quarantined]
        usable = [
            candidate
            for candidate in quality_candidates
            if candidate.product.sale_model != SaleModel.UNKNOWN.value
            and candidate.product.semantic_confidence in accepted_semantic_confidences
            and candidate.product.quantity_confidence in accepted_quantity_confidences
        ]

        reasons: list[CoverageFailureReason] = []
        if not candidates:
            reasons.append(CoverageFailureReason.NO_PRODUCT_IDS)
        elif not any(not candidate.quarantined for candidate in candidates):
            reasons.append(CoverageFailureReason.QUARANTINED)
        elif not any(
            _positive_price(candidate.price)
            for candidate in candidates
            if not candidate.quarantined
        ):
            reasons.append(CoverageFailureReason.NO_STORE_PRICE)
        elif not quality_candidates:
            reasons.append(CoverageFailureReason.STALE_PRICE)
        elif not usable:
            if any(
                candidate.product.sale_model == SaleModel.UNKNOWN.value
                for candidate in quality_candidates
            ):
                reasons.append(CoverageFailureReason.UNKNOWN_PURCHASE_MODEL)
            if any(
                candidate.product.semantic_confidence not in accepted_semantic_confidences
                for candidate in quality_candidates
            ):
                reasons.append(CoverageFailureReason.SEMANTIC_REJECTION)
            if any(
                candidate.product.quantity_confidence not in accepted_quantity_confidences
                for candidate in quality_candidates
            ):
                reasons.append(CoverageFailureReason.UNKNOWN_QUANTITY)

        usable_count = len(usable)
        level = 3 if usable_count >= 5 else 2 if usable_count >= 3 else 1 if usable_count else 0
        return IngredientCoverageRow(
            ingredient=ingredient,
            known_candidates=len(candidates),
            fresh_candidates=len(fresh),
            usable_candidates=usable_count,
            coverage_level=level,
            failure_reasons=reasons,
        )
