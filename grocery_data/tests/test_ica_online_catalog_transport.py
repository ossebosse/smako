from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

from grocery_data import __main__ as cli
from grocery_data.app.connectors.ica import (
    IcaOnlineCatalogClient,
    IcaOnlineCatalogConnector,
    IcaOnlineCollectionTransport,
    IcaOnlineSourcePolicyError,
)
from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
    IcaOnlineBrowserTransport,
    reconcile_category_proof,
)
from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_CATEGORY_TREE_KIND,
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    ICA_STORE_CONTEXT_KIND,
    IcaBatchResult,
    IcaProductPage,
)
from grocery_data.app.domain import Chain, CoverageLevel, RawBatch, RawFetch
from grocery_data.app.domain.raw import TransportMetrics

REGION_ID = "92198f17-b02f-4fae-ad41-228bcc725420"
RETAILER_ID = "1088004"
CATEGORY_ID = "ea243faf-2eca-47d7-af07-1dc61dd7693a"
FIXTURE_DIR = Path(__file__).parents[1] / "app" / "connectors" / "ica" / "fixtures"


class _NonHttpFullTransport:
    """A structural stand-in for browser-backed collection."""

    allow_full_crawl = True
    max_categories = None
    max_pages_per_category = None
    max_batches_per_page = None
    product_batch_size = 50
    requests_per_second = 0.5
    max_concurrency = 1
    allowed_context_ids = frozenset({REGION_ID})
    context_mappings: ClassVar[dict[str, str]] = {REGION_ID: RETAILER_ID}

    def __init__(self) -> None:
        self.closed = False
        self.catalog = RawBatch(
            chain=Chain.ICA,
            documents=(
                RawFetch(
                    chain=Chain.ICA,
                    store_external_id=REGION_ID,
                    kind="ica_product_page",
                    method="GET",
                    url=(
                        "https://handlaprivatkund.ica.se/stores/1088004/"
                        "api/webproductpagews/v6/product-pages"
                    ),
                    query={"category_id": "fixture", "page_index": "0"},
                    fetched_at=datetime(2026, 8, 25, tzinfo=UTC),
                    http_status=200,
                    content_type="application/json; profile=sanitized-ica-online-v1",
                    payload=b"{}",
                    connector_version="ica-online-catalog-v1",
                    page_number=0,
                ),
            ),
        )

    async def fetch_context(self, region_id: str) -> RawBatch:
        del region_id
        return RawBatch(chain=Chain.ICA, documents=())

    async def fetch_product_page(
        self,
        region_id: str,
        category_id: str,
        *,
        page_token: str | None = None,
        page_index: int = 0,
    ) -> tuple[RawFetch, IcaProductPage]:
        del region_id, category_id, page_token, page_index
        raise AssertionError("not needed by this transport-boundary test")

    async def fetch_product_batch(
        self,
        region_id: str,
        product_ids: Sequence[str],
        *,
        category_id: str,
        page_index: int,
        batch_index: int,
    ) -> tuple[RawFetch, IcaBatchResult]:
        del region_id, product_ids, category_id, page_index, batch_index
        raise AssertionError("not needed by this transport-boundary test")

    async def fetch_catalog(self, region_id: str) -> RawBatch:
        assert region_id == REGION_ID
        return self.catalog

    async def aclose(self) -> None:
        self.closed = True


class _OfflineProofTransport:
    allow_full_crawl = False
    max_categories = 1
    max_pages_per_category = None
    max_batches_per_page = None
    product_batch_size = None
    requests_per_second = 0.5
    max_concurrency = 1
    allowed_context_ids = frozenset({REGION_ID})
    context_mappings: ClassVar[dict[str, str]] = {REGION_ID: RETAILER_ID}

    def __init__(self, proof: RawBatch) -> None:
        self.proof = proof
        self.fetch_calls = 0
        self.closed = False

    async def observe_category_frontend(
        self,
        region_id: str,
        category_id: str,
    ) -> RawBatch:
        assert region_id == REGION_ID
        assert category_id == CATEGORY_ID
        self.fetch_calls += 1
        return self.proof

    async def aclose(self) -> None:
        self.closed = True


