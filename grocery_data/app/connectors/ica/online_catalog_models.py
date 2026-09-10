from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from hashlib import sha256
from math import isfinite
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.connectors.ica.models import IcaSchemaError, initial_data_from_html

ICA_STORE_ACTIVATION_KIND = "ica_store_activation"
ICA_STORE_CONTEXT_KIND = "ica_store_context"
ICA_SEARCH_KIND = "ica_search"
ICA_CATEGORY_TREE_KIND = "ica_category_tree"
ICA_PRODUCT_PAGE_KIND = "ica_product_page"
ICA_PRODUCT_BATCH_KIND = "ica_product_batch"
ICA_PROMOTION_RESOLUTION_KIND = "ica_promotion_resolution"
ICA_STORE_MAPPING_KIND = "ica_store_mapping"

_CONTEXT_SCHEMA = "ica-online-context-v1"
_CATEGORY_TREE_SCHEMA = "ica-online-category-tree-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class IcaOnlineSchemaError(IcaSchemaError):
    """The modern ICA online-catalog contract cannot be proved from this payload."""


def _json_object(payload: object, *, label: str) -> dict[str, Any]:
    if isinstance(payload, bytes | bytearray):
        try:
            payload = json.loads(bytes(payload))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IcaOnlineSchemaError(f"{label} is not valid UTF-8 JSON") from exc
    elif isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise IcaOnlineSchemaError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IcaOnlineSchemaError(f"{label} must be an object")
    return payload


def _canonical_uuid(value: object, *, label: str) -> str:
    if isinstance(value, bool) or value is None:
        raise IcaOnlineSchemaError(f"{label} must be a UUID")
    text = str(value).strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as exc:
        raise IcaOnlineSchemaError(f"{label} must be a UUID") from exc
    canonical = str(parsed)
    if text.casefold() != canonical:
        raise IcaOnlineSchemaError(f"{label} must use canonical UUID form")
    return canonical


def _non_empty_string(value: object, *, label: str) -> str:
    if isinstance(value, bool) or value is None:
        raise IcaOnlineSchemaError(f"{label} must be a non-empty string")
    text = str(value).strip()
    if not text:
        raise IcaOnlineSchemaError(f"{label} must be a non-empty string")
    return text


def _json_safe(value: object) -> object:
    """Return a stable JSON value or fail instead of stringifying an unknown object."""

    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise IcaOnlineSchemaError("ICA product semantics contain a non-finite number")
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    raise IcaOnlineSchemaError("ICA product semantics contain a non-JSON value")


_PURCHASE_SEMANTIC_FIELDS = (
    "productId",
    "retailerProductId",
    "type",
    "name",
    "brand",
    "countryOfOrigin",
    "available",
    "isInCurrentCatalog",
    "packSizeDescription",
    "price",
    "unitPrice",
    "featuredProductCampaign",
    "campaign",
    "campaigns",
    "promotion",
    "promotions",
)


