"""Physical flyer selection alongside, without changing, online selection."""
from pathlib import Path
from urllib.parse import urlsplit

from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.willys.municipality_inventory import (
    build_inventory as online_inventory,
)
from grocery_data.app.domain import GeographicArea, RawBatch, SourceStore
from grocery_data.app.services.coop_offer_job import write
from grocery_data.app.services.municipality_geometry import fetch_boundary


def build_inventory(area, registry, boundary):
    raw = RawBatch.model_validate(registry)
    result = online_inventory(area, raw, [d.url for d in raw.documents], boundary)
    source = {str(r.get('storeId')): r for r in raw.documents[0].json_payload() if isinstance(r, dict)}
    for row in result['stores']:
        store = row['store']
        original = source[store['external_id']]
        url = original.get('flyerURL', '')
        parsed = urlsplit(url)
        valid = (parsed.scheme == 'https' and parsed.netloc == 'reklamblad.willys.se'
                 and parsed.path.rstrip('/') == '/willys/' + store['external_id'] and not parsed.query)
        selected = row['geographic_evidence']['status'] == 'inside' and original.get('open') is True and valid
        # This optional feed targets the gap; existing online catalog collection
        # keeps its original independent selection and transport.
        selected = selected and store['online_shopping'] is False
        row['online_collection_selected'] = row['collection_selected']
        row['collection_selected'] = selected
        row['collection_reason'] = ('verified_official_flyer' if selected else
            'online_catalog_retained_separately' if store['online_shopping'] is True else
            'official_flyer_or_open_status_unverified' if row['geographic_evidence']['status'] == 'inside'
            else row['geographic_evidence']['reason'])
        store.update(coverage='offers_only', price_context_type='physical_store')
        store['source_fields'].update(official_store_url=url, flyer_url=url,
            source_id_namespace='willys:storeId', online_catalog_available=store['online_shopping'])
    result.update(schema='willys-flyer-municipal-v1', registry=registry, boundary=boundary,
        price_channel='physical_store_flyer', selected_store_ids=sorted(
            r['store']['external_id'] for r in result['stores'] if r['collection_selected']))
    return result


def approved_flyer_stores(inventory):
    if inventory.get('schema') != 'willys-flyer-municipal-v1':
        raise ValueError('unsupported Willys flyer inventory')
    rebuilt = build_inventory(GeographicArea.model_validate(inventory['area']), inventory['registry'], inventory['boundary'])
    if rebuilt != inventory:
        raise ValueError('flyer inventory differs from official evidence')
    return {r['store']['external_id']: SourceStore.model_validate(r['store'])
            for r in rebuilt['stores'] if r['collection_selected']}


async def discover(area, output, *, registry=None, boundary=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    if registry is None:
        client = WillysClient()
        try:
            registry = (await client.fetch_stores()).model_dump(mode='json')
        finally:
            await client.aclose()
    boundary = boundary or await fetch_boundary(area.municipality_code)
    result = build_inventory(area, registry, boundary)
    write(output / 'inventory.json', result)
    return result
