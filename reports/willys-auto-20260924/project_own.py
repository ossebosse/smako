import asyncio,json,sys
from pathlib import Path
import httpx
from app.providers.own import OwnGroceryPriceProvider
from app.providers.willys_flyers import WillysFlyerProvider
from app.services.production_price_universe_build import _read_only_app
from grocery_data.app.storage import create_database_engine,create_session_factory
class Base:
 async def find_stores(self,_):return []
 def report(self):return {}
async def project(directory):
 root=Path(directory);inv=json.loads((root/'inventory.json').read_bytes());report=json.loads((root/'coverage.json').read_bytes());sources=[];engines=[];clients=[]
 for row in report['stores']:
  if row['status']!='success':continue
  db=root/row['database'];engine=create_database_engine('sqlite:///'+db.resolve().as_posix());engines.append(engine)
  client=httpx.AsyncClient(transport=httpx.ASGITransport(app=_read_only_app(create_session_factory(engine))),base_url='http://own.local');clients.append(client)
  own=OwnGroceryPriceProvider(base_url="http://own.local",client=client,include_offers_only=True,include_conditional_offer_products=True)
  own.campaign_snapshot_ids=frozenset([row['snapshot_id']])
  sources.append(dict(own=own,database=db,inventory=inv,store_ids=[row['store_id']],snapshot_ids=[row['snapshot_id']]))
 provider=WillysFlyerProvider(Base(),sources,allow_empty_base=True);stores=await provider.find_stores('22223');products=[p for v in provider.products.values() for p in v]
 print(json.dumps({'stores':len(stores),'products':len(products),'diagnostics':provider.diagnostics}))
 (root/'projected-products.json').write_text(json.dumps([p.model_dump(mode='json') for p in products],ensure_ascii=False),encoding='utf-8')
 for c in clients:await c.aclose()
 for e in engines:e.dispose()
 return products
if __name__=='__main__':asyncio.run(project(sys.argv[1]))

