from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from sqlalchemy.orm import Session

from grocery_data.app.connectors.base import (
    ConnectorFetchError,
    GroceryConnector,
    enforce_collection_policy,
)
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ConnectorHealth,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    RawBatch,
    RunMetrics,
    SnapshotState,
    SourceCollectionAudit,
    SourceScopeDescriptor,
    SourceStore,
    StoredRawDocument,
    TransportMetrics,
    is_complete_catalog_coverage,
)
from grocery_data.app.monitoring import (
    AlertSink,
    CollectorEvent,
    CollectorEventSink,
    CollectorEventType,
    ConsoleAlertSink,
    ConsoleCollectorEventSink,
    SchemaDiff,
    SchemaFingerprint,
    alerts_from_assessment,
    assess_run_health,
    diff_fingerprints,
    fingerprint_json,
)
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.catalog_processor import CatalogProcessor, ProcessedCatalog
from grocery_data.app.services.coop_online_context_activation import (
    activate_promoted_coop_online_context,
)
from grocery_data.app.services.hemkop_context_collection import (
    activate_promoted_hemkop_online_context,
)
from grocery_data.app.services.ica_registry import IcaProductRegistry
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import (
    CollectorRunRepository,
    ConnectorHealthRepository,
    ParserFailureRepository,
    ProductBundleRepository,
    RawSnapshotRepository,
    SessionFactory,
    SnapshotRepository,
    StoreRepository,
    session_scope,
)
from grocery_data.app.storage.models import RawSnapshotModel, StoreModel


def _uses_ica_offer_registry(store: StoreModel) -> bool:
    """Keep the legacy registry restricted to the accepted offers surface."""

    return (
        store.chain == Chain.ICA.value
        and store.coverage == CoverageLevel.OFFERS_ONLY.value
    )


@dataclass(frozen=True, slots=True)
class CollectionResult:
    chain: Chain
    scope_key: str
    snapshot_id: str
    status: ConnectorStatus
    promoted: bool
    active_snapshot_id: str | None
    stores: tuple[SourceStore, ...]
    metrics: RunMetrics
    warnings: tuple[str, ...]
    raw_documents: int
    source_policy_audit: SourceCollectionAudit | None = None


class CatalogCompletenessError(RuntimeError):
    """Raised after raw evidence is saved when FULL_CATALOG cannot be proven."""


def _sum_metrics(metrics: list[RunMetrics], *, runtime_ms: int = 0) -> RunMetrics:
    fields = (
        "stores_found",
        "stores_successful",
        "stores_failed",
        "products_fetched",
        "products_parsed",
        "products_quarantined",
        "products_with_price",
        "products_with_gtin",
        "products_with_package_quantity",
        "unknown_sale_model",
        "request_count",
        "http_error_count",
        "rate_limit_count",
    )
    values = {field: sum(getattr(item, field) for item in metrics) for field in fields}
    values["runtime_ms"] = runtime_ms
    return RunMetrics(**values)


def _sum_transport(metrics: list[TransportMetrics]) -> TransportMetrics:
    return TransportMetrics(
        request_count=sum(item.request_count for item in metrics),
        http_error_count=sum(item.http_error_count for item in metrics),
        rate_limit_count=sum(item.rate_limit_count for item in metrics),
    )


def _batch_transport(batch: RawBatch) -> TransportMetrics:
    """Use physical-attempt counters, falling back to captured responses."""

    if batch.transport.request_count:
        return batch.transport
    return TransportMetrics(
        request_count=len(batch.documents),
        http_error_count=sum(document.http_status >= 400 for document in batch.documents),
        rate_limit_count=sum(document.http_status == 429 for document in batch.documents),
    )


def _catalog_completion_payload(evidence: CatalogCompletion) -> dict[str, Any]:
    """Persist additive partition evidence without rewriting legacy payload shape."""

    payload = evidence.model_dump(mode="json")
    if evidence.within_partition_duplicates is None:
        payload.pop("within_partition_duplicates", None)
    if evidence.cross_partition_duplicates is None:
        payload.pop("cross_partition_duplicates", None)
    if evidence.exact_duplicates_removed is None:
        payload.pop("exact_duplicates_removed", None)
    if evidence.conflicting_duplicates is None:
        payload.pop("conflicting_duplicates", None)
    if evidence.pagination_overlaps is None:
        payload.pop("pagination_overlaps", None)
    return payload


