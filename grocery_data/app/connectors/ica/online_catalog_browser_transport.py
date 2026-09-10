from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit, urlunsplit

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.ica.online_catalog_client import (
    _CHALLENGE_MARKERS,
    ICA_CATEGORY_TREE_KIND,
    ICA_STORE_CONTEXT_KIND,
    IcaOnlineAccessChallenge,
    IcaOnlineCatalogClient,
    IcaOnlineHttpError,
    IcaOnlineRateLimitStop,
    IcaOnlineSourcePolicyError,
    _environment_flag,
    _safe_raw_query,
    sanitized_api_payload,
)
from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    IcaBatchResult,
    IcaCategoryTree,
    IcaOnlineSchemaError,
    IcaProductPage,
    purchase_semantic_fingerprint,
    reconcile_page_batches,
    sanitized_category_tree_payload,
    sanitized_context_payload,
    validate_continuation_chain,
)
from grocery_data.app.domain import CatalogCompletion, Chain, RawBatch, RawFetch
from grocery_data.app.domain.raw import TransportMetrics

_STOP_STATUSES = frozenset({401, 403, 405, 429})
_FRONTEND_STOP_STATUSES = frozenset({202, 401, 403, 405, 429})
_EXPECTED_HOST = "handlaprivatkund.ica.se"
_PRODUCT_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_GUNNESBO_REGION_ID = "92198f17-b02f-4fae-ad41-228bcc725420"
_GUNNESBO_RETAILER_ID = "1088004"
_GUNNESBO_MEJERI_CATEGORY_ID = "ea243faf-2eca-47d7-af07-1dc61dd7693a"
_VERIFIED_CATEGORY_UI_PATHS = {
    (_GUNNESBO_REGION_ID, _GUNNESBO_MEJERI_CATEGORY_ID): (
        "/stores/1088004/categories/mejeri-ost/"
        "ea243faf-2eca-47d7-af07-1dc61dd7693a"
    ),
}

@dataclass(frozen=True, slots=True)
class _FrontendRequest:
    sequence: int
    kind: Literal["page", "batch"]
    path: str
    category_id: str
    request_token_hash: str | None = None
    requested_product_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _FrontendCapture:
    request: _FrontendRequest
    status: int
    payload: dict[str, Any]
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class _FrontendStop:
    status: int
    path: str
    classification: str
    content_type: str | None = None


def _never_http(request: httpx.Request) -> httpx.Response:
    del request
    raise RuntimeError("ICA browser transport must never use the HTTP client")


def _safe_response_url(value: object, *, expected_path_prefix: str) -> str:
    parsed = urlsplit(str(value))
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("ICA browser response has an invalid port") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != _EXPECTED_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or not parsed.path.startswith(expected_path_prefix)
    ):
        raise ValueError("ICA browser response left the exact public store API route")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _safe_context_url(value: object, *, retailer_id: str) -> str:
    safe = _safe_response_url(value, expected_path_prefix=f"/stores/{retailer_id}")
    parsed = urlsplit(safe)
    if parsed.path.rstrip("/") != f"/stores/{retailer_id}":
        raise ValueError("ICA browser context changed the exact public store route")
    return safe


def _safe_category_ui_url(
    value: object,
    *,
    retailer_id: str,
    category_id: str,
) -> str:
    expected_prefix = f"/stores/{retailer_id}/categories/"
    safe = _safe_response_url(value, expected_path_prefix=expected_prefix)
    parsed = urlsplit(safe)
    if not parsed.path.rstrip("/").endswith(f"/{category_id}"):
        raise ValueError("ICA frontend category route changed category identity")
    return safe


def _catalog_route(path: str, *, retailer_id: str) -> Literal["page", "batch", "search"] | None:
    prefix = f"/stores/{retailer_id}/api/webproductpagews/v6/"
    if path == f"{prefix}product-pages":
        return "page"
    if path == f"{prefix}products":
        return "batch"
    if path == f"{prefix}product-pages/search":
        return "search"
    return None


def _single_query_value(values: Mapping[str, list[str]], key: str) -> str | None:
    candidates = values.get(key, [])
    if not candidates:
        return None
    if len(candidates) != 1 or not candidates[0].strip():
        raise IcaOnlineSchemaError(f"ICA frontend request has ambiguous {key}")
    return candidates[0].strip()


def _frontend_request(
    request: Any,
    *,
    sequence: int,
    retailer_id: str,
    category_id: str,
) -> _FrontendRequest | None:
    """Project one ICA-owned request without reading headers or browser state."""

    parsed = urlsplit(str(request.url))
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname != _EXPECTED_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        return None
    route = _catalog_route(parsed.path, retailer_id=retailer_id)
    if route is None or route == "search":
        return None
    method = str(request.method).upper()
    if route == "page":
        if method != "GET":
            raise IcaOnlineSchemaError("ICA frontend product-pages method changed")
        query = parse_qs(parsed.query, keep_blank_values=True)
        requested_category = _single_query_value(query, "categoryId")
        if requested_category != category_id:
            return None
        token = _single_query_value(query, "pageToken")
        return _FrontendRequest(
            sequence=sequence,
            kind="page",
            path=parsed.path,
            category_id=category_id,
            request_token_hash=sha256(token.encode()).hexdigest() if token else None,
        )
    if method != "PUT":
        raise IcaOnlineSchemaError("ICA frontend products method changed")
    # This is the sole permitted request-body projection. The array is
    # immediately reduced to validated public catalog UUID identities; no raw
    # body, headers, CSRF/runtime values or unrelated fields are retained.
    try:
        raw_ids = request.post_data_json
    except (AttributeError, TypeError, ValueError) as exc:
        raise IcaOnlineSchemaError("ICA frontend products body is unavailable") from exc
    if (
        not isinstance(raw_ids, Sequence)
        or isinstance(raw_ids, str | bytes | bytearray)
        or not raw_ids
    ):
        raise IcaOnlineSchemaError("ICA frontend products body is not a UUID array")
    ids = tuple(str(value).strip().casefold() for value in raw_ids)
    if len(ids) != len(set(ids)) or any(_PRODUCT_UUID.fullmatch(value) is None for value in ids):
        raise IcaOnlineSchemaError("ICA frontend products body has invalid identities")
    return _FrontendRequest(
        sequence=sequence,
        kind="batch",
        path=parsed.path,
        category_id=category_id,
        requested_product_ids=ids,
    )