def purchase_semantic_fingerprint(row: Mapping[str, Any]) -> str:
    """Hash identity and purchasing semantics, excluding category/image placement.

    Cross-category presentation is allowed to differ. Price, package,
    availability and unresolved campaign evidence are deliberately included so
    a duplicate can never hide an economically meaningful conflict.
    """

    product_id = _canonical_uuid(row.get("productId"), label="ICA productId")
    projection = {
        field: _json_safe(row[field])
        for field in _PURCHASE_SEMANTIC_FIELDS
        if field in row
    }
    projection["productId"] = product_id
    canonical = json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _initial_data(payload: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    try:
        return initial_data_from_html(raw)
    except (UnicodeDecodeError, IcaSchemaError) as exc:
        raise IcaOnlineSchemaError("ICA online context HTML/state changed") from exc


def _values_for_key(value: object, key: str) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for current_key, current_value in value.items():
            if current_key == key and current_value is not None:
                found.add(str(current_value).strip())
            found.update(_values_for_key(current_value, key))
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            found.update(_values_for_key(item, key))
    return {item for item in found if item}


def _verified_context_projection(
    data: Mapping[str, Any],
    *,
    expected_retailer_region_id: str,
    expected_region_id: str,
) -> dict[str, str]:
    expected_retailer = _non_empty_string(
        expected_retailer_region_id,
        label="expected retailerRegionId",
    )
    expected_region = _canonical_uuid(expected_region_id, label="expected regionId")
    retailer_values = _values_for_key(data, "retailerRegionId")
    region_values = _values_for_key(data, "regionId")
    if retailer_values != {expected_retailer}:
        raise IcaOnlineSchemaError(
            "ICA context retailerRegionId readback differs from the requested context"
        )
    if region_values != {expected_region}:
        raise IcaOnlineSchemaError("ICA context regionId readback differs from the request")
    return {
        "schema": _CONTEXT_SCHEMA,
        "retailerRegionId": expected_retailer,
        "regionId": expected_region,
    }


def sanitized_context_payload(
    html: bytes | str | Mapping[str, Any],
    expected_retailer_region_id: str,
    expected_region_id: str,
) -> bytes:
    """Project anonymous context readback to two verified public identities.

    Arbitrary SSR state, cookies, tracking values and session material never
    enter the returned replay payload.
    """

    projection = _verified_context_projection(
        _initial_data(html),
        expected_retailer_region_id=expected_retailer_region_id,
        expected_region_id=expected_region_id,
    )
    return json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class IcaCategoryNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    category_id: str
    name: str = Field(min_length=1)
    product_count: int | None = Field(default=None, ge=0)
    retailer_category_id: str | None = None
    parent_category_id: str | None = None
    child_categories: tuple[IcaCategoryNode, ...] = ()

    @property
    def terminal(self) -> bool:
        return not self.child_categories


def _category_node(
    payload: object,
    *,
    parent_category_id: str | None,
) -> IcaCategoryNode:
    if not isinstance(payload, Mapping):
        raise IcaOnlineSchemaError("ICA category node must be an object")
    category_id = _canonical_uuid(
        payload.get("categoryId", payload.get("id")),
        label="ICA categoryId",
    )
    name = " ".join(_non_empty_string(payload.get("name"), label="ICA category name").split())
    raw_count = payload.get("productCount")
    if raw_count is not None and (isinstance(raw_count, bool) or not isinstance(raw_count, int)):
        raise IcaOnlineSchemaError("ICA category productCount must be an integer")
    if isinstance(raw_count, int) and raw_count < 0:
        raise IcaOnlineSchemaError("ICA category productCount must be non-negative")
    raw_retailer_id = payload.get("retailerCategoryId", payload.get("retailerId"))
    retailer_id = (
        _non_empty_string(raw_retailer_id, label="ICA retailerCategoryId")
        if raw_retailer_id is not None
        else None
    )
    raw_children = payload.get("childCategories", payload.get("children", ()))
    if raw_children is None:
        raw_children = ()
    if not isinstance(raw_children, Sequence) or isinstance(
        raw_children, str | bytes | bytearray
    ):
        raise IcaOnlineSchemaError("ICA childCategories must be a list")
    children = tuple(
        _category_node(child, parent_category_id=category_id) for child in raw_children
    )
    return IcaCategoryNode(
        category_id=category_id,
        name=name,
        product_count=raw_count,
        retailer_category_id=retailer_id,
        parent_category_id=parent_category_id,
        child_categories=children,
    )


class IcaCategoryTree(BaseModel):
    """Allowlisted ICA navigation tree used as the catalog partition proof."""

    model_config = ConfigDict(frozen=True)

    nodes: tuple[IcaCategoryNode, ...] = Field(min_length=1)

    @classmethod
    def from_payload(cls, payload: object) -> IcaCategoryTree:
        root = _json_object(payload, label="ICA category-tree payload")
        additional = root.get("additionalPageInfo")
        nested = additional.get("categories") if isinstance(additional, Mapping) else None
        raw_nodes = nested if nested is not None else root.get("categories")
        if not isinstance(raw_nodes, Sequence) or isinstance(
            raw_nodes, str | bytes | bytearray
        ):
            raise IcaOnlineSchemaError("ICA category-tree payload lacks categories")
        nodes = tuple(_category_node(node, parent_category_id=None) for node in raw_nodes)
        if not nodes:
            raise IcaOnlineSchemaError("ICA category tree is empty")
        tree = cls(nodes=nodes)
        identities: dict[str, IcaCategoryNode] = {}
        for node in tree.all_nodes:
            if node.category_id in identities:
                raise IcaOnlineSchemaError("ICA category tree repeats a categoryId")
            identities[node.category_id] = node
        return tree

    @property
    def all_nodes(self) -> tuple[IcaCategoryNode, ...]:
        def walk(node: IcaCategoryNode) -> tuple[IcaCategoryNode, ...]:
            return (node, *(nested for child in node.child_categories for nested in walk(child)))

        return tuple(nested for root in self.nodes for nested in walk(root))

    @property
    def terminal_nodes(self) -> tuple[IcaCategoryNode, ...]:
        return tuple(node for node in self.all_nodes if node.terminal)

    @property
    def node_count(self) -> int:
        return len(self.all_nodes)

    @property
    def terminal_count(self) -> int:
        return len(self.terminal_nodes)


def _category_projection(node: IcaCategoryNode) -> dict[str, object]:
    return {
        "categoryId": node.category_id,
        "name": node.name,
        "productCount": node.product_count,
        "retailerCategoryId": node.retailer_category_id,
        "childCategories": [_category_projection(child) for child in node.child_categories],
    }


def _category_candidates(value: object) -> tuple[IcaCategoryTree, ...]:
    candidates: list[IcaCategoryTree] = []
    if isinstance(value, Mapping):
        if "categories" in value:
            try:
                candidates.append(IcaCategoryTree.from_payload({"categories": value["categories"]}))
            except IcaOnlineSchemaError:
                pass
        for nested in value.values():
            candidates.extend(_category_candidates(nested))
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for nested in value:
            candidates.extend(_category_candidates(nested))
    return tuple(candidates)


def sanitized_category_tree_payload(
    html: bytes | str | Mapping[str, Any],
    expected_retailer_region_id: str,
    expected_region_id: str,
) -> bytes:
    """Extract the largest valid category tree and discard all other SSR state."""

    data = _initial_data(html)
    context = _verified_context_projection(
        data,
        expected_retailer_region_id=expected_retailer_region_id,
        expected_region_id=expected_region_id,
    )
    candidates = _category_candidates(data)
    if not candidates:
        raise IcaOnlineSchemaError("ICA context state contains no valid category tree")
    largest_count = max(candidate.node_count for candidate in candidates)
    largest = [candidate for candidate in candidates if candidate.node_count == largest_count]
    projections = {
        json.dumps(
            [_category_projection(node) for node in tree.nodes],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for tree in largest
    }
    if len(projections) != 1:
        raise IcaOnlineSchemaError("ICA context state has conflicting full category trees")
    categories = json.loads(next(iter(projections)))
    payload = {
        "schema": _CATEGORY_TREE_SCHEMA,
        "retailerRegionId": context["retailerRegionId"],
        "regionId": context["regionId"],
        "categories": categories,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class IcaDuplicateMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    exact_duplicates_removed: int = Field(default=0, ge=0)
    placement_overlaps: int = Field(default=0, ge=0)
    pagination_overlaps: int = Field(default=0, ge=0)
    cross_category_overlaps: int = Field(default=0, ge=0)
    conflicting_duplicates: int = Field(default=0, ge=0)

    @property
    def exact_duplicates(self) -> int:
        """Compatibility name used by collection metrics."""

        return self.exact_duplicates_removed

    @property
    def duplicate_products(self) -> int:
        return (
            self.exact_duplicates_removed
            + self.placement_overlaps
            + self.pagination_overlaps
            + self.cross_category_overlaps
        )


class IcaProductGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    decorated_products: tuple[dict[str, Any], ...] = ()
    other_product_ids: tuple[str, ...] = ()


def _groups(payload: Mapping[str, Any]) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    raw_groups = payload.get("productGroups")
    if isinstance(raw_groups, Mapping):
        groups: list[tuple[str, Mapping[str, Any]]] = []
        for name, group in raw_groups.items():
            if not isinstance(group, Mapping):
                raise IcaOnlineSchemaError("ICA productGroups value must be an object")
            groups.append((str(name), group))
        return tuple(groups)
    if isinstance(raw_groups, Sequence) and not isinstance(
        raw_groups, str | bytes | bytearray
    ):
        groups = []
        for index, group in enumerate(raw_groups):
            if not isinstance(group, Mapping):
                raise IcaOnlineSchemaError("ICA productGroups row must be an object")
            label = next(
                (
                    str(group[field]).strip()
                    for field in ("groupType", "type", "name", "id")
                    if group.get(field) is not None and str(group[field]).strip()
                ),
                f"group-{index}",
            )
            groups.append((label, group))
        return tuple(groups)
    raise IcaOnlineSchemaError("ICA product response lacks productGroups")


def _optional_token(metadata: Mapping[str, Any], name: str) -> str | None:
    value = metadata.get(name)
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not value.strip():
        raise IcaOnlineSchemaError(f"ICA {name} must be a non-empty string")
    return value.strip()


def _page_partition_id(value: object) -> str:
    text = _non_empty_string(value, label="ICA product-page partition")
    if text.startswith("search:"):
        if not text.removeprefix("search:").strip():
            raise IcaOnlineSchemaError("ICA search partition lacks query identity")
        return text
    return _canonical_uuid(text, label="ICA requested categoryId")


def _declared_product_count(
    payload: Mapping[str, Any],
    *,
    category_id: str,
) -> int | None:
    candidates: list[object] = []
    additional = payload.get("additionalPageInfo")
    metadata = additional.get("metadata") if isinstance(additional, Mapping) else None
    current_category = (
        additional.get("currentCategory") if isinstance(additional, Mapping) else None
    )
    if isinstance(current_category, Mapping) and not category_id.startswith("search:"):
        current_category_id = _canonical_uuid(
            current_category.get("categoryId", current_category.get("id")),
            label="ICA currentCategory.categoryId",
        )
        if current_category_id != category_id:
            raise IcaOnlineSchemaError("ICA currentCategory differs from requested categoryId")
    for source in (payload, additional, metadata, current_category):
        if not isinstance(source, Mapping):
            continue
        for field in (
            "productCount",
            "totalProductCount",
            "totalProducts",
            "totalNumberOfProducts",
        ):
            if source.get(field) is not None:
                candidates.append(source[field])
    if not category_id.startswith("search:"):
        try:
            response_tree = IcaCategoryTree.from_payload(payload)
        except IcaOnlineSchemaError:
            response_tree = None
        if response_tree is not None:
            matching_nodes = [
                node for node in response_tree.all_nodes if node.category_id == category_id
            ]
            if len(matching_nodes) > 1:
                raise IcaOnlineSchemaError("ICA product page repeats requested category metadata")
            if matching_nodes and matching_nodes[0].product_count is not None:
                candidates.append(matching_nodes[0].product_count)
    if not candidates:
        return None
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in candidates):
        raise IcaOnlineSchemaError("ICA declared product count must be non-negative integer")
    counts = {int(value) for value in candidates}
    if len(counts) != 1:
        raise IcaOnlineSchemaError("ICA declared product counts conflict")
    return next(iter(counts))


class IcaProductPage(BaseModel):
    """One reconciled product-pages response before batch decoration."""

    model_config = ConfigDict(frozen=True)

    category_id: str
    groups: tuple[IcaProductGroup, ...]
    decorated_products: tuple[dict[str, Any], ...]
    other_product_ids: tuple[str, ...]
    ordered_product_ids: tuple[str, ...]
    missed_promotions: tuple[dict[str, Any], ...] = ()
    declared_product_count: int | None = Field(default=None, ge=0)
    next_page_token: str | None = None
    next_page_token_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    terminal: bool
    raw_product_rows: int = Field(ge=0)
    duplicate_metrics: IcaDuplicateMetrics = Field(default_factory=IcaDuplicateMetrics)

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        category_id: str,
    ) -> IcaProductPage:
        root = _json_object(payload, label="ICA product page")
        canonical_category = _page_partition_id(category_id)
        additional = root.get("additionalPageInfo")
        if not isinstance(additional, Mapping):
            raise IcaOnlineSchemaError("ICA product page lacks additionalPageInfo")
        metadata = additional.get("metadata")
        if not isinstance(metadata, Mapping):
            raise IcaOnlineSchemaError("ICA product page lacks metadata")
        live_token = _optional_token(metadata, "nextPageToken")
        persisted_hash = _optional_token(metadata, "nextPageTokenHash")
        if live_token is not None and persisted_hash is not None:
            raise IcaOnlineSchemaError("ICA page contains both live and persisted continuation")
        if persisted_hash is not None and _SHA256.fullmatch(persisted_hash) is None:
            raise IcaOnlineSchemaError("ICA nextPageTokenHash is not SHA-256")
        terminal_value = metadata.get("terminal")
        if terminal_value is not None and not isinstance(terminal_value, bool):
            raise IcaOnlineSchemaError("ICA continuation terminal flag must be boolean")
        has_continuation = live_token is not None or persisted_hash is not None
        if terminal_value is True and has_continuation:
            raise IcaOnlineSchemaError("ICA terminal page cannot have a continuation token")
        terminal = not has_continuation if terminal_value is None else terminal_value
        if terminal is False and not has_continuation:
            raise IcaOnlineSchemaError("ICA non-terminal page lacks continuation evidence")
        token_hash = sha256(live_token.encode()).hexdigest() if live_token else persisted_hash

        declared_product_count = _declared_product_count(
            root,
            category_id=canonical_category,
        )
        missed_contract = root.get("missedPromotions")
        missing_contract = root.get("missingPromotions")
        if (
            missed_contract is not None
            and missing_contract is not None
            and missed_contract != missing_contract
        ):
            raise IcaOnlineSchemaError(
                "ICA page has conflicting missedPromotions/missingPromotions"
            )
        raw_missed_promotions = (
            missed_contract
            if missed_contract is not None
            else missing_contract
            if missing_contract is not None
            else ()
        )
        if not isinstance(raw_missed_promotions, Sequence) or isinstance(
            raw_missed_promotions,
            str | bytes | bytearray,
        ):
            raise IcaOnlineSchemaError("ICA missed/missing promotions must be a list")
        if any(not isinstance(item, dict) for item in raw_missed_promotions):
            raise IcaOnlineSchemaError("ICA missed/missing promotion row must be an object")

        parsed_groups: list[IcaProductGroup] = []
        decorated_by_id: dict[str, dict[str, Any]] = {}
        decorated_fingerprints: dict[str, str] = {}
        ordered_ids: list[str] = []
        other_ids: list[str] = []
        seen_ordered: set[str] = set()
        seen_other: set[str] = set()
        exact_duplicates = 0
        placement_overlaps = 0
        raw_rows = 0
        for group_name, group in _groups(root):
            raw_decorated = group.get("decoratedProducts", ())
            raw_other = group.get("otherProductIds", ())
            if not isinstance(raw_decorated, Sequence) or isinstance(
                raw_decorated, str | bytes | bytearray
            ):
                raise IcaOnlineSchemaError("ICA decoratedProducts must be a list")
            if not isinstance(raw_other, Sequence) or isinstance(
                raw_other, str | bytes | bytearray
            ):
                raise IcaOnlineSchemaError("ICA otherProductIds must be a list")
            group_decorated: list[dict[str, Any]] = []
            group_other: list[str] = []
            for raw_row in raw_decorated:
                if not isinstance(raw_row, dict):
                    raise IcaOnlineSchemaError("ICA decorated product must be an object")
                row = dict(raw_row)
                product_id = _canonical_uuid(row.get("productId"), label="ICA productId")
                fingerprint = purchase_semantic_fingerprint(row)
                raw_rows += 1
                previous = decorated_fingerprints.get(product_id)
                if previous is not None:
                    if previous != fingerprint:
                        raise IcaOnlineSchemaError(
                            f"ICA product page has conflicting product {product_id}"
                        )
                    exact_duplicates += 1
                    continue
                decorated_fingerprints[product_id] = fingerprint
                decorated_by_id[product_id] = row
                group_decorated.append(row)
                if product_id not in seen_ordered:
                    seen_ordered.add(product_id)
                    ordered_ids.append(product_id)
                else:
                    placement_overlaps += 1
            for raw_id in raw_other:
                product_id = _canonical_uuid(raw_id, label="ICA otherProductId")
                raw_rows += 1
                if product_id in decorated_by_id:
                    placement_overlaps += 1
                    continue
                if product_id in seen_other:
                    placement_overlaps += 1
                    continue
                seen_other.add(product_id)
                group_other.append(product_id)
                other_ids.append(product_id)
                if product_id not in seen_ordered:
                    seen_ordered.add(product_id)
                    ordered_ids.append(product_id)
            parsed_groups.append(
                IcaProductGroup(
                    name=group_name,
                    decorated_products=tuple(group_decorated),
                    other_product_ids=tuple(group_other),
                )
            )
        # A later group may decorate an ID that an earlier group placed in
        # otherProductIds. Inline decoration is complete evidence and wins.
        unresolved = tuple(product_id for product_id in other_ids if product_id not in decorated_by_id)
        return cls(
            category_id=canonical_category,
            groups=tuple(parsed_groups),
            decorated_products=tuple(decorated_by_id.values()),
            other_product_ids=unresolved,
            ordered_product_ids=tuple(ordered_ids),
            missed_promotions=tuple(dict(item) for item in raw_missed_promotions),
            declared_product_count=declared_product_count,
            next_page_token=live_token,
            next_page_token_hash=token_hash,
            terminal=terminal,
            raw_product_rows=raw_rows,
            duplicate_metrics=IcaDuplicateMetrics(
                exact_duplicates_removed=exact_duplicates,
                placement_overlaps=placement_overlaps,
            ),
        )


class IcaBatchResult(BaseModel):
    """One exact /products decoration response and its request identity set."""

    model_config = ConfigDict(frozen=True)

    products: tuple[dict[str, Any], ...]
    product_ids: tuple[str, ...]
    requested_product_ids: tuple[str, ...]
    missed_promotions: tuple[dict[str, Any], ...]
    restricted_groups: dict[str, Any]
    duplicate_metrics: IcaDuplicateMetrics = Field(default_factory=IcaDuplicateMetrics)

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        requested_product_ids: Iterable[str] | None = None,
    ) -> IcaBatchResult:
        root = _json_object(payload, label="ICA product batch")
        raw_products = root.get("products")
        missed = root.get("missedPromotions")
        restricted = root.get("restrictedGroups")
        if not isinstance(raw_products, Sequence) or isinstance(
            raw_products, str | bytes | bytearray
        ):
            raise IcaOnlineSchemaError("ICA product batch lacks products")
        if not isinstance(missed, Sequence) or isinstance(missed, str | bytes | bytearray):
            raise IcaOnlineSchemaError("ICA product batch lacks missedPromotions")
        if any(not isinstance(item, dict) for item in missed):
            raise IcaOnlineSchemaError("ICA missedPromotions row must be an object")
        if not isinstance(restricted, dict):
            raise IcaOnlineSchemaError("ICA product batch lacks restrictedGroups")

        unique: dict[str, dict[str, Any]] = {}
        fingerprints: dict[str, str] = {}
        exact_duplicates = 0
        for raw_row in raw_products:
            if not isinstance(raw_row, dict):
                raise IcaOnlineSchemaError("ICA batch product must be an object")
            row = dict(raw_row)
            product_id = _canonical_uuid(row.get("productId"), label="ICA productId")
            fingerprint = purchase_semantic_fingerprint(row)
            if product_id in unique:
                if fingerprints[product_id] != fingerprint:
                    raise IcaOnlineSchemaError(
                        f"ICA batch has conflicting duplicate {product_id}"
                    )
                exact_duplicates += 1
                continue
            unique[product_id] = row
            fingerprints[product_id] = fingerprint

        returned_ids = tuple(unique)
        if requested_product_ids is None:
            requested = returned_ids
        else:
            requested = tuple(
                _canonical_uuid(value, label="ICA requested productId")
                for value in requested_product_ids
            )
            if len(requested) != len(set(requested)):
                raise IcaOnlineSchemaError("ICA product batch request repeats a productId")
            missing = tuple(product_id for product_id in requested if product_id not in unique)
            unexpected = tuple(product_id for product_id in returned_ids if product_id not in requested)
            if missing or unexpected:
                raise IcaOnlineSchemaError(
                    "ICA product batch does not reconcile: "
                    f"missing={list(missing)}, unexpected={list(unexpected)}"
                )
        return cls(
            products=tuple(unique.values()),
            product_ids=returned_ids,
            requested_product_ids=requested,
            missed_promotions=tuple(dict(item) for item in missed),
            restricted_groups=dict(restricted),
            duplicate_metrics=IcaDuplicateMetrics(
                exact_duplicates_removed=exact_duplicates,
            ),
        )


