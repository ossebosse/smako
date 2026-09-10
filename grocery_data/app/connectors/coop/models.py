from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree


class CoopSchemaError(ValueError):
    """A public Coop payload no longer satisfies the verified source contract."""


class _ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._script_type: str | None = None
        self._parts: list[str] = []
        self.scripts: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        attributes = {name.casefold(): value or "" for name, value in attrs}
        self._script_type = attributes.get("type", "").casefold()
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._script_type is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "script" or self._script_type is None:
            return
        self.scripts.append((self._script_type, "".join(self._parts)))
        self._script_type = None
        self._parts = []


def json_scripts(payload: bytes, *, script_type: str) -> tuple[object, ...]:
    """Decode inert JSON script blocks without evaluating page JavaScript."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CoopSchemaError("Coop HTML is not UTF-8") from exc
    collector = _ScriptCollector()
    collector.feed(text)
    decoded: list[object] = []
    for candidate_type, value in collector.scripts:
        if candidate_type != script_type.casefold() or not value.strip():
            continue
        try:
            decoded.append(json.loads(value))
        except json.JSONDecodeError as exc:
            raise CoopSchemaError(f"Coop {script_type} script is not valid JSON") from exc
    return tuple(decoded)


def _walk(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def store_page_records(payload: bytes) -> tuple[dict[str, Any], ...]:
    """Return only verified StorePageType-shaped embedded records."""

    records: dict[str, dict[str, Any]] = {}
    for root in json_scripts(payload, script_type="application/json"):
        for row in _walk(root):
            store_id = str(row.get("storeID") or "").strip()
            name = str(row.get("name") or "").strip()
            # `storeID`, `ledgerAccountNumber` and `name` are the independently
            # verified public StorePageType fields. Requiring all three avoids
            # accidentally treating unrelated content records as stores.
            if not store_id or not name or row.get("ledgerAccountNumber") is None:
                continue
            records[store_id] = row
    if not records:
        raise CoopSchemaError("Coop page contains no verified StorePageType record")
    return tuple(records.values())


def grocery_store_records(payload: bytes) -> tuple[dict[str, Any], ...]:
    """Return public JSON-LD GroceryStore facts from a store detail page."""

    records: list[dict[str, Any]] = []
    for root in json_scripts(payload, script_type="application/ld+json"):
        for row in _walk(root):
            kind = row.get("@type")
            kinds = {str(item) for item in kind} if isinstance(kind, list) else {str(kind)}
            if "GroceryStore" in kinds:
                records.append(row)
    return tuple(records)


_STORE_ALLOWLIST = (
    "storeID",
    "ledgerAccountNumber",
    "organizationUnitID",
    "simpleAddressUrl",
    "name",
    "routeSegment",
    "url",
    "disableStoreOffersFlyer",
    "contentType",
)


def _safe_grocery_store(row: dict[str, Any]) -> dict[str, Any]:
    """Allowlist only location facts; runtime config/services never survive."""

    address = row.get("address") if isinstance(row.get("address"), dict) else {}
    geo = row.get("geo") if isinstance(row.get("geo"), dict) else {}
    safe_address = {
        key: address.get(key)
        for key in ("streetAddress", "addressLocality", "postalCode", "addressCountry")
        if address.get(key) is not None
    }
    safe_geo = {key: geo.get(key) for key in ("latitude", "longitude") if geo.get(key) is not None}
    safe: dict[str, Any] = {"@type": "GroceryStore"}
    for key in ("@id", "name"):
        if row.get(key) is not None:
            safe[key] = row[key]
    if safe_address:
        safe["address"] = safe_address
    if safe_geo:
        safe["geo"] = safe_geo
    return safe


def sanitized_store_page_html(payload: bytes) -> bytes:
    """Discard executable/runtime config before store evidence is persisted."""

    safe_records = [
        {key: row.get(key) for key in _STORE_ALLOWLIST if row.get(key) is not None}
        for row in store_page_records(payload)
    ]
    encoded = json.dumps(safe_records, ensure_ascii=False, separators=(",", ":"))
    safe_locations = [_safe_grocery_store(row) for row in grocery_store_records(payload)]
    encoded_locations = json.dumps(
        safe_locations,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    # JSON is inert inside this script type, but escaping '<' also prevents a
    # source string from terminating the script element.
    encoded = encoded.replace("<", "\\u003c")
    encoded_locations = encoded_locations.replace("<", "\\u003c")
    return (
        '<!doctype html><html><body><script type="application/json">'
        f'{encoded}</script><script type="application/ld+json">'
        f"{encoded_locations}</script></body></html>"
    ).encode()


def product_json_ld(payload: bytes) -> dict[str, Any]:
    """Select one public JSON-LD Product or fail closed on ambiguity."""

    products: list[dict[str, Any]] = []
    for root in json_scripts(payload, script_type="application/ld+json"):
        for row in _walk(root):
            kind = row.get("@type")
            kinds = {str(item) for item in kind} if isinstance(kind, list) else {str(kind)}
            if "Product" in kinds:
                products.append(row)
    if len(products) != 1:
        raise CoopSchemaError(
            f"Coop product detail must contain exactly one JSON-LD Product, got {len(products)}"
        )
    return products[0]


def product_sitemap_urls(payload: bytes) -> tuple[str, ...]:
    """Parse Coop's public product sitemap without treating URLs as priced rows."""

    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise CoopSchemaError("Coop product sitemap is not valid XML") from exc
    urls: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "loc" or not element.text:
            continue
        value = element.text.strip()
        if not value.startswith("https://www.coop.se/handla/varor/"):
            raise CoopSchemaError("Coop product sitemap contains an unexpected URL")
        urls.append(value)
    if not urls:
        raise CoopSchemaError("Coop product sitemap contains no product URLs")
    if len(set(urls)) != len(urls):
        raise CoopSchemaError("Coop product sitemap contains duplicate product URLs")
    return tuple(urls)


