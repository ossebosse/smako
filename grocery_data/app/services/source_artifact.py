"""Portable sanitized raw-source snapshots with independent qualification."""

from __future__ import annotations

import json
import os
import re
import zipfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.willys.connector import WillysConnector
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    GeographicArea,
    RawBatch,
    RawFetch,
    SourceCollectionAudit,
    SourceScopeDescriptor,
)
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.durable_files import _fsync_directory, require_free_space
from grocery_data.app.services.prepared_universe_activation import _assert_credential_free
from grocery_data.app.services.raw_storage import sanitize_json_payload

SCHEMA = "smako-source-snapshot-v1"
APPROVED_WILLYS_CONTEXTS = ("2176", "2354")
MAX_BYTES = 256 * 1024 * 1024
MAX_DOCUMENTS = 6000
HASH = re.compile(r"^[0-9a-f]{64}$")


class SourceArtifactError(ValueError):
    pass


def willys_collection_location() -> Literal["VPS_DIRECT", "LOCAL_RELAY"]:
    value = os.getenv("WILLYS_COLLECTION_LOCATION", "VPS_DIRECT").strip().upper()
    if value not in {"VPS_DIRECT", "LOCAL_RELAY"}:
        raise SourceArtifactError("unsupported Willys collection location")
    return value


class PayloadEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    metadata: dict[str, Any]
    path: str
    size: int = Field(ge=0, le=8 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["smako-source-snapshot-v1"] = SCHEMA
    source: Chain = Chain.WILLYS
    collection_location: Literal["LOCAL_RELAY"] = "LOCAL_RELAY"
    context_ids: tuple[str, ...]
    source_snapshot_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    parent_snapshot_ids: tuple[Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")], ...] = Field(
        default=(), max_length=4
    )
    source_scope: SourceScopeDescriptor
    municipality_boundary: dict[str, Any] | None = None
    collection_started_at: datetime
    collection_finished_at: datetime
    observed_from: datetime
    observed_to: datetime
    collector_version: str
    parser_version: str
    normalizer_version: str
    source_policy_version: str
    source_policy: SourceCollectionAudit
    row_count: int = Field(gt=0)
    product_count: int = Field(gt=0)
    request_count: int = Field(gt=0)
    catalog_completion: dict[str, CatalogCompletion]
    payloads: tuple[PayloadEntry, ...]


class VerifiedSourceArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)
    manifest: SourceManifest
    artifact_sha256: str
    documents: tuple[RawFetch, ...]
    completion: dict[str, CatalogCompletion]


def _json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise SourceArtifactError("source timestamps must include timezone")
    return value.astimezone(UTC)


def _source_stores(documents, area, boundary):
    raw = RawBatch(chain=Chain.WILLYS, documents=documents)
    refs = ["artifact:stores"] * len(documents)
    if area.mode == "municipality":
        from grocery_data.app.connectors.willys.municipality_inventory import build_inventory
        from grocery_data.app.domain import SourceStore

        inventory = build_inventory(area, raw, refs, boundary)
        return [SourceStore.model_validate(row["store"]) for row in inventory["stores"]
                if row["collection_selected"]]
    if boundary is not None:
        raise SourceArtifactError("municipal evidence on legacy locality contract")
    return WillysParser().parse_stores(raw, refs, area)


def _verify_scope(manifest):
    area = manifest.source_scope.geographic_area
    if area.mode == "municipality":
        if (manifest.source_scope.scope_key not in {area.city.casefold(), area.area_key.casefold()} or not manifest.municipality_boundary
                or manifest.source_policy_version != "willys-municipality-policy-v1"
                or not manifest.context_ids or tuple(sorted(set(manifest.context_ids))) != manifest.context_ids):
            raise SourceArtifactError("invalid municipal source contract")
    elif (manifest.source_scope.scope_key != "lund" or area.city.casefold() != "lund"
          or manifest.context_ids != APPROVED_WILLYS_CONTEXTS or manifest.municipality_boundary is not None
          or manifest.source_policy_version != "willys-source-policy-v1"):
        raise SourceArtifactError("unapproved legacy geographic source scope")


