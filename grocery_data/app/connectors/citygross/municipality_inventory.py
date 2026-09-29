"""Official national City Gross inventory and shared municipal selection.

Store numbers are online contexts, site IDs are physical stores. The two public
registers establish their exact relationship; fetched catalog rows must still
prove their own store number before any prices can be accepted.
"""
from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from grocery_data.app.connectors.citygross.client import CityGrossClient
from grocery_data.app.domain import GeographicArea, RawBatch, SourceStore
from grocery_data.app.services.area_membership import approved_municipal_stores, assess_area
from grocery_data.app.services.municipality_geometry import (
    bind_position,
    fetch_boundary,
    validate_boundary,
)

OFFICIAL_ROOT = "https://www.citygross.se"
REGISTRY_PATHS = {"stores": "/api/v1/PageData/stores", "store_number_map": "/api/v1/sites"}


def _source(document):
    return {"url": document.url, "sha256": document.payload_hash,
            "observed_at": document.fetched_at.isoformat()}


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _registry(raw, references):
    if raw.chain.value != "citygross":
        raise ValueError("City Gross registry chain required")
    documents = {}
    for document, reference in raw.with_references(references):
        if document.kind not in REGISTRY_PATHS:
            continue
        location = urlsplit(document.url)
        if (document.kind in documents or document.http_status != 200
                or location.scheme != "https" or location.netloc != "www.citygross.se"
                or location.path != REGISTRY_PATHS[document.kind]):
            raise ValueError("one successful official document per City Gross register required")
        documents[document.kind] = (document, reference)
    if set(documents) != set(REGISTRY_PATHS):
        raise ValueError("both official national City Gross registers required")
    rows = documents["stores"][0].json_payload()
    site_data = documents["store_number_map"][0].json_payload()
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing national store rows")
    if not isinstance(site_data, dict) or not isinstance(site_data.get("sites"), list):
        raise TypeError("missing national site mapping")
    if documents["store_number_map"][0].query.get("siteTypeId") != "3":
        raise ValueError("physical-store site type must be explicit")
    return documents, rows, site_data["sites"]


