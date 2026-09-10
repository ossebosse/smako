from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain import (
    CanonicalProduct,
    CatalogCompletion,
    Chain,
    Confidence,
    ConnectorHealth,
    ConnectorStatus,
    CoverageLevel,
    RunMetrics,
    SaleModel,
    SnapshotState,
    is_complete_catalog_coverage,
)
from grocery_data.app.monitoring import (
    SchemaDiff,
    SchemaFingerprint,
    assess_run_health,
    fingerprint_json,
)
from grocery_data.app.services.collector import _merge_schema_diff
from grocery_data.app.services.coop_online_context_activation import (
    activate_promoted_coop_online_context,
)
from grocery_data.app.services.diff import SnapshotDiff, SnapshotDiffer
from grocery_data.app.storage import (
    ConnectorHealthRepository,
    SessionFactory,
    SnapshotRepository,
    StoreRepository,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    ParserFailureModel,
    PriceObservationModel,
    ProductModel,
    StoreModel,
)


def _canonical_from_row(row: ProductModel) -> CanonicalProduct:
    return CanonicalProduct(
        source_product_key=row.source_product_key,
        chain=Chain(row.chain),
        store_external_id=row.store_external_id,
        external_product_id=row.external_product_id,
        gtin=row.gtin,
        name=row.name,
        brand=row.brand,
        category_path=tuple(row.category_path or []),
        canonical_food=row.canonical_food,
        product_role=row.product_role,
        product_form=row.product_form,
        semantic_confidence=Confidence(row.semantic_confidence),
        sale_model=SaleModel(row.sale_model),
        quantity_confidence=Confidence(row.quantity_confidence),
        package_quantity=row.package_quantity,
        package_unit=row.package_unit,
        usable_quantity=row.usable_quantity,
        usable_unit=row.usable_unit,
        sale_price=row.sale_price,
        sale_unit=row.sale_unit,
        unit_price=row.unit_price,
        comparison_price=row.comparison_price,
        comparison_unit=row.comparison_unit,
        availability=row.availability,
        raw_reference=row.raw_reference,
        parser_version=row.parser_version,
        normalizer_version=row.normalizer_version,
        observed_at=row.observed_at,
    )


class SnapshotValidationError(ValueError):
    """The persisted evidence does not support promoting this snapshot."""


def _validated_schema_payload(row: CatalogSnapshotModel) -> dict[str, SchemaFingerprint]:
    payload = row.metrics or {}
    raw_schemas = payload.get("schemas")
    if not isinstance(raw_schemas, dict):
        raise SnapshotValidationError("snapshot is missing schema evidence")
    try:
        schemas = {
            str(kind): SchemaFingerprint.model_validate(fingerprint)
            for kind, fingerprint in raw_schemas.items()
        }
    except (TypeError, ValueError) as exc:
        raise SnapshotValidationError("snapshot schema evidence is invalid") from exc
    expected = fingerprint_json(
        {kind: fingerprint.digest for kind, fingerprint in sorted(schemas.items())}
    ).digest
    if row.schema_fingerprint != expected:
        raise SnapshotValidationError("snapshot schema fingerprint does not match its evidence")
    return schemas


def _validated_metrics(row: CatalogSnapshotModel) -> RunMetrics:
    payload = row.metrics or {}
    raw_metrics = payload.get("run_metrics")
    if not isinstance(raw_metrics, dict):
        raise SnapshotValidationError("snapshot is missing run metrics")
    try:
        return RunMetrics.model_validate(raw_metrics)
    except ValueError as exc:
        raise SnapshotValidationError("snapshot run metrics are invalid") from exc