def _willys_completion(documents: tuple[RawFetch, ...], *, area=None, boundary=None, contexts=APPROVED_WILLYS_CONTEXTS) -> dict[str, CatalogCompletion]:
    """Derive completion from tree/pages; never trust a producer PASS flag."""
    allowed = contexts
    parser = WillysParser()
    discovery = [d for d in documents if d.kind == "stores"]
    if len(discovery) != 1 or discovery[0].store_external_id is not None:
        raise SourceArtifactError("one original store discovery is required")
    stores = _source_stores(tuple(discovery), area or GeographicArea(city="Lund"), boundary)
    chosen = [s for s in stores if s.external_id in allowed]
    if {s.external_id for s in chosen} != set(allowed):
        raise SourceArtifactError("approved contexts are absent from source discovery")
    if any(s.online_shopping is not True for s in chosen):
        raise SourceArtifactError("source context does not support online prices")
    completion = {}
    for context in allowed:
        scoped = [d for d in documents if d.store_external_id == context]
        by_kind: dict[str, list[RawFetch]] = defaultdict(list)
        for d in scoped:
            by_kind[d.kind].append(d)
        for kind in ("store_activation", "store_context", "category_tree"):
            if len(by_kind[kind]) != 1:
                raise SourceArtifactError("missing/duplicate original context or category evidence")
        activation, active, tree = (
            by_kind[k][0] for k in ("store_activation", "store_context", "category_tree")
        )
        if activation.query != {
            "storeId": context,
            "activelySelected": "true",
            "forceAsPickingStore": "true",
        }:
            raise SourceArtifactError("unapproved store activation shape")
        if activation.json_payload() != {}:
            raise SourceArtifactError("activation payload must not carry session data")
        if not WillysClient._contains_store_id(active.json_payload(), context):
            raise SourceArtifactError("active price context mismatch")
        leaves = parser.category_leaf_paths(tree.payload)
        if not leaves or len(set(leaves)) != len(leaves):
            raise SourceArtifactError("category tree is empty or duplicated")
        pages: dict[str, dict[int, RawFetch]] = defaultdict(dict)
        for d in by_kind["catalog_page"]:
            path = urlsplit(d.url).path.removeprefix("/axfood/rest/v1/c/")
            n = d.page_number
            if path not in leaves or n is None or n < 0 or n in pages[path]:
                raise SourceArtifactError("unapproved category or duplicate page")
            if d.query != {"page": str(n), "size": "30"}:
                raise SourceArtifactError("catalog page request shape changed")
            if not activation.fetched_at <= active.fetched_at <= tree.fetched_at <= d.fetched_at:
                raise SourceArtifactError("catalog observation precedes context activation")
            pages[path][n] = d
        if set(pages) != set(leaves):
            raise SourceArtifactError("category traversal is incomplete")
        products = set()
        for path in leaves:
            partition = pages[path]
            if 0 not in partition:
                raise SourceArtifactError("category first page missing")
            _, expected = WillysClient._validated_catalog_page(
                partition[0].json_payload(), requested_page=0
            )
            if set(partition) != set(range(max(1, expected))):
                raise SourceArtifactError("category page sequence is incomplete")
            previous = tree.fetched_at
            for n in sorted(partition):
                d = partition[n]
                rows, count = WillysClient._validated_catalog_page(
                    d.json_payload(), requested_page=n
                )
                if count != expected or d.fetched_at < previous:
                    raise SourceArtifactError("pagination count or observation order changed")
                previous = d.fetched_at
                for row in rows:
                    if not isinstance(row, dict) or not row.get("code"):
                        raise SourceArtifactError("catalog product identity missing")
                    products.add(str(row["code"]))
        if len(products) < 100:
            raise SourceArtifactError("catalog product count below normal minimum")
        completion[context] = CatalogCompletion(
            complete=True,
            limited=False,
            expected_categories=len(leaves),
            completed_categories=len(leaves),
            pages_fetched=sum(map(len, pages.values())),
            products_observed=len(products),
        )
    return completion