def build_inventory(area, raw, references, boundary):
    """Keep all published rows; never infer municipality from a store's name."""
    if area.mode != "municipality" or boundary["municipality_code"] != area.municipality_code:
        raise ValueError("municipality/boundary mismatch")
    validate_boundary(boundary)
    documents, rows, site_rows = _registry(raw, references)
    sites = {}
    for position, site in enumerate(site_rows):
        if isinstance(site, dict) and site.get("id") is not None:
            sites.setdefault(str(site["id"]), []).append((position, site))
    number_counts = Counter(str(s.get("storeNumber") or "") for s in site_rows if isinstance(s, dict))
    page_ids = Counter(str(r.get("data", {}).get("siteId") or "") for r in rows
                       if isinstance(r, dict) and isinstance(r.get("data"), dict))
    records, unresolved = [], []
    used_sites = set()
    for position, entry in enumerate(rows):
        row = entry.get("data") if isinstance(entry, dict) else None
        if not isinstance(row, dict):
            unresolved.append({"row_index": position, "status": "unknown", "reason": "invalid_store_row"})
            continue
        name = str(row.get("storeName") or row.get("name") or "").strip()
        site_id = str(row.get("siteId") or "").strip()
        if not name or not site_id:
            unresolved.append({"row_index": position, "site_id": site_id, "name": name,
                               "status": "unknown", "reason": "missing_store_identity_or_name"})
            continue
        matches = sites.get(site_id, [])
        used_sites.update(i for i, _ in matches)
        site = matches[0][1] if len(matches) == 1 else {}
        number = str(site.get("storeNumber") or "").strip()
        reason = ("duplicate_physical_store_identity" if page_ids[site_id] != 1 else
                  "ambiguous_site_mapping" if len(matches) > 1 else
                  "missing_site_mapping" if not matches else
                  "missing_store_number" if not number else
                  "invalid_store_number" if not number.isascii() or not number.isdigit() else
                  "ambiguous_store_number" if number_counts[number] != 1 else None)
        address = row.get("address") if isinstance(row.get("address"), dict) else {}
        location = row.get("storeLocation") if isinstance(row.get("storeLocation"), dict) else {}
        coordinates = str(location.get("coordinates") or "").split(",")
        latitude = _number(coordinates[0].strip()) if len(coordinates) == 2 else None
        longitude = _number(coordinates[1].strip()) if len(coordinates) == 2 else None
        store_url = urljoin(OFFICIAL_ROOT, str(row.get("url") or ""))
        if urlsplit(store_url).netloc != "www.citygross.se":
            reason = reason or "unofficial_store_url"
        external_id = number if not reason else f"unresolved-site:{site_id}:{position}"
        store = SourceStore(
            chain="citygross", external_id=external_id, name=name,
            address=str(address.get("streetAddress") or "").strip() or None,
            postal_code="".join(str(address.get("zipCode") or "").split()) or None,
            city=str(address.get("city") or "").strip() or None,
            latitude=latitude, longitude=longitude,
            online_shopping=True if reason is None else None,
            coverage="full_online_catalog" if reason is None else "partial_catalog",
            price_context_type="online_store" if reason is None else None,
            physical_store_external_id=site_id,
            raw_reference=f"{documents['stores'][1]}#row={position}",
            source_fields={
                "concept": "City Gross", "site_id": site_id, "store_number": number or None,
                "cms_id": row.get("id"), "provider": site.get("provider"),
                "store_page_url": store_url, "official_store_url": store_url,
                "catalog_url": OFFICIAL_ROOT + "/api/v1/Loop54/products",
                "source_id_namespace": "citygross-official-store-number",
                "coordinate_source": _source(documents["stores"][0]),
                "discovery_sources": [_source(d) for d, _ in documents.values()],
                "identity_conflict": reason is not None,
                "identity_reason": reason,
                "price_context_type": "online_store" if reason is None else None,
                "physical_store_external_id": site_id,
                "fulfillment_type": None,
                "price_context_verified": reason is None,
                "catalog_context_evidence": "official_exact_site_store_number_mapping;catalog_rows_must_match",
                "registry_row_index": position,
            },
        )
        store = bind_position(store, boundary)
        geo = assess_area(store, area)
        selected = geo["status"] == "inside" and reason is None
        records.append({"store": store.model_dump(mode="json"), "geographic_evidence": geo,
                        "collection_selected": selected,
                        "collection_reason": reason or ("verified_municipal_catalog_context" if selected else geo["reason"]),
                        "collection_status": "not_collected", "beta_status": "not_activated"})
    unresolved_sites = [{"row_index": i, "source_row": site, "status": "unknown",
                         "reason": "site_missing_from_store_pages"}
                        for i, site in enumerate(site_rows) if i not in used_sites]
    return {"schema": "citygross-municipal-inventory-v1", "area": area.model_dump(mode="json"),
            "sources": [_source(d) for d, _ in documents.values()],
            "registry": raw.model_dump(mode="json"), "boundary": boundary,
            "stores": records, "registry_rows": len(rows), "site_registry_rows": len(site_rows),
            "unresolved_registry_rows": unresolved, "unresolved_site_rows": unresolved_sites,
            "selected_store_ids": sorted(r["store"]["external_id"] for r in records if r["collection_selected"]),
            "complete": False, "published_registry_processed": True,
            "completeness_reason": "all_published_rows_processed;unknown_rows_retained;no_independent_municipal_business_total",
            "price_channel": "online_store;not_verified_physical_shelf_prices"}


def approved_citygross_stores(inventory):
    """Recompute membership and store mapping from retained official evidence."""
    if inventory.get("schema") != "citygross-municipal-inventory-v1":
        raise ValueError("unsupported City Gross municipality inventory")
    raw = RawBatch.model_validate(inventory["registry"])
    area = GeographicArea.model_validate(inventory["area"])
    rebuilt = build_inventory(area, raw, [f"retained:{i}" for i in range(len(raw.documents))], inventory["boundary"])
    approved = approved_municipal_stores(rebuilt, concepts=("City Gross",))
    original = approved_municipal_stores(inventory, concepts=("City Gross",))
    if set(approved) != set(original) or sorted(approved) != inventory["selected_store_ids"]:
        raise ValueError("saved City Gross municipal selection differs from official evidence")
    for key, store in original.items():
        expected = approved[key]
        if store.model_dump(exclude={"raw_reference"}) != expected.model_dump(exclude={"raw_reference"}):
            raise ValueError("saved City Gross identity differs from official evidence")
    return approved


async def discover(area, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = CityGrossClient(allow_full_crawl=False, max_pages=1)
    try:
        raw = await client.fetch_stores()
    finally:
        await client.aclose()
    (output / "registry.json").write_text(raw.model_dump_json(indent=2), encoding="utf-8")
    boundary = await fetch_boundary(area.municipality_code)
    (output / "boundary.json").write_text(json.dumps(boundary, ensure_ascii=False), encoding="utf-8")
    inventory = build_inventory(area, raw, [f"registry:{i}" for i in range(len(raw.documents))], boundary)
    (output / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    return inventory
