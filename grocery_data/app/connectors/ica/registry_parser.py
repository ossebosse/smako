from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from grocery_data.app.domain import IcaDiscoverySource, IcaRegistryObservation

from .models import IcaSchemaError, _replace_bare_javascript_values


def initial_state_from_html(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8")
    marker = "window.__INITIAL_STATE__"
    start = text.find(marker)
    if start < 0:
        raise IcaSchemaError("ICA page is missing window.__INITIAL_STATE__")
    assignment = text.find("=", start + len(marker))
    end = text.find(";</script>", assignment)
    if assignment < 0 or end < 0:
        raise IcaSchemaError("ICA initial-state script is unterminated")
    literal = _replace_bare_javascript_values(text[assignment + 1 : end].strip())
    try:
        result = json.loads(literal)
    except json.JSONDecodeError as exc:
        raise IcaSchemaError("ICA initial-state literal is not supported JSON") from exc
    if not isinstance(result, dict):
        raise IcaSchemaError("ICA initial state must be an object")
    return result


def _walk(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def _id(row: dict[str, Any]) -> str | None:
    for key in ("retailerProductId", "productId", "id"):
        value = str(row.get(key) or "").strip()
        if value and len(value) <= 255:
            return value
    return None


def _price(row: dict[str, Any]) -> Decimal | None:
    value = row.get("price") or row.get("currentPrice") or row.get("salesPrice")
    if isinstance(value, dict):
        current = value.get("current")
        value = (
            current.get("amount")
            if isinstance(current, dict)
            else value.get("value") or value.get("amount")
        )
    return _decimal(value)


def extract_registry_observations(
    state: dict[str, Any],
    *,
    store_external_id: str,
    source: IcaDiscoverySource,
    source_page: str,
    observed_at: datetime,
    raw_snapshot_id: str | None = None,
) -> list[IcaRegistryObservation]:
    """Extract IDs and decorated products without inventing absent source facts."""

    candidates: dict[str, dict[str, Any]] = {}
    for row in _walk(state):
        product_id = _id(row)
        if product_id is None:
            continue
        product_like = any(
            key in row
            for key in (
                "retailerProductId",
                "productId",
                "productName",
                "name",
                "price",
                "packageDescription",
            )
        )
        if not product_like:
            continue
        previous = candidates.get(product_id, {})
        if len(row) >= len(previous):
            candidates[product_id] = row
    observations = []
    for product_id, row in candidates.items():
        category = row.get("categoryPath")
        if isinstance(category, str):
            category_path = [part.strip() for part in category.split("/") if part.strip()]
        elif isinstance(category, list):
            category_path = [
                str(part.get("name") if isinstance(part, dict) else part) for part in category
            ]
        else:
            category_path = []
        price_block = row.get("price") if isinstance(row.get("price"), dict) else {}
        comparison = row.get("comparisonPrice") or row.get("unitPrice") or price_block.get("unit")
        if isinstance(comparison, dict):
            current_comparison = comparison.get("current")
            comparison_price = _decimal(
                current_comparison.get("amount")
                if isinstance(current_comparison, dict)
                else comparison.get("value") or comparison.get("amount") or comparison.get("price")
            )
            comparison_unit = (
                str(comparison.get("unit") or comparison.get("label") or "").strip() or None
            )
        else:
            comparison_price = None
            comparison_unit = None
        observations.append(
            IcaRegistryObservation(
                external_product_id=product_id,
                store_external_id=store_external_id,
                source=source,
                source_page=source_page,
                observed_at=observed_at,
                raw_snapshot_id=raw_snapshot_id,
                name=str(row.get("productName") or row.get("name") or "").strip() or None,
                brand=str(row.get("brand") or row.get("brandName") or "").strip() or None,
                gtin=(str(row.get("gtin") or row.get("ean") or "").strip() or None),
                category_path=category_path,
                package_text=str(
                    row.get("packageDescription")
                    or row.get("packSizeDescription")
                    or row.get("packageText")
                    or (
                        row.get("size", {}).get("value")
                        if isinstance(row.get("size"), dict)
                        else ""
                    )
                    or ""
                ).strip()
                or None,
                sale_price=_price(row),
                comparison_price=comparison_price,
                comparison_unit=comparison_unit,
                availability=(
                    "available"
                    if row.get("available") is True
                    else "unavailable"
                    if row.get("available") is False
                    else str(row.get("availability") or "").strip() or None
                ),
                promotion=(
                    row.get("promotion")
                    if isinstance(row.get("promotion"), dict)
                    else {"offers": row["promotions"]}
                    if isinstance(row.get("promotions"), list) and row["promotions"]
                    else None
                ),
            )
        )
    return observations


def declared_product_ids(state: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for row in _walk(state):
        for key in ("productIds", "allIds"):
            values = row.get(key)
            if isinstance(values, list):
                ids.update(str(value).strip() for value in values if str(value).strip())
        if set(row) <= {"id", "position", "rank"} and (value := _id(row)):
            ids.add(value)
    return ids


def has_access_challenge(*, status: int, body: str, title: str = "") -> bool:
    haystack = f"{title} {body[:10000]}".casefold()
    markers = ("captcha", "human verification", "aws waf", "access denied", "challenge")
    return status in {403, 405, 429} or any(marker in haystack for marker in markers)


_JSON_LD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(?P<value>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def extract_product_detail_jsonld(
    payload: bytes,
    *,
    store_external_id: str,
    source_page: str,
    observed_at: datetime,
    raw_snapshot_id: str | None = None,
) -> list[IcaRegistryObservation]:
    text = payload.decode("utf-8")
    if has_access_challenge(status=200, body=text):
        raise IcaSchemaError("ICA product detail contains an access challenge")
    observations = []
    for match in _JSON_LD.finditer(text):
        try:
            row = json.loads(match.group("value"))
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("@type") != "Product":
            continue
        product_id = str(row.get("sku") or "").strip()
        if not product_id:
            continue
        offers = row.get("offers") if isinstance(row.get("offers"), dict) else {}
        brand = row.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        observations.append(
            IcaRegistryObservation(
                external_product_id=product_id,
                store_external_id=store_external_id,
                source=IcaDiscoverySource.PRODUCT_DETAIL,
                source_page=source_page,
                observed_at=observed_at,
                raw_snapshot_id=raw_snapshot_id,
                name=str(row.get("name") or "").strip() or None,
                brand=str(brand or "").strip() or None,
                gtin=str(row.get("gtin") or row.get("gtin13") or row.get("gtin14") or "").strip()
                or None,
                sale_price=_decimal(offers.get("price")),
                availability=str(offers.get("availability") or "").rsplit("/", 1)[-1] or None,
            )
        )
    return observations
