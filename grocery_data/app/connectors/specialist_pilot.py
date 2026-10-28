"""Explicit five-article public-page pilot; no discovery or default activation.

Responses go through RawFetch and the existing immutable snapshot store before
any qualification. Only non-script public text and Product JSON-LD are retained;
cookies, response headers, forms and executable/session state are discarded.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

from grocery_data.app.connectors.base import enforce_collection_policy
from grocery_data.app.connectors.http import AsyncRateLimiter
from grocery_data.app.domain.enums import Chain, SourcePolicy
from grocery_data.app.domain.raw import RawFetch
from grocery_data.app.domain.source_policy import SourceCollectionAudit

PILOT_PAGES = {
    Chain.PONGMARKET: {
        "BW0003": "https://pongmarket.se/tapiokamj%C3%B6l-400g-cock-brand-kina/",
        "PMSM0014": "https://pongmarket.se/tapioka-p%C3%A4rlor-sm%C3%A5-400g-cock-brand/",
        "PMSM0031": "https://pongmarket.se/mj%C3%B6l-klibbigt-ris-500g-xin-liang-kina/",
        "delivery": "https://pongmarket.se/v%C3%A5ra-leveranss%C3%A4tt/",
        "terms": "https://pongmarket.se/k%C3%B6pvillkor/",
    },
    Chain.MED24: {
        "9576": "https://www.med24.se/matvaror/mjoel-gryn-och-bakning/korn-och-gryn/paerlkorn-m-m/urtekram-food-paerlkorn-eko-400-g",
        "delivery": "https://www.med24.se/leverans",
    },
    Chain.EXTREMEFOOD: {
        "944": "https://www.extremefood.se/mexikansk_mat/944-maseca-vitt-mexikanskt-majsmjol-1kg.html",
        "delivery": "https://www.extremefood.se/content/1-delivery",
        "category": "https://www.extremefood.se/39-tortillas-mjoel-mm",
    },
}
_PUBLIC_SCHEMA_FIELDS = frozenset({
    "@context", "@type", "@id", "name", "description", "sku", "mpn", "gtin", "gtin8",
    "gtin12", "gtin13", "gtin14", "brand", "url", "image", "offers", "price",
    "priceCurrency", "priceValidUntil", "availability", "itemCondition", "priceSpecification",
    "valueAddedTaxIncluded", "unitCode", "unitText", "weight", "value", "seller",
    "eligibleQuantity", "minValue", "maxValue", "shippingDetails", "shippingRate",
    "shippingDestination", "addressCountry", "addressRegion", "postalCode",
})


def _public_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (value.startswith(("/", "https://")) and not parsed.query and not parsed.fragment
            and not parsed.username and not parsed.password
            and not any(word in parsed.path.lower() for word in (
                "checkout", "account", "login", "cart", "session", "token")))


def _public_schema(value):
    if isinstance(value, dict):
        return {key: _public_schema(child) for key, child in value.items()
                if key in _PUBLIC_SCHEMA_FIELDS and (key not in {"@id", "url", "image"}
                    or isinstance(child, str) and _public_url(child))}
    if isinstance(value, list):
        return [_public_schema(child) for child in value]
    return value


class _PublicPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.lines = []
        self.headings = []
        self.links = []
        self.schema = []
        self.script = []
        self.jsonld = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag not in {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area", "base", "embed"}:
            self.stack.append(tag)
        if tag == "script":
            self.jsonld = attributes.get("type", "").lower() == "application/ld+json"
            self.script = []
        if tag == "a":
            url = attributes.get("href", "")
            # Retain only ordinary public path links, never query/fragment state.
            if _public_url(url) and not any(t in self.stack for t in ("form", "template")):
                self.links.append(url)

    def handle_endtag(self, tag):
        if tag == "script" and self.jsonld:
            try:
                payload = json.loads("".join(self.script))
                def products(value):
                    if isinstance(value, list):
                        for child in value:
                            yield from products(child)
                    elif isinstance(value, dict):
                        types = value.get("@type", [])
                        if types == "Product" or isinstance(types, list) and "Product" in types:
                            yield _public_schema(value)
                        elif "@graph" in value:
                            yield from products(value["@graph"])
                self.schema.extend(products(payload))
            except (ValueError, TypeError):
                pass
        if tag == "script":
            self.jsonld = False
            self.script = []
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]

    def handle_data(self, data):
        if "script" in self.stack:
            if self.jsonld:
                self.script.append(data)
            return
        if any(t in self.stack for t in ("style", "noscript", "template", "svg", "form")):
            return
        text = " ".join(data.split())
        if text:
            self.lines.append(text)
            if "h1" in self.stack:
                self.headings.append(text)


def sanitize_public_html(payload: bytes) -> bytes:
    page = _PublicPage()
    page.feed(payload.decode("utf-8", errors="replace"))
    return json.dumps({
        "schema": "smako-sanitized-public-page-v1",
        "transport_body_sha256": sha256(payload).hexdigest(),
        "headings": page.headings, "text_lines": page.lines,
        "product_json_ld": page.schema, "public_links": sorted(set(page.links)),
        "retention": "Non-script public text and whitelisted product schema; no forms, executable state, headers or cookies",
    }, ensure_ascii=False, separators=(",", ":")).encode()


class SpecialistPilotClient:
    source_policy = SourcePolicy.REVIEW
    connector_version = "specialist-five-article-public-pages-v1"

    def __init__(self, chain: Chain, *, operator_opt_in: bool = False, client=None):
        if chain not in PILOT_PAGES:
            raise ValueError("Chain is outside the approved five-article pilot")
        self.chain = chain
        self.operator_opt_in = operator_opt_in
        self.client = client
        self.limiter = AsyncRateLimiter(0.1)
        self.stopped = False

    def collection_policy_audit(self):
        return SourceCollectionAudit(source_policy=self.source_policy,
            operator_opt_in=self.operator_opt_in, store_allowlist=("se-dry-delivery-pilot",),
            requests_per_second=0.1, max_concurrency=1)

    async def fetch(self, page_id: str) -> RawFetch:
        enforce_collection_policy(self)
        if self.stopped:
            raise ValueError("Source stopped after access restriction or rate limit")
        if page_id not in PILOT_PAGES[self.chain]:
            raise ValueError("Page is outside the reviewed public allowlist")
        url = PILOT_PAGES[self.chain][page_id]
        await self.limiter.wait()
        owned = self.client is None
        client = self.client or httpx.AsyncClient(timeout=25, follow_redirects=False,
                                                 headers={"User-Agent": "Smako-source-review/1.0"})
        try:
            # Redirects are retained as failures for review, never followed to an
            # unreviewed URL. No session jar or headers survive this operation.
            async with client.stream("GET", url, follow_redirects=False) as response:
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > 2 * 1024 * 1024:
                        raise ValueError("Public source response exceeds the pilot bound")
                status = response.status_code
                restricted = status in {401, 403, 429} or any(marker in payload.lower() for marker in (
                    b"cf-chl-", b"verify you are human", b"checking your browser", b"captcha challenge"))
                if restricted:
                    self.stopped = True
                    safe = json.dumps({"access_stopped": True, "http_status": status}).encode()
                elif not 200 <= status < 300:
                    safe = json.dumps({"http_status": status, "usable_product_evidence": False}).encode()
                else:
                    safe = sanitize_public_html(bytes(payload))
                return RawFetch(chain=self.chain, store_external_id="se-dry-delivery-pilot",
                    kind="access_stopped" if restricted else "public_page", method="GET", url=url,
                    query={}, fetched_at=datetime.now(UTC), http_status=status,
                    content_type="application/json", payload=safe, connector_version=self.connector_version)
        finally:
            if owned:
                await client.aclose()
