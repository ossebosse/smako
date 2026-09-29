import asyncio
import json
from pathlib import Path
from job import configure, save
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.domain import GeographicArea
from grocery_data.app.services.ica_area_offers import collect_area_offers
from grocery_data.app.services.municipality_geometry import position_membership

async def main():
    configure()
    connector = HemkopConnector.for_bounded_discovery()
    try:
        raw = await connector.client.fetch_stores()
        save('hemkop-register-batch', raw.model_dump(mode='json'))
        result = {}
        rows = raw.documents[0].json_payload()
        for code, city in [('1281', 'Lund'), ('1280', 'Malmö')]:
            boundary = json.loads(Path('/evaluation/boundary-' + code + '.json').read_bytes())
            stores = []
            for row in rows:
                address = row.get('address') or {}; geo = row.get('geoPoint') or {}
                status, reason = position_membership(address.get('longitude') or geo.get('longitude'), address.get('latitude') or geo.get('latitude'), boundary)
                stores.append({'id': row.get('storeId'), 'name': row.get('name'), 'address': address, 'online': row.get('onlineStore'), 'status': status, 'reason': reason, 'fields': sorted(row)})
            result[code] = {'stores': stores, 'counts': {s: sum(r['status'] == s for r in stores) for s in ['inside','outside','unknown']}}
            coverage = await collect_area_offers(GeographicArea(city=city, mode='municipality', municipality_code=code), Path('/work/diagnostic-ica-' + code), inventory_only=True, collect_flyers=False, discover_flyers=False)
            print('ICA', code, coverage['area_counts'], [(r['name'], r['area_membership']) for r in coverage['stores']], flush=True)
        save('hemkop-inventory-diagnostic', result)
        print('Hemkop', {code: {'counts': v['counts'], 'inside': [r for r in v['stores'] if r['status']=='inside']} for code,v in result.items()}, flush=True)
    finally:
        await connector.aclose()

asyncio.run(main())
