from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse


class LidlSchemaError(ValueError):
    """A public Lidl response no longer satisfies the verified source contract."""


@dataclass(frozen=True, slots=True)
class LidlSearchPage:
    total: int
    offset: int
    fetch_size: int
    items: tuple[dict[str, Any], ...]


_DETAIL_LINK = re.compile(
    r'href=["\'](?P<path>/s/sv-SE/butiker/(?P<city>[^/]+)/[^/"\'#?]+/)["\']',
    re.IGNORECASE,
)
_STORE_HEADING = re.compile(
    r'<span[^>]*class=["\'][^"\']*main-info__headline-store[^"\']*["\'][^>]*>'
    r'(?P<value>.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
_TNC = re.compile(r'(?:[?&]|&amp;)TNC=(?P<value>\d+)(?:[&#"\']|$)', re.IGNORECASE)
_BING_POSITION = re.compile(
    r'https://bing\.com/maps/default\.aspx\?rtp=~pos\.'
    r'(?P<latitude>-?\d+(?:\.\d+)?)_(?P<longitude>-?\d+(?:\.\d+)?)_',
    re.IGNORECASE,
)
_ADDRESS = re.compile(
    r'^(?P<address>.+),\s*(?P<postal>\d{3}\s?\d{2})\s+(?P<city>.+)$',
    re.DOTALL,
)
_TAG = re.compile(r"<[^>]+>")


def _object(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LidlSchemaError(f"Lidl {field} must be an object")
    return value


def _integer(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LidlSchemaError(f"Lidl {field} must be a non-negative integer")
    return value


def validated_search_page(
    payload: bytes | dict[str, Any],
    *,
    requested_offset: int | None = None,
) -> LidlSearchPage:
    """Validate the public vendor-JSON pagination envelope and product identities."""

    try:
        root = json.loads(payload) if isinstance(payload, bytes) else payload
    except (TypeError, ValueError) as exc:
        raise LidlSchemaError("Lidl search response is not valid JSON") from exc
    root = _object(root, field="search response")
    if root.get("type") != "search" or root.get("resultType") != "search":
        raise LidlSchemaError("Lidl search discriminator changed")
    total = _integer(root.get("numFound"), field="numFound")
    offset = _integer(root.get("offset"), field="offset")
    fetch_size = _integer(root.get("fetchsize"), field="fetchsize")
    if fetch_size <= 0:
        raise LidlSchemaError("Lidl fetchsize must be positive")
    if requested_offset is not None and offset != requested_offset:
        raise LidlSchemaError("Lidl response offset does not match the requested offset")
    raw_items = root.get("items")
    if not isinstance(raw_items, list):
        raise LidlSchemaError("Lidl items must be an array")
    items: list[dict[str, Any]] = []
    for position, raw_item in enumerate(raw_items):
        item = _object(raw_item, field=f"items[{position}]")
        gridbox = _object(item.get("gridbox"), field=f"items[{position}].gridbox")
        product = _object(gridbox.get("data"), field=f"items[{position}].gridbox.data")
        product_id = product.get("productId")
        if isinstance(product_id, bool) or not isinstance(product_id, (int, str)):
            raise LidlSchemaError(f"Lidl product at position {position} lacks productId")
        if not str(product_id).strip():
            raise LidlSchemaError(f"Lidl product at position {position} has empty productId")
        # `gridbox.meta.ean` is an explicitly named source identity field and
        # is distinct from Lidl's internal productId/erpNumber. Preserve the
        # raw value for connector-local checksum validation without guessing
        # that any other numeric identifier is a GTIN.
        source_product = dict(product)
        metadata = gridbox.get("meta")
        if isinstance(metadata, dict) and "ean" in metadata:
            raw_ean = metadata["ean"]
            if raw_ean is not None and not isinstance(raw_ean, (str, int)):
                raise LidlSchemaError(
                    f"Lidl product at position {position} has non-scalar meta.ean"
                )
            source_product["_explicit_gridbox_meta_ean"] = raw_ean
        items.append(source_product)
    if offset < total and not items:
        raise LidlSchemaError("Lidl pagination stopped before the declared total")
    if len(items) > fetch_size:
        raise LidlSchemaError("Lidl page contains more rows than its declared fetchsize")
    return LidlSearchPage(
        total=total,
        offset=offset,
        fetch_size=fetch_size,
        items=tuple(items),
    )


def sanitized_store_index(
    payload: bytes,
    *,
    source_url: str,
    city_slug: str,
    requested_city: str,
) -> bytes:
    """Retain only public store-detail links; drop scripts and runtime configuration."""

    text = payload.decode("utf-8", errors="strict")
    paths = {
        unescape(match.group("path"))
        for match in _DETAIL_LINK.finditer(text)
        if match.group("city").casefold() == city_slug.casefold()
    }
    if not paths:
        raise LidlSchemaError("Lidl city page exposes no store-detail links")
    envelope = {
        "schema": "lidl-public-store-index-v1",
        "requested_city": requested_city,
        "city_slug": city_slug,
        "detail_urls": [urljoin(source_url, path) for path in sorted(paths)],
    }
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode("utf-8")


def store_detail_urls(payload: bytes) -> tuple[str, ...]:
    try:
        root = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise LidlSchemaError("Lidl sanitized store index is not valid JSON") from exc
    root = _object(root, field="sanitized store index")
    if root.get("schema") != "lidl-public-store-index-v1":
        raise LidlSchemaError("Lidl sanitized store-index schema changed")
    values = root.get("detail_urls")
    if not isinstance(values, list) or not values:
        raise LidlSchemaError("Lidl sanitized store index lacks detail URLs")
    urls = tuple(str(value) for value in values)
    if any(urlparse(url).netloc.casefold() != "www.lidl.se" for url in urls):
        raise LidlSchemaError("Lidl store index contains a non-Lidl URL")
    return urls


def sanitized_store_detail(payload: bytes, *, source_url: str) -> bytes:
    """Convert one public detail page into a closed, secret-free evidence record."""

    text = payload.decode("utf-8", errors="strict")
    heading_match = _STORE_HEADING.search(text)
    tnc_match = _TNC.search(text)
    position_match = _BING_POSITION.search(text)
    if heading_match is None or tnc_match is None:
        raise LidlSchemaError("Lidl store page lacks its visible heading or TNC identity")
    heading = unescape(_TAG.sub("", heading_match.group("value"))).strip()
    address_match = _ADDRESS.fullmatch(heading)
    if address_match is None:
        raise LidlSchemaError("Lidl store heading does not contain address, postal code and city")
    latitude = position_match.group("latitude") if position_match else None
    longitude = position_match.group("longitude") if position_match else None
    envelope = {
        "schema": "lidl-public-store-detail-v1",
        "external_id": tnc_match.group("value"),
        "id_namespace": "public_feedback_tnc",
        "id_stability": "inferred",
        "name": f"Lidl {address_match.group('address').strip()}",
        "address": address_match.group("address").strip(),
        "postal_code": address_match.group("postal").replace(" ", ""),
        "city": address_match.group("city").strip(),
        "latitude": latitude,
        "longitude": longitude,
        "canonical_url": source_url,
    }
    # The closed envelope is the persisted raw evidence. It cannot carry an
    # x-apikey, cookies, runtime tokens or session state from page scripts.
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode("utf-8")


def validated_store_detail(payload: bytes) -> dict[str, Any]:
    try:
        root = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise LidlSchemaError("Lidl sanitized store detail is not valid JSON") from exc
    root = _object(root, field="sanitized store detail")
    if root.get("schema") != "lidl-public-store-detail-v1":
        raise LidlSchemaError("Lidl sanitized store-detail schema changed")
    required = ("external_id", "name", "address", "postal_code", "city", "canonical_url")
    if any(not str(root.get(field) or "").strip() for field in required):
        raise LidlSchemaError("Lidl sanitized store detail lacks a required public field")
    return root
