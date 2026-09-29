from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.connectors.hemkop.client import (
    HemkopClient,
    HemkopSourcePolicyError,
)
from grocery_data.app.connectors.hemkop.parser import HemkopParser
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.registry import SOURCE_COVERAGE, ConnectorRegistry
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    PriceContextType,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SnapshotState,
    SourceStore,
    TransportMetrics,
)
from grocery_data.app.services.collector import CatalogCompletenessError, GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.services.snapshot_manager import SnapshotManager
from grocery_data.app.storage import (
    ConnectorHealthRepository,
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    SourceProductModel,
)

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "hemkop" / "fixtures"


def _fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_bytes())


def _lund_store_payload() -> bytes:
    rows = _fixture_json("stores.json")
    selected = [row for row in rows if str(row.get("storeId")) == "4224"]
    return json.dumps(selected, ensure_ascii=False, separators=(",", ":")).encode()


def _product_row(position: int) -> dict[str, Any]:
    row = copy.deepcopy(_fixture_json("fixed_package.json")["results"][0])
    row["code"] = f"HEMKOP_ACCEPTANCE_{position:04d}_ST"
    row["name"] = f"Acceptansprodukt {position}"
    row["priceValue"] = 10 + position
    return row


def _store_facets(store_id: str = "4224") -> list[dict[str, Any]]:
    return [
        {
            "values": [
                {
                    "query": {
                        "query": {"value": (f":topRated:salableOnlineInStore_string_mv:{store_id}")}
                    }
                }
            ]
        }
    ]


def _store_context_document(*, active_store_id: str = "4224") -> RawFetch:
    return RawFetch(
        chain=Chain.HEMKOP,
        store_external_id="4224",
        kind="store_context",
        method="GET",
        url="https://www.hemkop.se/axfood/rest/store/active",
        http_status=200,
        content_type="application/json",
        payload=json.dumps(
            {"store": {"storeId": active_store_id}},
            separators=(",", ":"),
        ).encode(),
        connector_version="hemkop-v1",
    )


def _catalog_documents(
    *,
    rename_results: bool = False,
    context: str = "matching",
) -> tuple[RawFetch, ...]:
    documents: list[RawFetch] = []
    if context == "matching":
        documents.append(_store_context_document())
    elif context == "mismatched":
        documents.append(_store_context_document(active_store_id="4114"))
    elif context != "missing":
        raise ValueError(f"unknown test context: {context}")
    position = 0
    categories = (
        ("mejeri-ost-och-agg", "Mejeri, ost och ägg", 5, 3),
        ("skafferi", "Skafferi", 3, 3),
    )
    for category_path, category_name, total, page_size in categories:
        number_of_pages = (total + page_size - 1) // page_size + int(total % page_size == 0)
        category_rows = [_product_row(position + offset) for offset in range(total)]
        position += total
        for page in range(number_of_pages):
            result_rows = (
                None
                if page * page_size == total
                else category_rows[page * page_size : (page + 1) * page_size]
            )
            payload: dict[str, Any] = {
                "results": result_rows,
                "pagination": {
                    "currentPage": page,
                    "numberOfPages": number_of_pages,
                    "pageSize": page_size,
                    "totalNumberOfResults": total,
                },
                "categoryInfo": {
                    "code": category_path,
                    "name": category_name,
                    "url": category_path,
                },
                "superCategories": [
                    {
                        "code": "N00",
                        "name": "Alla varor",
                        "url": "/alla-varor/c/",
                    }
                ],
                "facets": _store_facets(),
            }
            if rename_results:
                payload["items"] = payload.pop("results")
            documents.append(
                RawFetch(
                    chain=Chain.HEMKOP,
                    store_external_id="4224",
                    kind="catalog_page",
                    method="GET",
                    url=f"https://www.hemkop.se/c/{category_path}",
                    query={"page": str(page), "size": str(page_size)},
                    http_status=200,
                    content_type="application/json",
                    payload=json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode(),
                    connector_version="hemkop-v1",
                    page_number=page,
                )
            )
    return tuple(documents)


def _exact_completion(
    *,
    expected: int = 8,
    rows: int = 8,
    unique: int = 8,
    duplicates: int = 0,
    expected_pages: int = 4,
    pages_fetched: int = 4,
    complete: bool = True,
) -> CatalogCompletion:
    return CatalogCompletion(
        complete=complete,
        limited=not complete,
        expected_categories=2,
        completed_categories=2 if complete else 1,
        pages_fetched=pages_fetched,
        products_observed=unique,
        expected_products=expected,
        raw_rows=rows,
        unique_products=unique,
        duplicate_products=duplicates,
        expected_pages=expected_pages,
        reason=None if complete else "offline acceptance failure evidence",
    )