def _proof_raw(kind: str, payload: dict[str, object], **query: str) -> RawFetch:
    return RawFetch(
        chain=Chain.ICA,
        store_external_id=REGION_ID,
        kind=kind,
        method="PUT" if kind == ICA_PRODUCT_BATCH_KIND else "GET",
        url=f"https://handlaprivatkund.ica.se/stores/{RETAILER_ID}/api/proof",
        query=query,
        fetched_at=datetime(2026, 8, 25, tzinfo=UTC),
        http_status=200,
        content_type="application/json; profile=sanitized-ica-online-v1",
        payload=json.dumps(payload, ensure_ascii=False).encode(),
        connector_version="ica-online-browser-v1",
        page_number=int(query["page_index"]) if "page_index" in query else None,
    )


def _offline_category_proof() -> RawBatch:
    tree = json.loads((FIXTURE_DIR / "online_v6_category_tree.json").read_text("utf-8"))
    tree["retailerRegionId"] = RETAILER_ID
    page = json.loads((FIXTURE_DIR / "online_v6_product_page.json").read_text("utf-8"))
    page["missedPromotions"] = []
    page.pop("missingPromotions", None)
    for group in page["productGroups"]:
        for product in group.get("decoratedProducts", []):
            product.pop("featuredProductCampaign", None)
    batch = json.loads((FIXTURE_DIR / "online_v6_product_batch.json").read_text("utf-8"))
    batch["missedPromotions"] = []
    requested = page["productGroups"][0]["otherProductIds"]
    documents = (
        _proof_raw(
            ICA_STORE_CONTEXT_KIND,
            {
                "schema": "ica-online-context-v1",
                "regionId": REGION_ID,
                "retailerRegionId": RETAILER_ID,
            },
        ),
        _proof_raw(ICA_CATEGORY_TREE_KIND, tree),
        _proof_raw(
            ICA_PRODUCT_PAGE_KIND,
            page,
            category_id=CATEGORY_ID,
            page_index="0",
        ),
        _proof_raw(
            ICA_PRODUCT_BATCH_KIND,
            batch,
            category_id=CATEGORY_ID,
            page_index="0",
            batch_index="0",
            requested_product_ids=json.dumps(requested, separators=(",", ":")),
            observed_batch_size=str(len(requested)),
            frontend_observed="true",
        ),
    )
    return reconcile_category_proof(
        RawBatch(
            chain=Chain.ICA,
            documents=documents,
            transport=TransportMetrics(request_count=3),
        ),
        region_id=REGION_ID,
        category_id=CATEGORY_ID,
    )


@pytest.mark.asyncio
async def test_existing_http_client_satisfies_collection_transport_protocol() -> None:
    client = IcaOnlineCatalogClient(
        context_mappings={REGION_ID: RETAILER_ID},
        product_batch_size=5,
        allow_full_crawl=False,
        allowed_context_ids=(REGION_ID,),
    )
    try:
        assert isinstance(client, IcaOnlineCollectionTransport)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_connector_accepts_non_http_transport_without_changing_raw_contract() -> None:
    transport = _NonHttpFullTransport()

    assert isinstance(transport, IcaOnlineCollectionTransport)
    connector = IcaOnlineCatalogConnector.for_full_collection(client=transport)
    assert connector.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert connector.client is transport
    assert await transport.fetch_catalog(REGION_ID) is transport.catalog
    document = transport.catalog.documents[0]
    assert document.content_type == "application/json; profile=sanitized-ica-online-v1"
    assert document.store_external_id == REGION_ID

    await connector.aclose()
    assert transport.closed is True


def test_cli_exposes_browser_only_on_explicit_ica_operations() -> None:
    collect_default = cli._parser().parse_args(
        [
            "collect",
            "--chain",
            "ica",
            "--city",
            "Lund",
            "--context-store-id",
            REGION_ID,
        ]
    )
    collect_browser = cli._parser().parse_args(
        [
            "collect",
            "--chain",
            "ica",
            "--city",
            "Lund",
            "--context-store-id",
            REGION_ID,
            "--ica-transport",
            "browser",
        ]
    )
    canary = cli._parser().parse_args(
        ["canary", "ica", "--store", RETAILER_ID, "--ica-transport", "browser"]
    )
    proof = cli._parser().parse_args(
        [
            "ica-category-proof",
            "--store",
            REGION_ID,
            "--category-id",
            "ea243faf-2eca-47d7-af07-1dc61dd7693a",
            "--ica-transport",
            "browser",
        ]
    )

    assert collect_default.ica_transport == "http"
    assert collect_browser.ica_transport == "browser"
    assert canary.ica_transport == "browser"
    assert proof.command == "ica-category-proof"
    assert proof.ica_transport == "browser"