_SOURCE_ID_SUFFIX = re.compile(r"-(?P<source_id>\d{8}|\d{12,14})/?$")


def source_id_from_product_url(url: str) -> str | None:
    """Return Coop's URL suffix as a source ID, never as a claimed GTIN."""

    match = _SOURCE_ID_SUFFIX.search(url)
    return match.group("source_id") if match else None


@dataclass(frozen=True, slots=True)
class RenderedProductCard:
    href: str | None
    aria_label: str


class _RenderedCatalogCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._article_depth = 0
        self._body_parts: list[str] = []
        self.cards: list[RenderedProductCard] = []
        self.page_numbers: set[int] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.casefold(): value or "" for name, value in attrs}
        if tag.casefold() == "article":
            self._article_depth += 1
        normalized_tag = tag.casefold()
        if normalized_tag not in {"a", "button"}:
            return
        href = attributes.get("href", "")
        aria_label = attributes.get("aria-label", "")
        is_product_link = normalized_tag == "a" and href.startswith("/handla/varor/")
        is_offer_button = normalized_tag == "button" and bool(aria_label)
        if self._article_depth and aria_label and (is_product_link or is_offer_button):
            self.cards.append(RenderedProductCard(href=href or None, aria_label=aria_label))
        page_match = re.search(r"[?&]page=(\d+)(?:&|$)", href)
        if page_match:
            self.page_numbers.add(int(page_match.group(1)))

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "article" and self._article_depth:
            self._article_depth -= 1

    def handle_data(self, data: str) -> None:
        self._body_parts.append(data)

    @property
    def body_text(self) -> str:
        return " ".join("".join(self._body_parts).split())