def _validate_full_catalog_evidence(
    row: CatalogSnapshotModel,
    metrics: RunMetrics,
    *,
    full_catalog_min_products: int,
) -> None:
    """Fail closed when a FULL_CATALOG claim lacks traversal evidence.

    Collector and replay validate this evidence before parsing. Manual
    ``validate``/``promote`` commands must independently enforce the same
    invariant so an incomplete persisted candidate cannot bypass the normal
    pipeline.
    """

    try:
        coverage = CoverageLevel(row.coverage)
    except ValueError as exc:
        raise SnapshotValidationError("snapshot has an invalid coverage level") from exc
    if not is_complete_catalog_coverage(coverage):
        return
    payload = row.metrics or {}
    raw_completion = payload.get("catalog_completion")
    persisted_minimum = payload.get("minimum_products_for_full_catalog")
    if (
        not isinstance(raw_completion, dict)
        or isinstance(persisted_minimum, bool)
        or not isinstance(persisted_minimum, int)
        or persisted_minimum <= 0
    ):
        raise SnapshotValidationError(
            "complete catalog snapshot is missing traversal completion evidence"
        )
    if len(raw_completion) != metrics.stores_successful:
        raise SnapshotValidationError(
            "complete catalog evidence does not cover every successful store"
        )
    # Persisted evidence documents the policy used during collection, but it is
    # untrusted input to a later manual CLI promotion.  Never let a candidate
    # lower the operator's current minimum merely by storing ``1`` here.
    required_products = max(persisted_minimum, full_catalog_min_products)
    for store_external_id, raw in raw_completion.items():
        try:
            evidence = CatalogCompletion.model_validate(raw)
        except (TypeError, ValueError) as exc:
            raise SnapshotValidationError(
                f"complete catalog completion evidence is invalid for store {store_external_id}"
            ) from exc
        if evidence.has_exact_evidence and not evidence.exact_evidence_reconciles:
            raise SnapshotValidationError(
                f"complete catalog exact product/page counts do not reconcile for store {store_external_id}"
            )
        if not evidence.is_full_traversal:
            raise SnapshotValidationError(
                f"complete catalog traversal is incomplete for store {store_external_id}"
            )
        if evidence.products_observed < required_products:
            raise SnapshotValidationError(
                f"complete catalog product count is below the configured minimum for store {store_external_id}"
            )


def _assess_persisted_snapshot(
    session: Session,
    row: CatalogSnapshotModel,
    *,
    full_catalog_min_products: int,
) -> RunMetrics:
    metrics = _validated_metrics(row)
    schemas = _validated_schema_payload(row)
    _validate_full_catalog_evidence(
        row,
        metrics,
        full_catalog_min_products=full_catalog_min_products,
    )
    product_count = session.scalar(
        select(func.count(ProductModel.id)).where(ProductModel.catalog_snapshot_id == row.id)
    )
    price_count = session.scalar(
        select(func.count(PriceObservationModel.id)).where(
            PriceObservationModel.catalog_snapshot_id == row.id
        )
    )
    if not metrics.stores_successful or not metrics.products_parsed:
        raise SnapshotValidationError("snapshot has no successful store catalog with products")
    if product_count != metrics.products_parsed or price_count != metrics.products_parsed:
        raise SnapshotValidationError(
            "persisted product/price rows do not reconcile with parser metrics"
        )

    repository = SnapshotRepository(session)
    baseline = repository.active(Chain(row.chain), scope_key=row.scope_key)
    if baseline is not None and baseline.id == row.id:
        baseline = None
    baseline_metrics = None
    baseline_schemas = {}
    if baseline is not None:
        baseline_payload = baseline.metrics or {}
        raw_baseline_metrics = baseline_payload.get("run_metrics")
        if isinstance(raw_baseline_metrics, dict):
            try:
                baseline_metrics = RunMetrics.model_validate(raw_baseline_metrics)
            except ValueError as exc:
                raise SnapshotValidationError("active baseline run metrics are invalid") from exc
        raw_baseline_schemas = baseline_payload.get("schemas")
        if isinstance(raw_baseline_schemas, dict):
            baseline_schemas = raw_baseline_schemas

    try:
        schema_diff = _merge_schema_diff(baseline_schemas, schemas)
    except ValueError as exc:
        raise SnapshotValidationError("active baseline schema evidence is invalid") from exc
    payload = row.metrics or {}
    if not baseline_schemas:
        raw_diff = payload.get("schema_diff")
        if raw_diff is not None:
            try:
                schema_diff = SchemaDiff.model_validate(raw_diff)
            except ValueError as exc:
                raise SnapshotValidationError("snapshot schema diff is invalid") from exc
    if payload.get("schema_change_accepted") is True:
        schema_diff = None
    assessment = assess_run_health(
        metrics,
        baseline=baseline_metrics,
        schema_diff=schema_diff,
    )
    if assessment.status != ConnectorStatus.HEALTHY:
        detail = "; ".join(assessment.warnings) or assessment.status.value
        raise SnapshotValidationError(f"snapshot health check failed: {detail}")
    return metrics


