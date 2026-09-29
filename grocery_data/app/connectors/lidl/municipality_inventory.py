"""Published national Lidl sitemap, existing detail parser and shared SCB scope."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from grocery_data.app.connectors.lidl.client import LidlClient
from grocery_data.app.connectors.lidl.models import sanitized_store_detail, validated_store_detail
from grocery_data.app.domain import GeographicArea, RawFetch, SourceStore
from grocery_data.app.services.area_membership import assess_area
from grocery_data.app.services.municipality_geometry import bind_position, fetch_boundary

SITEMAP = "https://www.lidl.se/s/sv-SE/butiker/sitemap.xml"
DETAIL = re.compile(r"https://www\.lidl\.se/s/sv-SE/butiker/[^/]+/[^/]+/$")


def detail_urls(document):
    if document.url != SITEMAP or document.http_status != 200:
        raise ValueError("official successful national sitemap required")
    urls = [n.text for n in ElementTree.fromstring(document.payload).iter() if n.tag.endswith('}loc')]
    details = [u for u in urls if u and DETAIL.fullmatch(u)]
    if not details or len(details) != len(set(details)):
        raise ValueError("empty or duplicate Lidl sitemap")
    return sorted(details)


async def fetch_registry(output, *, sitemap=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = LidlClient()
    try:
        sitemap = sitemap or await client._request(SITEMAP, kind="national_store_sitemap")
        registry = {"sitemap": sitemap.model_dump(mode="json"), "details": []}
        for url in detail_urls(sitemap):
            try:
                raw = await client._request(url, kind="store_detail",
                    sanitizer=lambda payload, source: sanitized_store_detail(payload, source_url=source))
                record = {"url": url, "status": "success", "raw": raw.model_dump(mode="json")}
            except Exception as exc:  # noqa: BLE001 - retain every discovered failed store
                record = {"url": url, "status": "failed", "reason": type(exc).__name__}
                if hasattr(exc, "raw"):
                    record["raw"] = exc.raw.model_dump(mode="json")
                registry["details"].append(record)
                if type(exc).__name__ in {"LidlAccessChallenge", "LidlRateLimitStop"}:
                    # No further blocked calls without new evidence.
                    break
                continue
            registry["details"].append(record)
            (output / "registry-progress.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        seen = {r['url'] for r in registry['details']}
        registry['details'].extend({"url": u, "status": "not_attempted", "reason": "transport_stopped"}
                                   for u in detail_urls(sitemap) if u not in seen)
        (output / "registry.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        return registry
    finally:
        await client.aclose()


def build_inventory(area, registry, boundary):
    if area.mode != 'municipality' or boundary['municipality_code'] != area.municipality_code:
        raise ValueError('explicit matching municipality required')
    urls = detail_urls(RawFetch.model_validate(registry['sitemap']))
    if sorted(r['url'] for r in registry['details']) != urls:
        raise ValueError('all sitemap details including failures must be retained exactly once')
    prepared = []
    for record in registry['details']:
        reason = record.get('reason')
        row = {}
        if record['status'] == 'success':
            raw = RawFetch.model_validate(record['raw'])
            if raw.url != record['url'] or raw.http_status != 200:
                raise ValueError('store evidence URL mismatch')
            try:
                row = validated_store_detail(raw.payload)
            except ValueError as exc:
                reason = "store_detail_unverifiable:" + type(exc).__name__
            if row and row['canonical_url'] != record['url']:
                raise ValueError('store canonical identity mismatch')
        prepared.append((record, row, reason))
    counts = Counter(r['external_id'] for _, r, _ in prepared if r)
    stores = []
    for record, row, reason in prepared:
        identity = row.get('external_id') or 'unresolved:' + hashlib.sha256(record['url'].encode()).hexdigest()[:16]
        if row and counts[identity] != 1:
            reason = 'duplicate_official_identity'
        raw_source = record.get('raw', {})
        store = SourceStore(chain='lidl', external_id=identity,
            name=row.get('name', record['url']), address=row.get('address'), city=row.get('city'),
            postal_code=row.get('postal_code'), latitude=row.get('latitude'), longitude=row.get('longitude'),
            coverage='offers_only', price_context_type='physical_store', physical_store_external_id=identity,
            raw_reference=record['url'], source_fields={'concept': 'Lidl',
                'official_store_url': record['url'], 'canonical_url': record['url'],
                'source_id_namespace': row.get('id_namespace'), 'identity_stability': row.get('id_stability'),
                'identity_conflict': bool(reason), 'identity_reason': reason,
                'coordinate_source': {'url': record['url'], 'sha256': raw_source.get('payload_hash'),
                                      'observed_at': raw_source.get('fetched_at')}})
        store = bind_position(store, boundary)
        geo = assess_area(store, area)
        selected = geo['status'] == 'inside' and not reason
        stores.append({'store': store.model_dump(mode='json'), 'geographic_evidence': geo,
            'collection_selected': selected, 'collection_reason': reason or geo['reason'],
            'collection_status': 'pending_campaign_qualification' if selected else 'not_selected'})
    return {'schema': 'lidl-municipal-inventory-v1', 'area': area.model_dump(mode='json'),
        'registry': registry, 'boundary': boundary, 'stores': stores, 'registry_rows': len(urls),
        'selected_store_ids': sorted(r['store']['external_id'] for r in stores if r['collection_selected']),
        'published_registry_processed': True, 'complete': False,
        'completeness_reason': 'all_published_sitemap_stores;unknown_and_failed_retained'}


def approved_lidl_stores(inventory):
    if inventory.get('schema') != 'lidl-municipal-inventory-v1':
        raise ValueError('unsupported Lidl inventory')
    rebuilt = build_inventory(GeographicArea.model_validate(inventory['area']), inventory['registry'], inventory['boundary'])
    if rebuilt['stores'] != inventory['stores'] or rebuilt['selected_store_ids'] != inventory['selected_store_ids']:
        raise ValueError('saved Lidl selection differs from official evidence')
    return {r['store']['external_id']: SourceStore.model_validate(r['store']) for r in rebuilt['stores'] if r['collection_selected']}


async def discover(area, output, *, registry=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    registry = registry or await fetch_registry(output / 'national')
    boundary = await fetch_boundary(area.municipality_code)
    inventory = build_inventory(area, registry, boundary)
    (output / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False), encoding='utf-8')
    return inventory