@dataclass(frozen=True, slots=True)
class RenderedCatalogPage:
    cards: tuple[RenderedProductCard, ...]
    declared_total: int | None
    page_numbers: tuple[int, ...]
    store_external_id: str | None = None
    store_page_path: str | None = None
    captured_total: int | None = None
    capture_evidence: str | None = None


_DECLARED_TOTAL = re.compile(r"(?P<count>\d[\d\s]*)\s+(?:varor|sökresultat)\b", re.IGNORECASE)


def rendered_catalog_page(payload: bytes) -> RenderedCatalogPage:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CoopSchemaError("Coop rendered catalogue HTML is not UTF-8") from exc
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CoopSchemaError("Coop rendered-card envelope is invalid JSON") from exc
        if not isinstance(envelope, dict) or not isinstance(envelope.get("cards"), list):
            raise CoopSchemaError("Coop rendered-card envelope is missing cards")
        cards: list[RenderedProductCard] = []
        for item in envelope["cards"]:
            if not isinstance(item, dict):
                raise CoopSchemaError("Coop rendered-card envelope contains a non-object card")
            href = item.get("href")
            aria_label = item.get("aria_label")
            if href is not None and (
                not isinstance(href, str) or not href.startswith("/handla/varor/")
            ):
                raise CoopSchemaError("Coop rendered-card envelope contains an invalid href")
            if not isinstance(aria_label, str) or not aria_label.strip():
                raise CoopSchemaError("Coop rendered-card envelope contains an invalid label")
            cards.append(RenderedProductCard(href=href, aria_label=aria_label.strip()))
        if not cards:
            raise CoopSchemaError("Coop rendered-card envelope contains no cards")
        declared_total = envelope.get("declared_total")
        if declared_total is not None and (
            isinstance(declared_total, bool)
            or not isinstance(declared_total, int)
            or declared_total < 0
        ):
            raise CoopSchemaError("Coop rendered-card envelope has invalid declared_total")
        if declared_total is not None and len(cards) != declared_total:
            raise CoopSchemaError(
                "Coop rendered-card envelope is incomplete: "
                f"declared {declared_total}, captured {len(cards)}"
            )
        captured_total = envelope.get("captured_total")
        if (
            isinstance(captured_total, bool)
            or not isinstance(captured_total, int)
            or captured_total != len(cards)
        ):
            raise CoopSchemaError("Coop rendered-card envelope has invalid captured_total")
        capture_evidence = envelope.get("capture_evidence")
        if capture_evidence not in {"declared_total", "dom_stable"}:
            raise CoopSchemaError("Coop rendered-card envelope has invalid capture evidence")
        if (capture_evidence == "declared_total") != (declared_total is not None):
            raise CoopSchemaError("Coop rendered-card envelope has conflicting capture evidence")
        store_external_id = envelope.get("store_external_id")
        store_page_path = envelope.get("store_page_path")
        if not isinstance(store_external_id, str) or not store_external_id.strip():
            raise CoopSchemaError("Coop rendered-card envelope has no store identity")
        if not isinstance(store_page_path, str) or not store_page_path.startswith(
            "/butiker-erbjudanden/"
        ):
            raise CoopSchemaError("Coop rendered-card envelope has an invalid store path")
        return RenderedCatalogPage(
            cards=tuple(cards),
            declared_total=declared_total,
            page_numbers=(),
            store_external_id=store_external_id,
            store_page_path=store_page_path,
            captured_total=captured_total,
            capture_evidence=capture_evidence,
        )
    collector = _RenderedCatalogCollector()
    collector.feed(text)
    if not collector.cards:
        raise CoopSchemaError("Coop rendered catalogue page contains no semantic product cards")
    declared_match = _DECLARED_TOTAL.search(collector.body_text)
    declared_total = int(declared_match.group("count").replace(" ", "")) if declared_match else None
    return RenderedCatalogPage(
        cards=tuple(collector.cards),
        declared_total=declared_total,
        page_numbers=tuple(sorted(collector.page_numbers)),
    )
