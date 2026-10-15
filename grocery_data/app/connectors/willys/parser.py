from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from grocery_data.app.connectors.willys.models import (
    WillysCategoryNode,
    validated_catalog_page,
    validated_store_context,
)
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    PriceContextType,
    ProductParseResult,
    PromotionType,
    RawBatch,
    SourceOffer,
    SourceProduct,
    SourceStore,
)
from grocery_data.app.domain.product import ParseFailure

_AMOUNT_RE = re.compile(
    r"(?P<approx>ca\s*:?)?\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|cl|dl|l|st)\b",
    re.IGNORECASE,
)
_MULTIPACK_RE = re.compile(
    r"(?P<count>\d+)\s*[x×]\s*(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>kg|g|ml|cl|dl|l|st)\b",
    re.IGNORECASE,
)
_PACK_RE = re.compile(r"(?P<count>\d+)\s*[- ]?pack\b", re.IGNORECASE)
_PIECE_COUNT_RE = re.compile(r"(?P<count>\d+)\s*p\b", re.IGNORECASE)
_DRAINED_RE = re.compile(
    r"(?:avrunnen|drained)\s*(?:vikt|weight)?\s*:?[ ]*"
    r"(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_MAX_RE = re.compile(r"max\s+(\d+)", re.IGNORECASE)
_APPROXIMATE_RE = re.compile(r"(?i:\bca\s*:?)")
_CATALOG_ROOT_CODES = frozenset({"n00"})


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        match = _NUMBER_RE.search(value.replace("\u00a0", ""))
        if not match:
            return None
        value = match.group(0).replace(",", ".")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() and result > 0 else None


def _normalise_amount(amount: Decimal, unit: str) -> tuple[Decimal, str]:
    unit = unit.casefold()
    if unit == "kg":
        return amount * 1000, "g"
    if unit == "l":
        return amount * 1000, "ml"
    if unit == "cl":
        return amount * 10, "ml"
    if unit == "dl":
        return amount * 100, "ml"
    return amount, unit


def parse_package_text(value: object) -> tuple[Decimal | None, str | None, bool]:
    text = str(value or "").strip()
    approximate = bool(_APPROXIMATE_RE.search(text))
    multipack = _MULTIPACK_RE.search(text)
    if multipack:
        count = _decimal(multipack.group("count"))
        amount = _decimal(multipack.group("amount"))
        if count is None or amount is None:
            return None, None, approximate
        quantity, unit = _normalise_amount(count * amount, multipack.group("unit"))
        return quantity, unit, approximate
    matches = list(_AMOUNT_RE.finditer(text))
    # Prefer physical weight/volume over a leading "1st" marker.
    match = next(
        (candidate for candidate in matches if candidate.group("unit").casefold() != "st"),
        matches[0] if matches else None,
    )
    if match is None:
        package = _PACK_RE.search(text)
        piece_count = _PIECE_COUNT_RE.search(text)
        count_match = package or piece_count
        count = _decimal(count_match.group("count")) if count_match else None
        return (count, "st", approximate) if count is not None else (None, None, approximate)
    amount = _decimal(match.group("amount"))
    if amount is None:
        return None, None, approximate
    quantity, unit = _normalise_amount(amount, match.group("unit"))
    return quantity, unit, approximate


def parse_drained_quantity(value: object) -> tuple[Decimal | None, str | None]:
    match = _DRAINED_RE.search(str(value or ""))
    if not match:
        return None, None
    amount = _decimal(match.group("amount"))
    return _normalise_amount(amount, match.group("unit")) if amount is not None else (None, None)


def _category_path(payload: dict[str, Any]) -> tuple[str, ...]:
    """Read Willys' ordered page-level category context without inferring it.

    Live category pages put ancestors in ``superCategories`` and the leaf in
    ``categoryInfo``/``categoryBreadcrumbs``. Product-detail fixtures can
    instead carry a conventional ``breadcrumbs`` list. Only entries with both
    source identity and a name are accepted; the synthetic catalog root N00 is
    not a product category.
    """

    def entries(value: object) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    ancestors = entries(payload.get("superCategories"))
    breadcrumbs = entries(payload.get("breadcrumbs") or payload.get("breadCrumbs"))
    ordered = ancestors if ancestors else breadcrumbs
    ordered = [
        *ordered,
        *entries(payload.get("categoryInfo")),
        *entries(payload.get("categoryBreadcrumbs")),
    ]

    names: list[str] = []
    seen: set[str] = set()
    for item in ordered:
        code = str(item.get("code") or item.get("categoryCode") or "").strip()
        name = str(item.get("name") or "").strip()
        if not code or not name or code.casefold() in _CATALOG_ROOT_CODES:
            continue
        name_key = name.casefold()
        if name_key in seen:
            continue
        seen.add(name_key)
        names.append(name)
    return tuple(names)


class WillysParser:
    parser_version = "willys-parser-v6-picking-contract"

    def __init__(self, *, accept_sales_price_object: bool = True) -> None:
        self.accept_sales_price_object = accept_sales_price_object

    @staticmethod
    def category_leaf_paths(tree_fetch: bytes) -> list[str]:
        import json

        tree = WillysCategoryNode.model_validate(json.loads(tree_fetch))
        return sorted(set(tree.leaf_paths()))

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
        *,
        filter_locality: bool = True,
    ) -> list[SourceStore]:
        if len(raw.documents) != len(references):
            raise ValueError("raw references must align with documents")
        stores: dict[str, SourceStore] = {}
        city = area.city.casefold()
        for document, reference in zip(raw.documents, references, strict=True):
            if document.kind != "stores" or document.http_status != 200:
                continue
            payload = document.json_payload()
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict):
                    continue
                address = row.get("address") if isinstance(row.get("address"), dict) else {}
                name = str(row.get("name") or "").strip()
                town = str(address.get("town") or "").strip()
                town_key = town.casefold()
                name_has_city = re.search(rf"(?<!\w){re.escape(city)}(?!\w)", name.casefold())
                if filter_locality and ((town_key and town_key != city) or (not town_key and not name_has_city)):
                    continue
                external_id = str(row.get("storeId") or "").strip()
                if not external_id or not name:
                    continue
                if not validated_store_context(row, external_id):
                    raise ValueError("Willys unreviewed picking base store binding")
                latitude = _decimal(
                    address.get("latitude") or (row.get("geoPoint") or {}).get("latitude")
                )
                longitude = _decimal(
                    address.get("longitude") or (row.get("geoPoint") or {}).get("longitude")
                )
                online_value = row.get("onlineStore")
                online_shopping = (
                    online_value
                    if isinstance(online_value, bool)
                    else str(online_value).strip().casefold() == "true"
                    if online_value is not None
                    else None
                )
                stores[external_id] = SourceStore(
                    chain=Chain.WILLYS,
                    external_id=external_id,
                    name=name,
                    address=str(address.get("line1") or "").strip() or None,
                    postal_code=str(address.get("postalCode") or "").strip() or None,
                    city=town or None,
                    latitude=latitude,
                    longitude=longitude,
                    online_shopping=online_shopping,
                    coverage=(
                        CoverageLevel.FULL_CATALOG
                        if online_shopping is True
                        else CoverageLevel.PARTIAL_CATALOG
                    ),
                    price_context_type=(
                        PriceContextType.ONLINE_STORE if online_shopping is True else None
                    ),
                    physical_store_external_id=external_id,
                    raw_reference=f"{reference}#storeId={external_id}",
                    source_fields={
                        **({"hasPickingBaseStore": row["hasPickingBaseStore"]}
                           if "hasPickingBaseStore" in row else {}),
                        "coordinate_source": {"url": document.url,
                        "sha256": document.payload_hash, "observed_at": document.fetched_at.isoformat()}},
                )
        return sorted(stores.values(), key=lambda store: (store.name.casefold(), store.external_id))

    def _price(self, row: dict[str, Any]) -> Decimal | None:
        price = _decimal(row.get("priceValue"))
        if price is not None or not self.accept_sales_price_object:
            return price
        sales_price = row.get("salesPrice")
        if isinstance(sales_price, dict):
            return _decimal(sales_price.get("value"))
        return None

    @staticmethod
    def _offers(
        row: dict[str, Any],
        *,
        failures: list[ParseFailure] | None = None,
        raw_reference: str | None = None,
    ) -> tuple[SourceOffer, ...]:
        offers: list[SourceOffer] = []
        candidates = row.get("potentialPromotions") or []
        if not isinstance(candidates, list):
            return ()

        def quarantine(index: int, promotion: object, message: str) -> None:
            if failures is None or raw_reference is None:
                return
            sample = promotion if isinstance(promotion, dict) else {}
            failures.append(
                ParseFailure(
                    raw_record_reference=f"{raw_reference}#potentialPromotions[{index}]",
                    error_code="invalid_promotion",
                    error_message=message[:300],
                    parser_version=WillysParser.parser_version,
                    sample={
                        key: sample.get(key)
                        for key in ("code", "campaignType", "promotionType", "qualifyingCount")
                    },
                )
            )

        for index, promotion in enumerate(candidates):
            if not isinstance(promotion, dict):
                quarantine(index, promotion, "promotion must be an object")
                continue
            quantity_raw = promotion.get("qualifyingCount")
            try:
                quantity = int(quantity_raw) if quantity_raw else None
            except (TypeError, ValueError):
                quarantine(index, promotion, "qualifyingCount is not an integer")
                continue
            if quantity is not None and quantity < 1:
                quarantine(index, promotion, "qualifyingCount must be positive")
                continue
            member_only = str(promotion.get("campaignType") or "").upper() == "LOYALTY"
            if quantity and quantity > 1:
                promotion_type = PromotionType.MULTIBUY
                group_price = _decimal(promotion.get("rewardLabel"))
                if group_price is None:
                    unit_price = _decimal((promotion.get("price") or {}).get("value"))
                    group_price = unit_price * quantity if unit_price is not None else None
                if group_price is None:
                    quarantine(index, promotion, "multibuy promotion lacks a valid group price")
                    continue
                price = group_price
            else:
                promotion_type = (
                    PromotionType.MEMBER_PRICE if member_only else PromotionType.SALE_PRICE
                )
                price = _decimal((promotion.get("price") or {}).get("value"))
            valid_to = None
            epoch_ms = _decimal(promotion.get("validUntil"))
            if epoch_ms is not None:
                try:
                    valid_to = datetime.fromtimestamp(float(epoch_ms) / 1000, tz=UTC).date()
                except (OSError, OverflowError, ValueError):
                    valid_to = None
            max_match = _MAX_RE.search(str(promotion.get("redeemLimitLabel") or ""))
            # A count cap needs independent ordering-unit evidence. Preserve
            # the label and bind only the reviewed single-product kg contract.
            stated_quantity, stated_unit, _ = parse_package_text(str(row.get('productLine2') or ''))
            counted_weight = bool(max_match and promotion.get("code") and
                promotion.get('redeemLimitLabel') == f'Max {int(max_match.group(1))} köp' and
                promotion.get('promotionType') == 'SubtotalOrderPromotion' and
                promotion.get('realMixAndMatch') is False and
                promotion.get('mainProductCode') == row.get('code') and
                not promotion.get('productCodes') and not quantity and
                promotion.get('threshold') in (None, 0) and
                promotion.get('promotionPercentage') is None and
                promotion.get('textLabelManual') in (None, '') and
                row.get('priceUnit') == 'kr/kg' and
                isinstance(row.get('productBasketType'), dict) and
                row['productBasketType'].get('code') == 'ST' and
                (_decimal(row.get('averageWeight')) or 0) > 0 and
                stated_unit == 'g' and stated_quantity == _decimal(row['averageWeight']) * 1000 and
                (promotion.get('price') or {}).get('formattedValue', '').endswith('kr/kg'))
            try:
                offers.append(
                    SourceOffer(
                        external_id=str(promotion.get("code") or "").strip() or None,
                        type=promotion_type,
                        valid_to=valid_to,
                        price=price,
                        quantity=quantity,
                        member_only=member_only,
                        max_quantity=int(max_match.group(1)) if max_match else None,
                        description=str(
                            promotion.get("conditionLabel")
                            or promotion.get("textLabel")
                            or promotion.get("promotionType")
                            or "Kampanj"
                        ),
                        source_payload={
                            "redeemLimitLabel": promotion.get("redeemLimitLabel"),
                            **({'limit_unit': 'purchase_packages', 'price_basis_unit': 'kg',
                                'price_contract_id': f"axfood:counted:{promotion.get('code')}:{row['code']}:{valid_to}",
                                'limit_evidence': {'basket_type': 'ST', 'average_weight_kg': row['averageWeight'],
                                    'raw_reference': raw_reference, 'product_code': row['code'],
                                    'label': promotion['redeemLimitLabel']}} if counted_weight else {}),
                            "promotionType": promotion.get("promotionType"),
                            "campaignType": promotion.get("campaignType"),
                            "realMixAndMatch": promotion.get("realMixAndMatch"),
                            "lowestHistoricalPrice": promotion.get("lowestHistoricalPrice"),
                        },
                    )
                )
            except ValidationError as exc:
                quarantine(index, promotion, str(exc))
                continue
        return tuple(offers)

    def _parse_product(
        self,
        row: dict[str, Any],
        store: SourceStore,
        raw_reference: str,
        fetched_at: datetime,
        *,
        page_category_path: tuple[str, ...] = (),
    ) -> SourceProduct:
        external_id = str(row.get("code") or "").strip()
        if not external_id:
            raise ValueError("missing_product_id")
        name = str(row.get("name") or "").strip()
        if not name:
            raise ValueError("missing_name")
        price = self._price(row)
        has_price_field = row.get("priceValue") is not None or row.get("salesPrice") is not None
        if has_price_field and price is None:
            raise ValueError("invalid_price")
        price_unit_text = str(row.get("priceUnit") or "").casefold().strip()
        sale_unit = (
            {"kr/st": "st", "kr/kg": "kg", "kr/l": "l"}.get(price_unit_text)
            if price is not None
            else None
        )
        if price is not None and sale_unit is None:
            raise ValueError("unknown_price_unit")
        comparison_price = _decimal(row.get("comparePrice"))
        comparison_unit = str(row.get("comparePriceUnit") or "").casefold().strip() or None
        if comparison_price is None:
            comparison_unit = None
        package_text = str(row.get("productLine2") or "").strip() or None
        package_quantity, package_unit, _ = parse_package_text(package_text)
        drained_quantity, drained_unit = parse_drained_quantity(package_text)
        average_weight = _decimal(row.get("averageWeight"))
        if package_quantity is None and average_weight is not None:
            package_quantity, package_unit = average_weight * 1000, "g"
        category_path = _category_path(row) or page_category_path
        out_of_stock = row.get("outOfStock")
        availability = (
            "out_of_stock"
            if out_of_stock is True
            else "available"
            if out_of_stock is False
            else None
        )
        return SourceProduct(
            chain=Chain.WILLYS,
            store_external_id=store.external_id,
            external_product_id=external_id,
            gtin=str(row.get("ean") or "").strip() or None,
            name=name,
            brand=str(row.get("manufacturer") or "").strip() or None,
            category_path=category_path,
            sale_price=price,
            regular_price=price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            package_text=package_text,
            package_quantity=package_quantity,
            package_unit=package_unit,
            drained_quantity=(drained_quantity if drained_unit == package_unit else None),
            sale_unit=sale_unit,
            offers=self._offers(row, raw_reference=raw_reference),
            availability=availability,
            average_weight_kg=average_weight,
            increment_value=_decimal(row.get("incrementValue")),
            basket_type=str((row.get("productBasketType") or {}).get("code") or "").strip() or None,
            raw_reference=raw_reference,
            fetched_at=fetched_at,
            source_fields={
                "priceUnit": row.get("priceUnit"),
                "productBasketType": row.get("productBasketType"),
                "online": row.get("online"),
                "outOfStock": row.get("outOfStock"),
                "drainedUnit": drained_unit,
            },
        )

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        if len(raw.documents) != len(references):
            raise ValueError("raw references must align with documents")
        products: dict[str, SourceProduct] = {}
        failures: list[ParseFailure] = []
        contexts = [
            (document, reference)
            for document, reference in zip(raw.documents, references, strict=True)
            if document.kind == "store_context"
        ]
        # Legacy product-only inputs remain supported. Once a saved binding
        # or the new store flag is present, replay must validate that binding
        # just as live transport does, before consuming any catalogue prices.
        if contexts or "hasPickingBaseStore" in store.source_fields:
            confirmed = bool(contexts)
            for document, _reference in contexts:
                try:
                    confirmed = confirmed and (
                        document.http_status == 200
                        and document.store_external_id == store.external_id
                        and validated_store_context(document.json_payload(), store.external_id)
                    )
                except (TypeError, ValueError):
                    confirmed = False
            if not confirmed:
                return ProductParseResult(products=[], failures=[ParseFailure(
                    raw_record_reference=contexts[0][1] if contexts else store.raw_reference,
                    error_code="price_context_unverified",
                    error_message="Willys catalogue lacks a reviewed matching store context",
                    parser_version=self.parser_version,
                )])
        for document, reference in zip(raw.documents, references, strict=True):
            if document.kind not in {"catalog_page", "product_detail"}:
                continue
            if document.http_status != 200:
                failures.append(
                    ParseFailure(
                        raw_record_reference=reference,
                        error_code="schema_changed",
                        error_message=f"unexpected HTTP status {document.http_status}",
                        parser_version=self.parser_version,
                    )
                )
                continue
            try:
                payload = document.json_payload()
            except (TypeError, ValueError):
                failures.append(
                    ParseFailure(
                        raw_record_reference=reference,
                        error_code="invalid_json",
                        error_message="payload is not valid JSON",
                        parser_version=self.parser_version,
                    )
                )
                continue
            if not isinstance(payload, dict):
                failures.append(
                    ParseFailure(
                        raw_record_reference=reference,
                        error_code="schema_changed",
                        error_message="catalog payload must be an object",
                        parser_version=self.parser_version,
                    )
                )
                continue
            if document.kind == "product_detail":
                rows = [payload]
                page_category_path: tuple[str, ...] = ()
            else:
                try:
                    raw_results, _ = validated_catalog_page(
                        payload,
                        requested_page=document.page_number,
                    )
                except (TypeError, ValueError) as exc:
                    failures.append(
                        ParseFailure(
                            raw_record_reference=reference,
                            error_code="schema_changed",
                            error_message=str(exc),
                            parser_version=self.parser_version,
                        )
                    )
                    continue
                rows = raw_results
                page_category_path = _category_path(payload)
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    failures.append(
                        ParseFailure(
                            raw_record_reference=f"{reference}#results[{index}]",
                            error_code="schema_changed",
                            error_message="catalog result must be an object",
                            parser_version=self.parser_version,
                        )
                    )
                    continue
                row_reference = f"{reference}#results[{index}]"
                try:
                    parsed = self._parse_product(
                        row,
                        store,
                        row_reference,
                        document.fetched_at,
                        page_category_path=page_category_path,
                    )
                except (ValidationError, ValueError) as exc:
                    message = str(exc)
                    error_code = (
                        message
                        if message
                        in {
                            "missing_product_id",
                            "missing_name",
                            "invalid_price",
                            "unknown_price_unit",
                        }
                        else "unknown"
                    )
                    failures.append(
                        ParseFailure(
                            raw_record_reference=row_reference,
                            error_code=error_code,
                            error_message=message[:300],
                            parser_version=self.parser_version,
                            sample={
                                key: row.get(key)
                                for key in (
                                    "code",
                                    "name",
                                    "priceValue",
                                    "priceUnit",
                                    "productLine2",
                                )
                            },
                        )
                    )
                    continue
                self._offers(
                    row,
                    failures=failures,
                    raw_reference=row_reference,
                )
                existing = products.get(parsed.external_product_id or "")
                if existing is not None and existing.gtin and not parsed.gtin:
                    continue
                products[parsed.external_product_id or ""] = parsed
        return ProductParseResult(products=list(products.values()), failures=failures)