@pytest.mark.asyncio
async def test_browser_cli_factories_remain_exact_and_do_not_launch_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ICA_ONLINE_CONTEXT_IDS", REGION_ID)
    monkeypatch.delenv("ICA_PRODUCT_BATCH_SIZE", raising=False)
    monkeypatch.setenv("ICA_ALLOW_BROWSER_CATEGORY_PROOF", "true")

    canary = cli._canary_connector(
        Chain.ICA,
        store=RETAILER_ID,
        ica_transport="browser",
    )
    proof, proof_transport = cli._ica_browser_category_proof_connector(REGION_ID)
    try:
        assert isinstance(canary.client, IcaOnlineBrowserTransport)
        assert canary.coverage is CoverageLevel.PARTIAL_CATALOG
        assert canary.allowed_context_ids == frozenset({REGION_ID})
        assert isinstance(proof_transport, IcaOnlineBrowserTransport)
        assert proof.client is proof_transport
        assert proof_transport.allow_category_proof is True
        assert proof_transport.allow_full_crawl is False
        assert proof_transport.product_batch_size is None
        assert proof_transport.max_pages_per_category is None
    finally:
        await canary.aclose()
        await proof.aclose()


def test_legacy_browser_full_factory_fails_closed_after_existing_review_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ICA_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("ICA_ONLINE_CONTEXT_IDS", REGION_ID)
    monkeypatch.setenv("ICA_PRODUCT_BATCH_SIZE", "50")

    with pytest.raises(
        IcaOnlineSourcePolicyError,
        match="observer-backed full traversal",
    ):
        cli._exact_collection_connector(
            Chain.ICA,
            REGION_ID,
            ica_transport="browser",
        )


@pytest.mark.asyncio
async def test_browser_transport_is_rejected_outside_exact_ica_commands() -> None:
    with pytest.raises(ValueError, match="only for ICA"):
        cli._canary_connector(Chain.COOP, ica_transport="browser")
    with pytest.raises(ValueError, match="explicit --ica-transport browser"):
        await cli._ica_category_proof(
            type(
                "Args",
                (),
                {
                    "ica_transport": "http",
                    "store": REGION_ID,
                    "category_id": "category",
                    "city": "Lund",
                },
            )()
        )


@pytest.mark.asyncio
async def test_category_proof_cli_saves_raw_then_reconciles_after_transport_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proof = _offline_category_proof()
    transport = _OfflineProofTransport(proof)
    connector = IcaOnlineCatalogConnector(
        client=transport,  # type: ignore[arg-type]
        context_mappings={REGION_ID: RETAILER_ID},
        coverage=CoverageLevel.PARTIAL_CATALOG,
    )
    reports: list[dict[str, object]] = []
    monkeypatch.setattr(
        cli,
        "_ica_browser_category_proof_connector",
        lambda _store: (connector, transport),
    )
    monkeypatch.setattr(
        cli.GroceryDataSettings,
        "from_env",
        classmethod(lambda _cls: SimpleNamespace(raw_snapshot_root=tmp_path / "raw")),
    )
    monkeypatch.setattr(cli, "_json", reports.append)

    result = await cli._ica_category_proof(
        SimpleNamespace(
            ica_transport="browser",
            store=REGION_ID,
            category_id=CATEGORY_ID,
            city="Lund",
        )
    )

    assert result == 0
    assert transport.fetch_calls == 1
    assert transport.closed is True
    assert reports[0]["promotable"] is False
    assert reports[0]["observed_product_batch_sizes"] == [
        len(
            json.loads(
                next(
                    document.query["requested_product_ids"]
                    for document in proof.documents
                    if document.kind == ICA_PRODUCT_BATCH_KIND
                )
            )
        )
    ]
    replay = reports[0]["offline_replay"]
    assert isinstance(replay, dict)
    assert replay == {
        "browser_calls": 0,
        "network_calls": 0,
        "products": 3,
        "failures": 0,
        "status": "pass",
    }
    assert len(tuple((tmp_path / "raw").rglob("*.json"))) >= len(proof.documents)