class IcaPageProducts(BaseModel):
    model_config = ConfigDict(frozen=True)

    products: tuple[dict[str, Any], ...]
    product_ids: tuple[str, ...]


def reconcile_page_batches(
    page: IcaProductPage,
    batches: Iterable[IcaBatchResult],
) -> IcaPageProducts:
    """Require batches to decorate every and only unresolved page product ID."""

    batch_rows: dict[str, dict[str, Any]] = {}
    requested: set[str] = set()
    for batch in batches:
        overlap = requested.intersection(batch.requested_product_ids)
        if overlap:
            raise IcaOnlineSchemaError(
                f"ICA page decoration requests overlap: {sorted(overlap)}"
            )
        requested.update(batch.requested_product_ids)
        batch_rows.update(zip(batch.product_ids, batch.products, strict=True))
    expected = set(page.other_product_ids)
    if requested != expected:
        raise IcaOnlineSchemaError(
            "ICA page batches differ from otherProductIds: "
            f"missing={sorted(expected - requested)}, unexpected={sorted(requested - expected)}"
        )
    inline = {
        _canonical_uuid(row.get("productId"), label="ICA productId"): row
        for row in page.decorated_products
    }
    resolved = {**inline, **batch_rows}
    if set(resolved) != set(page.ordered_product_ids):
        raise IcaOnlineSchemaError("ICA page product decoration is incomplete")
    return IcaPageProducts(
        products=tuple(resolved[product_id] for product_id in page.ordered_product_ids),
        product_ids=page.ordered_product_ids,
    )


def validate_continuation_chain(pages: Iterable[IcaProductPage]) -> None:
    """Validate token replacement/termination for pages already in request order."""

    ordered = tuple(pages)
    if not ordered:
        raise IcaOnlineSchemaError("ICA category traversal has no product pages")
    seen: set[str] = set()
    for page in ordered:
        token_hash = page.next_page_token_hash
        if token_hash is not None:
            if token_hash in seen:
                raise IcaOnlineSchemaError("ICA category traversal repeated a continuation token")
            seen.add(token_hash)
    for index, page in enumerate(ordered):
        if index < len(ordered) - 1 and page.terminal:
            raise IcaOnlineSchemaError("ICA category traversal continued after a terminal page")
        if index == len(ordered) - 1 and not page.terminal:
            raise IcaOnlineSchemaError("ICA category traversal stopped before terminal page")
