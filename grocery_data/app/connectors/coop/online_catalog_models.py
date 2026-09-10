from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from math import ceil
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.connectors.coop.models import CoopSchemaError
from grocery_data.app.domain import CatalogCompletion, SourceProduct

_VERIFIED_EMPTY_ROOT_SENTINEL_CODES = frozenset({"0001", "0002"})


class CoopOnlineDuplicateKind(StrEnum):
    """Closed duplicate classes used by the catalogue reconciliation gate."""

    EXACT_ROW_DUPLICATE = "exact_row_duplicate"
    PAGINATION_OVERLAP = "pagination_overlap"
    CROSS_CATEGORY_OVERLAP = "cross_category_overlap"
    CONFLICTING_DUPLICATE = "conflicting_duplicate"


class CoopOnlineCategoryNode(BaseModel):
    """Allowlisted part of Coop's public product-navigation tree."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    code: str = Field(min_length=1)
    # The live tree has two verified, nameless root sentinels. Keep the field a
    # string for every consumer and validate the sole empty-name exception at
    # the tree boundary, where root-vs-nested position is known.
    name: str = ""
    canonical_path: str | None = Field(default=None, alias="canonicalPath")
    url: str | None = None
    children: tuple[CoopOnlineCategoryNode, ...] = ()

    def terminal_nodes(self) -> tuple[CoopOnlineCategoryNode, ...]:
        if not self.children:
            return (self,)
        return tuple(node for child in self.children for node in child.terminal_nodes())


class CoopOnlineCategoryTree(BaseModel):
    """Validated root envelope returned by the anonymous category-tree route."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    nodes: tuple[CoopOnlineCategoryNode, ...] = Field(min_length=1)

    @staticmethod
    def _is_verified_empty_root_sentinel(node: CoopOnlineCategoryNode) -> bool:
        return (
            node.code in _VERIFIED_EMPTY_ROOT_SENTINEL_CODES
            and not node.name.strip()
            and node.canonical_path is None
            and node.url == "/varor/"
            and not node.children
        )

    @classmethod
    def _validate_category_node(
        cls,
        node: CoopOnlineCategoryNode,
        *,
        is_root: bool,
    ) -> None:
        reserved_sentinel_code = node.code in _VERIFIED_EMPTY_ROOT_SENTINEL_CODES
        exact_root_sentinel = is_root and cls._is_verified_empty_root_sentinel(node)
        if reserved_sentinel_code:
            if not exact_root_sentinel:
                raise CoopSchemaError(
                    "Coop online category-tree sentinel changed shape or nesting"
                )
            return
        if not node.name.strip():
            raise CoopSchemaError("Coop online category node has no name")
        for child in node.children:
            cls._validate_category_node(child, is_root=False)

    def _validate_node_identities(self) -> None:
        for root in self.nodes:
            self._validate_category_node(root, is_root=True)

    def terminal_rows(self) -> tuple[CoopOnlineCategoryNode, ...]:
        self._validate_node_identities()
        return tuple(
            node
            for root in self.nodes
            if not self._is_verified_empty_root_sentinel(root)
            for node in root.terminal_nodes()
        )

    @property
    def ignored_sentinel_rows(self) -> int:
        """Exact non-category roots excluded from product partitions."""

        self._validate_node_identities()
        return sum(self._is_verified_empty_root_sentinel(root) for root in self.nodes)

    @property
    def ignored_sentinel_codes(self) -> tuple[str, ...]:
        self._validate_node_identities()
        return tuple(
            root.code
            for root in self.nodes
            if self._is_verified_empty_root_sentinel(root)
        )

    def terminal_nodes(self) -> tuple[CoopOnlineCategoryNode, ...]:
        # The 2026-08-25 live tree contained one byte-semantic duplicate leaf
        # (Presentinslagning, code 334819). An identical navigation row is safe
        # to collapse; the same code with another name/path is an identity
        # conflict and remains a hard failure.
        unique: dict[str, CoopOnlineCategoryNode] = {}
        for node in self.terminal_rows():
            previous = unique.get(node.code)
            if previous is None:
                unique[node.code] = node
                continue
            if (
                previous.name != node.name
                or previous.canonical_path != node.canonical_path
                or previous.url != node.url
            ):
                raise CoopSchemaError(
                    "Coop online category tree has a conflicting terminal code"
                )
        if not unique:
            raise CoopSchemaError("Coop online category tree has no product categories")
        return tuple(unique.values())

    @property
    def duplicate_terminal_rows(self) -> int:
        return len(self.terminal_rows()) - len(self.terminal_nodes())

    @property
    def navigation_aliases(self) -> dict[str, tuple[str, ...]]:
        """URLs intentionally shared by distinct category identities."""

        by_url: dict[str, list[str]] = {}
        for node in self.terminal_nodes():
            if node.url:
                by_url.setdefault(node.url, []).append(node.code)
        return {
            url: tuple(codes)
            for url, codes in sorted(by_url.items())
            if len(codes) > 1
        }


