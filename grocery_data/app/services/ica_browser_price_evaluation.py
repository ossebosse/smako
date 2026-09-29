"""Isolated adapter for a public browser SSR projection, not an HTTP collector.

Reuse the ICA online parser's identity, money and package rules. Unknown price
shapes or promotion fields cannot be silently relabelled as ordinary prices.
This module is deliberately absent from source registration and activation.
"""

from datetime import UTC, datetime

from grocery_data.app.connectors.ica.online_catalog_parser import IcaOnlineCatalogParser
from grocery_data.app.domain import Chain, CoverageLevel, PriceContextType, SourceStore


def adapt_public_browser_product(raw: dict) -> dict:
    """Convert the verified public UI shape to the existing online parser input."""
    allowed = {"productId", "retailerProductId", "name", "brand", "size", "price",
               "available", "isInCurrentCatalog", "categoryPath", "gtin", "ean"}
    if set(raw) - allowed:
        raise ValueError("unreviewed product or promotion schema")
    price = raw["price"]
    if set(price) != {"current", "unit"} or set(price["current"]) != {"amount", "currency"}:
        raise ValueError("ambiguous current/reference/member price")
    unit = price["unit"]
    if set(unit) != {"label", "current"} or set(unit["current"]) != {"amount", "currency"}:
        raise ValueError("ambiguous unit price schema")
    labels = {"fop.price.per.litre": "l", "fop.price.per.kg": "kg"}
    if unit["label"] not in labels or set(raw["size"]) != {"value"}:
        raise ValueError("unknown package/unit price semantics")
    if raw["available"] is not True or raw["isInCurrentCatalog"] is not True:
        raise ValueError("not currently purchasable in this online channel")
    adapted = {k: v for k, v in raw.items() if k not in {"price", "size"}}
    adapted.update(price=price["current"], packSizeDescription=raw["size"]["value"],
                   unitPrice={**unit["current"], "unit": labels[unit["label"]]})
    return adapted


def parse_public_browser_prices(document: dict) -> dict:
    if (document.get("schema") != "ica-browser-public-products-v1"
            or document.get("storeId") != "1088004"
            or document.get("channel") != "online_price"):
        raise ValueError("unverified browser store/channel/schema")
    captured = datetime.fromisoformat(document["capturedAt"])
    observed = datetime.fromtimestamp(document["sourceLastUpdated"] / 1000, UTC)
    if captured.tzinfo is None or observed > captured:
        raise ValueError("invalid browser observation times")
    store = SourceStore(
        chain=Chain.ICA, external_id="1088004", name="Maxi ICA Gunnesbo Online",
        city="Lund", online_shopping=True, coverage=CoverageLevel.PARTIAL_CATALOG,
        price_context_type=PriceContextType.ONLINE_STORE,
        physical_store_external_id="1088004",
        raw_reference="https://handlaprivatkund.ica.se/stores/1088004/search?q=mj%C3%B6lk",
        source_fields={"store_identifier_namespace": "official_browser_store_route"},
    )
    accepted, rejected, seen = [], [], set()
    for raw in document["products"]:
        identity = raw.get("retailerProductId")
        if identity in seen:
            raise ValueError("duplicate browser product identity")
        seen.add(identity)
        try:
            adapted = adapt_public_browser_product(raw)
            product = IcaOnlineCatalogParser().parse_product(
                adapted, store=store, reference=store.raw_reference, fetched_at=observed,
            )
            if product.package_quantity is None or product.package_unit is None:
                raise ValueError("unknown purchase package")
            accepted.append(product.model_copy(update={"source_fields": {
                **product.source_fields, "transport": "sanitized_browser_ssr_projection",
                "browser_captured_at": captured.isoformat(),
                "observation_basis": "source_search_state_lastUpdated_conservative_proxy",
                "shared_candidate_approved": False, "deposit_status": "not_verified",
                "catalog_complete": False,
            }}).model_dump(mode="json"))
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append({"retailer_product_id": identity, "reason": str(exc)})
    return {"store_id": "1088004", "channel": "online_price", "promoted": False,
            "observed_at": observed.isoformat(), "captured_at": captured.isoformat(),
            "fetched_count": len(document["products"]), "accepted_count": len(accepted),
            "rejected_count": len(rejected), "catalog_complete": False,
            "search_total_ids": document["totalProducts"],
            "products": accepted, "rejected": rejected}
