from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict

from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_CATEGORY_TREE_KIND,
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    IcaBatchResult,
    IcaCategoryNode,
    IcaCategoryTree,
    IcaDuplicateMetrics,
    IcaOnlineSchemaError,
    IcaProductPage,
    purchase_semantic_fingerprint,
    reconcile_page_batches,
    validate_continuation_chain,
)
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ParseFailure,
    PriceContextType,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SourceProduct,
    SourceStore,
)

_EXACT_PACKAGE = re.compile(
    r"^\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|mg|l|cl|dl|ml|st)\s*$",
    re.IGNORECASE,
)
_MULTIPACK = re.compile(
    r"^\s*(?P<count>\d+)\s*[x×]\s*(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>kg|g|mg|l|cl|dl|ml|st)\s*$",
    re.IGNORECASE,
)
_PACK_COUNT = re.compile(r"^\s*(?P<count>\d+)\s*[- ]?pack\s*$", re.IGNORECASE)
_UNIT_PRICE_TEXT = re.compile(
    r"^\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?:sek|kr)\s*/\s*"
    r"(?P<unit>kg|g|l|liter|lit|ml|st|styck)\s*$",
    re.IGNORECASE,
)
_GTIN_LENGTHS = frozenset({8, 12, 13, 14})
_COMPARISON_UNITS = {
    "kg": "kg",
    "kilogram": "kg",
    "g": "g",
    "gram": "g",
    "l": "l",
    "lit": "l",
    "liter": "l",
    "litre": "l",
    "ml": "ml",
    "milliliter": "ml",
    "st": "st",
    "styck": "st",
}


def _comparison_unit(value: Mapping[str, Any]) -> str | None:
    candidates = (
        value.get("unit"),
        value.get("unitName"),
        value.get("unitCode"),
        value.get("priceUnit"),
    )
    for raw_candidate in candidates:
        if isinstance(raw_candidate, Mapping):
            raw_candidate = (
                raw_candidate.get("unit")
                or raw_candidate.get("name")
                or raw_candidate.get("code")
            )
        normalized = str(raw_candidate or "").strip().casefold()
        if not normalized:
            continue
        direct = _COMPARISON_UNITS.get(normalized)
        if direct is not None:
            return direct
        suffix = normalized.rsplit(".", 1)[-1]
        if suffix.startswith("per_"):
            suffix = suffix.removeprefix("per_")
        elif suffix.startswith("per-"):
            suffix = suffix.removeprefix("per-")
        if suffix.startswith("per") and suffix not in _COMPARISON_UNITS:
            suffix = suffix.removeprefix("per").lstrip("_- ")
        resolved = _COMPARISON_UNITS.get(suffix)
        if resolved is not None:
            return resolved
    return None


class IcaOnlineCompletenessError(IcaOnlineSchemaError):
    """Saved partitions/batches cannot support a complete-catalog claim."""


class IcaOnlineCatalogReconciliation(BaseModel):
    model_config = ConfigDict(frozen=True)

    products: tuple[SourceProduct, ...]
    duplicate_metrics: IcaDuplicateMetrics
    completion: CatalogCompletion


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace("\u00a0", "").replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _valid_gtin(value: str) -> bool:
    if len(value) not in _GTIN_LENGTHS or not value.isascii() or not value.isdigit():
        return False
    body, supplied = value[:-1], int(value[-1])
    weighted = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(body))
    )
    return (10 - weighted % 10) % 10 == supplied


def _price(value: object, *, required: bool, label: str) -> tuple[Decimal | None, str | None]:
    if value is None and not required:
        return None, None
    if not isinstance(value, Mapping):
        raise IcaOnlineSchemaError(f"ICA {label} must be an object")
    amount = _decimal(value.get("amount"))
    currency_value = value.get("currency")
    currency = str(currency_value).strip().upper() if currency_value is not None else None
    if amount is None:
        if required:
            raise IcaOnlineSchemaError(f"ICA {label}.amount is missing or invalid")
        return None, currency
    if currency != "SEK":
        raise IcaOnlineSchemaError(f"ICA {label}.currency is not SEK")
    return amount, currency


