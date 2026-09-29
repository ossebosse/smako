"""Coop + X:-tra public registries, independent of existing price coverage."""
import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from grocery_data.app.connectors.coop.store_locator import CoopBrowserStoreLocatorTransport
from grocery_data.app.domain import SourceStore
from grocery_data.app.services.area_membership import assess_area
from grocery_data.app.services.municipality_geometry import bind_position, fetch_boundary

XTRA_URL = "https://x-tra.se/butiker"


def xtra_records(html):
    soup = BeautifulSoup(html, "html.parser")
    data = json.loads(soup.find("script", id="__NEXT_DATA__").string)["props"]["pageProps"]["data"]
    records = data["stores"]
    links = {a["href"].rstrip("/") for a in soup.select('a[href^="/butiker/"]')}
    result = []
    for row in records:
        if not row.get("slugId") or not row.get("id") or not row.get("ledgerAccountNumber"):
            raise ValueError("incomplete X:-tra registry record")
        path = "/butiker/" + row["slugId"]
        if path not in links:
            raise ValueError("X:-tra record absent from all-store link list")
        postal = re.search(r",\s*(\d{5})\s", row["address"])
        result.append({"storeId": row["id"], "ledgerAccountNumber": row["ledgerAccountNumber"],
                       "name": row["name"], "address": row["streetName"], "city": row["city"],
                       "postalCode": postal[1] if postal else None, "latitude": row.get("latitude"),
                       "longitude": row.get("longitude"), "url": "https://x-tra.se" + path,
                       "weeklyOffersLink": row.get("weeklyOffersLink"), "concept": "X:-tra"})
    if links != {"/butiker/" + urlsplit(r["url"]).path.split("/")[-1] for r in result}:
        raise ValueError("X:-tra visible/data registry totals disagree")
    return result


def make_store(row, source):
    path = row["url"]
    xtra = row.get("concept") == "X:-tra" or "x:-tra" in row["name"].casefold()
    concept = "X:-tra" if xtra else "Stora Coop" if row["name"].startswith("Stora Coop") else "Coop"
    if not xtra and (not path.startswith("/butiker-erbjudanden/") or urlsplit(path).netloc):
        raise ValueError("unexpected Coop store URL")
    return SourceStore(chain="coop", external_id=str(row["storeId"]), name=row["name"],
        address=row.get("address"), city=row.get("city"), postal_code=row.get("postalCode"),
        latitude=row.get("latitude"), longitude=row.get("longitude"), coverage="offers_only",
        price_context_type="physical_store", physical_store_external_id=str(row["storeId"]),
        raw_reference=source["url"], source_fields={"concept": concept,
            "source_id_namespace": "coop-public-store-registry", "ledger_account_number": str(row["ledgerAccountNumber"]),
            "official_store_url": path if path.startswith("https://") else "https://www.coop.se" + path,
            "store_page_path": None if xtra else path, "offers_url": row.get("weeklyOffersLink") if xtra else "https://www.coop.se"+path,
            "coordinate_source": source, "discovery_sources": [source], "aliases": []})


def build_inventory(area, coop, xtra, boundary, sources):
    if area.mode != "municipality":
        raise ValueError("explicit municipality mode required")
    by_ledger = {}
    for rows, source in ((coop, sources[0]), (xtra, sources[1])):
        for raw in rows:
            store = bind_position(make_store(raw, source), boundary)
            ledger = store.source_fields["ledger_account_number"]
            prior = by_ledger.get(ledger)
            if prior:
                # Official common ledger plus exact source ID and address is
                # the alias proof. Similar names/positions alone never merge.
                key = lambda s: (s.external_id, re.sub(r"\W", "", s.address or "").casefold())
                if key(prior) != key(store):
                    fields = {**store.source_fields, "identity_conflict": True,
                              "conflicting_record": prior.model_dump(mode="json")}
                    store = store.model_copy(update={"source_fields": fields})
                else:
                    fields = {**store.source_fields,
                              "aliases": [prior.name, *prior.source_fields.get("aliases", [])],
                              "discovery_sources": [*prior.source_fields["discovery_sources"], source]}
                    if assess_area(prior, area)["status"] != assess_area(store, area)["status"]:
                        fields["municipality_evidence_conflict"] = True
                    store = store.model_copy(update={"source_fields": fields})
            by_ledger[ledger] = store
    records = []
    for store in by_ledger.values():
        geo = assess_area(store, area)
        reason = "included_verified_municipality"
        eligible = geo["status"] == "inside" and not store.source_fields.get("identity_conflict")
        if not eligible:
            reason = "identity_conflict" if store.source_fields.get("identity_conflict") else geo["reason"]
        is_xtra = store.source_fields["concept"] == "X:-tra"
        records.append({"store": store.model_dump(mode="json"), "geographic_evidence": geo,
                        "collection_selected": eligible and not is_xtra,
                        "collection_reason": "xtra_document_text_requires_separate_contract" if eligible and is_xtra else reason,
                        "beta_status": "not_activated_by_this_run"})
    return {"area": area.model_dump(mode="json"), "sources": sources,
            "registry_rows": {"coop": len(coop), "xtra": len(xtra)},
            "discovered_physical_stores": len(records), "complete": False,
            "completeness_reason": "all_rows_of_published_registries_processed; no_independent_total_of_all_municipal_businesses",
            "stores": records,
            "selected_store_ids": sorted(r["store"]["external_id"] for r in records if r["collection_selected"])}


async def discover(area, output):
    output.mkdir(parents=True, exist_ok=False)
    boundary = await fetch_boundary(area.municipality_code)
    (output / "boundary.json").write_text(json.dumps(boundary, ensure_ascii=False), encoding="utf-8")
    raw = await CoopBrowserStoreLocatorTransport().fetch_national(area.city)
    (output / "coop-map.json").write_text(raw.model_dump_json(indent=2), encoding="utf-8")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(XTRA_URL)
        response.raise_for_status()
    xtra = xtra_records(response.text)
    source_xtra = {"url": XTRA_URL, "sha256": hashlib.sha256(response.content).hexdigest(),
                   "observed_at": datetime.now(UTC).isoformat()}
    # Save public store facts only, not framework settings or image payloads.
    (output / "xtra-registry.json").write_text(json.dumps({"source": source_xtra, "stores": xtra}, ensure_ascii=False), encoding="utf-8")
    sources = [{"url": raw.url, "sha256": raw.payload_hash, "observed_at": raw.fetched_at.isoformat()}, source_xtra]
    report = build_inventory(area, json.loads(raw.payload)["stores"], xtra, boundary, sources)
    (output / "inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