def _schema_fingerprints(batch: RawBatch) -> dict[str, SchemaFingerprint]:
    payloads: dict[str, list[Any]] = defaultdict(list)
    for document in batch.documents:
        if "json" not in (document.content_type or "").casefold():
            continue
        try:
            payloads[document.kind].append(document.json_payload())
        except (TypeError, ValueError):
            continue
    return {kind: fingerprint_json(values) for kind, values in sorted(payloads.items())}


def _merge_schema_diff(
    baseline_schemas: dict[str, Any],
    current_schemas: dict[str, SchemaFingerprint],
) -> SchemaDiff | None:
    if not baseline_schemas:
        return None
    added: set[str] = set()
    removed: set[str] = set()
    changed = []
    for kind in sorted(set(baseline_schemas) | set(current_schemas)):
        old_raw = baseline_schemas.get(kind)
        new = current_schemas.get(kind)
        prefix = f"{kind}:"
        if old_raw is None and new is not None:
            added.update(prefix + path for path in new.paths)
            continue
        if new is None and old_raw is not None:
            old = SchemaFingerprint.model_validate(old_raw)
            removed.update(prefix + path for path in old.paths)
            continue
        if old_raw is None or new is None:
            continue
        old = SchemaFingerprint.model_validate(old_raw)
        part = diff_fingerprints(old, new)
        added.update(prefix + path for path in part.added)
        removed.update(prefix + path for path in part.removed)
        changed.extend(
            item.model_copy(update={"path": prefix + item.path}) for item in part.type_changed
        )
    result = SchemaDiff(
        added=tuple(sorted(added)),
        removed=tuple(sorted(removed)),
        type_changed=tuple(changed),
    )
    return result if result.has_changes else None


def _review_schema_diff(
    chain: Chain, parser_version: str | None, diff: SchemaDiff | None, *, schemas=None,
) -> SchemaDiff | None:
    """Apply a versioned source contract review, retaining raw diff evidence.

    This is deliberately source-local: unrelated connectors keep exact schema
    gates. Persisted flags/effective diffs never authorize a schema change.
    """
    if diff is None:
        return diff
    required_type_changes = diff.type_changed
    if chain == Chain.LIDL:
        from grocery_data.app.connectors.lidl.models import reviewed_lidl_schema_diff
        from grocery_data.app.connectors.lidl.parser import LidlParser

        if parser_version != LidlParser.parser_version:
            return diff
        reviewed = reviewed_lidl_schema_diff(diff)
    elif chain == Chain.COOP and parser_version in {
        "coop-online-catalog-parser-v1", "coop-online-catalog-parser-v2", "coop-online-catalog-parser-v3",
    }:
        from grocery_data.app.connectors.coop.schema_review import reviewed_coop_online_schema_diff

        reviewed = reviewed_coop_online_schema_diff(
            diff, presentation_metadata=parser_version == "coop-online-catalog-parser-v3",
        )
    elif chain == Chain.HEMKOP and parser_version in {"hemkop-parser-v1", "hemkop-parser-v1.1-picking-contract", "hemkop-parser-v1.2-counted-weight", "hemkop-parser-v1.3-reviewed-catalog"}:
        from grocery_data.app.connectors.hemkop.schema_review import (
            reviewed_hemkop_schema_diff,
            reviewed_hemkop_type_change,
        )

        reviewed = reviewed_hemkop_schema_diff(
            diff, schemas=schemas, picking_contract=parser_version in {"hemkop-parser-v1.1-picking-contract", "hemkop-parser-v1.2-counted-weight", "hemkop-parser-v1.3-reviewed-catalog"},
        )
        required_type_changes = tuple(
            change for change in diff.type_changed if not reviewed_hemkop_type_change(change)
        )
    elif chain == Chain.WILLYS and parser_version in {"willys-parser-v3", "willys-parser-v4", "willys-parser-v5"}:
        from grocery_data.app.connectors.willys.schema_review import (
            reviewed_willys_schema_diff,
            reviewed_willys_type_change,
        )

        nullable_price = parser_version == "willys-parser-v5"
        reviewed = reviewed_willys_schema_diff(diff, nullable_price=nullable_price)
        required_type_changes = tuple(
            change for change in diff.type_changed
            if not reviewed_willys_type_change(change, nullable_price=nullable_price)
        )
    else:
        return diff
    if not isinstance(reviewed, SchemaDiff):
        raise TypeError("source schema review must return a SchemaDiff")
    if (not set(reviewed.added).issubset(diff.added)
            or not set(reviewed.removed).issubset(diff.removed)
            or reviewed.type_changed != required_type_changes):
        raise ValueError("source schema review altered unreviewable evidence")
    return reviewed if reviewed.has_changes else None


