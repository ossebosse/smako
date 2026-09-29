"""ICA area inventory/coverage on existing locator, parser and OWN collector.

Explicit caller-owned staging only. No scheduler installation or production
activation. Store-scoped collection prevents an optional shop from replacing
the city LKG or blocking other shops.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import AsyncRateLimiter, RetryPolicy, bounded_request
from grocery_data.app.connectors.ica import IcaConnector
from grocery_data.app.connectors.ica.models import initial_data_from_html
from grocery_data.app.domain import Chain, GeographicArea, RawBatch, SourceStore
from grocery_data.app.services.area_membership import (
    LOCALITY_PROVENANCE,
    MUNICIPALITY_PROVENANCE,
    area_membership,
    assess_area,
    reuse_municipality_evidence,
)
from grocery_data.app.services.official_store_discovery import stable_physical_store_id

AREA_PROVENANCE = LOCALITY_PROVENANCE


def inventory_counts(batch: RawBatch, stores: list[SourceStore]) -> dict:
    totals, source_rows = set(), 0
    for doc in batch.documents:
        root = initial_data_from_html(doc.payload).get("resultStore", {})
        source_rows += len(root.get("storeCards", []))
        total = next((root[k] for k in ("totalNrOfStores", "totalNumberOfStores", "total")
                      if isinstance(root.get(k), int)), None)
        if total is not None:
            totals.add(total)
    declared = next(iter(totals)) if len(totals) == 1 else None
    return {"source_declared": declared, "source_rows": source_rows,
            "discovered": len(stores), "pages_fetched": len(batch.documents),
            "complete": declared is not None and declared == len(stores)}


def offer_store_proposal(coverage: dict) -> dict:
    """Review input from complete verified inventory, independent of prices.

    A proposal is deliberately not a runtime setting or an activation command.
    Failed collection does not remove an otherwise verified physical store.
    """
    counts = coverage.get("inventory", {})
    approved = counts.get("complete") is True
    if coverage.get("area", {}).get("mode") == "municipality":
        approved = approved and counts.get("municipality_complete") is True
    rows = coverage.get("stores", [])
    ids = sorted({r["ica_account_id"] for r in rows
                  if approved and r.get("area_membership") == "inside"
                  and r.get("area_reason") in {"official_address_locality_matches_existing_area",
                                            "verified_address_municipality_matches"}})
    return {"ica_offer_store_ids": ids, "inventory_approved": approved,
            "area_provenance": coverage.get("area_provenance", AREA_PROVENANCE), "production_activation": False,
            "review_required": True, "discovered": len(rows),
            "unknown": sum(r.get("area_membership") == "unknown" for r in rows)}


def coverage_drift(previous: dict, current: dict) -> dict:
    old = {r["ica_account_id"]: r for r in previous.get("stores", [])}
    new = {r["ica_account_id"]: r for r in current.get("stores", [])}
    return {
        "new_stores": sorted(new.keys() - old.keys()),
        "not_seen_stores": sorted(old.keys() - new.keys()),
        "changed_sources": sorted(k for k in old.keys() & new.keys()
                                  if (old[k].get("offers_url"), old[k].get("flyer_links")) !=
                                  (new[k].get("offers_url"), new[k].get("flyer_links"))),
        "collection_regressions": sorted(k for k in old.keys() & new.keys()
                                         if old[k].get("collection_status") == "success"
                                         and new[k].get("collection_status") != "success"),
        "coverage_regressions": {
            metric: sorted(k for k in old.keys() & new.keys()
                           if isinstance(old[k].get(metric), int)
                           and isinstance(new[k].get(metric), int)
                           and new[k][metric] < old[k][metric])
            for metric in ("own_active", "price_universe_products", "planning_qualified_products")
        },
    }


class _RetainedStoreConnector(IcaConnector):
    def __init__(self, connector, store, locator, offers):
        super().__init__(client=connector.client, parser=connector.parser)
        self.store, self.locator, self.offers = store, locator, offers

    async def fetch_stores(self, area):
        return self.locator

    def parse_stores(self, raw, references, area):
        return [self.store]

    async def fetch_catalog(self, store):
        return self.offers

    async def aclose(self):
        # The area operation owns the shared transport, not a retained replay.
        pass


class RowApprovedOfferConnector(_RetainedStoreConnector):
    """Same raw fetch, separate explicit offers-only acceptance contract."""
    row_acceptance = None

    def parse_catalog(self, raw, references, store):
        from grocery_data.app.services.ica_flyer_pipeline import reconcile_flyer_products
        from grocery_data.app.services.offer_rows import qualify_rows

        parsed = super().parse_catalog(raw, references, store)
        original_parsed = parsed
        parsed, self.flyer_reconciliation = reconcile_flyer_products(parsed)
        result, self.row_acceptance = qualify_rows(
            parsed, store=store, observed_at=max(d.fetched_at for d in raw.documents), original_parsed=original_parsed)
        return result


def source_page_inventory(pages: list[dict]) -> dict:
    """The reader supplies empty spread slots before/after the actual book.

    Exclude only explicit empty boundary objects; never shrink the page count
    for a missing interior page, absent fields or unrecognized content.
    """
    empty = [i for i, page in enumerate(pages) if i in {0, len(pages)-1}
             and page == {'files': [], 'elements': []}]
    missing = [i for i, page in enumerate(pages) if i not in empty and not page.get('files')]
    return {'source_spread_slots': len(pages), 'expected_document_pages': len(pages)-len(empty),
            'verified_empty_boundary_slots': empty, 'missing_content_slots': missing,
            'pages': [{'slot': i, 'files': p.get('files'), 'elements': p.get('elements'),
                       'classification': 'empty_boundary' if i in empty else 'missing_content' if i in missing else 'published_page'}
                      for i, p in enumerate(pages)]}


class PublicFlyerReader:
    """e-magin's public reader protocol, discovered from its published JS.

    Only linked title/issue IDs are followed. All editions returned for a title
    and every PDF page are retained. PDF text remains review evidence, not
    automatically associated prices or guessed campaign dates.
    """
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30, follow_redirects=False)
        self.limiter = AsyncRateLimiter(1)
        self.cache = {}

    async def get(self, url):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc not in {"api.e-magin.se", "emaginstatic.b-cdn.net"}:
            raise ValueError("unverified flyer API URL")
        response = await bounded_request(self.client, self.limiter, RetryPolicy(), "GET", url)
        if response.status_code in {301, 302, 303, 307, 308}:
            destination = response.headers.get("location", "")
            target = urlsplit(destination)
            if (parsed.netloc != "api.e-magin.se" or target.scheme != "https"
                    or target.netloc != "emaginstatic.b-cdn.net"):
                raise ValueError("unverified flyer redirect")
            response = await bounded_request(self.client, self.limiter, RetryPolicy(), "GET", destination)
        response.raise_for_status()
        return response

    async def read(self, url: str, output: Path) -> dict:
        if url in self.cache:
            return self.cache[url]
        result = {"url": url, "status": "unsupported_source", "editions": [],
                  "campaign_parsing": "requires_review", "campaign_count": None}
        match = re.fullmatch(r"https://www\.e-magin\.se/(latestpaper|paper)/([a-z0-9]+)/paper(?:/\d+)?/?", url)
        if not match:
            return result
        try:
            kind, key = match.groups()
            if kind == "latestpaper":
                definition_url = f"https://api.e-magin.se/api/fusion/def/latestpaper/{key}"
                definition = (await self.get(definition_url)).json()
                editions = [p for t in definition.get("titles", []) for p in t.get("papers", [])]
            else:
                definition_url = url
                editions = [{"id": key}]
            result["source_editions"] = len(editions)
            for edition in editions:
                issue_id = edition["id"]
                if not re.fullmatch("[a-z0-9]+", issue_id):
                    raise ValueError("invalid public issue ID")
                issue_url = f"https://api.e-magin.se/api/fusion/issue/{issue_id}"
                issue = (await self.get(issue_url)).json()
                page_evidence = source_page_inventory(issue['pages'])
                declared = page_evidence['expected_document_pages']
                supplements = []
                for slot in page_evidence['missing_content_slots']:
                    elements = issue['pages'][slot].get('elements', [])
                    if not elements:
                        continue  # A missing content page still blocks completeness.
                    assets = []
                    for element in elements:
                        if element.get('type') != 'image':
                            continue
                        asset_url = element.get('uri', '')
                        response = await self.get(asset_url)
                        digest = hashlib.sha256(response.content).hexdigest()
                        suffix = '.png' if response.content.startswith(b'\x89PNG') else '.jpg' if response.content.startswith(b'\xff\xd8') else None
                        if not suffix:
                            raise ValueError('unrecognized supplemental image type')
                        asset_path = output / ('flyer-asset-' + digest + suffix)
                        if not asset_path.exists():
                            asset_path.write_bytes(response.content)
                        assets.append({'url':asset_url,'sha256':digest,'file':asset_path.name,
                                       'observed_at':datetime.now(UTC).isoformat()})
                    supplements.append({'reader_slot':slot,'elements':elements,'assets':assets,
                        'complete':all(e.get('type') in {'image','text','link'} for e in elements)
                            and sum(e.get('type')=='image' for e in elements)==len(assets),
                        'price_extraction':'requires_layout_review'})
                (output / f"flyer-{issue_id}-source-pages.json").write_text(json.dumps({
                    "id": issue_id, "name": issue.get("name"), "declared_pages": declared,
                    **page_evidence}, ensure_ascii=False, indent=2), encoding="utf8")
                pdf_url = f"https://api.e-magin.se/api/pdf/{issue_id}/download"
                pdf = await self.get(pdf_url)
                if not pdf.content.startswith(b"%PDF"):
                    raise ValueError("flyer is not a PDF")
                path = output / f"flyer-{issue_id}.pdf"
                if path.exists() and path.read_bytes() != pdf.content:
                    raise ValueError("same issue changed during collection; retained PDF preserved")
                if not path.exists():
                    path.write_bytes(pdf.content)
                from pypdf import PdfReader
                pages = PdfReader(io.BytesIO(pdf.content)).pages
                text_pages = [p.extract_text() for p in pages]
                (output / f"flyer-{issue_id}-text.json").write_text(
                    json.dumps(text_pages, ensure_ascii=False, indent=2), encoding="utf8")
                result["editions"].append({
                    "id": issue_id, "title": issue.get("name"), "definition_url": definition_url,
                    "issue_url": issue_url, "pdf_url": pdf_url, "source_pages": declared,
                    "fetched_pages": len(pages), "text_pages": sum(bool(t.strip()) for t in text_pages),
                    "complete": declared == len(pages)+len(supplements)
                        and all(s['complete'] for s in supplements)
                        and len(supplements)==len(page_evidence['missing_content_slots']),
                    "supplemental_pages": supplements,
                    "source_spread_slots": len(issue['pages']),
                    "verified_empty_boundary_slots": page_evidence['verified_empty_boundary_slots'],
                    "period_status": "unknown_requires_review",
                    "sha256": hashlib.sha256(pdf.content).hexdigest(), "file": path.name,
                    "fetched_at": datetime.now(UTC).isoformat(),
                })
            result["status"] = ("success" if editions and all(e["complete"] for e in result["editions"])
                                else "incomplete")
        except Exception as exc:  # noqa: BLE001 - retain explicit partial flyer failure
            result["status"] = "error"
            result["error"] = type(exc).__name__
            if isinstance(exc, httpx.HTTPStatusError):
                result["http_status"] = exc.response.status_code
        self.cache[url] = result
        return result


async def enrich_municipality_addresses(stores, area, connector, output, *, max_queries=8):
    """Discover missing administrative fields, never infer membership from URL.

    ICA map cards omit fields present in full locality cards. An official store
    URL is only a bounded discovery hint. Exact account AND address must agree
    before the full address municipality evidence can be reused.
    """
    from grocery_data.app.connectors.ica.parser import _location_key

    queries = sorted({s.city for s in stores if s.city and s.city != area.city
        and not s.source_fields.get("municipality")
        and urlsplit(str(s.source_fields.get("official_store_url", ""))).hostname == "www.ica.se"
        and f"/{_location_key(area.city)}/" in str(s.source_fields.get("official_store_url", ""))})
    evidence = {"queries_discovered": queries, "query_budget": max_queries,
                "queries": [], "unqueried": queries[max_queries:]}
    by_id = {s.external_id: s for s in stores}
    for index, locality in enumerate(queries[:max_queries]):
        entry = {"locality": locality, "updated_ids": [], "conflicting_ids": []}
        evidence["queries"].append(entry)
        try:
            batch = await connector.fetch_physical_stores(GeographicArea(city=locality))
            refs = []
            for page, doc in enumerate(batch.documents):
                name = f"municipality-address-{index}-{page}.json"
                (output / name).write_bytes(doc.payload)
                refs.append(name)
            rows = connector.parser.parse_physical_stores(batch, refs,
                GeographicArea(city=locality), include_outside=True)
            entry.update(status="success", source_urls=[d.url for d in batch.documents],
                observed_at=max(d.fetched_at for d in batch.documents).isoformat())
            for candidate in rows:
                old = by_id.get(candidate.external_id)
                if old is None or not candidate.source_fields.get("municipality"):
                    continue
                if (old.address, old.postal_code) != (candidate.address, candidate.postal_code):
                    entry["conflicting_ids"].append(candidate.external_id)
                    continue
                if not old.source_fields.get("municipality"):
                    fields = dict(old.source_fields)
                    for key in ("municipality", "address_municipality_evidence"):
                        fields[key] = candidate.source_fields[key]
                    by_id[old.external_id] = old.model_copy(update={"source_fields": fields})
                    entry["updated_ids"].append(old.external_id)
        except Exception as exc:  # noqa: BLE001 - retain failed optional address evidence
            entry.update(status="error", error=type(exc).__name__)
            evidence["unqueried"].extend(queries[index+1:max_queries])
            break  # no repeated blocked transport under another locality
    return list(by_id.values()), evidence


async def collect_area_offers(area: GeographicArea, output: Path, *, collector=None,
                              connector=None, collect_flyers=True, previous=None,
                              inventory_only=False, row_approved_offers=False, approved_flyer_batches=None,
                              only_store_ids=None, discover_flyers=True, municipality_reference_stores=()) -> dict:
    if (previous and previous.get("area", {}).get("city") is not None
            and str(previous["area"]["city"]).casefold() != area.city.casefold()):
        raise ValueError("cannot retain coverage across different geographic areas")
    if previous and previous.get("area", {}).get("mode", "locality") != area.mode:
        raise ValueError("cannot retain coverage across different geographic modes")
    if previous and previous.get("area", {}).get("municipality_code") != area.municipality_code:
        raise ValueError("cannot retain coverage across different municipalities")
    output.mkdir(parents=True, exist_ok=False)
    connector = connector or IcaConnector()
    reader = PublicFlyerReader()
    report = {"schema": "ica-area-offers-v1", "area": area.model_dump(mode="json"),
              "area_provenance": (MUNICIPALITY_PROVENANCE if area.mode == "municipality" else AREA_PROVENANCE),
              "boundary": "official_address_municipality" if area.mode == "municipality" else "official_address_locality",
              "generated_at": datetime.now(UTC).isoformat(), "production_activation": False,
              "inventory": {}, "stores": []}
    try:
        try:
            locator = await connector.fetch_physical_stores(area)
        except ConnectorFetchError as exc:
            locator = exc.partial_batch
            report["inventory_error"] = type(exc.__cause__).__name__
            report['inventory_failure_evidence'] = [
                {'url': d.url, 'observed_at': d.fetched_at.isoformat(), 'http_status': d.http_status,
                 'sanitized_response': d.payload.decode('utf8')} for d in locator.documents]
        good = tuple(d for d in locator.documents if d.http_status == 200)
        locator = locator.model_copy(update={"documents": good})
        for i, doc in enumerate(good):
            (output / f"locator-{i}.json").write_bytes(doc.payload)
        stores = connector.parser.parse_physical_stores(
            locator, [f"locator-{i}.json" for i in range(len(good))], area, include_outside=True)
        report["inventory"] = inventory_counts(locator, stores)
        if area.mode == "municipality":
            stores, report["municipality_address_enrichment"] = await enrich_municipality_addresses(
                stores, area, connector, output)
        if report.get("inventory_error"):
            report["inventory"]["complete"] = False
        if area.mode == "municipality":
            report["inventory"].update(municipality_complete=False,
                completeness_reason="locator_result_count_is_not_independent_municipality_coverage_proof")
        for store in stores:
            store = reuse_municipality_evidence(store, list(municipality_reference_stores), area)
            membership, reason = area_membership(store, area)
            row = {"physical_store_id": stable_physical_store_id(Chain.ICA, store.external_id),
                   "store": store.model_dump(mode="json"),
                   "ica_account_id": store.external_id, "ica_bms_id": store.source_fields.get("store_id"),
                   "other_provider_ids": {}, "name": store.name, "address": store.address,
                   "postal_code": store.postal_code, "locality": store.city,
                   "latitude": str(store.latitude) if store.latitude else None,
                   "longitude": str(store.longitude) if store.longitude else None,
                   "official_store_url": store.source_fields.get("official_store_url"),
                   "offers_url": store.source_fields.get("offers_url"),
                   "discovery_sources": [d.url for d in good],
                   "discovered_at": max(d.fetched_at for d in good).isoformat(),
                   "area_membership": membership, "area_reason": reason,
                   "geographic_evidence": assess_area(store, area),
                   "collection_status": "not_requested_outside_area", "last_success_at": None,
                   "error": None, "flyer_links": [], "flyers": [], "source_offer_count": None,
                   "fetched": None, "parsed": None, "rejected": None, "deduplicated": None,
                   "own_active": None, "price_universe_products": None,
                   "planning_qualified_products": None, "planning_status": "not_evaluated"}
            report["stores"].append(row)
            if inventory_only:
                row["collection_status"] = "not_requested_inventory_only"
                continue
            if membership != "inside":
                continue
            previous_row = next((r for r in (previous or {}).get('stores', [])
                                 if r['ica_account_id'] == store.external_id), None)
            # The locator can omit a link already verified on the same official
            # store page. Retain that source binding until its scheduled check;
            # an unrelated due store must not trigger fresh price requests here.
            if (only_store_ids is not None and store.external_id not in only_store_ids
                    and previous_row and not row['offers_url']
                    and previous_row.get('offers_url')
                    and all(row.get(k) == previous_row.get(k) for k in
                            ['official_store_url', 'address', 'postal_code', 'locality'])
                    and row['official_store_url']
                    and urlsplit(previous_row['offers_url']).netloc == 'www.ica.se'
                    and urlsplit(previous_row['offers_url']).path.rstrip('/').endswith('-' + store.external_id)):
                row['offers_url'] = previous_row['offers_url']
                store = store.model_copy(update={'source_fields': {
                    **store.source_fields, 'offers_url': row['offers_url']}})
                row['store'] = store.model_dump(mode='json')
            if (only_store_ids is not None and store.external_id not in only_store_ids
                    and previous_row and previous_row.get('offers_url') == row['offers_url']):
                row.update({k: v for k, v in previous_row.items() if k not in {
                    'discovered_at', 'discovery_sources', 'area_membership', 'area_reason',
                    'name', 'address', 'postal_code', 'locality', 'official_store_url', 'offers_url',
                    'store', 'geographic_evidence'}})
                row['collection_status'] = 'not_due_retained'
                continue
            try:
                if not row["offers_url"] and row["official_store_url"]:
                    document = await connector.client.fetch_public_page(row["official_store_url"], store_id=store.external_id)
                    links = json.loads(document.payload)
                    matches = [u for u in links.get("offers_links", [])
                               if urlsplit(u).path.rstrip("/").endswith("-" + store.external_id)]
                    if len(matches) == 1:
                        row["offers_url"] = matches[0]
                        store = store.model_copy(update={"source_fields": {
                            **store.source_fields, "offers_url": matches[0]}})
                    row["flyer_links"].extend(links.get("flyer_links", []))
                if not row["offers_url"]:
                    row["collection_status"] = "missing_integration"
                    continue
                batch = await connector.fetch_catalog(store)
                (output / f'offers-{store.external_id}-batch.json').write_text(
                    batch.model_dump_json(), encoding='utf8')
                for i, doc in enumerate(batch.documents):
                    (output / f"offers-{store.external_id}-{i}.json").write_bytes(doc.payload)
                    row["flyer_links"].extend(initial_data_from_html(doc.payload).get("public_links", {}).get("flyer_links", []))
                parsed = connector.parse_catalog(batch, [f"offers-{store.external_id}-{i}.json" for i in range(len(batch.documents))], store)
                count = sum(len(connector.parser.weekly_offer_rows(initial_data_from_html(d.payload))) for d in batch.documents)
                row.update(source_offer_count=count, fetched=count, parsed=len(parsed.products),
                           rejected=len(parsed.failures),
                           deduplicated=count-len(parsed.products)-len(parsed.failures),
                           collection_status="confirmed_empty" if count == 0 else "success",
                           last_success_at=max(d.fetched_at for d in batch.documents).isoformat(),
                           campaign_windows=[{'valid_from': p.offers[0].valid_from.isoformat() if p.offers[0].valid_from else None,
                                              'valid_to': p.offers[0].valid_to.isoformat() if p.offers[0].valid_to else None}
                                             for p in parsed.products if p.offers],
                           rejection_reasons=dict(Counter(f.error_message for f in parsed.failures)),
                           periods=dict(Counter("future" if p.offers[0].valid_from and p.offers[0].valid_from > datetime.now(UTC).date()
                                                else "expired" if p.offers[0].valid_to and p.offers[0].valid_to < datetime.now(UTC).date()
                                                else "current_observed" for p in parsed.products)))
                if collector is not None:
                    retained = _RetainedStoreConnector(connector, store, locator, batch)
                    result = await collector.collect_area(retained, area, auto_promote=not row_approved_offers,
                                                         scope_key=f"{area.city.casefold()}:ica:{store.external_id}:offers")
                    row["own_result"] = {"snapshot_id": result.snapshot_id,
                                         "promoted": result.promoted, "status": result.status.value,
                                         "metrics": result.metrics.model_dump(mode="json"),
                                         "warnings": list(result.warnings)}
                    row["own_active"] = result.metrics.products_parsed if result.promoted else 0
                    if row_approved_offers:
                        extras = (approved_flyer_batches or {}).get(store.external_id, [])
                        # Reverify official store -> linked edition -> exact PDF
                        # before a retained review can enter the normal pipeline.
                        if extras:
                            page = await connector.client.fetch_public_page(row['official_store_url'], store_id=store.external_id)
                            row['flyer_links'].extend(json.loads(page.payload)['flyer_links'])
                            verified = [await reader.read(url, output) for url in set(row['flyer_links'])]
                            editions = [e for f in verified for e in f['editions'] if e.get('complete')]
                            accepted_extras = []
                            row['flyer_review_rejections'] = []
                            for extra in extras:
                                evidence = extra.documents[0].json_payload()['review_evidence']
                                if any(e['id'] == evidence['issue_id'] and e['sha256'] == evidence['pdf_sha256']
                                       and e['pdf_url'] == evidence['source_url'] for e in editions):
                                    accepted_extras.append(extra)
                                else:
                                    row['flyer_review_rejections'].append({'evidence': evidence,
                                        'reason': 'current_official_store_edition_hash_not_verified'})
                            extras = accepted_extras
                        combined = batch.model_copy(update={"documents": (
                            *batch.documents, *(d for b in extras for d in b.documents))})
                        retained_rows = RowApprovedOfferConnector(connector, store, locator, combined)
                        retained_rows.original_full_health = result.status.value
                        partial = await collector.collect_area(retained_rows, area, auto_promote=True,
                            scope_key=f"{area.city.casefold()}:ica:{store.external_id}:offer-rows")
                        row["row_approved_result"] = {
                            "snapshot_id": partial.snapshot_id, "published": partial.promoted,
                            "full_health": result.status.value,
                            "row_only_health_assessment": partial.status.value,
                            "metrics": partial.metrics.model_dump(mode="json"),
                            "acceptance": retained_rows.row_acceptance,
                            "flyer_reconciliation": retained_rows.flyer_reconciliation,
                        }
                        row["row_approved_own"] = partial.metrics.products_parsed if partial.promoted else 0
            except Exception as exc:  # noqa: BLE001 - optional stores fail independently
                row["collection_status"], row["error"] = "error", type(exc).__name__
            try:
                if discover_flyers and row["official_store_url"]:
                    doc = await connector.client.fetch_public_page(row["official_store_url"], store_id=store.external_id)
                    (output / f"store-page-{store.external_id}.json").write_bytes(doc.payload)
                    row["flyer_links"].extend(json.loads(doc.payload)["flyer_links"])
                row["flyer_links"] = sorted(set(row["flyer_links"]))
                if collect_flyers:
                    row["flyers"] = [await reader.read(url, output) for url in row["flyer_links"]]
            except Exception as exc:  # noqa: BLE001 - flyers cannot block structured collection
                row["flyer_discovery_error"] = type(exc).__name__
        if previous:
            current_ids = {r['ica_account_id'] for r in report['stores']}
            for old in previous.get('stores', []):
                if old['ica_account_id'] not in current_ids:
                    report['stores'].append({**old, 'inventory_status': 'not_seen_in_current_inventory',
                        'collection_status': 'unknown_current_inventory_failed_or_store_removed',
                        'own_active': 0, 'row_approved_own': 0, 'row_approved_result': None,
                        'price_universe_products': None, 'planning_qualified_products': None,
                        'flyers': [], 'error': report.get('inventory_error', 'not_seen'),
                        'last_success_at': old.get('last_success_at')})
                    report['inventory']['complete'] = False
        report["area_counts"] = dict(Counter(r["area_membership"] for r in report["stores"]))
        inside = [r for r in report["stores"] if r["area_membership"] == "inside"]
        report["coverage"] = {"inventory": report["inventory"], "in_area_denominator": len(inside),
                              "collection_success_stores": sum(r["collection_status"] == "success" for r in inside),
                              "planning_coverage": None, "planning_status": "not_evaluated"}
        if previous:
            report["drift"] = coverage_drift(previous, report)
            old = {r["ica_account_id"]: r for r in previous.get("stores", [])}
            for row in report["stores"]:
                if row["last_success_at"] is None:
                    row["last_success_at"] = old.get(row["ica_account_id"], {}).get("last_success_at")
        (output / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
        return report
    finally:
        await connector.aclose()
        await reader.client.aclose()
