from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import pytest

from grocery_data import __main__ as cli
from grocery_data.app.connectors.ica import (
    IcaOnlineCatalogConnector,
    IcaOnlineOperatorCrawlPolicy,
    IcaOnlineSourcePolicyError,
)
from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_CATEGORY_TREE_KIND,
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    ICA_STORE_CONTEXT_KIND,
    ICA_STORE_MAPPING_KIND,
    IcaBatchResult,
    IcaProductPage,
)
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    RawBatch,
    RawFetch,
)
from grocery_data.app.domain.raw import TransportMetrics

FIXTURE_DIR = Path(__file__).parents[1] / "app" / "connectors" / "ica" / "fixtures"
REGION_ID = "92198f17-b02f-4fae-ad41-228bcc725420"
RETAILER_ID = "1088004"
CATEGORY_ID = "ea243faf-2eca-47d7-af07-1dc61dd7693a"
OBSERVED_AT = datetime(2026, 8, 25, 12, tzinfo=UTC)


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _raw(
    kind: str,
    payload: dict[str, object],
    *,
    store_external_id: str | None = REGION_ID,
    query: dict[str, str] | None = None,
    page_number: int | None = None,
) -> RawFetch:
    return RawFetch(
        chain=Chain.ICA,
        store_external_id=store_external_id,
        kind=kind,
        method="PUT" if kind == ICA_PRODUCT_BATCH_KIND else "GET",
        url=f"https://handlaprivatkund.ica.se/stores/{RETAILER_ID}/api/test",
        query=query or {},
        fetched_at=OBSERVED_AT,
        http_status=200,
        content_type="application/json; profile=sanitized-ica-online-v1",
        payload=json.dumps(payload, ensure_ascii=False).encode(),
        connector_version="ica-online-catalog-v1",
        page_number=page_number,
    )


def _context_batch() -> RawBatch:
    tree = _fixture("online_v6_category_tree.json")
    tree["retailerRegionId"] = RETAILER_ID
    return RawBatch(
        chain=Chain.ICA,
        documents=(
            _raw(
                ICA_STORE_CONTEXT_KIND,
                {
                    "schema": "ica-online-context-v1",
                    "regionId": REGION_ID,
                    "retailerRegionId": RETAILER_ID,
                },
            ),
            _raw(ICA_CATEGORY_TREE_KIND, tree),
        ),
        transport=TransportMetrics(request_count=1),
    )


def _page_raw(payload: dict[str, object] | None = None) -> RawFetch:
    return _raw(
        ICA_PRODUCT_PAGE_KIND,
        payload or _fixture("online_v6_product_page.json"),
        query={"category_id": CATEGORY_ID, "page_index": "0"},
        page_number=0,
    )


def _full_page_payload() -> dict[str, object]:
    payload = deepcopy(_fixture("online_v6_product_page.json"))
    payload["missingPromotions"] = []
    payload["missedPromotions"] = []
    product = payload["productGroups"][0]["decoratedProducts"][0]  # type: ignore[index]
    product.pop("featuredProductCampaign", None)
    return payload


def _batch_raw(payload: dict[str, object] | None = None) -> RawFetch:
    body = payload or _fixture("online_v6_product_batch.json")
    requested = [str(row["productId"]) for row in body["products"]]  # type: ignore[index]
    return _raw(
        ICA_PRODUCT_BATCH_KIND,
        body,
        query={
            "category_id": CATEGORY_ID,
            "page_index": "0",
            "batch_index": "0",
            "requested_product_ids": json.dumps(requested, separators=(",", ":")),
        },
        page_number=0,
    )


class _FakeBoundedClient:
    allow_full_crawl = False
    max_categories = 1
    max_pages_per_category = 1
    max_batches_per_page = 1
    product_batch_size = 5
    requests_per_second = 0.5
    max_concurrency = 1
    allowed_context_ids = frozenset({REGION_ID})
    context_mappings: ClassVar[dict[str, str]] = {REGION_ID: RETAILER_ID}

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.closed = False

    async def fetch_context(self, region_id: str) -> RawBatch:
        self.calls.append(("context", region_id))
        return _context_batch()

    async def fetch_product_page(
        self,
        region_id: str,
        category_id: str,
        *,
        page_index: int,
    ) -> tuple[RawFetch, IcaProductPage]:
        self.calls.append(("page", (region_id, category_id, page_index)))
        raw = _page_raw()
        return raw, IcaProductPage.from_payload(raw.json_payload(), category_id=category_id)

    async def fetch_product_batch(
        self,
        region_id: str,
        product_ids: tuple[str, ...],
        *,
        category_id: str,
        page_index: int,
        batch_index: int,
    ) -> tuple[RawFetch, IcaBatchResult]:
        self.calls.append(("batch", tuple(product_ids)))
        raw = _batch_raw()
        return raw, IcaBatchResult.from_payload(
            raw.json_payload(),
            requested_product_ids=product_ids,
        )

    async def aclose(self) -> None:
        self.closed = True


