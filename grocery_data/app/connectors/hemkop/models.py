from __future__ import annotations

import json
import re
from math import ceil
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Hemköp is verified to use the same Axfood pagination arithmetic as Willys.
# A live 200-product category with page size 100 declared three pages and its
# final page returned the strict ``results: null`` sentinel. An empty list is
# deliberately rejected because it has not been observed for this contract.
_PROVEN_TERMINAL_RESULTS_SHAPE: str | None = "null"
_STORE_CONTEXT_TOKEN = re.compile(r"(?:^|:)salableOnlineInStore_string_mv:([^:]+)")


class HemkopSchemaError(ValueError):
    """The public Hemköp response no longer satisfies its observed contract."""


class HemkopCatalogPage(BaseModel):
    """One exactly reconciled page from Hemköp's public category source."""

    model_config = ConfigDict(frozen=True)

    results: tuple[dict[str, Any], ...]
    current_page: int
    number_of_pages: int
    page_size: int
    total_results: int


class HemkopCategoryNode(BaseModel):
    """The small, stable subset of the public Axfood category-tree shape."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    url: str = ""
    valid: bool = True
    children: list[HemkopCategoryNode] = Field(default_factory=list)

    def top_level_paths(self) -> tuple[str, ...]:
        """Return only the root's valid first-level source partitions.

        Hemköp's 20 observed first-level categories are the source's broad
        navigation partitions. They are not disjoint: documented identical
        cross-partition product repeats are classified during traversal. A
        within-partition repeat remains a hard failure unless the connector
        proves an exact semantic duplicate and records its removal. Traversing
        hundreds of descendant leaves would multiply this overlap unnecessarily.
        """

        paths: list[str] = []
        for child in self.children:
            path = child.url.strip("/")
            if child.valid and child.id.casefold() != "n00" and path:
                paths.append(path)
        if len(paths) != len(set(paths)):
            raise HemkopSchemaError("Hemköp category tree contains duplicate top-level paths")
        return tuple(sorted(paths))


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HemkopSchemaError(f"Hemköp {field} must be an explicit integer")
    return value


def _facet_store_contexts(payload: dict[str, Any]) -> frozenset[str]:
    """Read only the structured query values under public facet entries."""

    facets = payload.get("facets")
    if not isinstance(facets, list):
        raise HemkopSchemaError("Hemköp catalog page facets must be a list")
    store_ids: set[str] = set()
    for facet in facets:
        if not isinstance(facet, dict):
            raise HemkopSchemaError("Hemköp catalog facet must be an object")
        values = facet.get("values")
        if values is None:
            continue
        if not isinstance(values, list):
            raise HemkopSchemaError("Hemköp catalog facet values must be a list")
        for value in values:
            if not isinstance(value, dict):
                raise HemkopSchemaError("Hemköp catalog facet value must be an object")
            query = value.get("query")
            if not isinstance(query, dict):
                continue
            structured_query = query.get("query")
            if not isinstance(structured_query, dict):
                continue
            query_value = structured_query.get("value")
            if not isinstance(query_value, str):
                continue
            store_ids.update(_STORE_CONTEXT_TOKEN.findall(query_value))
    return frozenset(store_ids)


def validated_catalog_page(
    payload: object,
    *,
    requested_page: int | None = None,
    requested_size: int | None = None,
    expected_store_id: str | None = None,
    require_product_identity: bool = True,
) -> HemkopCatalogPage:
    """Fail closed unless one category page reconciles all pagination facts.

    The verified Axfood exact-multiple arithmetic is supported with only the
    reference protocol's strict terminal ``results: null`` sentinel. Every
    production/replay call also supplies an expected store identity, which is
    checked against the structured page-local assortment facet.
    """

    if not isinstance(payload, dict):
        raise HemkopSchemaError("Hemköp catalog page must be an object")
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        raise HemkopSchemaError("Hemköp catalog page pagination must be an object")
    current_page = _integer(pagination.get("currentPage"), "currentPage")
    number_of_pages = _integer(pagination.get("numberOfPages"), "numberOfPages")
    page_size = _integer(pagination.get("pageSize"), "pageSize")
    total_results = _integer(
        pagination.get("totalNumberOfResults"),
        "totalNumberOfResults",
    )
    if current_page < 0 or number_of_pages < 0 or page_size <= 0 or total_results < 0:
        raise HemkopSchemaError("Hemköp pagination bounds are invalid")
    if requested_page is not None and current_page != requested_page:
        raise HemkopSchemaError("Hemköp did not return the requested page")
    if requested_size is not None and page_size != requested_size:
        raise HemkopSchemaError("Hemköp did not return the requested page size")
    if expected_store_id is not None:
        expected_contexts = frozenset({str(expected_store_id).strip()})
        if not next(iter(expected_contexts)):
            raise ValueError("expected_store_id must be non-empty")
        actual_contexts = _facet_store_contexts(payload)
        if actual_contexts != expected_contexts:
            raise HemkopSchemaError(
                "Hemköp catalog page lacks the exact requested store facet context"
            )

    # The public Axfood storefront declares one extra terminal page when an
    # exact multiple fills the preceding page. Hemköp live evidence proves
    # this arithmetic (200 rows, size 100, 3 declared pages). Only the strict
    # Axfood/Willys null sentinel is accepted; [] is deliberately not.
    product_pages = ceil(total_results / page_size) if total_results else 0
    has_terminal_sentinel = total_results > 0 and total_results % page_size == 0
    expected_pages = product_pages + int(has_terminal_sentinel)
    if number_of_pages != expected_pages:
        raise HemkopSchemaError("Hemköp numberOfPages is inconsistent with totalNumberOfResults")
    if "results" not in payload:
        raise HemkopSchemaError("Hemköp catalog page results field is missing")
    raw_results = payload.get("results")
    if total_results == 0:
        if current_page != 0 or raw_results:
            raise HemkopSchemaError("Hemköp empty pagination is inconsistent")
    elif current_page >= number_of_pages:
        raise HemkopSchemaError("Hemköp currentPage exceeds numberOfPages")

    is_terminal_sentinel = (
        has_terminal_sentinel
        and current_page == number_of_pages - 1
        and current_page * page_size == total_results
    )
    if is_terminal_sentinel:
        if _PROVEN_TERMINAL_RESULTS_SHAPE is None:
            raise HemkopSchemaError(
                "Hemköp terminal page shape is unverified (null versus empty list)"
            )
        if _PROVEN_TERMINAL_RESULTS_SHAPE == "null" and raw_results is not None:
            raise HemkopSchemaError("Hemköp terminal page no longer uses proven null results")
        if _PROVEN_TERMINAL_RESULTS_SHAPE == "empty" and raw_results != []:
            raise HemkopSchemaError(
                "Hemköp terminal page no longer uses the proven empty results list"
            )
        raw_results = []
    elif not isinstance(raw_results, list):
        raise HemkopSchemaError("Hemköp catalog page results must be a list")

    expected_rows = min(page_size, max(total_results - current_page * page_size, 0))
    if len(raw_results) != expected_rows:
        raise HemkopSchemaError("Hemköp page row count is inconsistent with pagination metadata")

    results: list[dict[str, Any]] = []
    for index, row in enumerate(raw_results):
        if not isinstance(row, dict):
            raise HemkopSchemaError(f"Hemköp result {index} must be an object")
        if require_product_identity and not str(row.get("code") or "").strip():
            raise HemkopSchemaError(f"Hemköp result {index} lacks product identity")
        results.append(row)
    return HemkopCatalogPage(
        results=tuple(results),
        current_page=current_page,
        number_of_pages=number_of_pages,
        page_size=page_size,
        total_results=total_results,
    )


def top_level_category_paths(tree_fetch: bytes) -> tuple[str, ...]:
    try:
        payload = json.loads(tree_fetch)
    except (TypeError, ValueError) as exc:
        raise HemkopSchemaError("Hemköp category tree is not valid JSON") from exc
    try:
        tree = HemkopCategoryNode.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise HemkopSchemaError("Hemköp category tree shape changed") from exc
    return tree.top_level_paths()


def validated_store_context(payload: object, expected: str) -> bool:
    """Exact observed active store shapes; never infer a picking-base mapping.

    Missing flag retains the legacy contract. Explicit false is the only new
    value evidenced in the 2026-10-08 store/active responses. True may signal
    a different picking store and requires a separately reviewed binding.
    Null, numbers and strings are not boolean false. Do not recurse through
    arbitrary nested store IDs to authorize a price context.
    """
    if not isinstance(payload, dict):
        return False
    rows = [payload] if "storeId" in payload else [
        payload[key] for key in ("store", "pickingStore") if key in payload
    ]
    return bool(rows) and all(
        isinstance(row, dict) and str(row.get("storeId") or "") == expected
        and ("hasPickingBaseStore" not in row or row["hasPickingBaseStore"] is False)
        for row in rows
    )
