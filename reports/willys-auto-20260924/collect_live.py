import asyncio,json
from pathlib import Path
from grocery_data.app.connectors.willys.flyer_inventory import build_inventory,approved_flyer_stores
from grocery_data.app.connectors.willys.flyer_offers import AutomaticWillysFlyerConnector
from grocery_data.app.domain import GeographicArea,RawBatch
from grocery_data.scripts.collect_willys_flyers import collect
R=Path(__file__).parent
async def run():
 fresh=json.loads((R/'inventory-1281/inventory.json').read_bytes())
 old=json.loads((R.parent/'willys-flyers-20260923/inventory-1280/inventory.json').read_bytes())
 malmo=build_inventory(GeographicArea.model_validate(old['area']),fresh['registry'],old['boundary'])
 (R/'inventory-1280').mkdir(exist_ok=True)
 (R/'inventory-1280/inventory.json').write_text(json.dumps(malmo,ensure_ascii=False),encoding='utf-8')
 for inv in (fresh,malmo):
  code=inv['area']['municipality_code'];folder=R/f'live-collection-{code}'
  if not folder.exists():
   result=await collect(inv,approved_flyer_stores(inv),folder)
   print('LIVE',code,[(s['store_id'],s['status'],s.get('own'),s.get('reason')) for s in result['stores']],result['external_price_requests'],flush=True)
  identity='2863' if code=='1281' else '2352'
  raw=RawBatch.model_validate_json((folder/identity/'source.json').read_bytes())
  AutomaticWillysFlyerConnector.allow_legacy_review=False
  try:result=await collect(inv,[identity],R/f'automatic-only-{code}',raw_by_store={identity:raw})
  finally:AutomaticWillysFlyerConnector.allow_legacy_review=True
  print('AUTO ONLY REPLAY',code,[(s['store_id'],s['status'],s.get('own'),s.get('reason')) for s in result['stores']],flush=True)
asyncio.run(run())
