import asyncio,json
from pathlib import Path
from grocery_data.app.connectors.hemkop import HemkopConnector
async def main():
 c=HemkopConnector.for_bounded_discovery()
 try:
  from grocery_data.app.domain import RawFetch
  d=RawFetch.model_validate_json(Path('/work/hemkop-offers-probe.json').read_bytes())
  Path('/work/hemkop-offers-probe.json').write_text(d.model_dump_json())
  v=d.json_payload();print('keys',list(v));print('pagination',v.get('pagination'));print('binding',json.dumps({k:v[k] for k in ['currentQuery','facets','breadcrumbs']},ensure_ascii=True)[:9000]);print('rows',[(r.get('name'),r.get('displayVolume'),[(p.get('mainProductCode'),p.get('productCodes'),p.get('realMixAndMatch')) for p in r.get('potentialPromotions',[])]) for r in v.get('results',[])])
 finally:await c.aclose()
asyncio.run(main())