class SnapshotManager:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        full_catalog_min_products: int = 100,
    ) -> None:
        if full_catalog_min_products <= 0:
            raise ValueError("full_catalog_min_products must be positive")
        self.session_factory = session_factory
        self.full_catalog_min_products = full_catalog_min_products

    def get(self, snapshot_id: str) -> CatalogSnapshotModel:
        with session_scope(self.session_factory) as session:
            row = SnapshotRepository(session).get(snapshot_id)
            if row is None:
                raise LookupError(f"snapshot {snapshot_id!r} does not exist")
            session.expunge(row)
            return row

    def validate(self, snapshot_id: str) -> CatalogSnapshotModel:
        failure: SnapshotValidationError | None = None
        result: CatalogSnapshotModel | None = None
        with session_scope(self.session_factory) as session:
            repository = SnapshotRepository(session)
            row = repository.get(snapshot_id)
            if row is None:
                raise LookupError(f"snapshot {snapshot_id!r} does not exist")
            if row.state == SnapshotState.PROMOTED.value:
                session.expunge(row)
                return row
            if row.state not in {
                SnapshotState.PARSED.value,
                SnapshotState.VALIDATED.value,
                SnapshotState.HEALTH_CHECKED.value,
            }:
                raise ValueError(f"snapshot cannot be validated from state {row.state!r}")
            try:
                _assess_persisted_snapshot(
                    session,
                    row,
                    full_catalog_min_products=self.full_catalog_min_products,
                )
            except SnapshotValidationError as exc:
                row = repository.reject(
                    snapshot_id,
                    reason="manual snapshot validation failed",
                )
                failure = exc
            else:
                if row.state == SnapshotState.PARSED.value:
                    row = repository.transition(snapshot_id, SnapshotState.VALIDATED)
                if row.state == SnapshotState.VALIDATED.value:
                    row = repository.transition(snapshot_id, SnapshotState.HEALTH_CHECKED)
            session.expunge(row)
            result = row
        if failure is not None:
            raise failure
        if result is None:  # pragma: no cover - guarded by the transaction above
            raise LookupError(snapshot_id)
        return result

    def promote(self, snapshot_id: str) -> CatalogSnapshotModel:
        failure: SnapshotValidationError | None = None
        result: CatalogSnapshotModel | None = None
        with session_scope(self.session_factory) as session:
            repository = SnapshotRepository(session)
            row = repository.get(snapshot_id)
            if row is None:
                raise LookupError(f"snapshot {snapshot_id!r} does not exist")
            if row.state != SnapshotState.HEALTH_CHECKED.value:
                raise ValueError("only a health-checked snapshot can be promoted")
            try:
                metrics = _assess_persisted_snapshot(
                    session,
                    row,
                    full_catalog_min_products=self.full_catalog_min_products,
                )
            except SnapshotValidationError as exc:
                row = repository.reject(
                    snapshot_id,
                    reason="manual snapshot promotion health check failed",
                )
                failure = exc
            else:
                row = repository.promote(snapshot_id)
                store_external_ids = set(
                    session.scalars(
                        select(StoreModel.external_id)
                        .join(ProductModel, ProductModel.store_id == StoreModel.id)
                        .where(ProductModel.catalog_snapshot_id == row.id)
                    )
                )
                if store_external_ids:
                    StoreRepository(session).reconcile_scope(
                        Chain(row.chain),
                        city=row.scope_key,
                        seen_external_ids=store_external_ids,
                    )
                activate_promoted_coop_online_context(session, row)
                ConnectorHealthRepository(session).upsert(
                    ConnectorHealth(
                        chain=Chain(row.chain),
                        coverage=CoverageLevel(row.coverage),
                        status=ConnectorStatus.HEALTHY,
                        last_success_at=row.promoted_at,
                        active_snapshot_id=row.id,
                        metrics=metrics,
                        schema_fingerprint=row.schema_fingerprint,
                    )
                )
            session.expunge(row)
            result = row
        if failure is not None:
            raise failure
        if result is None:  # pragma: no cover - guarded by the transaction above
            raise LookupError(snapshot_id)
        return result

    def products(self, snapshot_id: str) -> list[CanonicalProduct]:
        with session_scope(self.session_factory) as session:
            rows = list(
                session.scalars(
                    select(ProductModel)
                    .where(ProductModel.catalog_snapshot_id == snapshot_id)
                    .order_by(ProductModel.id)
                )
            )
            return [_canonical_from_row(row) for row in rows]

    def diff(self, old_snapshot_id: str, new_snapshot_id: str) -> SnapshotDiff:
        return SnapshotDiffer().compare(
            self.products(old_snapshot_id),
            self.products(new_snapshot_id),
            old_parser_failures=self.parser_failure_count(old_snapshot_id),
            new_parser_failures=self.parser_failure_count(new_snapshot_id),
        )

    def parser_failure_count(self, snapshot_id: str) -> int:
        with session_scope(self.session_factory) as session:
            return int(
                session.scalar(
                    select(func.count(ParserFailureModel.id)).where(
                        ParserFailureModel.catalog_snapshot_id == snapshot_id
                    )
                )
                or 0
            )