def _connector(client: _FakeBoundedClient) -> IcaOnlineCatalogConnector:
    return IcaOnlineCatalogConnector(
        client=client,  # type: ignore[arg-type]
        context_mappings={REGION_ID: RETAILER_ID},
        coverage=CoverageLevel.PARTIAL_CATALOG,
    )


@pytest.mark.asyncio
async def test_bounded_canary_is_context_one_category_one_tiny_batch() -> None:
    client = _FakeBoundedClient()
    connector = _connector(client)
    area = GeographicArea(city="Lund")

    stores_raw = await connector.fetch_stores(area)
    stores = connector.parse_stores(stores_raw, ["raw:mapping"], area)
    store = stores[0]
    catalog = await connector.fetch_catalog(store)
    parsed = connector.parse_catalog(
        catalog,
        [f"raw:catalog:{index}" for index in range(len(catalog.documents))],
        store,
    )
    await connector.aclose()

    assert store.external_id == REGION_ID
    assert store.physical_store_external_id == RETAILER_ID
    assert store.source_fields["price_semantics"] == "online_price"
    assert stores_raw.documents[0].kind == ICA_STORE_MAPPING_KIND
    assert stores_raw.documents[0].store_external_id is None
    assert [call[0] for call in client.calls] == ["context", "page", "batch"]
    assert client.calls[-1][1] == (
        "b0a25230-ba6f-4c0c-991f-c223cfa58090",
        "cf78ca6f-30b1-4935-b48e-8f0386fc6c58",
    )
    assert len(parsed.products) == 3
    assert parsed.failures == []
    assert catalog.catalog_completion is not None
    assert catalog.catalog_completion.complete is False
    assert catalog.catalog_completion.limited is True
    assert catalog.transport.request_count == 3
    assert client.closed is True
    serialized = b"".join(document.payload for document in (*stores_raw.documents, *catalog.documents))
    for forbidden in (b"Cookie", b"Authorization", b"sessionId", b"trackingId"):
        assert forbidden.lower() not in serialized.lower()


