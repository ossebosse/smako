import asyncio,json
from pathlib import Path
from prove_automatic import purchases
from app.services.production_price_universe_build import build_city_price_universe
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.personal_source_facts import load_retained_facts
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
R=Path(__file__).parent
async def main():
 for code,city,postal in [('1281','Lund','22223'),('1280','Malmö','21120')]:
  root=R/f'runtime-{code}';collection=R/f'collection-final-{code}'
  if code=='1281':
   inv=json.loads((collection/'inventory.json').read_bytes());report=json.loads((collection/'coverage.json').read_bytes())
   sources=[dict(database=collection/s['database'],store_ids=[s['store_id']],snapshot_ids=[s['snapshot_id']],inventory=inv) for s in report['stores']]
   path=collection/'prepared-inactive.json'
   build=await build_city_price_universe(database=root/'grocery.sqlite',city=city,postal_code=postal,external_cache=None,output=path,max_price_age_hours=48,willys_flyer_enabled=True,willys_flyer_sources=sources)
   (collection/'build-inactive.json').write_text(json.dumps(build,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  else:path=PreparedUniverseArtifactStore(root/'price-universes').resolve_active_artifact(city,verify_hash=True)
  prepared=PreparedPriceUniverseArtifact.model_validate_json(path.read_bytes()).restore()
  facts=load_retained_facts(prepared,database=root/'grocery.sqlite',raw_root=root/'raw')
  fly=[p for p in prepared.universe.products if p.chain=='willys' and p.source_provenance.source_channel=='offers']
  assert all(facts.get((p.store_id,p.product_id)) is None for p in fly)
  rows=purchases(prepared)
  report={'scope':'published isolated ordinary instance' if code=='1280' else 'validated inactive candidate; full publication blocked by missing fresh complete base',
    'price_universe_products':len(fly),'source_facts_exact_links':0,'nutrition_approval_added':False,'network_requests':0,'rows':rows}
  (root/'purchases-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  print(code,len(fly),'PU',sum(x['audit_passed'] for x in rows),'passed food purchases',len(rows),'tested')
asyncio.run(main())
