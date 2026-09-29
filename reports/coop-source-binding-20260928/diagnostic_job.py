import asyncio
import json
from pathlib import Path

from grocery_data.app.connectors.coop import structured_offers as source
from grocery_data.scripts.collect_coop_physical_offers import collect

P = Path('/work')
prior = Path('/prior/coop-municipal/1281/attempts/20260928T070313-cfce2f18c7f5/structured/sources/1158-store.json')
store = json.loads(prior.read_bytes())
original = source.sanitized_response
findings = []

def diagnose(payload):
    def walk(row, path):
        known = {*source._ROW_KEYS, 'priceInformation', 'content', 'clusterInteriorOffers',
                 'otherLogos', 'unifiedSplash', 'categoryGroup', 'categoryTeam'}
        for label, value, keys in [('', row, known),
                ('.priceInformation', row.get('priceInformation', {}), set(source._PRICE_KEYS)),
                ('.content', row.get('content', {}), {*source._CONTENT_KEYS, 'imageUrl', 'enrichedComparisonPrice'})]:
            for key in sorted(set(value) - keys):
                findings.append({'path':path+label+'.'+key, 'type':type(value[key]).__name__, 'value':value[key]})
        for index, child in enumerate(row.get('clusterInteriorOffers', [])):
            walk(child, path+f'.clusterInteriorOffers[{index}]')
    for gi, group in enumerate(payload['sortingGroups']):
        for ri, row in enumerate(group['offers']):
            walk(row, f'sortingGroups[{gi}].offers[{ri}]')
    (P/'schema-diagnostic.json').write_text(json.dumps({'store':store['external_id'],
        'unknown_fields':findings}, ensure_ascii=False, indent=2))
    return original(payload)  # Original gate remains in place during diagnosis.

source.sanitized_response = diagnose
result = asyncio.run(collect({'stores':[{'store':store}]}, {'1158'}, P/'diagnostic'))
print(json.dumps({'findings':findings[:12], 'unknown_occurrences':len(findings),
    'stores':[{k:r.get(k) for k in ['store_id','status','own','error_type']} for r in result['stores']]}))
