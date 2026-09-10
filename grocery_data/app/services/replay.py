from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from grocery_data.app.connectors.base import GroceryConnector
from grocery_data.app.domain import (
    CanonicalProduct,
    CatalogCompletion,
    ConnectorHealth,
    ConnectorStatus,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    RawFetch,
    RunMetrics,
    SnapshotState,
    SourceScopeDescriptor,
    SourceStore,
    StoredRawDocument,
)
from grocery_data.app.monitoring import SchemaFingerprint, assess_run_health, fingerprint_json
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.collector import (
    GroceryCollector,
    _catalog_completion_payload,
    _eligible_catalog_stores,
    _merge_schema_diff,
    _schema_fingerprints,
    _sum_metrics,
)
from grocery_data.app.services.coop_online_context_activation import (
    activate_promoted_coop_online_context,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import (
    CollectorRunRepository,
    ConnectorHealthRepository,
    RawSnapshotRepository,
    SessionFactory,
    SnapshotRepository,
    StoreRepository,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    RawSnapshotModel,
    StoreModel,
)


@dataclass(frozen=True, slots=True)
class ReplayResult:
    parsed: ProductParseResult
    normalized: tuple[CanonicalProduct, ...]
    network_requests: int = 0


class ReplayService:
    """Re-run parser and normalizer from immutable local evidence only."""

    def __init__(
        self,
        raw_store: FilesystemRawSnapshotStore,
        normalizer: ProductNormalizer | None = None,
    ) -> None:
        self.raw_store = raw_store
        self.normalizer = normalizer or ProductNormalizer()

    def replay_catalog(
        self,
        connector: GroceryConnector,
        records: list[StoredRawDocument],
        store: SourceStore,
    ) -> ReplayResult:
        documents = tuple(
            RawFetch(
                chain=record.chain,
                store_external_id=record.store_external_id,
                kind=record.kind,
                method=record.method,
                url=record.url,
                query=record.query,
                fetched_at=record.fetched_at,
                http_status=record.http_status,
                content_type=record.content_type,
                payload=self.raw_store.load(record),
                connector_version=record.connector_version,
                page_number=record.page_number,
            )
            for record in records
        )
        batch = RawBatch(chain=connector.chain, documents=documents)
        references = [f"raw:{record.document_id}" for record in records]
        parsed = connector.parse_catalog(batch, references, store)
        normalized = tuple(
            self.normalizer.normalize(product, parser_version=connector.parser_version)
            for product in parsed.products
        )
        return ReplayResult(parsed=parsed, normalized=normalized)


@dataclass(frozen=True, slots=True)
class SnapshotReplayResult:
    source_snapshot_id: str
    replay_snapshot_id: str
    network_requests: int
    products_parsed: int
    products_quarantined: int
    status: ConnectorStatus
    promoted: bool


class DatabaseReplayService:
    """Create a new candidate snapshot by replaying saved response bodies."""

    def __init__(
        self,
        session_factory: SessionFactory,
        raw_store: FilesystemRawSnapshotStore,
        normalizer: ProductNormalizer | None = None,
        *,
        full_catalog_min_products: int = 100,
    ) -> None:
        self.session_factory = session_factory
        self.raw_store = raw_store
        self.normalizer = normalizer or ProductNormalizer()
        self.collector = GroceryCollector(
            session_factory,
            raw_store,
            normalizer=self.normalizer,
            full_catalog_min_products=full_catalog_min_products,
        )

    @staticmethod
    def _stored(row: RawSnapshotModel) -> StoredRawDocument:
        return StoredRawDocument(
            snapshot_id=row.catalog_snapshot_id,
            document_id=row.id,
            chain=row.chain,
            store_external_id=row.store_external_id,
            kind=row.kind,
            method=row.method,
            url=row.url,
            query=row.query,
            relative_path=row.payload_location,
            payload_hash=row.payload_hash,
            fetched_at=row.fetched_at,
            http_status=row.http_status,
            content_type=row.content_type,
            connector_version=row.connector_version,
            page_number=row.page_number,
            schema_fingerprint=row.schema_fingerprint,
        )

    def _load_batch(
        self,
        rows: list[RawSnapshotModel],
        connector: GroceryConnector,
        *,
        catalog_completion: CatalogCompletion | None = None,
    ) -> RawBatch:
        documents = tuple(
            RawFetch(
                chain=connector.chain,
                store_external_id=row.store_external_id,
                kind=row.kind,
                method=row.method,
                url=row.url,
                query=row.query,
                fetched_at=row.fetched_at,
                http_status=row.http_status,
                content_type=row.content_type,
                payload=self.raw_store.load(self._stored(row)),
                connector_version=row.connector_version,
                page_number=row.page_number,
            )
            for row in rows
        )
        return RawBatch(
            chain=connector.chain,
            documents=documents,
            catalog_completion=catalog_completion,
        )

    @staticmethod
    def _validated_source_scope(
        value: object,
        *,
        expected_scope_key: str,
    ) -> SourceScopeDescriptor | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise TypeError("snapshot source-scope descriptor is invalid")
        descriptor = SourceScopeDescriptor.model_validate(value)
        if descriptor.scope_key != expected_scope_key:
            raise ValueError("snapshot source-scope descriptor does not match scope_key")
        return descriptor

    @classmethod
    def _source_scope_for_replay(
        cls,
        session: Session,
        source_snapshot: CatalogSnapshotModel,
        source_rows: list[RawSnapshotModel],
    ) -> SourceScopeDescriptor:
        """Recover geography without treating an ownership key as a city.

        New snapshots persist an explicit descriptor.  Older snapshots first
        reuse the descriptor on their collector run, then recover one exact
        city from their already-persisted contextual stores.  Only a legacy
        plain (non-contextual) scope key retains the old city fallback.
        """

        metrics = source_snapshot.metrics or {}
        descriptor = cls._validated_source_scope(
            metrics.get("source_scope"),
            expected_scope_key=source_snapshot.scope_key,
        )
        if descriptor is not None:
            return descriptor

        if source_snapshot.collector_run_id is not None:
            run = session.get(CollectorRunModel, source_snapshot.collector_run_id)
            if run is not None:
                run_scope = run.scope or {}
                descriptor = cls._validated_source_scope(
                    run_scope.get("source_scope"),
                    expected_scope_key=source_snapshot.scope_key,
                )
                if descriptor is not None:
                    return descriptor

        contextual_store_ids = {
            row.store_external_id for row in source_rows if row.store_external_id is not None
        }
        cities_by_key: dict[str, str] = {}
        if contextual_store_ids:
            stores = session.scalars(
                select(StoreModel)
                .where(
                    StoreModel.chain == source_snapshot.chain,
                    StoreModel.external_id.in_(contextual_store_ids),
                )
                .order_by(StoreModel.id)
            )
            for store in stores:
                city = (store.city or "").strip()
                if city:
                    cities_by_key.setdefault(city.casefold(), city)
        if len(cities_by_key) == 1:
            city = next(iter(cities_by_key.values()))
            return SourceScopeDescriptor(
                scope_key=source_snapshot.scope_key,
                geographic_area=GeographicArea(city=city),
            )
        if len(cities_by_key) > 1:
            raise ValueError("legacy snapshot spans multiple persisted geographic cities")

        # Before explicit descriptors, an unqualified scope key was the city.
        # A compound key is never guessed: it needs persisted store evidence.
        if ":" not in source_snapshot.scope_key:
            return SourceScopeDescriptor(
                scope_key=source_snapshot.scope_key,
                geographic_area=GeographicArea(city=source_snapshot.scope_key),
            )
        raise ValueError("legacy contextual snapshot lacks recoverable geographic scope")

    async def replay_snapshot(
        self,
        connector: GroceryConnector,
        snapshot_id: str,
        *,
        promote: bool = False,
        accept_schema_change: bool = False,
    ) -> SnapshotReplayResult:
        with session_scope(self.session_factory) as session:
            source_snapshot = SnapshotRepository(session).get(snapshot_id)
            if source_snapshot is None:
                raise LookupError(f"catalog snapshot {snapshot_id!r} does not exist")
            if source_snapshot.chain != connector.chain.value:
                raise ValueError("connector chain does not match replay snapshot")
            source_rows = list(
                session.scalars(
                    select(RawSnapshotModel)
                    .where(RawSnapshotModel.catalog_snapshot_id == snapshot_id)
                    .order_by(RawSnapshotModel.created_at, RawSnapshotModel.id)
                )
            )
            if not source_rows:
                raise ValueError("snapshot has no replayable raw responses")
            scope_key = source_snapshot.scope_key
            source_scope = self._source_scope_for_replay(
                session,
                source_snapshot,
                source_rows,
            )
            coverage = source_snapshot.coverage
            source_metrics = source_snapshot.metrics or {}
            relay_evidence = source_metrics.get("source_artifact") or source_metrics.get(
                "source_artifact_lineage"
            )
            relay_lineage = (
                {"collection_location": "LOCAL_RELAY"}
                if isinstance(relay_evidence, dict)
                and relay_evidence.get("collection_location") == "LOCAL_RELAY"
                else None
            )
            raw_completion = (source_snapshot.metrics or {}).get("catalog_completion", {})
            if not isinstance(raw_completion, dict):
                raise TypeError("snapshot catalog-completion evidence is invalid")
            source_minimum = (source_snapshot.metrics or {}).get(
                "minimum_products_for_full_catalog"
            )
            effective_minimum = self.collector._minimum_products_for_complete_catalog(
                connector,
                persisted_minimum=source_minimum,
            )
            completion_by_store = {
                str(store_id): CatalogCompletion.model_validate(evidence)
                for store_id, evidence in raw_completion.items()
            }

        run_id, replay_id, baseline_id = self.collector._start(
            connector,
            scope_key,
            source_scope=source_scope,
        )
        schemas: dict[str, object] = {}
        metric_parts = []
        completion_failures: list[str] = []
        stores: list[SourceStore] = []
        catalog_stores: list[SourceStore] = []
        try:
            # Store-discovery document names are connector-local (for example
            # Willys ``stores`` and ICA ``stores_page``). Discovery fetches
            # are the raw documents without a store context; replay must not
            # hard-code one chain's kind name.
            store_rows = [row for row in source_rows if row.store_external_id is None]
            store_batch = self._load_batch(store_rows, connector)
            store_schema = _schema_fingerprints(store_batch)
            schemas.update(store_schema)
            with session_scope(self.session_factory) as session:
                raw_repository = RawSnapshotRepository(session)
                new_raw_by_old: dict[str, RawSnapshotModel] = {}
                for old, document in zip(store_rows, store_batch.documents, strict=True):
                    new_raw_by_old[old.id] = raw_repository.record_fetch(
                        document,
                        catalog_snapshot_id=replay_id,
                        collector_run_id=run_id,
                        payload_location=old.payload_location,
                        schema_fingerprint=old.schema_fingerprint,
                    )
                references = [f"raw:{row.id}" for row in store_rows]
                stores = connector.parse_stores(
                    store_batch,
                    references,
                    source_scope.geographic_area,
                )
                store_repository = StoreRepository(session)
                for store in stores:
                    store_repository.upsert(store, activate=None)

            catalog_rows_by_store: dict[str, list[RawSnapshotModel]] = {}
            for row in source_rows:
                if row.store_external_id is None:
                    continue
                catalog_rows_by_store.setdefault(row.store_external_id, []).append(row)
            catalog_stores = _eligible_catalog_stores(connector, stores)
            for store in catalog_stores:
                old_rows = catalog_rows_by_store.get(store.external_id, [])
                batch = self._load_batch(
                    old_rows,
                    connector,
                    catalog_completion=completion_by_store.get(store.external_id),
                )
                completion_reconciler = getattr(
                    connector,
                    "reconcile_replay_catalog_completion",
                    None,
                )
                if completion_reconciler is not None:
                    if not callable(completion_reconciler):
                        raise TypeError("reconcile_replay_catalog_completion must be callable")
                    reconciled = completion_reconciler(batch, store)
                    if not isinstance(reconciled, RawBatch):
                        raise TypeError("reconcile_replay_catalog_completion must return RawBatch")
                    if reconciled.chain is not connector.chain:
                        raise ValueError("reconciled replay batch changed source chain")
                    batch = reconciled
                    if batch.catalog_completion is None:
                        raise ValueError("reconciled replay batch lacks completion evidence")
                    completion_by_store[store.external_id] = batch.catalog_completion
                try:
                    self.collector._validate_catalog_completion(
                        connector,
                        batch,
                        minimum_products=effective_minimum,
                    )
                except RuntimeError as exc:
                    # Incomplete captures remain useful parser-repair evidence,
                    # but can never become an active full-catalog snapshot.
                    completion_failures.append(f"{store.external_id}:{type(exc).__name__}")
                local_schemas = _schema_fingerprints(batch)
                schemas.update(
                    {
                        f"{store.external_id}:{kind}": fingerprint
                        for kind, fingerprint in local_schemas.items()
                    }
                )
                with session_scope(self.session_factory) as session:
                    raw_repository = RawSnapshotRepository(session)
                    raw_map: dict[str, RawSnapshotModel] = {}
                    for old, document in zip(old_rows, batch.documents, strict=True):
                        raw_map[old.id] = raw_repository.record_fetch(
                            document,
                            catalog_snapshot_id=replay_id,
                            collector_run_id=run_id,
                            payload_location=old.payload_location,
                            schema_fingerprint=old.schema_fingerprint,
                        )
                    references = [f"raw:{row.id}" for row in old_rows]
                    processed = self.collector.processor.process(
                        connector,
                        batch,
                        references,
                        store,
                    )
                    metric_parts.append(processed.metrics)
                    store_model = StoreRepository(session).get(connector.chain, store.external_id)
                    if store_model is None:
                        raise LookupError("replay store is missing")
                    self.collector._persist_catalog(
                        session,
                        processed,
                        snapshot_id=replay_id,
                        run_id=run_id,
                        store=store_model,
                        raw_rows=raw_map,
                    )

            aggregate = _sum_metrics(metric_parts).model_copy(
                update={
                    "stores_found": len(stores),
                    "stores_successful": len(metric_parts),
                    "stores_failed": max(0, len(catalog_stores) - len(metric_parts)),
                    "request_count": 0,
                }
            )
            with session_scope(self.session_factory) as session:
                snapshots = SnapshotRepository(session)
                replay_snapshot = snapshots.get(replay_id, lock=True)
                baseline = snapshots.get(baseline_id) if baseline_id else None
                if replay_snapshot is None:
                    raise LookupError("replay snapshot disappeared")
                baseline_metrics = None
                baseline_schemas = {}
                if baseline is not None:
                    baseline_metrics = RunMetrics.model_validate(
                        (baseline.metrics or {}).get("run_metrics", {})
                    )
                    baseline_schemas = (baseline.metrics or {}).get("schemas", {})
                typed_schemas = {
                    key: value
                    for key, value in schemas.items()
                    if isinstance(value, SchemaFingerprint)
                }
                schema_diff = _merge_schema_diff(baseline_schemas, typed_schemas)
                assessment = assess_run_health(
                    aggregate,
                    baseline=baseline_metrics,
                    schema_diff=None if accept_schema_change else schema_diff,
                )
                if aggregate.products_parsed == 0 or completion_failures:
                    assessment = assessment.model_copy(update={"status": ConnectorStatus.BROKEN})
                replay_snapshot.coverage = coverage
                replay_snapshot.metrics = {
                    **({"source_artifact_lineage": relay_lineage} if relay_lineage else {}),
                    "source_scope": source_scope.model_dump(mode="json"),
                    "run_metrics": aggregate.model_dump(mode="json"),
                    "schemas": {
                        kind: fingerprint.model_dump(mode="json")
                        for kind, fingerprint in typed_schemas.items()
                    },
                    "schema_diff": schema_diff.model_dump(mode="json") if schema_diff else None,
                    "replayed_from": snapshot_id,
                    "network_requests": 0,
                    "schema_change_accepted": accept_schema_change,
                    "catalog_completion": {
                        store_id: _catalog_completion_payload(evidence)
                        for store_id, evidence in sorted(completion_by_store.items())
                    },
                    "minimum_products_for_full_catalog": effective_minimum,
                    "completion_failures": completion_failures,
                }
                replay_snapshot.schema_fingerprint = fingerprint_json(
                    {
                        kind: fingerprint.digest
                        for kind, fingerprint in sorted(typed_schemas.items())
                    }
                ).digest
                snapshots.transition(replay_id, "parsed")
                snapshots.transition(replay_id, "validated")
                snapshots.transition(replay_id, "health_checked")
                promoted = promote and assessment.status == ConnectorStatus.HEALTHY
                if promoted:
                    promoted_snapshot = snapshots.promote(replay_id)
                    StoreRepository(session).reconcile_scope(
                        connector.chain,
                        city=source_scope.geographic_area.city,
                        seen_external_ids={store.external_id for store in stores},
                        deactivate_unseen=(
                            scope_key == source_scope.geographic_area.city.casefold().strip()
                        ),
                    )
                    activate_promoted_coop_online_context(session, promoted_snapshot)
                elif assessment.status == ConnectorStatus.BROKEN:
                    snapshots.reject(replay_id, reason="replay health check failed")
                active = snapshots.active(connector.chain, scope_key=scope_key)
                if promoted or assessment.status == ConnectorStatus.BROKEN:
                    ConnectorHealthRepository(session).upsert(
                        ConnectorHealth(
                            chain=connector.chain,
                            coverage=connector.coverage,
                            status=assessment.status,
                            last_success_at=(
                                datetime.now(tz=UTC)
                                if promoted
                                else active.promoted_at
                                if active is not None
                                else None
                            ),
                            active_snapshot_id=active.id if active is not None else None,
                            metrics=aggregate,
                            warnings=(*assessment.warnings, *completion_failures),
                            schema_fingerprint=replay_snapshot.schema_fingerprint,
                        )
                    )
                CollectorRunRepository(session).finish(
                    run_id,
                    successful=assessment.status == ConnectorStatus.HEALTHY,
                    metrics=aggregate.model_dump(mode="json"),
                    error_summary=(
                        None
                        if assessment.status == ConnectorStatus.HEALTHY
                        else "; ".join((*assessment.warnings, *completion_failures))[:2000]
                        or "replay health check failed"
                    ),
                )
            return SnapshotReplayResult(
                source_snapshot_id=snapshot_id,
                replay_snapshot_id=replay_id,
                network_requests=0,
                products_parsed=aggregate.products_parsed,
                products_quarantined=aggregate.products_quarantined,
                status=assessment.status,
                promoted=promoted,
            )
        except Exception as exc:
            failed_metrics = _sum_metrics(metric_parts).model_copy(
                update={
                    "stores_found": len(stores),
                    "stores_successful": len(metric_parts),
                    "stores_failed": max(0, len(catalog_stores) - len(metric_parts)),
                    "request_count": 0,
                }
            )
            with session_scope(self.session_factory) as session:
                snapshots = SnapshotRepository(session)
                replay_snapshot = snapshots.get(replay_id)
                failed_schema_fingerprints = {
                    kind: fingerprint
                    for kind, fingerprint in schemas.items()
                    if isinstance(fingerprint, SchemaFingerprint)
                }
                if replay_snapshot is not None:
                    replay_snapshot.metrics = {
                        "source_scope": source_scope.model_dump(mode="json"),
                        "run_metrics": failed_metrics.model_dump(mode="json"),
                        "schemas": {
                            kind: fingerprint.model_dump(mode="json")
                            for kind, fingerprint in sorted(failed_schema_fingerprints.items())
                        },
                        "catalog_completion": {
                            store_id: _catalog_completion_payload(evidence)
                            for store_id, evidence in sorted(completion_by_store.items())
                        },
                        "minimum_products_for_full_catalog": effective_minimum,
                        "replayed_from": snapshot_id,
                        "network_requests": 0,
                        "failure_type": type(exc).__name__,
                    }
                    if failed_schema_fingerprints:
                        replay_snapshot.schema_fingerprint = fingerprint_json(
                            {
                                kind: fingerprint.digest
                                for kind, fingerprint in failed_schema_fingerprints.items()
                            }
                        ).digest
                    if replay_snapshot.state not in {
                        SnapshotState.PROMOTED.value,
                        SnapshotState.REJECTED.value,
                    }:
                        snapshots.reject(replay_id, reason=type(exc).__name__)
                active = snapshots.active(connector.chain, scope_key=scope_key)
                ConnectorHealthRepository(session).upsert(
                    ConnectorHealth(
                        chain=connector.chain,
                        coverage=connector.coverage,
                        status=ConnectorStatus.BROKEN,
                        last_success_at=active.promoted_at if active is not None else None,
                        active_snapshot_id=active.id if active is not None else None,
                        metrics=failed_metrics,
                        warnings=(type(exc).__name__,),
                        schema_fingerprint=(
                            replay_snapshot.schema_fingerprint
                            if replay_snapshot is not None
                            else None
                        ),
                    )
                )
                CollectorRunRepository(session).finish(
                    run_id,
                    successful=False,
                    metrics=failed_metrics.model_dump(mode="json"),
                    error_summary=type(exc).__name__,
                )
            raise
        finally:
            await connector.aclose()
