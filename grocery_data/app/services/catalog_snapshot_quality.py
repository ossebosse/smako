from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from grocery_data.app.domain import CatalogCompletion, RunMetrics, SaleModel
from grocery_data.app.services.purchase_model_analysis import is_recipe_relevant
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    ParserFailureModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreModel,
)

_GTIN_LENGTHS = frozenset({8, 12, 13, 14})
_MAX_MANUAL_SAMPLES = 100


def _percent(part: int, whole: int) -> Decimal:
    if whole == 0:
        return Decimal("0.00")
    return (Decimal(part) * Decimal(100) / Decimal(whole)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _positive(value: Decimal | None) -> bool:
    return value is not None and Decimal(value) > 0


def _distribution(values: list[str]) -> dict[str, int]:
    counts = Counter(value or "(missing)" for value in values)
    return dict(sorted(counts.items()))


def _raw_gtin(source: SourceProductModel) -> str | None:
    source_fields = source.source_fields if isinstance(source.source_fields, dict) else {}
    value = source_fields.get("raw_gtin")
    if value is None:
        value = source.gtin
    if isinstance(value, (str, int)):
        normalized = str(value).strip()
        return normalized or None
    return None


def is_valid_gtin(value: str | None) -> bool:
    """Validate GTIN-8/12/13/14 without guessing or zero-padding source IDs."""

    if value is None or len(value) not in _GTIN_LENGTHS or not value.isascii():
        return False
    if not value.isdigit():
        return False
    body, supplied_check_digit = value[:-1], int(value[-1])
    weighted_sum = sum(
        int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(body))
    )
    expected_check_digit = (10 - (weighted_sum % 10)) % 10
    return supplied_check_digit == expected_check_digit


class ProductQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    products: int = Field(ge=0)
    products_with_price: int = Field(ge=0)
    price_coverage_percent: Decimal = Field(ge=0, le=100)
    products_with_regular_price: int = Field(ge=0)
    regular_price_coverage_percent: Decimal = Field(ge=0, le=100)
    products_with_raw_gtin: int = Field(ge=0)
    raw_gtin_coverage_percent: Decimal = Field(ge=0, le=100)
    products_with_valid_gtin: int = Field(ge=0)
    valid_gtin_coverage_percent: Decimal = Field(ge=0, le=100)
    valid_gtin_percent_of_raw: Decimal = Field(ge=0, le=100)
    products_with_package_quantity: int = Field(ge=0)
    package_quantity_coverage_percent: Decimal = Field(ge=0, le=100)
    products_with_resolved_purchase_model: int = Field(ge=0)
    resolved_purchase_model_percent: Decimal = Field(ge=0, le=100)
    quantity_confidence_distribution: dict[str, int]
    products_with_availability: int = Field(ge=0)
    availability_coverage_percent: Decimal = Field(ge=0, le=100)


class PromotionQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    promotions: int = Field(ge=0)
    promoted_products: int = Field(ge=0)
    type_distribution: dict[str, int]
    member_only: int = Field(ge=0)
    multibuy: int = Field(ge=0)
    member_multibuy: int = Field(ge=0)
    with_max_quantity: int = Field(ge=0)
    max_quantity_distribution: dict[str, int]
    with_valid_from: int = Field(ge=0)
    with_valid_to: int = Field(ge=0)
    with_complete_validity_period: int = Field(ge=0)


class RawPayloadQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_payloads: int = Field(ge=0)
    snapshot_bytes: int = Field(ge=0)
    selected_store_payloads: int = Field(ge=0)
    selected_store_bytes: int = Field(ge=0)
    http_status_distribution: dict[str, int]
    captured_http_errors: int = Field(ge=0)
    captured_429_responses: int = Field(ge=0)


class TransportQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    collector_run_id: str | None
    run_status: str | None
    run_successful: bool | None
    run_metrics_present: bool
    run_metrics_valid: bool
    request_count: int = Field(ge=0)
    http_error_count: int = Field(ge=0)
    rate_limit_count: int = Field(ge=0)
    runtime_ms: int = Field(ge=0)
    wall_clock_runtime_ms: int | None = Field(default=None, ge=0)


class CompletionEvidenceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_external_id: str
    present: bool
    valid: bool
    full_traversal_proven: bool
    complete: bool | None = None
    limited: bool | None = None
    expected_categories: int | None = None
    completed_categories: int | None = None
    pages_fetched: int | None = None
    products_observed: int | None = None
    expected_products: int | None = None
    raw_rows: int | None = None
    unique_products: int | None = None
    duplicate_products: int | None = None
    within_partition_duplicates: int | None = None
    cross_partition_duplicates: int | None = None
    exact_duplicates_removed: int | None = None
    conflicting_duplicates: int | None = None
    pagination_overlaps: int | None = None
    expected_pages: int | None = None
    reason: str | None = None
    validation_error: str | None = None


class QuarantineQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_failures: int = Field(ge=0)
    selected_store_failures: int = Field(ge=0)
    selected_store_code_distribution: dict[str, int]


class ManualProductSample(BaseModel):
    """A bounded diagnostic row that deliberately excludes raw/session lineage."""

    model_config = ConfigDict(frozen=True)

    external_product_id: str | None
    gtin: str | None
    name: str
    brand: str | None
    category_path: list[str]
    canonical_food: str | None
    sale_model: str
    semantic_confidence: str
    quantity_confidence: str
    package_quantity: Decimal | None
    package_unit: str | None
    usable_quantity: Decimal | None
    usable_unit: str | None
    sale_price: Decimal | None
    regular_price: Decimal | None
    member_price: Decimal | None
    comparison_price: Decimal | None
    comparison_unit: str | None
    sale_unit: str | None
    availability: str | None
    promotion_types: list[str]