@pytest.mark.asyncio
async def test_full_collection_requires_all_three_explicit_operator_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ICA_ALLOW_FULL_CRAWL", raising=False)
    monkeypatch.delenv("ICA_ONLINE_CONTEXT_IDS", raising=False)
    monkeypatch.delenv("ICA_PRODUCT_BATCH_SIZE", raising=False)

    with pytest.raises(IcaOnlineSourcePolicyError, match="ICA_ALLOW_FULL_CRAWL"):
        IcaOnlineCatalogConnector.for_exact_full_collection(REGION_ID)

    monkeypatch.setenv("ICA_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("ICA_ONLINE_CONTEXT_IDS", REGION_ID)
    with pytest.raises(IcaOnlineSourcePolicyError, match="ICA_PRODUCT_BATCH_SIZE"):
        IcaOnlineCatalogConnector.for_exact_full_collection(REGION_ID)

    policy = IcaOnlineOperatorCrawlPolicy(
        allow_full_crawl=True,
        allowed_context_ids=frozenset({REGION_ID}),
        product_batch_size=24,
    )
    with pytest.raises(IcaOnlineSourcePolicyError, match="ICA_PRODUCT_BATCH_SIZE"):
        IcaOnlineCatalogConnector.for_exact_full_collection(REGION_ID, policy=policy)

    monkeypatch.setenv("ICA_PRODUCT_BATCH_SIZE", "24")
    connector = IcaOnlineCatalogConnector.for_exact_full_collection(
        REGION_ID,
        policy=policy,
    )
    try:
        assert connector.coverage is CoverageLevel.FULL_ONLINE_CATALOG
        assert connector.client is not None
        assert connector.client.max_categories is None
        assert connector.client.max_pages_per_category is None
        assert connector.client.max_batches_per_page is None
        assert connector.client.product_batch_size == 24
        assert connector.collection_policy_audit().operator_opt_in is True
        assert connector.collection_policy_audit().store_allowlist == (REGION_ID,)
    finally:
        await connector.aclose()


@pytest.mark.asyncio
async def test_replay_is_network_inert_and_reconciles_full_fixture() -> None:
    connector = IcaOnlineCatalogConnector.for_replay(context_ids=(REGION_ID,))
    mapping = _raw(
        ICA_STORE_MAPPING_KIND,
        {
            "schema": "ica-online-store-mapping-v1",
            "regionId": REGION_ID,
            "retailerRegionId": RETAILER_ID,
            "name": "Maxi ICA Stormarknad Gunnesbo Lund",
            "city": "Lund",
            "priceSemantics": "online_price",
            "relationEvidence": "exact_public_ssr_readback",
        },
        store_external_id=None,
    )
    store = connector.parse_stores(
        RawBatch(chain=Chain.ICA, documents=(mapping,)),
        ["raw:mapping"],
        GeographicArea(city="Lund"),
    )[0]
    tree = _fixture("online_v6_category_tree.json")
    tree["retailerRegionId"] = RETAILER_ID
    raw = RawBatch(
        chain=Chain.ICA,
        documents=(
            _raw(ICA_CATEGORY_TREE_KIND, tree),
            _page_raw(_full_page_payload()),
            _batch_raw(),
        ),
    )
    references = ["raw:tree", "raw:page", "raw:batch"]

    reconciled = connector.reconcile_replay_catalog_completion(raw, store)
    parsed = connector.parse_catalog(reconciled, references, store)

    assert reconciled.catalog_completion is not None
    assert reconciled.catalog_completion.is_full_traversal is True
    assert reconciled.catalog_completion.unique_products == 3
    assert len(parsed.products) == 3
    assert parsed.failures == []
    with pytest.raises(RuntimeError, match="cannot make network requests"):
        await connector.fetch_stores(GeographicArea(city="Lund"))


def test_replay_critical_price_break_fails_closed() -> None:
    connector = IcaOnlineCatalogConnector.for_replay(context_ids=(REGION_ID,))
    mapping = _raw(
        ICA_STORE_MAPPING_KIND,
        {
            "schema": "ica-online-store-mapping-v1",
            "regionId": REGION_ID,
            "retailerRegionId": RETAILER_ID,
            "name": "Maxi ICA Stormarknad Gunnesbo Lund",
            "city": "Lund",
            "priceSemantics": "online_price",
            "relationEvidence": "exact_public_ssr_readback",
        },
        store_external_id=None,
    )
    store = connector.parse_stores(
        RawBatch(chain=Chain.ICA, documents=(mapping,)),
        ["raw:mapping"],
        GeographicArea(city="Lund"),
    )[0]
    broken_page = _full_page_payload()
    del broken_page["productGroups"][0]["decoratedProducts"][0]["price"]["amount"]  # type: ignore[index]
    tree = _fixture("online_v6_category_tree.json")
    tree["retailerRegionId"] = RETAILER_ID
    raw = RawBatch(
        chain=Chain.ICA,
        documents=(
            _raw(ICA_CATEGORY_TREE_KIND, tree),
            _page_raw(broken_page),
            _batch_raw(),
        ),
    )
    references = ["raw:tree", "raw:page", "raw:batch"]

    result = connector.parse_catalog(raw, references, store)

    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "schema_changed"


@pytest.mark.asyncio
async def test_cli_hooks_keep_default_ica_legacy_and_exact_online_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed_args = cli._parser().parse_args(
        ["canary", "ica", "--city", "Lund", "--store", RETAILER_ID]
    )
    assert parsed_args.store == RETAILER_ID

    with pytest.raises(ValueError, match="requires --store"):
        cli._canary_connector(Chain.ICA)

    canary = cli._canary_connector(Chain.ICA, store=RETAILER_ID)
    try:
        assert isinstance(canary, IcaOnlineCatalogConnector)
        assert canary.coverage is CoverageLevel.PARTIAL_CATALOG
        assert canary.client is not None
        assert canary.client.max_categories == 1
        assert canary.client.max_pages_per_category == 1
        assert canary.client.max_batches_per_page == 1
        assert canary.client.product_batch_size == 5
        assert canary.collection_policy_audit().operator_opt_in is False
    finally:
        await canary.aclose()

    assert cli._exact_collection_scope(Chain.ICA, "Lund", REGION_ID) == (
        f"ica:online:{REGION_ID}"
    )
    replay = cli._replay_connector(
        Chain.ICA,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        catalog_completion={REGION_ID: {"complete": True}},
    )
    assert isinstance(replay, IcaOnlineCatalogConnector)
    assert replay.replay_only is True
    assert replay.client is None

    monkeypatch.delenv("ICA_ALLOW_FULL_CRAWL", raising=False)
    monkeypatch.delenv("ICA_ONLINE_CONTEXT_IDS", raising=False)
    monkeypatch.delenv("ICA_PRODUCT_BATCH_SIZE", raising=False)
    with pytest.raises(IcaOnlineSourcePolicyError):
        cli._exact_collection_connector(Chain.ICA, REGION_ID)