def verify_source_artifact(path: Path, *, now: datetime | None = None) -> VerifiedSourceArtifact:
    now = _aware(now or datetime.now(UTC))
    if path.suffix != ".smako-source" or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise SourceArtifactError("invalid or incomplete source container")
    data = path.read_bytes()
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) > MAX_DOCUMENTS + 2 or len(names) != len(set(names)):
                raise SourceArtifactError("duplicate or excessive archive entries")
            if sum(i.file_size for i in infos) > MAX_BYTES:
                raise SourceArtifactError("source artifact exceeds expanded size bound")
            if any(i.flag_bits & 1 or i.file_size > 8 * 1024 * 1024 for i in infos):
                raise SourceArtifactError("encrypted or oversized archive entry")
            manifest_data = archive.read("manifest.json")
            manifest_hash = archive.read("manifest.sha256").decode("ascii").strip()
            if (
                not HASH.fullmatch(manifest_hash)
                or sha256(manifest_data).hexdigest() != manifest_hash
            ):
                raise SourceArtifactError("manifest hash mismatch")
            _assert_credential_free(json.loads(manifest_data))
            manifest = SourceManifest.model_validate_json(manifest_data)
            # The container is source-neutral; each enabled retailer needs its
            # own independently reviewed qualifier before it can be imported.
            if manifest.source is not Chain.WILLYS:
                raise SourceArtifactError("source has no approved artifact qualifier")
            _verify_scope(manifest)
            if (
                manifest.collector_version != WillysConnector.connector_version
                or manifest.parser_version != WillysConnector.parser_version
            ):
                raise SourceArtifactError("unqualified collector/parser version")
            if manifest.normalizer_version != ProductNormalizer.normalizer_version:
                raise SourceArtifactError("unqualified normalizer version")
            policy = manifest.source_policy
            if (
                policy.source_policy.value != "allow"
                or policy.store_allowlist != manifest.context_ids
                or policy.max_concurrency != 1
                or policy.requests_per_second != 1
            ):
                raise SourceArtifactError("unapproved source collection policy")
            if not len(manifest.payloads) + 2 <= manifest.request_count <= (min(5900, 1000 * len(manifest.context_ids) + 100) if manifest.municipality_boundary else 2000):
                raise SourceArtifactError("request count does not reconcile original evidence")
            expected_names = {"manifest.json", "manifest.sha256"} | {
                p.path for p in manifest.payloads
            }
            if set(names) != expected_names or len(manifest.payloads) != len(expected_names) - 2:
                raise SourceArtifactError("payload inventory mismatch")
            documents = []
            for index, entry in enumerate(manifest.payloads):
                if entry.path != f"raw/{index:05d}.json":
                    raise SourceArtifactError("invalid payload path")
                payload = archive.read(entry.path)
                if len(payload) != entry.size or sha256(payload).hexdigest() != entry.sha256:
                    raise SourceArtifactError("payload hash or length mismatch")
                if set(entry.metadata) != set(RawFetch.model_fields) - {"payload"}:
                    raise SourceArtifactError("unexpected raw metadata fields")
                d = RawFetch.model_validate({**entry.metadata, "payload": payload})
                parsed = d.json_payload()
                _assert_credential_free(parsed)
                if sanitize_json_payload(parsed) != parsed:
                    raise SourceArtifactError(
                        "credential/session-shaped raw data must be sanitized"
                    )
                route = urlsplit(d.url)
                prefix = "/axfood/rest/v1/"
                routes = {
                    "stores": "store",
                    "store_activation": "store/activate",
                    "store_context": "store/active",
                    "category_tree": "leftMenu/categorytree",
                }
                if d.kind not in {*routes, "catalog_page"}:
                    raise SourceArtifactError("unsupported raw evidence kind")
                if (
                    route.scheme != "https"
                    or route.netloc != "www.willys.prod.axcsfprod.aws.axfoodapp.cloud"
                    or route.query
                    or route.fragment
                ):
                    raise SourceArtifactError("raw public endpoint mismatch")
                if d.kind in routes and route.path != prefix + routes[d.kind]:
                    raise SourceArtifactError("raw path mismatch")
                if d.kind == "catalog_page" and not route.path.startswith(prefix + "c/"):
                    raise SourceArtifactError("catalog path mismatch")
                if (
                    d.method != ("POST" if d.kind == "store_activation" else "GET")
                    or d.http_status != 200
                    or "json" not in (d.content_type or "")
                ):
                    raise SourceArtifactError("raw request did not return normal JSON")
                if (d.kind == "stores") != (d.store_external_id is None):
                    raise SourceArtifactError("raw context scope mismatch")
                if d.kind in {"stores", "store_context", "category_tree"} and d.query:
                    raise SourceArtifactError("unexpected public request parameters")
                if (
                    d.store_external_id not in (*manifest.context_ids, None)
                    or d.connector_version != manifest.collector_version
                ):
                    raise SourceArtifactError("raw source context/version mismatch")
                documents.append(d)
    except (zipfile.BadZipFile, KeyError, UnicodeError, TypeError, ValueError) as exc:
        raise SourceArtifactError("source artifact validation failed") from exc
    start, finish, oldest, newest = map(
        _aware,
        (
            manifest.collection_started_at,
            manifest.collection_finished_at,
            manifest.observed_from,
            manifest.observed_to,
        ),
    )
    if not documents or not start <= oldest <= newest <= finish <= now + timedelta(minutes=5):
        raise SourceArtifactError("invalid source observation interval")
    if now - oldest >= timedelta(hours=48):
        raise SourceArtifactError("source artifact is stale; import cannot refresh its age")
    if oldest != min(_aware(d.fetched_at) for d in documents) or newest != max(
        _aware(d.fetched_at) for d in documents
    ):
        raise SourceArtifactError("observation interval does not match raw evidence")
    area = manifest.source_scope.geographic_area
    if area.mode == "municipality":
        chosen = _source_stores(tuple(d for d in documents if d.kind == "stores"), area, manifest.municipality_boundary)
        if {s.external_id for s in chosen} != set(manifest.context_ids):
            raise SourceArtifactError("municipal contexts differ from independently verified inventory")
    completion = _willys_completion(tuple(documents), area=area, boundary=manifest.municipality_boundary, contexts=manifest.context_ids)
    if manifest.catalog_completion != completion:
        raise SourceArtifactError("declared completion differs from independent traversal")
    _verify_product_counts(tuple(documents), manifest)
    return VerifiedSourceArtifact(
        manifest=manifest,
        artifact_sha256=sha256(data).hexdigest(),
        documents=tuple(documents),
        completion=completion,
    )