class CatalogSnapshotQualityReport(BaseModel):
    """Offline quality evidence for one persisted snapshot/store pair."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    store_id: str
    store_external_id: str
    chain: str
    snapshot_state: str
    snapshot_coverage: str
    normalized_rows: int = Field(ge=0)
    overall: ProductQualitySummary
    recipe_relevant: ProductQualitySummary
    recipe_relevant_classification: str = "broad category diagnostic only"
    promotions: PromotionQualitySummary
    raw_payloads: RawPayloadQualitySummary
    transport: TransportQualitySummary
    completion: CompletionEvidenceSummary
    quarantine: QuarantineQualitySummary
    manual_samples: list[ManualProductSample]


@dataclass(frozen=True, slots=True)
class _ProductRow:
    product: ProductModel
    source: SourceProductModel
    price: PriceObservationModel | None


def _deduplicate(rows: list[_ProductRow]) -> list[_ProductRow]:
    products: dict[str, _ProductRow] = {}
    for row in rows:
        identity = row.product.source_product_key or row.product.id
        products.setdefault(identity, row)
    return list(products.values())


def _quality(rows: list[_ProductRow]) -> ProductQualitySummary:
    total = len(rows)
    raw_gtins = [_raw_gtin(row.source) for row in rows]
    raw_gtin_count = sum(value is not None for value in raw_gtins)
    valid_gtin_count = sum(is_valid_gtin(value) for value in raw_gtins)
    with_price = sum(row.price is not None and _positive(row.price.sale_price) for row in rows)
    with_regular_price = sum(
        row.price is not None and _positive(row.price.regular_price) for row in rows
    )
    with_package_quantity = sum(_positive(row.product.package_quantity) for row in rows)
    with_resolved_model = sum(row.product.sale_model != SaleModel.UNKNOWN.value for row in rows)
    with_availability = sum(bool(str(row.product.availability or "").strip()) for row in rows)
    return ProductQualitySummary(
        products=total,
        products_with_price=with_price,
        price_coverage_percent=_percent(with_price, total),
        products_with_regular_price=with_regular_price,
        regular_price_coverage_percent=_percent(with_regular_price, total),
        products_with_raw_gtin=raw_gtin_count,
        raw_gtin_coverage_percent=_percent(raw_gtin_count, total),
        products_with_valid_gtin=valid_gtin_count,
        valid_gtin_coverage_percent=_percent(valid_gtin_count, total),
        valid_gtin_percent_of_raw=_percent(valid_gtin_count, raw_gtin_count),
        products_with_package_quantity=with_package_quantity,
        package_quantity_coverage_percent=_percent(with_package_quantity, total),
        products_with_resolved_purchase_model=with_resolved_model,
        resolved_purchase_model_percent=_percent(with_resolved_model, total),
        quantity_confidence_distribution=_distribution(
            [row.product.quantity_confidence for row in rows]
        ),
        products_with_availability=with_availability,
        availability_coverage_percent=_percent(with_availability, total),
    )


def category_stratified_manual_sample(
    samples: list[ManualProductSample], *, max_samples: int
) -> list[ManualProductSample]:
    """Choose a bounded deterministic round-robin sample across source categories."""

    if max_samples < 0 or max_samples > _MAX_MANUAL_SAMPLES:
        raise ValueError(f"max_samples must be between 0 and {_MAX_MANUAL_SAMPLES}")
    buckets: dict[str, list[ManualProductSample]] = defaultdict(list)
    for sample in samples:
        category = (
            str(sample.category_path[0]).strip() if sample.category_path else "(uncategorized)"
        )
        buckets[category].append(sample)
    for bucket_samples in buckets.values():
        bucket_samples.sort(
            key=lambda sample: (
                sample.name.casefold(),
                str(sample.external_product_id or ""),
                str(sample.gtin or ""),
            )
        )

    selected: list[ManualProductSample] = []
    category_names = sorted(buckets, key=lambda value: (value.casefold(), value))
    depth = 0
    while len(selected) < max_samples:
        appended = False
        for category in category_names:
            bucket = buckets[category]
            if depth >= len(bucket):
                continue
            selected.append(bucket[depth])
            appended = True
            if len(selected) == max_samples:
                break
        if not appended:
            break
        depth += 1

    return selected


def _safe_manual_samples(
    rows: list[_ProductRow], promotion_types_by_product: dict[str, list[str]]
) -> list[ManualProductSample]:
    return [
        ManualProductSample(
            external_product_id=row.product.external_product_id,
            gtin=row.product.gtin if is_valid_gtin(row.product.gtin) else None,
            name=row.product.name,
            brand=row.product.brand,
            category_path=list(row.product.category_path or []),
            canonical_food=row.product.canonical_food,
            sale_model=row.product.sale_model,
            semantic_confidence=row.product.semantic_confidence,
            quantity_confidence=row.product.quantity_confidence,
            package_quantity=row.product.package_quantity,
            package_unit=row.product.package_unit,
            usable_quantity=row.product.usable_quantity,
            usable_unit=row.product.usable_unit,
            sale_price=row.price.sale_price if row.price is not None else None,
            regular_price=row.price.regular_price if row.price is not None else None,
            member_price=row.price.member_price if row.price is not None else None,
            comparison_price=(row.price.comparison_price if row.price is not None else None),
            comparison_unit=(row.price.comparison_unit if row.price is not None else None),
            sale_unit=row.price.sale_unit if row.price is not None else None,
            availability=row.product.availability,
            promotion_types=promotion_types_by_product.get(row.product.id, []),
        )
        for row in rows
    ]


def _completion(
    snapshot: CatalogSnapshotModel, store_external_id: str
) -> CompletionEvidenceSummary:
    metrics = snapshot.metrics if isinstance(snapshot.metrics, dict) else {}
    completion_by_store = metrics.get("catalog_completion")
    if not isinstance(completion_by_store, dict) or store_external_id not in completion_by_store:
        return CompletionEvidenceSummary(
            store_external_id=store_external_id,
            present=False,
            valid=False,
            full_traversal_proven=False,
        )
    raw = completion_by_store[store_external_id]
    try:
        evidence = CatalogCompletion.model_validate(raw)
    except (TypeError, ValueError):
        return CompletionEvidenceSummary(
            store_external_id=store_external_id,
            present=True,
            valid=False,
            full_traversal_proven=False,
            validation_error="invalid_catalog_completion_evidence",
        )
    return CompletionEvidenceSummary(
        store_external_id=store_external_id,
        present=True,
        valid=True,
        full_traversal_proven=evidence.is_full_traversal,
        complete=evidence.complete,
        limited=evidence.limited,
        expected_categories=evidence.expected_categories,
        completed_categories=evidence.completed_categories,
        pages_fetched=evidence.pages_fetched,
        products_observed=evidence.products_observed,
        expected_products=evidence.expected_products,
        raw_rows=evidence.raw_rows,
        unique_products=evidence.unique_products,
        duplicate_products=evidence.duplicate_products,
        within_partition_duplicates=evidence.within_partition_duplicates,
        cross_partition_duplicates=evidence.cross_partition_duplicates,
        exact_duplicates_removed=evidence.exact_duplicates_removed,
        conflicting_duplicates=evidence.conflicting_duplicates,
        pagination_overlaps=evidence.pagination_overlaps,
        expected_pages=evidence.expected_pages,
        reason=evidence.reason,
    )


def _transport(
    snapshot: CatalogSnapshotModel,
    run: CollectorRunModel | None,
) -> TransportQualitySummary:
    snapshot_metrics = snapshot.metrics if isinstance(snapshot.metrics, dict) else {}
    raw_metrics: Any = snapshot_metrics.get("run_metrics")
    if not isinstance(raw_metrics, dict) and run is not None:
        raw_metrics = run.metrics
    metrics_present = isinstance(raw_metrics, dict)
    try:
        metrics = RunMetrics.model_validate(raw_metrics if metrics_present else {})
        metrics_valid = metrics_present
    except (TypeError, ValueError):
        metrics = RunMetrics()
        metrics_valid = False

    wall_clock_runtime_ms: int | None = None
    if run is not None and run.finished_at is not None:
        elapsed = run.finished_at - run.started_at
        wall_clock_runtime_ms = max(0, round(elapsed.total_seconds() * 1000))
    return TransportQualitySummary(
        collector_run_id=run.id if run is not None else snapshot.collector_run_id,
        run_status=run.status if run is not None else None,
        run_successful=run.successful if run is not None else None,
        run_metrics_present=metrics_present,
        run_metrics_valid=metrics_valid,
        request_count=metrics.request_count,
        http_error_count=metrics.http_error_count,
        rate_limit_count=metrics.rate_limit_count,
        runtime_ms=metrics.runtime_ms,
        wall_clock_runtime_ms=wall_clock_runtime_ms,
    )


class CatalogSnapshotQualityReporter:
    """Build an evidence-backed report without network or raw-payload reads."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        snapshot_id: str,
        store_id: str,
        *,
        max_manual_samples: int = 20,
    ) -> CatalogSnapshotQualityReport:
        if max_manual_samples < 0 or max_manual_samples > _MAX_MANUAL_SAMPLES:
            raise ValueError(f"max_manual_samples must be between 0 and {_MAX_MANUAL_SAMPLES}")
        snapshot = self.session.get(CatalogSnapshotModel, snapshot_id)
        store = self.session.get(StoreModel, store_id)
        if snapshot is None:
            raise LookupError(f"catalog snapshot {snapshot_id!r} does not exist")
        if store is None:
            raise LookupError(f"store {store_id!r} does not exist")
        if snapshot.chain != store.chain:
            raise ValueError("catalog snapshot and store must belong to the same chain")

        database_rows = self.session.execute(
            select(ProductModel, SourceProductModel, PriceObservationModel)
            .join(SourceProductModel, SourceProductModel.id == ProductModel.source_product_id)
            .outerjoin(
                PriceObservationModel,
                and_(
                    PriceObservationModel.product_id == ProductModel.id,
                    PriceObservationModel.catalog_snapshot_id == snapshot.id,
                    PriceObservationModel.store_id == store.id,
                ),
            )
            .where(
                ProductModel.catalog_snapshot_id == snapshot.id,
                ProductModel.store_id == store.id,
                ProductModel.chain == snapshot.chain,
                ProductModel.store_external_id == store.external_id,
            )
            .order_by(
                ProductModel.observed_at.desc(), ProductModel.created_at.desc(), ProductModel.id
            )
        ).all()
        normalized_rows = len(database_rows)
        rows = _deduplicate(
            [
                _ProductRow(product=product, source=source, price=price)
                for product, source, price in database_rows
            ]
        )

        promotions = list(
            self.session.scalars(
                select(PromotionModel)
                .where(
                    PromotionModel.catalog_snapshot_id == snapshot.id,
                    PromotionModel.store_id == store.id,
                )
                .order_by(PromotionModel.type, PromotionModel.id)
            )
        )
        promotion_types_by_product: dict[str, list[str]] = defaultdict(list)
        for promotion in promotions:
            if promotion.product_id is not None:
                promotion_types_by_product[promotion.product_id].append(promotion.type)
        for types in promotion_types_by_product.values():
            types.sort()

        raw_rows = list(
            self.session.scalars(
                select(RawSnapshotModel)
                .where(RawSnapshotModel.catalog_snapshot_id == snapshot.id)
                .order_by(RawSnapshotModel.id)
            )
        )
        selected_raw_rows = [row for row in raw_rows if row.store_external_id == store.external_id]
        raw_statuses = Counter(str(row.http_status) for row in raw_rows)

        failures = list(
            self.session.scalars(
                select(ParserFailureModel)
                .where(ParserFailureModel.catalog_snapshot_id == snapshot.id)
                .order_by(ParserFailureModel.error_code, ParserFailureModel.id)
            )
        )
        store_failures = [
            failure for failure in failures if failure.store_external_id == store.external_id
        ]
        run = (
            self.session.get(CollectorRunModel, snapshot.collector_run_id)
            if snapshot.collector_run_id
            else None
        )
        recipe_rows = [
            row
            for row in rows
            if is_recipe_relevant(tuple(str(value) for value in row.product.category_path or []))
        ]

        promotion_type_counts = _distribution([promotion.type for promotion in promotions])
        max_quantity_counts = _distribution(
            [str(promotion.max_quantity) for promotion in promotions if promotion.max_quantity]
        )
        multibuy = [promotion for promotion in promotions if promotion.type == "multibuy"]
        return CatalogSnapshotQualityReport(
            snapshot_id=snapshot.id,
            store_id=store.id,
            store_external_id=store.external_id,
            chain=snapshot.chain,
            snapshot_state=snapshot.state,
            snapshot_coverage=snapshot.coverage,
            normalized_rows=normalized_rows,
            overall=_quality(rows),
            recipe_relevant=_quality(recipe_rows),
            promotions=PromotionQualitySummary(
                promotions=len(promotions),
                promoted_products=len(
                    {promotion.product_id for promotion in promotions if promotion.product_id}
                ),
                type_distribution=promotion_type_counts,
                member_only=sum(promotion.member_only for promotion in promotions),
                multibuy=len(multibuy),
                member_multibuy=sum(promotion.member_only for promotion in multibuy),
                with_max_quantity=sum(
                    promotion.max_quantity is not None and promotion.max_quantity > 0
                    for promotion in promotions
                ),
                max_quantity_distribution=max_quantity_counts,
                with_valid_from=sum(promotion.valid_from is not None for promotion in promotions),
                with_valid_to=sum(promotion.valid_to is not None for promotion in promotions),
                with_complete_validity_period=sum(
                    promotion.valid_from is not None and promotion.valid_to is not None
                    for promotion in promotions
                ),
            ),
            raw_payloads=RawPayloadQualitySummary(
                snapshot_payloads=len(raw_rows),
                snapshot_bytes=sum(row.payload_size for row in raw_rows),
                selected_store_payloads=len(selected_raw_rows),
                selected_store_bytes=sum(row.payload_size for row in selected_raw_rows),
                http_status_distribution=dict(sorted(raw_statuses.items())),
                captured_http_errors=sum(row.http_status >= 400 for row in raw_rows),
                captured_429_responses=sum(row.http_status == 429 for row in raw_rows),
            ),
            transport=_transport(snapshot, run),
            completion=_completion(snapshot, store.external_id),
            quarantine=QuarantineQualitySummary(
                snapshot_failures=len(failures),
                selected_store_failures=len(store_failures),
                selected_store_code_distribution=_distribution(
                    [failure.error_code for failure in store_failures]
                ),
            ),
            manual_samples=category_stratified_manual_sample(
                _safe_manual_samples(rows, dict(promotion_types_by_product)),
                max_samples=max_manual_samples,
            ),
        )