def _comparison(value: object) -> tuple[Decimal | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, str):
        match = _UNIT_PRICE_TEXT.fullmatch(value)
        if match is None:
            return None, None
        amount = _decimal(match.group("amount"))
        unit = _COMPARISON_UNITS.get(match.group("unit").casefold())
        return (amount, unit) if amount is not None and unit is not None else (None, None)
    if not isinstance(value, Mapping):
        raise IcaOnlineSchemaError("ICA unitPrice must be an object or formatted string")
    amount_value: object = value.get("amount")
    currency_value: object = value.get("currency")
    nested_price = value.get("price")
    if isinstance(nested_price, Mapping):
        amount_value = nested_price.get("amount", amount_value)
        currency_value = nested_price.get("currency", currency_value)
    amount = _decimal(amount_value)
    if amount is None:
        return None, None
    currency = str(currency_value or "").strip().upper()
    if currency and currency != "SEK":
        raise IcaOnlineSchemaError("ICA unitPrice.currency is not SEK")
    unit = _comparison_unit(value)
    return (amount, unit) if unit is not None else (None, None)


def _normalized_quantity(amount: Decimal, unit: str) -> tuple[Decimal, str]:
    normalized = unit.casefold()
    conversions = {
        "kg": (Decimal(1000), "g"),
        "g": (Decimal(1), "g"),
        "mg": (Decimal("0.001"), "g"),
        "l": (Decimal(1000), "ml"),
        "cl": (Decimal(10), "ml"),
        "dl": (Decimal(100), "ml"),
        "ml": (Decimal(1), "ml"),
        "st": (Decimal(1), "st"),
    }
    factor, target = conversions[normalized]
    return amount * factor, target


def _package(value: object) -> tuple[Decimal | None, str | None, int | None]:
    text = " ".join(str(value or "").split())
    exact = _EXACT_PACKAGE.fullmatch(text)
    if exact:
        amount = _decimal(exact.group("amount"))
        if amount is not None:
            quantity, unit = _normalized_quantity(amount, exact.group("unit"))
            return quantity, unit, None
    multipack = _MULTIPACK.fullmatch(text)
    if multipack:
        count = int(multipack.group("count"))
        amount = _decimal(multipack.group("amount"))
        if amount is not None and count > 0:
            quantity, unit = _normalized_quantity(amount * count, multipack.group("unit"))
            return quantity, unit, count
    pack = _PACK_COUNT.fullmatch(text)
    if pack:
        count = int(pack.group("count"))
        return Decimal(count), "st", count
    return None, None, None