def _challenge_marker(value: str) -> bool:
    beginning = value[:65536].lstrip().casefold().encode()
    return any(marker in beginning for marker in _CHALLENGE_MARKERS)


def _raw_index(document: RawFetch, key: str) -> int:
    value = document.query.get(key)
    if value is None:
        raise IcaOnlineSchemaError(f"ICA category proof raw lacks {key}")
    try:
        index = int(value)
    except (TypeError, ValueError) as exc:
        raise IcaOnlineSchemaError(f"ICA category proof {key} is not an integer") from exc
    if index < 0 or document.page_number not in {None, index}:
        raise IcaOnlineSchemaError(f"ICA category proof has invalid {key}")
    return index


def _raw_requested_ids(document: RawFetch) -> tuple[str, ...]:
    encoded = document.query.get("requested_product_ids")
    if encoded is None:
        raise IcaOnlineSchemaError("ICA category proof batch lacks requested product IDs")
    try:
        decoded = json.loads(encoded)
    except (json.JSONDecodeError, TypeError) as exc:
        raise IcaOnlineSchemaError(
            "ICA category proof requested product IDs are invalid JSON"
        ) from exc
    if not isinstance(decoded, list) or any(not isinstance(item, str) for item in decoded):
        raise IcaOnlineSchemaError("ICA category proof requested product IDs are not a list")
    return tuple(decoded)


def reconcile_category_proof(
    raw: RawBatch,
    *,
    region_id: str,
    category_id: str,
) -> RawBatch:
    """Replay one captured ICA category without a browser or network client."""

    if raw.chain is not Chain.ICA:
        raise IcaOnlineSchemaError("ICA category proof has the wrong chain")
    relevant = tuple(
        document
        for document in raw.documents
        if document.kind
        in {ICA_CATEGORY_TREE_KIND, ICA_PRODUCT_PAGE_KIND, ICA_PRODUCT_BATCH_KIND}
    )
    if any(document.store_external_id != region_id for document in relevant):
        raise IcaOnlineSchemaError("ICA category proof mixes online contexts")
    tree_documents = tuple(
        document for document in relevant if document.kind == ICA_CATEGORY_TREE_KIND
    )
    if len(tree_documents) != 1:
        raise IcaOnlineSchemaError("ICA category proof requires exactly one category tree")
    tree = IcaCategoryTree.from_payload(tree_documents[0].json_payload())
    matching_nodes = tuple(node for node in tree.all_nodes if node.category_id == category_id)
    if len(matching_nodes) != 1:
        raise IcaOnlineSchemaError("ICA category proof target is absent or repeated in tree")

    page_documents: list[tuple[int, RawFetch]] = []
    batch_documents: dict[tuple[int, int], RawFetch] = {}
    for document in relevant:
        if document.kind == ICA_CATEGORY_TREE_KIND:
            continue
        if document.query.get("category_id") != category_id:
            raise IcaOnlineSchemaError("ICA category proof contains another category")
        page_index = _raw_index(document, "page_index")
        if document.kind == ICA_PRODUCT_PAGE_KIND:
            page_documents.append((page_index, document))
            continue
        batch_index = _raw_index(document, "batch_index")
        key = (page_index, batch_index)
        if key in batch_documents:
            raise IcaOnlineSchemaError("ICA category proof repeats a batch index")
        batch_documents[key] = document
    page_documents.sort(key=lambda item: item[0])
    if not page_documents:
        raise IcaOnlineSchemaError("ICA category proof contains no product pages")
    if tuple(index for index, _ in page_documents) != tuple(range(len(page_documents))):
        raise IcaOnlineSchemaError("ICA category proof page indices are incomplete")
    pages = tuple(
        IcaProductPage.from_payload(document.json_payload(), category_id=category_id)
        for _, document in page_documents
    )
    if any(page.next_page_token is not None for page in pages):
        raise IcaOnlineSchemaError("ICA category proof raw retained a live continuation token")
    validate_continuation_chain(pages)
    if page_documents[0][1].query.get("previous_page_token_hash") is not None:
        raise IcaOnlineSchemaError("ICA category proof first page has continuation lineage")
    for index in range(1, len(page_documents)):
        previous_hash = page_documents[index][1].query.get("previous_page_token_hash")
        if previous_hash != pages[index - 1].next_page_token_hash:
            raise IcaOnlineSchemaError("ICA category proof continuation lineage is broken")

    products: dict[str, dict[str, Any]] = {}
    fingerprints: dict[str, str] = {}
    raw_rows = 0
    exact_page_duplicates = 0
    placement_overlaps = 0
    pagination_overlaps = 0
    for (page_index, _), page in zip(page_documents, pages, strict=True):
        raw_rows += page.raw_product_rows
        exact_page_duplicates += page.duplicate_metrics.exact_duplicates_removed
        placement_overlaps += page.duplicate_metrics.placement_overlaps
        indexed_batches = sorted(
            (
                (batch_index, document)
                for (candidate_page, batch_index), document in batch_documents.items()
                if candidate_page == page_index
            ),
            key=lambda item: item[0],
        )
        if tuple(index for index, _ in indexed_batches) != tuple(range(len(indexed_batches))):
            raise IcaOnlineSchemaError("ICA category proof batch indices are incomplete")
        batches = tuple(
            IcaBatchResult.from_payload(
                document.json_payload(),
                requested_product_ids=_raw_requested_ids(document),
            )
            for _, document in indexed_batches
        )
        resolved = reconcile_page_batches(page, batches)
        for product_id, product in zip(resolved.product_ids, resolved.products, strict=True):
            fingerprint = purchase_semantic_fingerprint(product)
            previous = fingerprints.get(product_id)
            if previous is not None:
                if previous != fingerprint:
                    raise IcaOnlineSchemaError(
                        "ICA category proof has conflicting pagination duplicate"
                    )
                pagination_overlaps += 1
                continue
            products[product_id] = product
            fingerprints[product_id] = fingerprint
    used_batch_keys = {
        (page_index, batch_index)
        for page_index, _ in page_documents
        for batch_index in range(
            len(
                [
                    key
                    for key in batch_documents
                    if key[0] == page_index
                ]
            )
        )
    }
    if set(batch_documents) != used_batch_keys:
        raise IcaOnlineSchemaError("ICA category proof has orphaned batch documents")

    declared_candidates = {
        value
        for value in (
            matching_nodes[0].product_count,
            *(page.declared_product_count for page in pages),
        )
        if value is not None
    }
    if len(declared_candidates) != 1:
        raise IcaOnlineSchemaError("ICA category proof lacks one consistent declared count")
    declared = next(iter(declared_candidates))
    if len(products) != declared:
        raise IcaOnlineSchemaError(
            "ICA category proof does not match declared product count: "
            f"declared={declared}, unique={len(products)}"
        )
    exact_duplicates = exact_page_duplicates + placement_overlaps + pagination_overlaps
    if raw_rows != len(products) + exact_duplicates:
        raise IcaOnlineSchemaError("ICA category proof duplicate metrics do not reconcile")
    completion = CatalogCompletion(
        complete=True,
        limited=True,
        expected_categories=1,
        completed_categories=1,
        pages_fetched=len(pages),
        products_observed=len(products),
        expected_products=raw_rows,
        raw_rows=raw_rows,
        unique_products=len(products),
        duplicate_products=exact_duplicates,
        within_partition_duplicates=exact_duplicates,
        cross_partition_duplicates=0,
        exact_duplicates_removed=exact_duplicates,
        conflicting_duplicates=0,
        pagination_overlaps=pagination_overlaps,
        expected_pages=len(pages),
        reason=f"complete one-category browser proof; declared={declared}",
    )
    if not completion.exact_evidence_reconciles:
        raise IcaOnlineSchemaError("ICA category proof exact evidence does not reconcile")
    return raw.model_copy(update={"catalog_completion": completion})


