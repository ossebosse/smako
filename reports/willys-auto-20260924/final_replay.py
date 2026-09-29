import asyncio,json
from pathlib import Path
from grocery_data.app.domain import RawBatch
from grocery_data.scripts.collect_willys_flyers import collect
async def main():
 r=Path('reports/willys-auto-20260924')
 for code in ('1281','1280'):
  inv=json.loads((r/f'inventory-{code}/inventory.json').read_bytes())
  live=r/f'live-collection-{code}';report=json.loads((live/'coverage.json').read_bytes())
  raws={s['store_id']:RawBatch.model_validate_json((live/s['store_id']/'source.json').read_bytes()) for s in report['stores']}
  result=await collect(inv,list(raws),r/f'collection-final-{code}',raw_by_store=raws)
  print('FINAL REPLAY',code,[(s['store_id'],s['status'],s.get('own')) for s in result['stores']])
asyncio.run(main())