def _category_path(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        separators = ">" if ">" in value else "/" if "/" in value else None
        raw_items = value.split(separators) if separators else [value]
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        raw_items = list(value)
    else:
        return ()
    result: list[str] = []
    for item in raw_items:
        if isinstance(item, Mapping):
            item = item.get("name")
        name = " ".join(str(item or "").split())
        if name and name.casefold() not in {prior.casefold() for prior in result}:
            result.append(name)
    return tuple(result)


def _requested_product_ids(document: RawFetch) -> tuple[str, ...]:
    raw_value = document.query.get("requested_product_ids")
    if raw_value is None:
        raise IcaOnlineCompletenessError("ICA batch raw evidence lacks requested_product_ids")
    try:
        values = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise IcaOnlineCompletenessError(
            "ICA batch requested_product_ids is not a JSON array"
        ) from exc
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise IcaOnlineCompletenessError(
            "ICA batch requested_product_ids must be a JSON string array"
        )
    return tuple(values)


def _page_index(document: RawFetch) -> int:
    raw_value: object = document.query.get("page_index")
    if raw_value is None:
        raw_value = document.page_number
    if isinstance(raw_value, bool) or raw_value is None:
        raise IcaOnlineCompletenessError("ICA raw page lacks page_index")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise IcaOnlineCompletenessError("ICA raw page_index is not an integer") from exc
    if value < 0:
        raise IcaOnlineCompletenessError("ICA raw page_index must be non-negative")
    return value


class IcaOnlineCatalogParser:
    """Strict offline parser for ICA's current region-scoped online catalog."""

    parser_version = "ica-online-catalog-parser-v1"

    @staticmethod
    def _require_context(document: RawFetch, store: SourceStore) -> None:
        if store.chain is not Chain.ICA or document.chain is not Chain.ICA:
            raise IcaOnlineSchemaError("ICA online parser received another chain")
        if store.price_context_type not in {
            PriceContextType.ONLINE_STORE,
            PriceContextType.ONLINE_FULFILLMENT,
            PriceContextType.REGIONAL,
        }:
            raise IcaOnlineSchemaError("ICA online catalog requires an online price context")
        if document.store_external_id != store.external_id:
            raise IcaOnlineSchemaError("ICA region context identity differs from raw response")
        if document.http_status != 200:
            raise IcaOnlineSchemaError("ICA online response is not HTTP 200")

    @staticmethod
    def _payload(document: RawFetch) -> dict[str, Any]:
        try:
            payload = document.json_payload()
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IcaOnlineSchemaError("ICA online response is not JSON") from exc
        if not isinstance(payload, dict):
            raise IcaOnlineSchemaError("ICA online response root must be an object")
        return payload

    def parse_product(
        self,
        row: Mapping[str, Any],
        *,
        store: SourceStore,
        reference: str,
        fetched_at: datetime,
    ) -> SourceProduct:
        # Validation and canonicalisation are shared with duplicate handling.
        purchase_semantic_fingerprint(row)
        product_id = str(row.get("productId")).strip()
        retailer_product_id = row.get("retailerProductId")
        if isinstance(retailer_product_id, bool) or retailer_product_id is None:
            raise IcaOnlineSchemaError("ICA product lacks retailerProductId")
        retailer_id = str(retailer_product_id).strip()
        if not retailer_id:
            raise IcaOnlineSchemaError("ICA product lacks retailerProductId")
        name = " ".join(str(row.get("name") or "").split())
        if not name:
            raise IcaOnlineSchemaError("ICA product lacks name")
        available = row.get("available")
        current = row.get("isInCurrentCatalog")
        if not isinstance(available, bool):
            raise IcaOnlineSchemaError("ICA product available must be boolean")
        if not isinstance(current, bool):
            raise IcaOnlineSchemaError("ICA product isInCurrentCatalog must be boolean")
        basket_eligible = available and current
        base_price, currency = _price(
            row.get("price"),
            required=basket_eligible,
            label="price",
        )
        comparison_price, comparison_unit = _comparison(row.get("unitPrice"))
        package_text = " ".join(str(row.get("packSizeDescription") or "").split()) or None
        package_quantity, package_unit, pack_count = _package(package_text)

        explicit_gtins = {
            str(row[field]).strip()
            for field in ("gtin", "ean")
            if row.get(field) is not None and str(row[field]).strip()
        }
        gtin = next(iter(explicit_gtins)) if len(explicit_gtins) == 1 else None
        if gtin is not None and not _valid_gtin(gtin):
            gtin = None

        if not current:
            availability = "not_in_current_catalog"
        elif not available:
            availability = "unavailable"
        else:
            availability = "available"
        raw_campaign = row.get("featuredProductCampaign")
        return SourceProduct(
            chain=Chain.ICA,
            store_external_id=store.external_id,
            external_product_id=product_id,
            gtin=gtin,
            name=name,
            brand=" ".join(str(row.get("brand") or "").split()) or None,
            category_path=_category_path(row.get("categoryPath")),
            sale_price=base_price if basket_eligible else None,
            regular_price=base_price if basket_eligible else None,
            member_price=None,
            comparison_price=comparison_price if basket_eligible else None,
            comparison_unit=comparison_unit if basket_eligible else None,
            package_text=package_text,
            package_quantity=package_quantity,
            package_unit=package_unit,
            sale_unit="st",
            offers=(),
            availability=availability,
            basket_type="ST",
            raw_reference=reference,
            fetched_at=fetched_at,
            source_fields={
                "retailer_product_id": retailer_id,
                "available": available,
                "is_in_current_catalog": current,
                "price_amount": str(base_price) if base_price is not None else None,
                "price_currency": currency,
                "raw_unit_price": row.get("unitPrice"),
                "comparison_unit_verified": comparison_unit is not None,
                "quantity_in_basket": row.get("quantityInBasket"),
                "product_type": row.get("type"),
                "pack_count": pack_count,
                "price_context_type": (
                    store.price_context_type.value if store.price_context_type else None
                ),
                "price_semantics": "online_price",
                # Campaign-shaped fields are lineage only until a separate,
                # evidenced resolver proves price, validity and eligibility.
                "featured_product_campaign": raw_campaign,
                "promotion_resolution": "unresolved" if raw_campaign is not None else "none",
            },
        )

    def parse_category_tree(self, document: RawFetch, *, store: SourceStore) -> IcaCategoryTree:
        if document.kind != ICA_CATEGORY_TREE_KIND:
            raise IcaOnlineSchemaError("expected ICA category-tree response")
        self._require_context(document, store)
        return IcaCategoryTree.from_payload(self._payload(document))

    def parse_product_page(
        self,
        document: RawFetch,
        *,
        store: SourceStore,
    ) -> IcaProductPage:
        if document.kind != ICA_PRODUCT_PAGE_KIND:
            raise IcaOnlineSchemaError("expected ICA product-page response")
        self._require_context(document, store)
        category_id = document.query.get("category_id")
        if category_id is None:
            raise IcaOnlineSchemaError("ICA product-page raw lacks category_id")
        return IcaProductPage.from_payload(
            self._payload(document),
            category_id=category_id,
        )

    def parse_product_batch(
        self,
        document: RawFetch,
        *,
        store: SourceStore,
    ) -> IcaBatchResult:
        if document.kind != ICA_PRODUCT_BATCH_KIND:
            raise IcaOnlineSchemaError("expected ICA product-batch response")
        self._require_context(document, store)
        return IcaBatchResult.from_payload(
            self._payload(document),
            requested_product_ids=_requested_product_ids(document),
        )

    def reconcile_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> IcaOnlineCatalogReconciliation:
        pairs = raw.with_references(references)
        tree_documents = [
            document for document, _ in pairs if document.kind == ICA_CATEGORY_TREE_KIND
        ]
        if len(tree_documents) != 1:
            raise IcaOnlineCompletenessError(
                "ICA full catalog requires exactly one category-tree document"
            )
        tree = self.parse_category_tree(tree_documents[0], store=store)
        terminals = {node.category_id: node for node in tree.terminal_nodes}

        page_documents: dict[str, list[tuple[int, RawFetch, str]]] = defaultdict(list)
        batch_documents: dict[tuple[str, int], list[tuple[int, RawFetch]]] = defaultdict(list)
        for document, reference in pairs:
            if document.kind not in {ICA_PRODUCT_PAGE_KIND, ICA_PRODUCT_BATCH_KIND}:
                continue
            self._require_context(document, store)
            category_id = str(document.query.get("category_id") or "")
            if category_id not in terminals:
                raise IcaOnlineCompletenessError(
                    f"ICA raw response has unexpected terminal category {category_id}"
                )
            page_index = _page_index(document)
            if document.kind == ICA_PRODUCT_PAGE_KIND:
                page_documents[category_id].append((page_index, document, reference))
                continue
            raw_batch_index = document.query.get("batch_index")
            if raw_batch_index is None:
                raise IcaOnlineCompletenessError("ICA product batch lacks batch_index")
            try:
                batch_index = int(raw_batch_index)
            except (TypeError, ValueError) as exc:
                raise IcaOnlineCompletenessError(
                    "ICA product batch_index is not an integer"
                ) from exc
            if batch_index < 0:
                raise IcaOnlineCompletenessError("ICA product batch_index must be non-negative")
            batch_documents[(category_id, page_index)].append((batch_index, document))
        if set(page_documents) != set(terminals):
            raise IcaOnlineCompletenessError(
                "ICA terminal category partitions differ: "
                f"missing={sorted(set(terminals) - set(page_documents))}, "
                f"unexpected={sorted(set(page_documents) - set(terminals))}"
            )

        global_products: dict[str, SourceProduct] = {}
        global_fingerprints: dict[str, str] = {}
        global_first_category: dict[str, str] = {}
        raw_rows = 0
        pages_fetched = 0
        exact_duplicates = 0
        placement_overlaps = 0
        pagination_overlaps = 0
        cross_category_overlaps = 0
        for category_id in sorted(terminals):
            indexed_pages = sorted(page_documents[category_id], key=lambda item: item[0])
            indices = tuple(index for index, _, _ in indexed_pages)
            if indices != tuple(range(len(indexed_pages))):
                raise IcaOnlineCompletenessError(
                    f"ICA category {category_id} page indices are incomplete"
                )
            pages = tuple(
                self.parse_product_page(document, store=store)
                for _, document, _ in indexed_pages
            )
            validate_continuation_chain(pages)
            if indexed_pages[0][1].query.get("previous_page_token_hash") is not None:
                raise IcaOnlineCompletenessError(
                    f"ICA category {category_id} first page has continuation lineage"
                )
            for index in range(1, len(indexed_pages)):
                previous_hash = indexed_pages[index][1].query.get("previous_page_token_hash")
                if previous_hash != pages[index - 1].next_page_token_hash:
                    raise IcaOnlineCompletenessError(
                        f"ICA category {category_id} continuation lineage is broken"
                    )

            category_rows: dict[str, tuple[dict[str, Any], str, datetime]] = {}
            category_fingerprints: dict[str, str] = {}
            for (page_index, document, reference), page in zip(
                indexed_pages,
                pages,
                strict=True,
            ):
                raw_rows += page.raw_product_rows
                pages_fetched += 1
                if page.missed_promotions:
                    raise IcaOnlineCompletenessError(
                        "ICA full catalog has unresolved missedPromotions evidence"
                    )
                exact_duplicates += page.duplicate_metrics.exact_duplicates_removed
                placement_overlaps += page.duplicate_metrics.placement_overlaps
                indexed_batches = sorted(
                    batch_documents.pop((category_id, page_index), ()),
                    key=lambda item: item[0],
                )
                batch_indices = tuple(index for index, _ in indexed_batches)
                if batch_indices != tuple(range(len(indexed_batches))):
                    raise IcaOnlineCompletenessError(
                        f"ICA category {category_id} page {page_index} batch indices are incomplete"
                    )
                batches = tuple(
                    self.parse_product_batch(batch_document, store=store)
                    for _, batch_document in indexed_batches
                )
                resolved = reconcile_page_batches(page, batches)
                for product_index, row in enumerate(resolved.products):
                    if row.get("featuredProductCampaign") is not None:
                        raise IcaOnlineCompletenessError(
                            "ICA full catalog has unresolved promotion semantics"
                        )
                    product_id = resolved.product_ids[product_index]
                    fingerprint = purchase_semantic_fingerprint(row)
                    if product_id in category_rows:
                        if category_fingerprints[product_id] != fingerprint:
                            raise IcaOnlineCompletenessError(
                                f"ICA category {category_id} conflicts for {product_id}"
                            )
                        pagination_overlaps += 1
                        exact_duplicates += 1
                        continue
                    category_rows[product_id] = (
                        row,
                        f"{reference}#products[{product_index}]",
                        document.fetched_at,
                    )
                    category_fingerprints[product_id] = fingerprint

            declared_candidates = {
                value
                for value in (
                    terminals[category_id].product_count,
                    *(page.declared_product_count for page in pages),
                )
                if value is not None
            }
            if not declared_candidates:
                raise IcaOnlineCompletenessError(
                    f"ICA terminal category {category_id} lacks declared productCount"
                )
            if len(declared_candidates) != 1:
                raise IcaOnlineCompletenessError(
                    f"ICA terminal category {category_id} has conflicting productCount"
                )
            declared = next(iter(declared_candidates))
            if len(category_rows) != declared:
                raise IcaOnlineCompletenessError(
                    f"ICA category {category_id} count differs: "
                    f"declared={declared}, unique={len(category_rows)}"
                )
            for product_id, (row, reference, fetched_at) in category_rows.items():
                fingerprint = category_fingerprints[product_id]
                prior = global_fingerprints.get(product_id)
                if prior is not None:
                    if prior != fingerprint:
                        raise IcaOnlineCompletenessError(
                            "ICA cross-category product conflict for "
                            f"{product_id} ({global_first_category[product_id]} vs {category_id})"
                        )
                    cross_category_overlaps += 1
                    continue
                global_fingerprints[product_id] = fingerprint
                global_first_category[product_id] = category_id
                global_products[product_id] = self.parse_product(
                    row,
                    store=store,
                    reference=reference,
                    fetched_at=fetched_at,
                )
        if batch_documents:
            raise IcaOnlineCompletenessError("ICA catalog contains orphan product batches")

        within_duplicates = exact_duplicates + placement_overlaps
        duplicate_products = within_duplicates + cross_category_overlaps
        if raw_rows != len(global_products) + duplicate_products:
            raise IcaOnlineCompletenessError(
                "ICA duplicate metrics do not reconcile raw product placements"
            )
        completion = CatalogCompletion(
            complete=True,
            expected_categories=len(terminals),
            completed_categories=len(page_documents),
            pages_fetched=pages_fetched,
            products_observed=len(global_products),
            # Every terminal category's declared unique count was checked
            # above. CatalogCompletion's exact-count contract represents raw
            # source placements, including safely classified overlaps.
            expected_products=raw_rows,
            raw_rows=raw_rows,
            unique_products=len(global_products),
            duplicate_products=duplicate_products,
            within_partition_duplicates=within_duplicates,
            cross_partition_duplicates=cross_category_overlaps,
            exact_duplicates_removed=within_duplicates,
            conflicting_duplicates=0,
            pagination_overlaps=pagination_overlaps,
            expected_pages=pages_fetched,
        )
        metrics = IcaDuplicateMetrics(
            exact_duplicates_removed=exact_duplicates,
            placement_overlaps=placement_overlaps,
            pagination_overlaps=pagination_overlaps,
            cross_category_overlaps=cross_category_overlaps,
        )
        return IcaOnlineCatalogReconciliation(
            products=tuple(global_products[key] for key in sorted(global_products)),
            duplicate_metrics=metrics,
            completion=completion,
        )

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        try:
            reconciliation = self.reconcile_catalog(raw, references, store)
        except (IcaOnlineSchemaError, ValueError) as exc:
            reference = references[0] if references else "raw:ica-online-catalog"
            return ProductParseResult(
                failures=[
                    ParseFailure(
                        raw_record_reference=reference,
                        error_code="schema_changed",
                        error_message=str(exc)[:300],
                        parser_version=self.parser_version,
                    )
                ]
            )
        return ProductParseResult(products=list(reconciliation.products))


def terminal_category_ids(nodes: Iterable[IcaCategoryNode]) -> tuple[str, ...]:
    """Small deterministic helper for clients that already hold category nodes."""

    identifiers = tuple(node.category_id for node in nodes if node.terminal)
    if len(identifiers) != len(set(identifiers)):
        raise IcaOnlineSchemaError("ICA terminal category IDs are not unique")
    return identifiers