def _verify_product_counts(documents: tuple[RawFetch, ...], manifest: SourceManifest) -> None:
    """Normal parser, identity, price-sanity and normalization gates before DB writes."""
    from grocery_data.app.monitoring import assess_run_health
    from grocery_data.app.services.catalog_processor import CatalogProcessor
    from grocery_data.app.services.collector import _sum_metrics

    discovery = tuple(d for d in documents if d.kind == "stores")
    parser = WillysParser()
    stores = _source_stores(discovery, manifest.source_scope.geographic_area, manifest.municipality_boundary)
    processor = CatalogProcessor()
    parts = []
    products = []

    # No HTTP client is constructed: only the existing parser protocol is needed.
    class ParserOnly:
        parser_version = WillysParser.parser_version
        parse_catalog = parser.parse_catalog

    for store in stores:
        if store.external_id not in manifest.context_ids:
            continue
        scoped = tuple(d for d in documents if d.store_external_id == store.external_id)
        batch = RawBatch(chain=Chain.WILLYS, documents=scoped)
        processed = processor.process(
            ParserOnly(), batch, [f"artifact:{i}" for i in range(len(scoped))], store
        )
        parts.append(processed.metrics)
        products.extend(processed.products)
    if (
        len(products) != manifest.row_count
        or len({p.canonical.external_product_id for p in products}) != manifest.product_count
    ):
        raise SourceArtifactError("manifest product counts do not reconcile normal parsing")
    if assess_run_health(_sum_metrics(parts)).status.value != "healthy":
        raise SourceArtifactError("source product qualification failed")