def _eligible_catalog_stores(
    connector: GroceryConnector,
    stores: list[SourceStore],
) -> list[SourceStore]:
    """Keep source-specific catalog eligibility inside the connector contract."""

    return [store for store in stores if connector.catalog_eligible(store)]


class GroceryCollector:
    """Fetch raw evidence, parse, validate, health-check and atomically promote."""

    def __init__(
        self,
        session_factory: SessionFactory,
        raw_store: FilesystemRawSnapshotStore,
        *,
        alert_sink: AlertSink | None = None,
        event_sink: CollectorEventSink | None = None,
        normalizer: ProductNormalizer | None = None,
        full_catalog_min_products: int = 100,
    ) -> None:
        if full_catalog_min_products <= 0:
            raise ValueError("full_catalog_min_products must be positive")
        self.session_factory = session_factory
        self.raw_store = raw_store
        self.alert_sink = alert_sink or ConsoleAlertSink()
        self.event_sink = event_sink or ConsoleCollectorEventSink()
        self.normalizer = normalizer or ProductNormalizer()
        self.processor = CatalogProcessor(self.normalizer)
        self.full_catalog_min_products = full_catalog_min_products

    def _minimum_products_for_complete_catalog(
        self,
        connector: GroceryConnector,
        *,
        persisted_minimum: int | None = None,
    ) -> int:
        """Resolve the strongest operator, connector and persisted minimum."""

        connector_minimum = getattr(connector, "minimum_full_catalog_products", None)
        if connector_minimum is not None and (
            isinstance(connector_minimum, bool)
            or not isinstance(connector_minimum, int)
            or connector_minimum <= 0
        ):
            raise ValueError("minimum_full_catalog_products must be a positive integer")
        if persisted_minimum is not None and (
            isinstance(persisted_minimum, bool)
            or not isinstance(persisted_minimum, int)
            or persisted_minimum <= 0
        ):
            raise ValueError("persisted full-catalog minimum must be a positive integer")
        return max(
            self.full_catalog_min_products,
            connector_minimum or 0,
            persisted_minimum or 0,
        )

    def _emit_event(
        self,
        event_type: CollectorEventType,
        connector: GroceryConnector,
        scope_key: str,
        snapshot_id: str,
        *,
        metrics: RunMetrics | None = None,
        status: ConnectorStatus = ConnectorStatus.UNKNOWN,
    ) -> None:
        metrics = metrics or RunMetrics()
        self.event_sink.emit(
            CollectorEvent(
                event=event_type,
                chain=connector.chain,
                scope=scope_key,
                snapshot_id=snapshot_id,
                products=metrics.products_parsed,
                errors=(
                    metrics.products_quarantined + metrics.http_error_count + metrics.stores_failed
                ),
                request_count=metrics.request_count,
                runtime_ms=metrics.runtime_ms,
                status=status,
            )
        )

    def _validate_catalog_completion(
        self,
        connector: GroceryConnector,
        batch: RawBatch,
        *,
        minimum_products: int | None = None,
    ) -> None:
        if not is_complete_catalog_coverage(connector.coverage):
            return
        evidence = batch.catalog_completion
        if evidence is None:
            raise CatalogCompletenessError(
                "complete catalog coverage requires explicit traversal completion evidence"
            )
        if evidence.has_exact_evidence and not evidence.exact_evidence_reconciles:
            raise CatalogCompletenessError(
                "complete catalog exact product/page counts do not reconcile"
            )
        if not evidence.is_full_traversal:
            raise CatalogCompletenessError(
                "complete catalog traversal was incomplete or explicitly limited"
            )
        required_products = (
            minimum_products
            if minimum_products is not None
            else self._minimum_products_for_complete_catalog(connector)
        )
        if evidence.products_observed < required_products:
            raise CatalogCompletenessError(
                "complete catalog product count is below the configured absolute minimum"
            )

    def _start(
        self,
        connector: GroceryConnector,
        scope_key: str,
        policy_audit: SourceCollectionAudit | None = None,
        *,
        source_scope: SourceScopeDescriptor | None = None,
    ) -> tuple[str, str, str | None]:
        with session_scope(self.session_factory) as session:
            snapshots = SnapshotRepository(session)
            baseline = snapshots.active(connector.chain, scope_key=scope_key)
            run_scope: dict[str, Any] = {"scope_key": scope_key}
            if source_scope is not None:
                if source_scope.scope_key != scope_key:
                    raise ValueError("source-scope descriptor does not match scope_key")
                run_scope["source_scope"] = source_scope.model_dump(mode="json")
            if policy_audit is not None:
                run_scope.update(policy_audit.model_dump(mode="json"))
            run = CollectorRunRepository(session).start(
                chain=connector.chain,
                connector_version=connector.connector_version,
                parser_version=connector.parser_version,
                normalizer_version=self.normalizer.normalizer_version,
                scope=run_scope,
            )
            snapshot = snapshots.create(
                chain=connector.chain,
                coverage=connector.coverage,
                connector_version=connector.connector_version,
                scope_key=scope_key,
                collector_run_id=run.id,
                parser_version=connector.parser_version,
                normalizer_version=self.normalizer.normalizer_version,
                metrics=(
                    {"source_scope": source_scope.model_dump(mode="json")}
                    if source_scope is not None
                    else None
                ),
            )
            baseline_id = baseline.id if baseline else None
            return run.id, snapshot.id, baseline_id

    def _save_raw(
        self,
        session: Session,
        batch: RawBatch,
        *,
        snapshot_id: str,
        run_id: str,
        schemas: dict[str, SchemaFingerprint],
    ) -> tuple[list[StoredRawDocument], dict[str, RawSnapshotModel]]:
        by_hash = {
            document.payload_hash: schemas[document.kind].digest
            for document in batch.documents
            if document.kind in schemas
        }
        stored = self.raw_store.save_batch(
            batch,
            snapshot_id=snapshot_id,
            schema_fingerprints=by_hash,
        )
        repository = RawSnapshotRepository(session)
        rows: dict[str, RawSnapshotModel] = {}
        for document, record in zip(batch.documents, stored, strict=True):
            persisted_document = document.model_copy(
                update={"payload": self.raw_store.load(record)}
            )
            row = repository.record_fetch(
                persisted_document,
                catalog_snapshot_id=snapshot_id,
                collector_run_id=run_id,
                payload_location=record.relative_path,
                schema_fingerprint=record.schema_fingerprint,
            )
            rows[record.document_id] = row
        return stored, rows

    def _save_raw_durably(
        self,
        batch: RawBatch,
        *,
        snapshot_id: str,
        run_id: str,
        schemas: dict[str, SchemaFingerprint],
    ) -> tuple[list[StoredRawDocument], dict[str, RawSnapshotModel]]:
        """Commit immutable raw lineage before any parser or completion gate runs.

        Raw payload files are written by :meth:`_save_raw` and cannot participate
        in a database transaction.  Giving their metadata its own committed unit
        of work keeps the filesystem and database replay index in step when a
        later catalog-completion, parser, or candidate-persistence check fails.

        The returned ORM rows are detached after commit, but callers only use
        their immutable primary keys when persisting product lineage.  Product
        rows and snapshot state remain in later candidate transactions, so this
        durability boundary cannot promote or partially activate a catalog.
        """

        with session_scope(self.session_factory) as session:
            return self._save_raw(
                session,
                batch,
                snapshot_id=snapshot_id,
                run_id=run_id,
                schemas=schemas,
            )

    @staticmethod
    def _raw_row_for_reference(
        reference: str,
        rows: dict[str, RawSnapshotModel],
    ) -> RawSnapshotModel:
        document_id = reference.removeprefix("raw:").split("#", 1)[0]
        row = rows.get(document_id)
        if row is None:
            raise LookupError(f"raw lineage document {document_id!r} is missing")
        return row

    def _persist_catalog(
        self,
        session: Session,
        processed: ProcessedCatalog,
        *,
        snapshot_id: str,
        run_id: str,
        store: StoreModel,
        raw_rows: dict[str, RawSnapshotModel],
    ) -> None:
        bundles = ProductBundleRepository(session)
        failures = ParserFailureRepository(session)
        # The legacy registry is an opportunistic offers/enrichment surface.
        # A future ICA FULL_ONLINE candidate must remain a normal catalog
        # product universe and must never be flattened into offer-registry
        # semantics merely because its chain is ICA.
        ica_registry = IcaProductRegistry(session) if _uses_ica_offer_registry(store) else None
        fallback_raw = next(iter(raw_rows.values()))
        for product in processed.products:
            raw = self._raw_row_for_reference(product.source.raw_reference, raw_rows)
            bundles.persist(
                source=product.source,
                canonical=product.canonical,
                catalog_snapshot_id=snapshot_id,
                raw_snapshot_id=raw.id,
                store_id=store.id,
                parser_version=product.canonical.parser_version,
            )
            if ica_registry is not None:
                ica_registry.ingest_offer_product(
                    product.source,
                    raw_snapshot_id=raw.id,
                    canonical_food=product.canonical.canonical_food,
                    sale_model=product.canonical.sale_model.value,
                    semantic_confidence=product.canonical.semantic_confidence.value,
                    quantity_confidence=product.canonical.quantity_confidence.value,
                )
        for failure in processed.failures:
            try:
                raw = self._raw_row_for_reference(failure.raw_record_reference, raw_rows)
            except LookupError:
                raw = fallback_raw
            failures.record(
                failure,
                chain=Chain(store.chain),
                catalog_snapshot_id=snapshot_id,
                raw_snapshot_id=raw.id,
                store_external_id=store.external_id,
                collector_run_id=run_id,
            )

    async def collect_area(
        self,
        connector: GroceryConnector,
        area: GeographicArea,
        *,
        auto_promote: bool = True,
        scope_key: str | None = None,
    ) -> CollectionResult:
        started = monotonic()
        # A city remains the backwards-compatible default.  Connectors with
        # multiple independently priced contexts in one city may supply an
        # explicit context scope (for example ``lund:hemkop:4123``), so one
        # promoted context never replaces another merely because both are in
        # Lund.  Store filtering and lifecycle reconciliation still use the
        # real geographic ``area.city`` below.
        scope_key = (scope_key or area.city).casefold().strip()
        if not scope_key:
            raise ValueError("scope_key must not be blank")
        source_scope = SourceScopeDescriptor(
            scope_key=scope_key,
            geographic_area=area,
        )
        # Enforce policy before creating a run/snapshot or making any source
        # request. Connector-local guards remain defense in depth.
        policy_audit = enforce_collection_policy(connector)
        policy_payload = policy_audit.model_dump(mode="json") if policy_audit is not None else None
        minimum_products = self._minimum_products_for_complete_catalog(connector)
        run_id, snapshot_id, baseline_id = self._start(
            connector,
            scope_key,
            policy_audit,
            source_scope=source_scope,
        )
        self._emit_event(
            CollectorEventType.STARTED,
            connector,
            scope_key,
            snapshot_id,
        )
        all_schemas: dict[str, SchemaFingerprint] = {}
        raw_count = 0
        stores: list[SourceStore] = []
        metric_parts: list[RunMetrics] = []
        transport_parts: list[TransportMetrics] = []
        completion_by_store: dict[str, CatalogCompletion] = {}
        warnings: list[str] = []
        successful_stores = 0
        try:
            try:
                store_batch = await connector.fetch_stores(area)
            except ConnectorFetchError as exc:
                store_batch = exc.partial_batch
                transport_parts.append(_batch_transport(store_batch))
                store_schemas = _schema_fingerprints(store_batch)
                all_schemas.update(store_schemas)
                stored, _ = self._save_raw_durably(
                    store_batch,
                    snapshot_id=snapshot_id,
                    run_id=run_id,
                    schemas=store_schemas,
                )
                raw_count += len(stored)
                raise
            transport_parts.append(_batch_transport(store_batch))
            store_schemas = _schema_fingerprints(store_batch)
            all_schemas.update(store_schemas)
            stored, store_raw_rows = self._save_raw_durably(
                store_batch,
                snapshot_id=snapshot_id,
                run_id=run_id,
                schemas=store_schemas,
            )
            raw_count += len(stored)
            with session_scope(self.session_factory) as session:
                references = [f"raw:{record.document_id}" for record in stored]
                stores = connector.parse_stores(store_batch, references, area)
                store_repository = StoreRepository(session)
                for source in stores:
                    # Candidate discovery must not reactivate or deactivate a
                    # store until the snapshot has passed every health gate.
                    store_repository.upsert(source, activate=None)
                del store_raw_rows

            catalog_stores = _eligible_catalog_stores(connector, stores)
            skipped_stores = len(stores) - len(catalog_stores)
            if skipped_stores:
                warnings.append(
                    f"{skipped_stores} discovered stores lacked a verified catalog context and were skipped"
                )
            for source_store in catalog_stores:
                try:
                    catalog_batch = await connector.fetch_catalog(source_store)
                except ConnectorFetchError as exc:
                    catalog_batch = exc.partial_batch
                    transport_parts.append(_batch_transport(catalog_batch))
                    if catalog_batch.catalog_completion is not None:
                        completion_by_store[source_store.external_id] = (
                            catalog_batch.catalog_completion
                        )
                    schemas = _schema_fingerprints(catalog_batch)
                    for kind, fingerprint in schemas.items():
                        all_schemas[f"{source_store.external_id}:{kind}"] = fingerprint
                    stored, _ = self._save_raw_durably(
                        catalog_batch,
                        snapshot_id=snapshot_id,
                        run_id=run_id,
                        schemas=schemas,
                    )
                    raw_count += len(stored)
                    raise
                transport_parts.append(_batch_transport(catalog_batch))
                if catalog_batch.catalog_completion is not None:
                    completion_by_store[source_store.external_id] = catalog_batch.catalog_completion
                schemas = _schema_fingerprints(catalog_batch)
                for kind, fingerprint in schemas.items():
                    all_schemas[f"{source_store.external_id}:{kind}"] = fingerprint
                stored, raw_rows = self._save_raw_durably(
                    catalog_batch,
                    snapshot_id=snapshot_id,
                    run_id=run_id,
                    schemas=schemas,
                )
                raw_count += len(stored)
                # This gate intentionally runs *after* the raw transaction has
                # committed and *before* parsers can create any product rows.
                self._validate_catalog_completion(
                    connector,
                    catalog_batch,
                    minimum_products=minimum_products,
                )
                references = [f"raw:{record.document_id}" for record in stored]
                processed = self.processor.process(
                    connector,
                    catalog_batch,
                    references,
                    source_store,
                )
                metric_parts.append(processed.metrics)
                warnings.extend(processed.warnings)
                with session_scope(self.session_factory) as session:
                    store_model = StoreRepository(session).get(
                        connector.chain,
                        source_store.external_id,
                    )
                    if store_model is None:
                        raise LookupError("persisted source store is missing")
                    self._persist_catalog(
                        session,
                        processed,
                        snapshot_id=snapshot_id,
                        run_id=run_id,
                        store=store_model,
                        raw_rows=raw_rows,
                    )
                    successful_stores += 1

            runtime_ms = round((monotonic() - started) * 1000)
            transport = _sum_transport(transport_parts)
            aggregate = _sum_metrics(metric_parts, runtime_ms=runtime_ms).model_copy(
                update={
                    "stores_found": len(stores),
                    "stores_successful": successful_stores,
                    "stores_failed": max(0, len(catalog_stores) - successful_stores),
                    "request_count": transport.request_count or raw_count,
                    "http_error_count": transport.http_error_count,
                    "rate_limit_count": transport.rate_limit_count,
                }
            )
            with session_scope(self.session_factory) as session:
                snapshots = SnapshotRepository(session)
                baseline = snapshots.get(baseline_id) if baseline_id else None
                baseline_metrics = None
                baseline_schemas: dict[str, Any] = {}
                if baseline is not None:
                    baseline_payload = baseline.metrics or {}
                    baseline_metrics = RunMetrics.model_validate(
                        baseline_payload.get("run_metrics", {})
                    )
                    baseline_schemas = baseline_payload.get("schemas", {})
                schema_diff = _merge_schema_diff(baseline_schemas, all_schemas)
                effective_schema_diff = _review_schema_diff(
                    connector.chain, connector.parser_version, schema_diff, schemas=all_schemas,
                )
                assessment = assess_run_health(
                    aggregate,
                    baseline=baseline_metrics,
                    schema_diff=effective_schema_diff,
                )
                if not stores or aggregate.products_parsed == 0:
                    assessment = assessment.model_copy(update={"status": ConnectorStatus.BROKEN})
                    warnings.append("no stores or parsed products; snapshot cannot be promoted")
                snapshot = snapshots.get(snapshot_id, lock=True)
                if snapshot is None:
                    raise LookupError("catalog snapshot disappeared")
                snapshot.metrics = {
                    "runtime_build_id": os.getenv("BUILD_ID", "unknown"),
                    "source_scope": source_scope.model_dump(mode="json"),
                    "run_metrics": aggregate.model_dump(mode="json"),
                    "schemas": {
                        kind: fingerprint.model_dump(mode="json")
                        for kind, fingerprint in sorted(all_schemas.items())
                    },
                    "schema_diff": schema_diff.model_dump(mode="json") if schema_diff else None,
                    "effective_schema_diff": (
                        effective_schema_diff.model_dump(mode="json")
                        if effective_schema_diff else None
                    ),
                    "catalog_completion": {
                        store_id: _catalog_completion_payload(evidence)
                        for store_id, evidence in sorted(completion_by_store.items())
                    },
                    "minimum_products_for_full_catalog": minimum_products,
                    "source_policy_audit": policy_payload,
                }
                snapshot.schema_fingerprint = fingerprint_json(
                    {kind: fingerprint.digest for kind, fingerprint in all_schemas.items()}
                ).digest
                snapshots.transition(snapshot_id, SnapshotState.PARSED)
                snapshots.transition(snapshot_id, SnapshotState.VALIDATED)
                snapshots.transition(snapshot_id, SnapshotState.HEALTH_CHECKED)
                healthy_candidate = assessment.status == ConnectorStatus.HEALTHY
                row_acceptance = getattr(connector, "row_acceptance", None)
                row_candidate = False
                if row_acceptance is not None:
                    from grocery_data.app.services.offer_rows import contract_allows_publication

                    row_candidate = contract_allows_publication(
                        row_acceptance, metrics=aggregate, scope_key=scope_key,
                        chain=connector.chain.value, coverage=connector.coverage.value)
                    # Schema change is shared evidence. Row isolation cannot
                    # bless a changed parser contract or a transport failure.
                    if effective_schema_diff and effective_schema_diff.has_changes:
                        row_candidate = False
                    snapshot.metrics = {**snapshot.metrics, "row_acceptance": row_acceptance,
                        "full_snapshot_health": getattr(connector, "original_full_health", assessment.status.value),
                        "acceptance_status": "partial_row_approved" if row_candidate else "row_candidate_blocked"}
                promoted = auto_promote and (row_candidate if row_acceptance is not None else healthy_candidate)
                if promoted:
                    promoted_snapshot = snapshots.promote(snapshot_id)
                    StoreRepository(session).reconcile_scope(
                        connector.chain,
                        city=area.city,
                        seen_external_ids={store.external_id for store in stores},
                        deactivate_unseen=(scope_key == area.city.casefold().strip()),
                    )
                    # Promotion and pickup-context activation share one atomic
                    # transaction, so a missing exact relation or raw price
                    # lineage cannot replace the last-known-good context.
                    activate_promoted_coop_online_context(session, promoted_snapshot)
                    activate_promoted_hemkop_online_context(session, promoted_snapshot)
                    active_snapshot_id = snapshot_id
                elif not (row_candidate if row_acceptance is not None else healthy_candidate):
                    snapshots.reject(
                        snapshot_id,
                        reason="; ".join((*assessment.warnings, *warnings))[:2000]
                        or "health check failed",
                    )
                    active = snapshots.active(connector.chain, scope_key=scope_key)
                    active_snapshot_id = active.id if active else None
                else:
                    active = snapshots.active(connector.chain, scope_key=scope_key)
                    active_snapshot_id = active.id if active else None
                health = ConnectorHealth(
                    chain=connector.chain,
                    coverage=connector.coverage,
                    status=assessment.status,
                    last_success_at=(
                        datetime.now(tz=UTC)
                        if promoted
                        else baseline.promoted_at
                        if baseline is not None
                        else None
                    ),
                    active_snapshot_id=active_snapshot_id,
                    metrics=aggregate,
                    warnings=(*assessment.warnings, *warnings),
                    schema_fingerprint=snapshot.schema_fingerprint,
                )
                # A healthy review candidate is evidence about the candidate,
                # not a replacement for connector health/freshness of the
                # currently active snapshot. Manual promotion updates health.
                if promoted or not healthy_candidate:
                    ConnectorHealthRepository(session).upsert(health)
                run_metrics = aggregate.model_dump(mode="json")
                if row_acceptance is not None:
                    run_metrics.update(acceptance_contract=row_acceptance["contract"],
                                       partial_rows_published=promoted,
                                       full_fetch_quality=row_acceptance["full_parse"])
                if policy_payload is not None:
                    run_metrics.update(policy_payload)
                CollectorRunRepository(session).finish(
                    run_id,
                    successful=healthy_candidate or row_candidate,
                    metrics=run_metrics,
                    error_summary=(
                        None if healthy_candidate else "; ".join(health.warnings)[:2000]
                    ),
                )
                for alert in alerts_from_assessment(
                    assessment,
                    chain=connector.chain,
                    snapshot_id=snapshot_id,
                ):
                    self.alert_sink.send(alert)
            self._emit_event(
                CollectorEventType.FINISHED,
                connector,
                scope_key,
                snapshot_id,
                metrics=aggregate,
                status=assessment.status,
            )
            return CollectionResult(
                chain=connector.chain,
                scope_key=scope_key,
                snapshot_id=snapshot_id,
                status=assessment.status,
                promoted=promoted,
                active_snapshot_id=active_snapshot_id,
                stores=tuple(stores),
                metrics=aggregate,
                warnings=(*assessment.warnings, *warnings),
                raw_documents=raw_count,
                source_policy_audit=policy_audit,
            )
        except Exception as exc:
            failed_metrics = _sum_metrics(
                metric_parts,
                runtime_ms=round((monotonic() - started) * 1000),
            )
            transport = _sum_transport(transport_parts)
            failed_metrics = failed_metrics.model_copy(
                update={
                    "stores_found": len(stores),
                    "stores_successful": successful_stores,
                    "stores_failed": max(
                        0,
                        len(_eligible_catalog_stores(connector, stores)) - successful_stores,
                    ),
                    "request_count": transport.request_count or raw_count,
                    "http_error_count": transport.http_error_count,
                    "rate_limit_count": transport.rate_limit_count,
                }
            )
            self._emit_event(
                CollectorEventType.FAILED,
                connector,
                scope_key,
                snapshot_id,
                metrics=failed_metrics,
                status=ConnectorStatus.BROKEN,
            )
            with session_scope(self.session_factory) as session:
                snapshots = SnapshotRepository(session)
                snapshot = snapshots.get(snapshot_id)
                if snapshot is not None and snapshot.state not in {
                    SnapshotState.PROMOTED.value,
                    SnapshotState.REJECTED.value,
                }:
                    snapshots.reject(snapshot_id, reason=type(exc).__name__)
                active = snapshots.active(connector.chain, scope_key=scope_key)
                if snapshot is not None:
                    snapshot.metrics = {
                        "runtime_build_id": os.getenv("BUILD_ID", "unknown"),
                        "source_scope": source_scope.model_dump(mode="json"),
                        "run_metrics": failed_metrics.model_dump(mode="json"),
                        "schemas": {
                            kind: fingerprint.model_dump(mode="json")
                            for kind, fingerprint in sorted(all_schemas.items())
                        },
                        "catalog_completion": {
                            store_id: _catalog_completion_payload(evidence)
                            for store_id, evidence in sorted(completion_by_store.items())
                        },
                        "minimum_products_for_full_catalog": minimum_products,
                        "failure_type": type(exc).__name__,
                        "source_policy_audit": policy_payload,
                    }
                    if all_schemas:
                        snapshot.schema_fingerprint = fingerprint_json(
                            {kind: fingerprint.digest for kind, fingerprint in all_schemas.items()}
                        ).digest
                ConnectorHealthRepository(session).upsert(
                    ConnectorHealth(
                        chain=connector.chain,
                        coverage=connector.coverage,
                        status=ConnectorStatus.BROKEN,
                        last_success_at=active.promoted_at if active else None,
                        active_snapshot_id=active.id if active else None,
                        metrics=failed_metrics,
                        warnings=(type(exc).__name__,),
                    )
                )
                failed_run_metrics = failed_metrics.model_dump(mode="json")
                if policy_payload is not None:
                    failed_run_metrics.update(policy_payload)
                CollectorRunRepository(session).finish(
                    run_id,
                    successful=False,
                    metrics=failed_run_metrics,
                    error_summary=type(exc).__name__,
                )
            raise
        finally:
            await connector.aclose()