class FullFixtureHemkopClient:
    """No-network full source stand-in with the same closed policy surface."""

    connector_version = "hemkop-v1"
    allow_full_crawl = True
    max_categories = None
    max_pages_per_category = None
    allowed_store_ids = frozenset({"4224"})
    requests_per_second = 0.1
    max_concurrency = 1

    def __init__(
        self,
        *,
        documents: tuple[RawFetch, ...] | None = None,
        completion: CatalogCompletion | None = None,
    ) -> None:
        self.documents = documents or _catalog_documents()
        self.completion = completion or _exact_completion()
        self.fetch_calls = 0
        self.closed = False

    def store_allowed(self, store_external_id: str) -> bool:
        return store_external_id in self.allowed_store_ids

    async def fetch_stores(self) -> RawBatch:
        self.fetch_calls += 1
        return RawBatch(
            chain=Chain.HEMKOP,
            documents=(
                RawFetch(
                    chain=Chain.HEMKOP,
                    kind="stores",
                    method="GET",
                    url="https://www.hemkop.se/axfood/rest/store",
                    query={"online": "false"},
                    http_status=200,
                    content_type="application/json",
                    payload=_lund_store_payload(),
                    connector_version=self.connector_version,
                ),
            ),
            transport=TransportMetrics(request_count=1),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        self.fetch_calls += 1
        assert store.external_id == "4224"
        return RawBatch(
            chain=Chain.HEMKOP,
            documents=self.documents,
            transport=TransportMetrics(request_count=len(self.documents)),
            catalog_completion=self.completion,
        )

    async def aclose(self) -> None:
        self.closed = True


class ResultsFieldRepairParser(HemkopParser):
    """Connector-local repair for a simulated ``results`` to ``items`` rename."""

    parser_version = "hemkop-parser-v2-results-repair"

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        repaired: list[RawFetch] = []
        for document in raw.documents:
            if document.kind != "catalog_page":
                repaired.append(document)
                continue
            payload = document.json_payload()
            if "results" not in payload and "items" in payload:
                payload["results"] = payload.pop("items")
            repaired.append(
                document.model_copy(
                    update={
                        "payload": json.dumps(
                            payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode()
                    }
                )
            )
        return super().parse_catalog(
            raw.model_copy(update={"documents": tuple(repaired)}),
            references,
            store,
        )


def _full_connector(
    client: FullFixtureHemkopClient,
    *,
    parser: HemkopParser | None = None,
    minimum: int = 8,
) -> HemkopConnector:
    connector = HemkopConnector.for_full_collection(
        client=client,  # type: ignore[arg-type]
        parser=parser,
    )
    connector.minimum_full_catalog_products = minimum
    return connector


@pytest.mark.parametrize("collapsed_count", [100, 7_999])
def test_hemkop_full_and_replay_gate_rejects_a_future_collapsed_catalog(
    tmp_path: Path,
    collapsed_count: int,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    collector = GroceryCollector(
        create_session_factory(engine),
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    )
    connector = HemkopConnector.for_full_collection(client=FullFixtureHemkopClient())  # type: ignore[arg-type]
    evidence = CatalogCompletion(
        complete=True,
        expected_categories=1,
        completed_categories=1,
        pages_fetched=1,
        products_observed=collapsed_count,
        expected_products=collapsed_count,
        raw_rows=collapsed_count,
        unique_products=collapsed_count,
        duplicate_products=0,
        expected_pages=1,
    )

    try:
        assert connector.minimum_full_catalog_products == 8_000
        with pytest.raises(CatalogCompletenessError, match="absolute minimum"):
            collector._validate_catalog_completion(
                connector,
                RawBatch(
                    chain=Chain.HEMKOP,
                    documents=(),
                    catalog_completion=evidence,
                ),
            )
    finally:
        engine.dispose()


def _projection(session, snapshot_id: str) -> tuple[tuple[Any, ...], ...]:  # type: ignore[no-untyped-def]
    products = tuple(
        tuple(row)
        for row in session.execute(
            select(
                ProductModel.external_product_id,
                ProductModel.name,
                ProductModel.sale_price,
                ProductModel.sale_model,
                ProductModel.package_quantity,
                ProductModel.package_unit,
            )
            .where(ProductModel.catalog_snapshot_id == snapshot_id)
            .order_by(ProductModel.external_product_id)
        )
    )
    prices = tuple(
        tuple(row)
        for row in session.execute(
            select(
                ProductModel.external_product_id,
                PriceObservationModel.sale_price,
                PriceObservationModel.regular_price,
                PriceObservationModel.comparison_price,
                PriceObservationModel.comparison_unit,
            )
            .join(PriceObservationModel, PriceObservationModel.product_id == ProductModel.id)
            .where(PriceObservationModel.catalog_snapshot_id == snapshot_id)
            .order_by(ProductModel.external_product_id)
        )
    )
    promotions = tuple(
        tuple(row)
        for row in session.execute(
            select(
                ProductModel.external_product_id,
                PromotionModel.external_id,
                PromotionModel.type,
                PromotionModel.price,
                PromotionModel.quantity,
                PromotionModel.member_only,
            )
            .join(PromotionModel, PromotionModel.product_id == ProductModel.id)
            .where(PromotionModel.catalog_snapshot_id == snapshot_id)
            .order_by(ProductModel.external_product_id, PromotionModel.external_id)
        )
    )
    return products, prices, promotions


def _source_store() -> SourceStore:
    return SourceStore(
        chain=Chain.HEMKOP,
        external_id="4224",
        name="Hemköp Lund Brunnshög",
        city="Lund",
        online_shopping=True,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        price_context_type=PriceContextType.ONLINE_STORE,
        physical_store_external_id="4224",
        raw_reference="raw:stores#storeId=4224",
        source_fields={"price_context_verified": True},
    )


@pytest.mark.asyncio
async def test_hemkop_review_policy_requires_opt_in_allowlist_and_stays_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEMKOP_ALLOW_FULL_CRAWL", raising=False)
    monkeypatch.delenv("HEMKOP_STORE_EXTERNAL_IDS", raising=False)

    bounded = HemkopConnector.for_bounded_discovery()
    assert bounded.coverage is CoverageLevel.PARTIAL_CATALOG
    assert bounded.collection_policy_audit().model_dump(mode="json") == {
        "source_policy": "review",
        "operator_opt_in": False,
        "store_allowlist": [],
        "requests_per_second": 0.1,
        "max_concurrency": 1,
    }
    await bounded.aclose()

    with pytest.raises(HemkopSourcePolicyError, match="explicitly"):
        HemkopClient(
            allow_full_crawl=False,
            max_categories=None,
            max_pages_per_category=None,
        )
    with pytest.raises(HemkopSourcePolicyError, match="allowlist"):
        HemkopClient(
            allow_full_crawl=True,
            max_categories=None,
            max_pages_per_category=None,
            allowed_store_ids=(),
        )

    transport = httpx.MockTransport(lambda request: httpx.Response(500, request=request))
    http_client = httpx.AsyncClient(transport=transport)
    try:
        full_client = HemkopClient(
            allow_full_crawl=True,
            max_categories=None,
            max_pages_per_category=None,
            allowed_store_ids=("4224",),
            client=http_client,
        )
        full = HemkopConnector.for_full_collection(client=full_client)
        assert full.collection_policy_audit().model_dump(mode="json") == {
            "source_policy": "review",
            "operator_opt_in": True,
            "store_allowlist": ["4224"],
            "requests_per_second": 0.1,
            "max_concurrency": 1,
        }
        await full.aclose()
    finally:
        await http_client.aclose()


def test_hemkop_registry_cannot_get_ahead_of_live_acceptance() -> None:
    descriptor = SOURCE_COVERAGE[Chain.HEMKOP]
    registry = ConnectorRegistry()

    if descriptor.acceptance_contract_passed:
        assert descriptor.implemented is True
        assert registry.create(Chain.HEMKOP).chain is Chain.HEMKOP
    else:
        assert descriptor.implemented is False
        with pytest.raises(NotImplementedError):
            registry.create(Chain.HEMKOP)


@pytest.mark.asyncio
async def test_real_client_proves_exact_top_level_partition_pagination() -> None:
    rows = [_product_row(index) for index in range(5)]
    tree = {
        "id": "N00",
        "title": "Alla varor",
        "url": "/alla-varor/c/",
        "valid": True,
        "children": [
            {"id": "N01", "title": "A", "url": "a", "valid": True},
            {"id": "N02", "title": "B", "url": "b", "valid": True},
        ],
    }
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if path == "/axfood/rest/csrf-token":
            return httpx.Response(200, json="ephemeral-csrf", request=request)
        if path == "/axfood/rest/store/activate":
            return httpx.Response(200, json={"ok": True}, request=request)
        if path == "/axfood/rest/store/active":
            return httpx.Response(
                200,
                json={"store": {"storeId": "4224"}},
                request=request,
            )
        if path == "/leftMenu/categorytree":
            return httpx.Response(200, json=tree, request=request)
        if path in {"/c/a", "/c/b"}:
            page = int(request.url.params["page"])
            category_rows = rows[:3] if path == "/c/a" else rows[3:]
            total = len(category_rows)
            page_size = 2
            number_of_pages = (total + page_size - 1) // page_size + int(total % page_size == 0)
            result_rows = (
                None
                if page * page_size == total
                else category_rows[page * page_size : (page + 1) * page_size]
            )
            return httpx.Response(
                200,
                json={
                    "results": result_rows,
                    "pagination": {
                        "currentPage": page,
                        "numberOfPages": number_of_pages,
                        "pageSize": page_size,
                        "totalNumberOfResults": total,
                    },
                    "facets": _store_facets(),
                },
                request=request,
            )
        raise AssertionError(f"unexpected Hemköp request: {request.method} {path}")

    http_client = httpx.AsyncClient(
        base_url="https://www.hemkop.se",
        transport=httpx.MockTransport(handler),
    )
    client = HemkopClient(
        requests_per_second=100_000,
        retry_policy=RetryPolicy(attempts=1, base_delay_seconds=0, max_delay_seconds=0),
        page_size=2,
        max_categories=None,
        max_pages_per_category=None,
        allow_full_crawl=True,
        allowed_store_ids=("4224",),
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_source_store())
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.model_dump(mode="json", exclude_none=True) == {
        "complete": True,
        "limited": False,
        "expected_categories": 2,
        "completed_categories": 2,
        "pages_fetched": 4,
        "products_observed": 5,
        "expected_products": 5,
        "raw_rows": 5,
        "unique_products": 5,
        "duplicate_products": 0,
        "within_partition_duplicates": 0,
        "cross_partition_duplicates": 0,
        "expected_pages": 4,
    }
    assert batch.transport.request_count == 8
    assert calls.count("/c/a") == 2
    assert calls.count("/c/b") == 2
    assert sum(document.kind == "catalog_page" for document in batch.documents) == 4
    assert all(b"ephemeral-csrf" not in document.payload for document in batch.documents)
    activation = next(
        document for document in batch.documents if document.kind == "store_activation"
    )
    assert activation.payload == b"{}"


@pytest.mark.asyncio
async def test_hemkop_staged_replay_rejections_lkg_and_parser_local_repair(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    collector = GroceryCollector(factory, raw_store, full_catalog_min_products=1)

    try:
        good_client = FullFixtureHemkopClient()
        candidate = await collector.collect_area(
            _full_connector(good_client),
            GeographicArea(city="Lund"),
            auto_promote=False,
        )

        expected_audit = {
            "source_policy": "review",
            "operator_opt_in": True,
            "store_allowlist": ["4224"],
            "requests_per_second": 0.1,
            "max_concurrency": 1,
        }
        assert candidate.status is ConnectorStatus.HEALTHY
        assert candidate.promoted is False
        assert candidate.active_snapshot_id is None
        assert candidate.metrics.products_parsed == 8
        assert candidate.metrics.products_with_price == 8
        assert candidate.source_policy_audit is not None
        assert candidate.source_policy_audit.model_dump(mode="json") == expected_audit
        assert good_client.fetch_calls == 2
        assert good_client.closed is True

        with session_scope(factory) as session:
            row = SnapshotRepository(session).get(candidate.snapshot_id)
            assert row is not None
            assert row.state == SnapshotState.HEALTH_CHECKED.value
            assert row.coverage == CoverageLevel.FULL_ONLINE_CATALOG.value
            assert row.metrics["source_policy_audit"] == expected_audit
            expected_completion = _exact_completion().model_dump(mode="json")
            expected_completion.pop("within_partition_duplicates")
            expected_completion.pop("cross_partition_duplicates")
            expected_completion.pop("exact_duplicates_removed")
            expected_completion.pop("conflicting_duplicates")
            expected_completion.pop("pagination_overlaps")
            assert row.metrics["catalog_completion"]["4224"] == expected_completion
            assert row.metrics["minimum_products_for_full_catalog"] == 8
            run = session.get(CollectorRunModel, row.collector_run_id)
            assert run is not None
            assert run.scope == {
                "scope_key": "lund",
                "source_scope": {
                    "scope_key": "lund",
                    "geographic_area": {
                        "city": "Lund",
                        "mode": "locality",
                        "municipality_code": None,
                        "postal_codes": [],
                        "latitude": None,
                        "longitude": None,
                    },
                },
                **expected_audit,
            }
            activation_flags = tuple(
                session.scalars(
                    select(SourceProductModel.source_fields).where(
                        SourceProductModel.catalog_snapshot_id == candidate.snapshot_id
                    )
                )
            )
            assert len(activation_flags) == 8
            assert all(
                fields["price_context_activation_confirmed"] is True for fields in activation_flags
            )
            source_projection = _projection(session, candidate.snapshot_id)

        replay_connector = HemkopConnector.for_replay(store_external_ids=("4224",))
        replay_connector.minimum_full_catalog_products = 1
        replay_connector.client.fetch_stores = AsyncMock(side_effect=AssertionError("network"))
        replay_connector.client.fetch_catalog = AsyncMock(side_effect=AssertionError("network"))
        replayed = await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(replay_connector, candidate.snapshot_id)

        assert replayed.network_requests == 0
        assert replayed.status is ConnectorStatus.HEALTHY
        assert replayed.promoted is False
        assert replayed.products_parsed == 8
        replay_connector.client.fetch_stores.assert_not_awaited()
        replay_connector.client.fetch_catalog.assert_not_awaited()
        with session_scope(factory) as session:
            replay_row = SnapshotRepository(session).get(replayed.replay_snapshot_id)
            assert replay_row is not None
            assert replay_row.state == SnapshotState.HEALTH_CHECKED.value
            assert replay_row.metrics["network_requests"] == 0
            assert replay_row.metrics["minimum_products_for_full_catalog"] == 8
            assert _projection(session, replayed.replay_snapshot_id) == source_projection

        promoted = SnapshotManager(factory, full_catalog_min_products=1).promote(
            candidate.snapshot_id
        )
        assert promoted.state == SnapshotState.PROMOTED.value

        invalid_completions = (
            _exact_completion(
                pages_fetched=2,
                rows=5,
                unique=5,
                complete=False,
            ),
            _exact_completion(expected=9, complete=False),
            _exact_completion(unique=7, duplicates=1, complete=False),
        )
        for completion in invalid_completions:
            client = FullFixtureHemkopClient(completion=completion)
            with pytest.raises(CatalogCompletenessError):
                await collector.collect_area(
                    _full_connector(client),
                    GeographicArea(city="Lund"),
                    auto_promote=False,
                )
            assert client.closed is True
            with session_scope(factory) as session:
                active = SnapshotRepository(session).active(Chain.HEMKOP, scope_key="lund")
                assert active is not None and active.id == candidate.snapshot_id
                latest = session.scalar(
                    select(CatalogSnapshotModel)
                    .where(CatalogSnapshotModel.state == SnapshotState.REJECTED.value)
                    .order_by(CatalogSnapshotModel.created_at.desc())
                )
                assert latest is not None
                assert latest.metrics["failure_type"] == "CatalogCompletenessError"
                assert latest.metrics["source_policy_audit"] == expected_audit
                health = ConnectorHealthRepository(session).get(Chain.HEMKOP)
                assert health is not None
                assert health.status == ConnectorStatus.BROKEN.value
                assert health.active_snapshot_id == candidate.snapshot_id

        context_calls: list[str] = []

        def context_handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            context_calls.append(path)
            if path == "/axfood/rest/store":
                return httpx.Response(200, content=_lund_store_payload(), request=request)
            if path == "/axfood/rest/csrf-token":
                return httpx.Response(200, json="ephemeral-csrf", request=request)
            if path == "/axfood/rest/store/activate":
                return httpx.Response(200, json={"ok": True}, request=request)
            if path == "/axfood/rest/store/active":
                return httpx.Response(
                    200,
                    json={"store": {"storeId": "4114"}},
                    request=request,
                )
            raise AssertionError(f"request continued after context switch: {path}")

        context_http = httpx.AsyncClient(
            base_url="https://www.hemkop.se",
            transport=httpx.MockTransport(context_handler),
        )
        context_client = HemkopClient(
            requests_per_second=100_000,
            retry_policy=RetryPolicy(
                attempts=1,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            page_size=2,
            max_categories=None,
            max_pages_per_category=None,
            allow_full_crawl=True,
            allowed_store_ids=("4224",),
            client=context_http,
        )
        context_connector = HemkopConnector.for_full_collection(client=context_client)
        context_connector.minimum_full_catalog_products = 1
        try:
            with pytest.raises(ConnectorFetchError):
                await collector.collect_area(
                    context_connector,
                    GeographicArea(city="Lund"),
                    auto_promote=False,
                )
        finally:
            await context_http.aclose()
        assert "/leftMenu/categorytree" not in context_calls
        assert not any(path.startswith("/c/") for path in context_calls)
        with session_scope(factory) as session:
            active = SnapshotRepository(session).active(Chain.HEMKOP, scope_key="lund")
            assert active is not None and active.id == candidate.snapshot_id

        for context in ("missing", "mismatched"):
            context_evidence_client = FullFixtureHemkopClient(
                documents=_catalog_documents(context=context)
            )
            unverified = await collector.collect_area(
                _full_connector(context_evidence_client),
                GeographicArea(city="Lund"),
                auto_promote=True,
            )
            assert unverified.status is ConnectorStatus.BROKEN
            assert unverified.promoted is False
            assert unverified.metrics.products_parsed == 0
            assert unverified.metrics.products_quarantined == 1
            assert unverified.active_snapshot_id == candidate.snapshot_id
            with session_scope(factory) as session:
                rejected = SnapshotRepository(session).get(unverified.snapshot_id)
                assert rejected is not None
                assert rejected.state == SnapshotState.REJECTED.value
                active = SnapshotRepository(session).active(
                    Chain.HEMKOP,
                    scope_key="lund",
                )
                assert active is not None and active.id == candidate.snapshot_id
                assert (
                    session.scalar(
                        select(SourceProductModel.id).where(
                            SourceProductModel.catalog_snapshot_id == unverified.snapshot_id
                        )
                    )
                    is None
                )

        schema_client = FullFixtureHemkopClient(documents=_catalog_documents(rename_results=True))
        schema_broken = await collector.collect_area(
            _full_connector(schema_client),
            GeographicArea(city="Lund"),
            auto_promote=False,
        )
        assert schema_broken.status is ConnectorStatus.BROKEN
        assert schema_broken.promoted is False
        assert schema_broken.metrics.products_parsed == 0
        assert schema_broken.metrics.products_quarantined == 4
        assert schema_broken.active_snapshot_id == candidate.snapshot_id
        with session_scope(factory) as session:
            broken_row = SnapshotRepository(session).get(schema_broken.snapshot_id)
            assert broken_row is not None
            assert broken_row.state == SnapshotState.REJECTED.value
            assert broken_row.metrics["schema_diff"] is not None
            active = SnapshotRepository(session).active(Chain.HEMKOP, scope_key="lund")
            assert active is not None and active.id == candidate.snapshot_id

        repaired_connector = HemkopConnector.for_replay(
            store_external_ids=("4224",),
            parser=ResultsFieldRepairParser(),
        )
        repaired_connector.minimum_full_catalog_products = 1
        repaired_connector.client.fetch_stores = AsyncMock(side_effect=AssertionError("network"))
        repaired_connector.client.fetch_catalog = AsyncMock(side_effect=AssertionError("network"))
        repaired = await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(
            repaired_connector,
            schema_broken.snapshot_id,
            promote=True,
            accept_schema_change=True,
        )

        assert repaired.network_requests == 0
        assert repaired.status is ConnectorStatus.HEALTHY
        assert repaired.promoted is True
        repaired_connector.client.fetch_stores.assert_not_awaited()
        repaired_connector.client.fetch_catalog.assert_not_awaited()
        with session_scope(factory) as session:
            repaired_row = SnapshotRepository(session).get(repaired.replay_snapshot_id)
            assert repaired_row is not None
            assert repaired_row.state == SnapshotState.PROMOTED.value
            assert repaired_row.metrics["replayed_from"] == schema_broken.snapshot_id
            assert repaired_row.metrics["network_requests"] == 0
            assert _projection(session, repaired.replay_snapshot_id) == source_projection
            active = SnapshotRepository(session).active(Chain.HEMKOP, scope_key="lund")
            assert active is not None and active.id == repaired.replay_snapshot_id
            assert (
                session.scalar(
                    select(ProductModel.id).where(
                        ProductModel.catalog_snapshot_id == repaired.replay_snapshot_id
                    )
                )
                is not None
            )
    finally:
        engine.dispose()