def write_source_artifact(
    manifest: SourceManifest, documents: tuple[RawFetch, ...], destination: Path
) -> Path:
    """Publish only a fully verified immutable container, using same-filesystem rename."""
    destination = destination.resolve()
    if destination.suffix != ".smako-source" or destination.exists():
        raise SourceArtifactError("artifact destination must be new and have the final suffix")
    destination.parent.mkdir(parents=True, exist_ok=True)
    require_free_space(
        destination.parent,
        required_bytes=sum(len(d.payload) for d in documents),
        reserve_bytes=64 * 1024 * 1024,
    )
    staged = destination.parent / f".{uuid4().hex}.smako-source"
    try:
        with staged.open("xb") as handle:
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                body = _json(manifest.model_dump(mode="json"))
                archive.writestr("manifest.json", body)
                archive.writestr("manifest.sha256", sha256(body).hexdigest())
                for entry, document in zip(manifest.payloads, documents, strict=True):
                    archive.writestr(entry.path, document.payload)
            handle.flush()
            os.fsync(handle.fileno())
        verify_source_artifact(staged)
        # Hard link publishes without overwriting another writer's immutable name.
        os.chmod(staged, 0o600)
        os.link(staged, destination)
        _fsync_directory(destination.parent)
        return destination
    finally:
        staged.unlink(missing_ok=True)


class OfflineWillysClient:
    """Replay original source observations through the normal collector without sockets."""

    requests_per_second = 1.0
    max_concurrency = 1

    def __init__(self, verified: VerifiedSourceArtifact):
        self.verified = verified

    async def fetch_stores(self) -> RawBatch:
        return RawBatch(
            chain=Chain.WILLYS,
            documents=tuple(d for d in self.verified.documents if d.kind == "stores"),
        )

    async def fetch_catalog(self, store: Any) -> RawBatch:
        return RawBatch(
            chain=Chain.WILLYS,
            documents=tuple(
                d for d in self.verified.documents if d.store_external_id == store.external_id
            ),
            catalog_completion=self.verified.completion[store.external_id],
        )

    async def aclose(self) -> None:
        pass