class CoopOnlineResultsPage(BaseModel):
    """One exactly reconciled offset page from a Coop product endpoint."""

    model_config = ConfigDict(frozen=True)

    reported_count: int = Field(ge=0)
    skip: int = Field(ge=0)
    take: int = Field(gt=0)
    items: tuple[dict[str, Any], ...]
    query_used: str | None = None

    @property
    def expected_rows(self) -> int:
        return min(self.take, max(self.reported_count - self.skip, 0))

    @property
    def page_index(self) -> int:
        return self.skip // self.take

    @property
    def expected_pages(self) -> int:
        # A terminal category is queried once even when it currently contains
        # zero products. That empty first response is itself the completion
        # evidence for the partition.
        return max(1, ceil(self.reported_count / self.take))


class CoopOnlineDuplicateMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    exact_duplicates_removed: int = Field(default=0, ge=0)
    pagination_overlaps: int = Field(default=0, ge=0)
    cross_category_overlaps: int = Field(default=0, ge=0)
    conflicting_duplicates: int = Field(default=0, ge=0)

    @property
    def duplicate_products(self) -> int:
        return self.exact_duplicates_removed + self.cross_category_overlaps


class CoopOnlineCatalogReconciliation(BaseModel):
    """Parsed products plus the exact evidence used by the promotion gate."""

    model_config = ConfigDict(frozen=True)

    products: tuple[SourceProduct, ...]
    duplicate_metrics: CoopOnlineDuplicateMetrics
    completion: CatalogCompletion


def validated_category_tree(payload: object) -> CoopOnlineCategoryTree:
    """Validate only the stable category identity/navigation subset."""

    try:
        tree = CoopOnlineCategoryTree.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise CoopSchemaError("Coop online category-tree schema changed") from exc
    # Trigger duplicate-code validation before the tree can be used for a crawl.
    tree.terminal_nodes()
    return tree


def validated_results_page(
    payload: object,
    *,
    requested_skip: int,
    requested_take: int,
    expected_query: str | None = None,
) -> CoopOnlineResultsPage:
    """Fail closed unless result count, offset, page size and row count reconcile."""

    if isinstance(requested_skip, bool) or requested_skip < 0:
        raise ValueError("requested_skip must be a non-negative integer")
    if isinstance(requested_take, bool) or requested_take <= 0:
        raise ValueError("requested_take must be a positive integer")
    if not isinstance(payload, dict):
        raise CoopSchemaError("Coop online product response must be an object")
    results = payload.get("results")
    if not isinstance(results, dict):
        raise CoopSchemaError("Coop online product response lacks results")
    count = results.get("count")
    items = results.get("items")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise CoopSchemaError("Coop online results.count must be a non-negative integer")
    if not isinstance(items, list):
        raise CoopSchemaError("Coop online results.items must be a list")
    if any(not isinstance(item, dict) for item in items):
        raise CoopSchemaError("Coop online product page contains a non-object row")
    query_used_value = payload.get("queryUsed")
    query_used = str(query_used_value).strip() if query_used_value is not None else None
    if expected_query is not None and query_used != expected_query:
        raise CoopSchemaError("Coop online response queryUsed differs from the request")
    page = CoopOnlineResultsPage(
        reported_count=count,
        skip=requested_skip,
        take=requested_take,
        items=tuple(items),
        query_used=query_used or None,
    )
    if requested_skip % requested_take:
        raise CoopSchemaError("Coop online skip must align to the requested take")
    if len(page.items) != page.expected_rows:
        raise CoopSchemaError("Coop online page row count does not reconcile with results.count")
    for index, item in enumerate(page.items):
        if not str(item.get("id") or "").strip():
            raise CoopSchemaError(f"Coop online result {index} lacks stable id")
    return page


def flatten_terminal_categories(payload: object) -> tuple[CoopOnlineCategoryNode, ...]:
    """Convenience boundary for clients and offline replay."""

    return validated_category_tree(payload).terminal_nodes()


def iter_category_codes(nodes: Iterable[CoopOnlineCategoryNode]) -> tuple[str, ...]:
    codes = tuple(node.code for node in nodes)
    if len(codes) != len(set(codes)):
        raise CoopSchemaError("Coop online category sequence contains duplicate codes")
    return codes