def _frontend_category_batch(
    *,
    context_documents: tuple[RawFetch, RawFetch],
    captures: Sequence[_FrontendCapture],
    region_id: str,
    retailer_id: str,
    category_id: str,
    transport: TransportMetrics,
    connector_version: str,
) -> RawBatch:
    page_rows = [
        (capture, IcaProductPage.from_payload(capture.payload, category_id=category_id))
        for capture in captures
        if capture.request.kind == "page"
    ]
    initial = [row for row in page_rows if row[0].request.request_token_hash is None]
    if len(initial) != 1:
        raise IcaOnlineSchemaError("ICA frontend proof requires one initial product page")
    continuation: dict[str, tuple[_FrontendCapture, IcaProductPage]] = {}
    for row in page_rows:
        request_hash = row[0].request.request_token_hash
        if request_hash is None:
            continue
        if request_hash in continuation:
            raise IcaOnlineSchemaError("ICA frontend repeated a continuation request")
        continuation[request_hash] = row
    ordered_pages: list[tuple[_FrontendCapture, IcaProductPage]] = []
    seen_response_tokens: set[str] = set()
    current = initial[0]
    while True:
        ordered_pages.append(current)
        page = current[1]
        if page.terminal:
            break
        next_hash = page.next_page_token_hash
        if next_hash is None or next_hash in seen_response_tokens:
            raise IcaOnlineSchemaError("ICA frontend continuation loop or missing hash")
        seen_response_tokens.add(next_hash)
        following = continuation.get(next_hash)
        if following is None:
            raise IcaOnlineSchemaError("ICA frontend has not requested the next continuation")
        current = following
    if len(ordered_pages) != len(page_rows):
        raise IcaOnlineSchemaError("ICA frontend captured an orphan product page")

    batches_by_page: dict[int, list[tuple[_FrontendCapture, IcaBatchResult]]] = {
        index: [] for index in range(len(ordered_pages))
    }
    # Frontends can repeat an already-completed lazy-load request during
    # rendering.  Suppress it only when both its exact requested identity set
    # and complete sanitized response are byte-identical.  A second response
    # for the same requested set with different purchase semantics is a hard
    # conflict, never "last response wins".
    seen_batch_payloads: dict[tuple[str, ...], bytes] = {}
    for capture in sorted(captures, key=lambda item: item.request.sequence):
        if capture.request.kind != "batch":
            continue
        batch_key = capture.request.requested_product_ids
        payload = sanitized_api_payload(capture.payload)
        previous_payload = seen_batch_payloads.get(batch_key)
        if previous_payload is not None:
            if previous_payload != payload:
                raise IcaOnlineSchemaError(
                    "ICA frontend repeated a product batch with conflicting semantics"
                )
            continue
        seen_batch_payloads[batch_key] = payload
        batch = IcaBatchResult.from_payload(
            capture.payload,
            requested_product_ids=capture.request.requested_product_ids,
        )
        requested = set(capture.request.requested_product_ids)
        candidates = [
            (page_capture.request.sequence, page_index)
            for page_index, (page_capture, page) in enumerate(ordered_pages)
            if page_capture.request.sequence < capture.request.sequence
            and requested.issubset(set(page.other_product_ids))
        ]
        if not candidates:
            raise IcaOnlineSchemaError("ICA frontend product batch is orphaned")
        _, page_index = max(candidates)
        batches_by_page[page_index].append((capture, batch))

    documents: list[RawFetch] = list(context_documents)
    api_base = f"https://{_EXPECTED_HOST}/stores/{retailer_id}/api/webproductpagews/v6"
    for page_index, (capture, _) in enumerate(ordered_pages):
        logical_query: dict[str, object] = {
            "category_id": category_id,
            "page_index": page_index,
            "frontend_observed": True,
        }
        if capture.request.request_token_hash is not None:
            logical_query["previous_page_token_hash"] = capture.request.request_token_hash
        documents.append(
            RawFetch(
                chain=Chain.ICA,
                store_external_id=region_id,
                kind=ICA_PRODUCT_PAGE_KIND,
                method="GET",
                url=f"{api_base}/product-pages",
                query=_safe_raw_query(logical_query),
                fetched_at=capture.fetched_at,
                http_status=capture.status,
                content_type="application/json; profile=sanitized-ica-online-v1",
                payload=sanitized_api_payload(capture.payload),
                connector_version=connector_version,
                page_number=page_index,
            )
        )
        for batch_index, (batch_capture, _) in enumerate(
            sorted(
                batches_by_page[page_index],
                key=lambda item: item[0].request.sequence,
            )
        ):
            ids = batch_capture.request.requested_product_ids
            documents.append(
                RawFetch(
                    chain=Chain.ICA,
                    store_external_id=region_id,
                    kind=ICA_PRODUCT_BATCH_KIND,
                    method="PUT",
                    url=f"{api_base}/products",
                    query=_safe_raw_query(
                        {
                            "category_id": category_id,
                            "page_index": page_index,
                            "batch_index": batch_index,
                            "requested_product_ids": ids,
                            "observed_batch_size": len(ids),
                            "frontend_observed": True,
                        }
                    ),
                    fetched_at=batch_capture.fetched_at,
                    http_status=batch_capture.status,
                    content_type="application/json; profile=sanitized-ica-online-v1",
                    payload=sanitized_api_payload(batch_capture.payload),
                    connector_version=connector_version,
                    page_number=page_index,
                )
            )
    return reconcile_category_proof(
        RawBatch(
            chain=Chain.ICA,
            documents=tuple(documents),
            transport=transport,
        ),
        region_id=region_id,
        category_id=category_id,
    )