async def import_source_candidate(
    path: Path, session_factory: Any, raw_store: Any
) -> dict[str, Any]:
    """Independently verify and create an inactive normal source candidate.

    The operator must hold the shared operation lock. Promotion and PriceUniverse
    activation belong to the normal operational activation boundary, not upload.
    """
    from sqlalchemy import func, select

    from grocery_data.app.services.collector import GroceryCollector
    from grocery_data.app.services.snapshot_manager import SnapshotManager
    from grocery_data.app.storage import session_scope
    from grocery_data.app.storage.models import CatalogSnapshotModel, ProductModel, RawSnapshotModel

    verified = verify_source_artifact(path)
    from grocery_data.app.services.willys_municipal_scope import require_import_scope
    require_import_scope(verified.manifest)
    duplicate = None
    unchanged_requalification = False
    unchanged_snapshot_id = None
    with session_scope(session_factory) as session:
        for snapshot in session.scalars(
            select(CatalogSnapshotModel).where(CatalogSnapshotModel.chain == "willys")
        ):
            if (snapshot.is_active
                    and snapshot.scope_key == verified.manifest.source_scope.geographic_area.city.casefold()
                    and (snapshot.metrics or {}).get("willys_municipal_inventory")
                    and verified.manifest.source_scope.geographic_area.mode != "municipality"):
                raise SourceArtifactError("legacy relay cannot silently replace a municipal source")
            if (snapshot.is_active
                    and snapshot.scope_key == verified.manifest.source_scope.geographic_area.city.casefold()
                    and verified.manifest.source_scope.geographic_area.mode == "municipality"
                    and not (snapshot.metrics or {}).get("willys_municipal_inventory")
                    and snapshot.parser_version == verified.manifest.parser_version
                    and snapshot.normalizer_version == verified.manifest.normalizer_version):
                # Scope-only requalification is allowed only for the EXACT
                # existing raw observations, not equal prices or fuzzy products.
                old_evidence = set(session.execute(select(
                    RawSnapshotModel.store_external_id, RawSnapshotModel.kind,
                    RawSnapshotModel.payload_hash, RawSnapshotModel.fetched_at,
                ).where(RawSnapshotModel.catalog_snapshot_id == snapshot.id)))
                incoming_evidence = {(d.store_external_id, d.kind, sha256(raw_store._safe_payload(d)).hexdigest(), d.fetched_at)
                                     for d in verified.documents}
                unchanged_requalification = bool(old_evidence) and old_evidence == incoming_evidence
                if unchanged_requalification:
                    unchanged_snapshot_id = snapshot.id
            if (snapshot.metrics or {}).get("source_artifact", {}).get(
                "sha256"
            ) == verified.artifact_sha256:
                duplicate = {
                    "status": "duplicate",
                    "snapshot_id": snapshot.id,
                    "state": snapshot.state,
                    "artifact_sha256": verified.artifact_sha256,
                    "network_requests": 0,
                }
                if snapshot.state == "promoted":
                    return duplicate
                if snapshot.state != "health_checked":
                    raise SourceArtifactError("previous imported candidate is not promotable")
                break
        active_observations = session.execute(
            select(
                ProductModel.store_external_id,
                CatalogSnapshotModel.id,
                func.min(ProductModel.observed_at),
                func.max(ProductModel.observed_at),
            )
            .join(CatalogSnapshotModel, ProductModel.catalog_snapshot_id == CatalogSnapshotModel.id)
            .where(CatalogSnapshotModel.chain == "willys", CatalogSnapshotModel.is_active.is_(True))
            .group_by(ProductModel.store_external_id, CatalogSnapshotModel.id)
        )
        for context, active_snapshot_id, oldest, newest in active_observations:
            observations = [
                d.fetched_at
                for d in verified.documents
                if d.store_external_id == context and d.kind == "catalog_page"
            ]
            if (observations and (min(observations) < oldest or max(observations) <= newest)
                    and active_snapshot_id != unchanged_snapshot_id):
                raise SourceArtifactError("artifact would replace newer active source observations")
    if duplicate is not None:
        return duplicate
    connector = WillysConnector(
        client=OfflineWillysClient(verified), allowed_store_ids=verified.manifest.context_ids,
        municipality_boundary=verified.manifest.municipality_boundary
    )
    result = await GroceryCollector(session_factory, raw_store).collect_area(
        connector, verified.manifest.source_scope.geographic_area, auto_promote=False,
        scope_key=verified.manifest.source_scope.geographic_area.city.casefold()
    )
    manager = SnapshotManager(session_factory)
    manager.validate(result.snapshot_id)
    with session_scope(session_factory) as session:
        row_count = session.scalar(
            select(func.count(ProductModel.id)).where(
                ProductModel.catalog_snapshot_id == result.snapshot_id
            )
        )
        distinct_count = session.scalar(
            select(func.count(func.distinct(ProductModel.external_product_id))).where(
                ProductModel.catalog_snapshot_id == result.snapshot_id
            )
        )
        if (
            row_count != verified.manifest.row_count
            or distinct_count != verified.manifest.product_count
        ):
            raise SourceArtifactError("server parser product counts differ from manifest")
        snapshot = session.get(CatalogSnapshotModel, result.snapshot_id)
        snapshot.metrics = {
            **snapshot.metrics,
            "requalification_without_new_price_observation": unchanged_requalification,
            **({"willys_municipal_inventory": connector.municipality_inventory} if connector.municipality_inventory else {}),
            "source_artifact": {
                "schema_version": SCHEMA,
                "sha256": verified.artifact_sha256,
                "source_snapshot_id": verified.manifest.source_snapshot_id,
                "parent_snapshot_ids": list(verified.manifest.parent_snapshot_ids),
                "collection_location": "LOCAL_RELAY",
                "retailer_source": "willys",
                "collection_started_at": verified.manifest.collection_started_at.isoformat(),
                "collection_finished_at": verified.manifest.collection_finished_at.isoformat(),
                "observed_from": verified.manifest.observed_from.isoformat(),
                "observed_to": verified.manifest.observed_to.isoformat(),
                "original_request_count": verified.manifest.request_count,
            },
        }
    return {
        "status": "candidate",
        "snapshot_id": result.snapshot_id,
        "artifact_sha256": verified.artifact_sha256,
        "network_requests": 0,
    }


def export_source_artifact(
    session_factory: Any,
    raw_store: Any,
    snapshot_id: str,
    destination: Path,
    *,
    collection_started_at: datetime | None = None,
    collection_finished_at: datetime | None = None,
    original_request_count: int | None = None,
    municipality_boundary: dict | None = None,
) -> Path:
    """Package an existing normal HEALTH_CHECKED candidate, never a partial run."""
    from sqlalchemy import func, select

    from grocery_data.app.services.replay import DatabaseReplayService
    from grocery_data.app.services.snapshot_manager import SnapshotManager
    from grocery_data.app.storage import session_scope
    from grocery_data.app.storage.models import (
        CollectorRunModel,
        ProductModel,
        RawSnapshotModel,
    )

    snapshot = SnapshotManager(session_factory).validate(snapshot_id)
    if snapshot.chain != "willys" or snapshot.state not in {"health_checked", "promoted"}:
        raise SourceArtifactError("export requires a qualified registered source snapshot")
    with session_scope(session_factory) as session:
        rows = list(
            session.scalars(
                select(RawSnapshotModel)
                .where(RawSnapshotModel.catalog_snapshot_id == snapshot_id)
                .order_by(RawSnapshotModel.fetched_at, RawSnapshotModel.id)
            )
        )
        run = session.get(CollectorRunModel, snapshot.collector_run_id)
        if run is None or run.finished_at is None:
            raise SourceArtifactError("interrupted source collection cannot be exported")
        start = collection_started_at or run.started_at
        finish = collection_finished_at or run.finished_at
        count = original_request_count or (run.metrics or {}).get("request_count", 0)
        row_count = session.scalar(
            select(func.count(ProductModel.id)).where(
                ProductModel.catalog_snapshot_id == snapshot_id
            )
        )
        product_count = session.scalar(
            select(func.count(func.distinct(ProductModel.external_product_id))).where(
                ProductModel.catalog_snapshot_id == snapshot_id
            )
        )
    docs = tuple(
        RawFetch(
            chain=Chain(row.chain),
            store_external_id=row.store_external_id,
            kind=row.kind,
            method=row.method,
            url=row.url,
            query=row.query,
            fetched_at=row.fetched_at,
            http_status=row.http_status,
            content_type=row.content_type,
            payload=raw_store.load(DatabaseReplayService._stored(row)),
            connector_version=row.connector_version,
            page_number=row.page_number,
        )
        for row in rows
    )
    scope = SourceScopeDescriptor.model_validate(snapshot.metrics["source_scope"])
    contexts = tuple(sorted(s.external_id for s in _source_stores(tuple(d for d in docs if d.kind == "stores"), scope.geographic_area, municipality_boundary))) if municipality_boundary else APPROVED_WILLYS_CONTEXTS
    completion = _willys_completion(docs, area=scope.geographic_area, boundary=municipality_boundary, contexts=contexts)
    entries = tuple(
        PayloadEntry(
            metadata=d.model_dump(mode="json", exclude={"payload", "payload_hash"}),
            path=f"raw/{i:05d}.json",
            size=len(d.payload),
            sha256=sha256(d.payload).hexdigest(),
        )
        for i, d in enumerate(docs)
    )
    manifest = SourceManifest(
        context_ids=contexts,
        municipality_boundary=municipality_boundary,
        source_snapshot_id=snapshot_id,
        source_scope=snapshot.metrics["source_scope"],
        collection_started_at=start,
        collection_finished_at=finish,
        observed_from=min(d.fetched_at for d in docs),
        observed_to=max(d.fetched_at for d in docs),
        collector_version=snapshot.connector_version,
        parser_version=snapshot.parser_version,
        normalizer_version=snapshot.normalizer_version,
        source_policy_version="willys-municipality-policy-v1" if municipality_boundary else "willys-source-policy-v1",
        source_policy=snapshot.metrics["source_policy_audit"],
        row_count=row_count,
        product_count=product_count,
        request_count=count,
        catalog_completion=completion,
        payloads=entries,
    )
    return write_source_artifact(manifest, docs, destination)