def _partial_frontend_documents(
    captures: Sequence[_FrontendCapture],
    *,
    region_id: str,
    retailer_id: str,
    category_id: str,
    connector_version: str,
) -> tuple[RawFetch, ...]:
    """Retain sanitized successful responses without claiming replay completeness."""

    api_base = f"https://{_EXPECTED_HOST}/stores/{retailer_id}/api/webproductpagews/v6"
    documents: list[RawFetch] = []
    for capture in sorted(captures, key=lambda item: item.request.sequence):
        request = capture.request
        query: dict[str, object] = {
            "category_id": category_id,
            "observation_sequence": request.sequence,
            "frontend_observed": True,
        }
        if request.request_token_hash is not None:
            query["previous_page_token_hash"] = request.request_token_hash
        if request.kind == "batch":
            query.update(
                {
                    "requested_product_ids": request.requested_product_ids,
                    "observed_batch_size": len(request.requested_product_ids),
                }
            )
        documents.append(
            RawFetch(
                chain=Chain.ICA,
                store_external_id=region_id,
                kind=(
                    ICA_PRODUCT_PAGE_KIND if request.kind == "page" else ICA_PRODUCT_BATCH_KIND
                ),
                method="GET" if request.kind == "page" else "PUT",
                url=(
                    f"{api_base}/product-pages"
                    if request.kind == "page"
                    else f"{api_base}/products"
                ),
                query=_safe_raw_query(query),
                fetched_at=capture.fetched_at,
                http_status=capture.status,
                content_type="application/json; profile=sanitized-ica-online-v1",
                payload=sanitized_api_payload(capture.payload),
                connector_version=connector_version,
            )
        )
    return tuple(documents)