async def import_source_inbox(
    session_factory: Any, raw_store: Any, inbox: Path, *, limit: int = 5
) -> list[dict[str, Any]]:
    """Consume bounded asynchronous arrivals under the caller's operation lock.

    Only normal source promotion occurs here. The existing daily refresh builds
    and activates its PriceUniverse afterwards. Bad arrivals do not block other
    retailers, and processed bytes remain in the inbox archive for audit.
    """
    import sqlite3

    from sqlalchemy.exc import SQLAlchemyError

    from grocery_data.app.services.failure_diagnostics import failure_details
    from grocery_data.app.services.snapshot_manager import SnapshotManager

    if not inbox.is_dir():
        return []
    root = inbox.resolve()
    paths = sorted(root.glob("*.smako-source"), key=lambda p: p.stat().st_mtime, reverse=True)
    reports = []
    for path in paths[:limit]:
        if path.is_symlink() or path.resolve().parent != root or not HASH.fullmatch(path.stem):
            reports.append({"status": "rejected", "reason": "invalid_inbox_path"})
            continue
        bucket = "rejected"
        try:
            if (
                path.stat().st_size > MAX_BYTES
                or sha256(path.read_bytes()).hexdigest() != path.stem
            ):
                raise SourceArtifactError("inbox transport hash mismatch")
            result = await import_source_candidate(path, session_factory, raw_store)
            manager = SnapshotManager(session_factory)
            snapshot = manager.get(result["snapshot_id"])
            if snapshot.state == "health_checked":
                manager.promote(snapshot.id)
            reports.append(result)
            bucket = "processed"
        except (SQLAlchemyError, sqlite3.Error, OSError) as exc:
            # An infrastructure failure is not invalid source evidence. Keep
            # the exact inbox bytes queued for retry and expose the DB cause.
            reports.append({"status": "deferred", "artifact_sha256": path.stem,
                            "error_type": type(exc).__name__, "causes": failure_details(exc)})
            continue
        except (ValueError, RuntimeError) as exc:
            reports.append(
                {
                    "status": "rejected",
                    "artifact_sha256": path.stem,
                    "error_type": type(exc).__name__,
                    "causes": failure_details(exc),
                }
            )
        archive = root / bucket
        if archive.is_symlink():
            raise SourceArtifactError("inbox archive cannot be a symlink")
        archive.mkdir(exist_ok=True)
        target = archive / path.name
        if target.exists():
            if sha256(target.read_bytes()).hexdigest() != sha256(path.read_bytes()).hexdigest():
                raise SourceArtifactError("immutable inbox archive collision")
            path.unlink()
        else:
            path.rename(target)
        _fsync_directory(archive)
        _fsync_directory(root)
    return reports