class IcaOnlineBrowserTransport(IcaOnlineCatalogClient):
    """Strict ephemeral Chromium transport for ICA's current public runtime.

    The inherited client owns all traversal and reconciliation. This subclass
    replaces only context activation and JSON I/O. Every active region gets a
    newly-created anonymous browser context. Browser state is never read,
    serialized, logged or included in a :class:`RawFetch`.
    """

    connector_version = "ica-online-browser-v1"

    def __init__(
        self,
        *,
        context_mappings: Mapping[str, str],
        requests_per_second: float | None = None,
        max_categories: int | None = 1,
        max_pages_per_category: int | None = 1,
        max_batches_per_page: int | None = 1,
        product_batch_size: int | None = None,
        allow_full_crawl: bool | None = None,
        allowed_context_ids: Iterable[str] | str | None = None,
        max_concurrency: int | None = None,
        page_size: int = 300,
        max_products_to_decorate: int = 50,
        navigation_timeout_ms: int = 30_000,
        allow_category_proof: bool | None = None,
        frontend_headless: bool = False,
        frontend_max_scrolls: int = 400,
        frontend_scroll_pixels: int = 1_600,
        frontend_settle_ms: int = 750,
        category_ui_paths: Mapping[tuple[str, str], str] | None = None,
        playwright_factory: Callable[[], Any] | None = None,
    ) -> None:
        if navigation_timeout_ms <= 0:
            raise ValueError("ICA browser navigation timeout must be positive")
        inert_client = httpx.AsyncClient(
            base_url=self.base_url,
            transport=httpx.MockTransport(_never_http),
        )
        super().__init__(
            context_mappings=context_mappings,
            requests_per_second=requests_per_second,
            max_categories=max_categories,
            max_pages_per_category=max_pages_per_category,
            max_batches_per_page=max_batches_per_page,
            product_batch_size=product_batch_size,
            allow_full_crawl=allow_full_crawl,
            allowed_context_ids=allowed_context_ids,
            max_concurrency=max_concurrency,
            page_size=page_size,
            max_products_to_decorate=max_products_to_decorate,
            client=inert_client,
        )
        self._inert_client = inert_client
        self.navigation_timeout_ms = navigation_timeout_ms
        self.allow_category_proof = (
            _environment_flag("ICA_ALLOW_BROWSER_CATEGORY_PROOF", default=False)
            if allow_category_proof is None
            else allow_category_proof
        )
        if not isinstance(self.allow_category_proof, bool):
            raise TypeError("allow_category_proof must be a boolean")
        if not isinstance(frontend_headless, bool):
            raise TypeError("frontend_headless must be a boolean")
        if frontend_max_scrolls <= 0 or frontend_scroll_pixels <= 0 or frontend_settle_ms <= 0:
            raise ValueError("ICA frontend observation bounds must be positive")
        if self.allow_category_proof and self.allow_full_crawl:
            raise ValueError("ICA browser category proof and full crawl are separate authorities")
        if self.allow_category_proof:
            if self.max_categories != 1:
                raise ValueError("ICA browser category proof requires exactly one category")
            # The parent constructor first validates the ordinary bounded
            # canary. This explicit second gate permits observation of complete
            # frontend pagination for exactly one category, never the full tree.
            self.max_pages_per_category = None
            self.max_batches_per_page = None
        self.frontend_headless = frontend_headless
        self.frontend_max_scrolls = frontend_max_scrolls
        self.frontend_scroll_pixels = frontend_scroll_pixels
        self.frontend_settle_ms = frontend_settle_ms
        paths = dict(_VERIFIED_CATEGORY_UI_PATHS)
        paths.update(category_ui_paths or {})
        self.category_ui_paths = {
            (str(region).strip().casefold(), str(category).strip().casefold()): str(path).strip()
            for (region, category), path in paths.items()
        }
        self._playwright_factory = playwright_factory
        self._playwright_manager: Any | None = None
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._browser_context: Any | None = None
        self._page: Any | None = None
        self._active_region_id: str | None = None
        self._context_documents: tuple[RawFetch, RawFetch] | None = None

    @staticmethod
    def _default_playwright_factory() -> Any:
        from playwright.async_api import async_playwright

        return async_playwright()

    def _diagnostic_raw_from_browser(
        self,
        *,
        method: str,
        url: str,
        kind: str,
        region_id: str,
        logical_query: Mapping[str, object] | None,
        page_number: int | None,
        status: int,
        classification: str,
        observed_content_type: str | None = None,
    ) -> RawFetch:
        diagnostic: dict[str, object] = {
            "schema": "ica-online-transport-stop-v1",
            "classification": classification,
            "http_status": status,
        }
        if observed_content_type is not None:
            diagnostic["observed_content_type"] = observed_content_type
        payload = json.dumps(
            diagnostic,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        parsed = urlsplit(url)
        safe_path = parsed.path if parsed.hostname == _EXPECTED_HOST else "/"
        safe_url = f"https://{_EXPECTED_HOST}{safe_path}"
        return RawFetch(
            chain=Chain.ICA,
            store_external_id=region_id,
            kind=kind,
            method=method,
            url=safe_url,
            query=_safe_raw_query(logical_query),
            fetched_at=datetime.now(tz=UTC),
            http_status=status,
            content_type="application/json; profile=transport-stop-diagnostic",
            payload=payload,
            connector_version=self.connector_version,
            page_number=page_number,
        )

    async def _discard_browser(self) -> None:
        page, context, browser, playwright = (
            self._page,
            self._browser_context,
            self._browser,
            self._playwright,
        )
        self._page = None
        self._browser_context = None
        self._browser = None
        self._playwright = None
        self._playwright_manager = None
        self._active_region_id = None
        self._context_documents = None
        if page is not None:
            with suppress(Exception):
                await page.close()
        if context is not None:
            with suppress(Exception):
                await context.close()
        if browser is not None:
            with suppress(Exception):
                await browser.close()
        if playwright is not None:
            with suppress(Exception):
                await playwright.stop()

    async def _raise_access_stop(
        self,
        *,
        raw: RawFetch,
        classification: str,
    ) -> None:
        await self._discard_browser()
        error_type = IcaOnlineRateLimitStop if classification == "rate_limit" else (
            IcaOnlineAccessChallenge
        )
        raise error_type(
            f"ICA browser collection stopped ({classification}, HTTP {raw.http_status})",
            raw,
        )

    async def _activate_context(
        self,
        region_id: str,
    ) -> tuple[RawFetch, RawFetch]:
        region_id, retailer_id = self.require_context(region_id)
        if self._active_region_id == region_id and self._context_documents is not None:
            return self._context_documents
        if self._active_region_id is not None:
            # Context-specific prices must never share ephemeral browser state.
            await self._discard_browser()

        manager = (
            self._playwright_factory()
            if self._playwright_factory is not None
            else self._default_playwright_factory()
        )
        self._playwright_manager = manager
        try:
            playwright = await manager.start()
            self._playwright = playwright
            # No launch args, browser channel, executable override, persistent
            # profile, proxy, headers, locale or fingerprint customization.
            browser = await playwright.chromium.launch(headless=True)
            self._browser = browser
            context = await browser.new_context()
            self._browser_context = context
            page = await context.new_page()
            self._page = page
            url = f"{self.base_url}/stores/{retailer_id}"
            await self._limiter.wait()
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.navigation_timeout_ms,
            )
            status = int(response.status) if response is not None else 0
            self._observe(status)
            final_url = str(page.url)
            safe_url = _safe_context_url(final_url, retailer_id=retailer_id)
            body_text = await page.locator("body").inner_text(
                timeout=self.navigation_timeout_ms
            )
            if status in _STOP_STATUSES or _challenge_marker(body_text):
                if status < 400:
                    self._http_error_count += 1
                classification = "rate_limit" if status == 429 else "access_challenge"
                raw = self._diagnostic_raw_from_browser(
                    method="GET",
                    url=safe_url,
                    kind=ICA_STORE_CONTEXT_KIND,
                    region_id=region_id,
                    logical_query={"retailer_region_id": retailer_id},
                    page_number=None,
                    status=status,
                    classification=classification,
                )
                await self._raise_access_stop(raw=raw, classification=classification)
            if response is None or status >= 400:
                raw = self._diagnostic_raw_from_browser(
                    method="GET",
                    url=safe_url,
                    kind=ICA_STORE_CONTEXT_KIND,
                    region_id=region_id,
                    logical_query={"retailer_region_id": retailer_id},
                    page_number=None,
                    status=status,
                    classification="browser_navigation_error",
                )
                raise IcaOnlineHttpError("ICA browser context navigation failed", raw)
            html = await page.content()
            if _challenge_marker(html):
                self._http_error_count += 1
                raw = self._diagnostic_raw_from_browser(
                    method="GET",
                    url=safe_url,
                    kind=ICA_STORE_CONTEXT_KIND,
                    region_id=region_id,
                    logical_query={"retailer_region_id": retailer_id},
                    page_number=None,
                    status=status,
                    classification="access_challenge",
                )
                await self._raise_access_stop(raw=raw, classification="access_challenge")
            try:
                context_payload = sanitized_context_payload(
                    html,
                    expected_retailer_region_id=retailer_id,
                    expected_region_id=region_id,
                )
                category_payload = sanitized_category_tree_payload(
                    html,
                    expected_retailer_region_id=retailer_id,
                    expected_region_id=region_id,
                )
            except (UnicodeError, ValueError, IcaOnlineSchemaError) as exc:
                raw = self._diagnostic_raw_from_browser(
                    method="GET",
                    url=safe_url,
                    kind=ICA_STORE_CONTEXT_KIND,
                    region_id=region_id,
                    logical_query={"retailer_region_id": retailer_id},
                    page_number=None,
                    status=status,
                    classification="sanitization_failure",
                )
                raise IcaOnlineHttpError("ICA browser context readback failed closed", raw) from exc
            fetched_at = datetime.now(tz=UTC)
            common = {
                "chain": Chain.ICA,
                "store_external_id": region_id,
                "method": "GET",
                "url": safe_url,
                "query": {"retailer_region_id": retailer_id},
                "fetched_at": fetched_at,
                "http_status": status,
                "connector_version": self.connector_version,
            }
            documents = (
                RawFetch(
                    **common,
                    kind=ICA_STORE_CONTEXT_KIND,
                    content_type="application/json; profile=sanitized-ica-store-context-v1",
                    payload=context_payload,
                ),
                RawFetch(
                    **common,
                    kind=ICA_CATEGORY_TREE_KIND,
                    content_type="application/json; profile=sanitized-ica-category-tree-v1",
                    payload=category_payload,
                ),
            )
            self._active_region_id = region_id
            self._context_documents = documents
            return documents
        except Exception:
            if self._active_region_id != region_id:
                await self._discard_browser()
            raise

    async def fetch_context(self, region_id: str) -> RawBatch:
        region_id, _ = self.require_context(region_id)
        before = self._metrics_snapshot()
        try:
            documents = await self._activate_context(region_id)
        except Exception as exc:
            raw = exc.raw if isinstance(exc, IcaOnlineHttpError) else None
            raise ConnectorFetchError(
                "ICA browser context verification stopped",
                partial_batch=RawBatch(
                    chain=Chain.ICA,
                    documents=((raw,) if raw is not None else ()),
                    transport=self._metrics_since(before),
                ),
            ) from exc
        return RawBatch(
            chain=Chain.ICA,
            documents=documents,
            transport=self._metrics_since(before),
        )

    async def observe_category_frontend(
        self,
        region_id: str,
        category_id: str,
    ) -> RawBatch:
        """Observe ICA's own category runtime without synthesizing API requests."""

        region_id, retailer_id = self.require_context(region_id)
        if not self.allow_category_proof or self.allow_full_crawl:
            raise PermissionError(
                "ICA frontend category proof requires separate explicit REVIEW authority"
            )
        category_id = category_id.strip().casefold()
        if _PRODUCT_UUID.fullmatch(category_id) is None:
            raise ValueError("ICA frontend category ID must be a UUID")
        ui_path = self.category_ui_paths.get((region_id, category_id))
        if ui_path is None:
            raise IcaOnlineSchemaError("ICA category has no exact verified frontend UI path")
        parsed_ui_path = urlsplit(ui_path)
        if parsed_ui_path.scheme or parsed_ui_path.netloc or parsed_ui_path.query:
            raise ValueError("ICA verified frontend path must be a relative query-free path")
        _safe_category_ui_url(
            f"{self.base_url}{ui_path}",
            retailer_id=retailer_id,
            category_id=category_id,
        )

        before = self._metrics_snapshot()
        context_documents: tuple[RawFetch, RawFetch] = ()
        captures: list[_FrontendCapture] = []
        request_metadata: dict[int, _FrontendRequest] = {}
        ignored_requests: set[int] = set()
        pending_tasks: set[asyncio.Task[None]] = set()
        stop: _FrontendStop | None = None
        request_sequence = 0
        stop_event = asyncio.Event()

        def set_stop(
            *,
            status: int,
            path: str,
            classification: str,
            content_type: str | None = None,
        ) -> None:
            nonlocal stop
            if stop is None:
                stop = _FrontendStop(
                    status=status,
                    path=path,
                    classification=classification,
                    content_type=content_type,
                )
                stop_event.set()

        def on_request(request: Any) -> None:
            nonlocal request_sequence
            parsed = urlsplit(str(request.url))
            route = _catalog_route(parsed.path, retailer_id=retailer_id)
            if parsed.hostname != _EXPECTED_HOST or route is None:
                return
            try:
                _safe_response_url(
                    request.url,
                    expected_path_prefix=(
                        f"/stores/{retailer_id}/api/webproductpagews/v6/"
                    ),
                )
            except ValueError:
                set_stop(
                    status=0,
                    path=parsed.path,
                    classification="frontend_request_origin_error",
                )
                return
            request_sequence += 1
            try:
                metadata = _frontend_request(
                    request,
                    sequence=request_sequence,
                    retailer_id=retailer_id,
                    category_id=category_id,
                )
            except IcaOnlineSchemaError:
                set_stop(
                    status=0,
                    path=parsed.path,
                    classification="frontend_request_schema_error",
                )
                return
            if metadata is None:
                ignored_requests.add(id(request))
            else:
                request_metadata[id(request)] = metadata

        async def capture_response(response: Any) -> None:
            parsed = urlsplit(str(response.url))
            route = _catalog_route(parsed.path, retailer_id=retailer_id)
            if parsed.hostname != _EXPECTED_HOST or route is None:
                return
            try:
                _safe_response_url(
                    response.url,
                    expected_path_prefix=(
                        f"/stores/{retailer_id}/api/webproductpagews/v6/"
                    ),
                )
            except ValueError:
                set_stop(
                    status=0,
                    path=parsed.path,
                    classification="frontend_response_origin_error",
                )
                return
            try:
                content_type = str(
                    await response.header_value("content-type") or ""
                ).split(";", 1)[0].strip().casefold()
                status = int(response.status)
            except (AttributeError, TypeError, ValueError):
                set_stop(
                    status=0,
                    path=parsed.path,
                    classification="frontend_response_metadata_error",
                )
                return
            self._observe(status)
            if status in _FRONTEND_STOP_STATUSES or content_type != "application/json":
                if status < 400:
                    self._http_error_count += 1
                set_stop(
                    status=status,
                    path=parsed.path,
                    classification=("rate_limit" if status == 429 else "access_challenge"),
                    content_type=content_type or None,
                )
                return
            if status != 200:
                set_stop(
                    status=status,
                    path=parsed.path,
                    classification="frontend_http_error",
                    content_type=content_type or None,
                )
                return
            request_key = id(response.request)
            if request_key in ignored_requests:
                return
            metadata = request_metadata.get(request_key)
            if metadata is None:
                set_stop(
                    status=status,
                    path=parsed.path,
                    classification="frontend_request_lineage_missing",
                    content_type=content_type or None,
                )
                return
            try:
                decoded = await response.json()
            except (AttributeError, json.JSONDecodeError, TypeError, ValueError):
                set_stop(
                    status=status,
                    path=parsed.path,
                    classification="invalid_json",
                    content_type=content_type or None,
                )
                return
            if not isinstance(decoded, dict) or _challenge_marker(
                json.dumps(decoded, ensure_ascii=False, separators=(",", ":"))
            ):
                set_stop(
                    status=status,
                    path=parsed.path,
                    classification="access_challenge",
                    content_type=content_type or None,
                )
                return
            try:
                if metadata.kind == "page":
                    IcaProductPage.from_payload(decoded, category_id=category_id)
                else:
                    IcaBatchResult.from_payload(
                        decoded,
                        requested_product_ids=metadata.requested_product_ids,
                    )
            except IcaOnlineSchemaError:
                set_stop(
                    status=status,
                    path=parsed.path,
                    classification="frontend_response_schema_error",
                    content_type=content_type or None,
                )
                return
            captures.append(
                _FrontendCapture(
                    request=metadata,
                    status=status,
                    payload=decoded,
                    fetched_at=datetime.now(tz=UTC),
                )
            )

        def on_response(response: Any) -> None:
            task = asyncio.create_task(capture_response(response))
            pending_tasks.add(task)

        async def drain_responses() -> None:
            while pending_tasks:
                current = tuple(pending_tasks)
                pending_tasks.difference_update(current)
                results = await asyncio.gather(*current, return_exceptions=True)
                if any(isinstance(result, BaseException) for result in results):
                    set_stop(
                        status=0,
                        path=(
                            f"/stores/{retailer_id}/api/webproductpagews/v6/"
                            "product-pages"
                        ),
                        classification="frontend_response_capture_error",
                    )

        async def wait_or_stop(page: Any) -> None:
            timer = asyncio.create_task(page.wait_for_timeout(self.frontend_settle_ms))
            stopper = asyncio.create_task(stop_event.wait())
            done, pending = await asyncio.wait(
                {timer, stopper},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                await task

        manager = (
            self._playwright_factory()
            if self._playwright_factory is not None
            else self._default_playwright_factory()
        )
        playwright: Any | None = None
        browser: Any | None = None
        context: Any | None = None
        page: Any | None = None
        last_reconciliation_error: Exception | None = None
        try:
            playwright = await manager.start()
            # One fixed mode per run. A challenge never triggers a retry in a
            # different mode, browser/channel or modified context.
            browser = await playwright.chromium.launch(headless=self.frontend_headless)
            context = await browser.new_context()
            page = await context.new_page()
            page.on("request", on_request)
            page.on("response", on_response)
            url = f"{self.base_url}{ui_path}?source=navigation"
            navigation = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.navigation_timeout_ms,
            )
            navigation_status = int(navigation.status) if navigation is not None else 0
            self._observe(navigation_status)
            safe_ui_url = _safe_category_ui_url(
                str(page.url),
                retailer_id=retailer_id,
                category_id=category_id,
            )
            navigation_content_type = (
                str(await navigation.header_value("content-type") or "")
                .split(";", 1)[0]
                .strip()
                .casefold()
                if navigation is not None
                else None
            )
            visible = await page.locator("body").inner_text(
                timeout=self.navigation_timeout_ms
            )
            if (
                navigation is None
                or navigation_status in _FRONTEND_STOP_STATUSES
                or navigation_status >= 400
                or _challenge_marker(visible)
            ):
                set_stop(
                    status=navigation_status,
                    path=urlsplit(safe_ui_url).path,
                    classification="access_challenge",
                    content_type=navigation_content_type,
                )
            if stop is None:
                html = await page.content()
                if _challenge_marker(html):
                    set_stop(
                        status=navigation_status,
                        path=urlsplit(safe_ui_url).path,
                        classification="access_challenge",
                        content_type=navigation_content_type,
                    )
                else:
                    context_payload = sanitized_context_payload(
                        html,
                        expected_retailer_region_id=retailer_id,
                        expected_region_id=region_id,
                    )
                    category_payload = sanitized_category_tree_payload(
                        html,
                        expected_retailer_region_id=retailer_id,
                        expected_region_id=region_id,
                    )
                    fetched_at = datetime.now(tz=UTC)
                    common = {
                        "chain": Chain.ICA,
                        "store_external_id": region_id,
                        "method": "GET",
                        "url": safe_ui_url,
                        "query": {"retailer_region_id": retailer_id},
                        "fetched_at": fetched_at,
                        "http_status": navigation_status,
                        "connector_version": self.connector_version,
                    }
                    context_documents = (
                        RawFetch(
                            **common,
                            kind=ICA_STORE_CONTEXT_KIND,
                            content_type=(
                                "application/json; profile=sanitized-ica-store-context-v1"
                            ),
                            payload=context_payload,
                        ),
                        RawFetch(
                            **common,
                            kind=ICA_CATEGORY_TREE_KIND,
                            content_type=(
                                "application/json; profile=sanitized-ica-category-tree-v1"
                            ),
                            payload=category_payload,
                        ),
                    )

            for scroll_index in range(self.frontend_max_scrolls + 1):
                await wait_or_stop(page)
                await drain_responses()
                if stop is not None:
                    break
                try:
                    return _frontend_category_batch(
                        context_documents=context_documents,
                        captures=captures,
                        region_id=region_id,
                        retailer_id=retailer_id,
                        category_id=category_id,
                        transport=self._metrics_since(before),
                        connector_version=self.connector_version,
                    )
                except IcaOnlineSchemaError as exc:
                    last_reconciliation_error = exc
                if scroll_index >= self.frontend_max_scrolls:
                    break
                await page.mouse.wheel(0, self.frontend_scroll_pixels)
                visible = await page.locator("body").inner_text(
                    timeout=self.navigation_timeout_ms
                )
                if _challenge_marker(visible):
                    set_stop(
                        status=0,
                        path=urlsplit(safe_ui_url).path,
                        classification="access_challenge",
                    )
                    break
            if stop is None:
                if last_reconciliation_error is not None:
                    # Preserve the exact fail-closed reason. In particular, a
                    # conflicting repeated batch must never be flattened into
                    # a generic timeout/incompleteness diagnostic.
                    raise last_reconciliation_error
                raise IcaOnlineSchemaError(
                    "ICA frontend category did not reconcile within bounded scrolling"
                )
            diagnostic = self._diagnostic_raw_from_browser(
                method="GET",
                url=f"{self.base_url}{stop.path}",
                kind=ICA_PRODUCT_PAGE_KIND,
                region_id=region_id,
                logical_query={
                    "category_id": category_id,
                    "frontend_observed": True,
                },
                page_number=None,
                status=stop.status,
                classification=stop.classification,
                observed_content_type=stop.content_type,
            )
            if stop.classification == "rate_limit":
                error_type = IcaOnlineRateLimitStop
            elif stop.classification == "access_challenge":
                error_type = IcaOnlineAccessChallenge
            else:
                error_type = IcaOnlineHttpError
            raise error_type("ICA frontend observation stopped", diagnostic)
        except Exception as exc:
            partial_documents = [*context_documents]
            partial_documents.extend(
                _partial_frontend_documents(
                    captures,
                    region_id=region_id,
                    retailer_id=retailer_id,
                    category_id=category_id,
                    connector_version=self.connector_version,
                )
            )
            if isinstance(exc, IcaOnlineHttpError) and exc.raw not in partial_documents:
                partial_documents.append(exc.raw)
            raise ConnectorFetchError(
                "ICA frontend-observed category proof stopped",
                partial_batch=RawBatch(
                    chain=Chain.ICA,
                    documents=tuple(partial_documents),
                    transport=self._metrics_since(before),
                ),
            ) from exc
        finally:
            # A failed response task must never prevent destruction of the
            # anonymous context.  Browser state remains memory-only and is
            # discarded even if task draining or an individual close fails.
            with suppress(Exception):
                await drain_responses()
            if page is not None:
                with suppress(Exception):
                    await page.close()
            if context is not None:
                with suppress(Exception):
                    await context.close()
            if browser is not None:
                with suppress(Exception):
                    await browser.close()
            if playwright is not None:
                with suppress(Exception):
                    await playwright.stop()

    async def _json_request(
        self,
        method: Literal["GET", "PUT"],
        path: str,
        *,
        kind: str,
        region_id: str,
        params: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        logical_query: Mapping[str, object] | None = None,
        json_body: object | None = None,
        page_number: int | None = None,
    ) -> tuple[RawFetch, dict[str, Any]]:
        del (
            method,
            path,
            kind,
            region_id,
            params,
            logical_query,
            json_body,
            page_number,
        )
        raise IcaOnlineSourcePolicyError(
            "ICA browser transport may only observe requests issued by ICA's frontend runtime"
        )

    async def fetch_category_proof(
        self,
        region_id: str,
        category_id: str,
    ) -> RawBatch:
        """Observe and reconcile one allowlisted frontend-owned category flow."""

        return await self.observe_category_frontend(region_id, category_id)

    async def fetch_search(
        self,
        region_id: str,
        query: str,
        *,
        decorate_one_batch: bool = True,
    ) -> RawBatch:
        try:
            return await super().fetch_search(
                region_id,
                query,
                decorate_one_batch=decorate_one_batch,
            )
        finally:
            await self._discard_browser()

    async def fetch_catalog(self, region_id: str) -> RawBatch:
        try:
            return await super().fetch_catalog(region_id)
        finally:
            await self._discard_browser()

    async def aclose(self) -> None:
        await self._discard_browser()
        self._client.cookies.clear()
        await self._inert_client.aclose()


__all__ = ["IcaOnlineBrowserTransport", "reconcile_category_proof"]
