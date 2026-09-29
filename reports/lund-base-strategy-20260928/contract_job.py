"""Single real resolution; retain only allowlisted public raw store contract fields."""
import asyncio,json,sqlite3,hashlib
from pathlib import Path
from job import configure,save
configure()
from app.services.production_primat_refresh import _primat_primary_contexts
from app.services.primat_frozen_cache_collect import revalidate_primat_contexts
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from scripts.benchmark_lund_phase_c import _BoundedPrimatProvider
async def main():
 eligible=_primat_primary_contexts(Path('/prior/grocery.sqlite'),city='Lund',max_age_hours=48)
 provider=_BoundedPrimatProvider.load(exact_contexts=frozenset((r.chain.value,r.provider_context_id) for r in eligible),max_requests=1,context_bootstrap=True)
 raw={};original=provider._request
 async def observed(method,path,**kwargs):
  payload=await original(method,path,**kwargs)
  if path=='/stores/resolve':
   fields=['chain','store_id','key','name','tier','coverage','selected','price_context_type']
   raw.update(default_selection=payload.get('default_selection'),stores=[{k:r[k] for k in fields if k in r} for r in payload.get('stores',[]) if str(r.get('store_id')) in {'1004409','1088004'}])
  return payload
 provider._request=observed
 try:
  resolution=await provider.resolve_store_candidates('22350');bundle=primat_store_discovery_bundle(resolution);rows=[]
  for old in eligible:
   candidate=next(r for r in bundle.items if r.provider_context_id==old.provider_context_id)
   try:revalidate_primat_contexts(resolution,(old,),city='Lund');reason=None
   except ValueError as exc:reason=str(exc)
   rows.append({'persisted':old.model_dump(mode='json'),'current':candidate.model_dump(mode='json'),'identity_fingerprint_equal':candidate.identity_fingerprint==old.verified_identity_fingerprint,'accepted':reason is None,'reason':reason})
  history={}
  with sqlite3.connect('file:/prior/grocery.sqlite?mode=ro',uri=True) as db:
   db.row_factory=sqlite3.Row
   history['identity_mapping']=[dict(r) for r in db.execute("select * from provider_store_identity_mappings where provider_store_id in ('1004409','1088004')")]
   history['context_link']=[dict(r) for r in db.execute("select * from store_context_links where grocery_context_id in ('primat:ica:1004409','primat:ica:1088004')")]
  save('primat-contract',{'raw_contract_fields':raw,'raw_capture_scope':'allowlisted actual source fields before parsing, never transport headers/credentials; absence of coverage retained as absence','response_sha256':resolution.response_sha256,'observed_at':resolution.observed_at,'transport':provider.transport_report,'comparisons':rows,'persisted_history':history,'original_policy_unchanged':True})
  print([(r['current']['provider_context_id'],r['current']['coverage'],r['identity_fingerprint_equal']) for r in rows])
 finally:await provider.aclose()
asyncio.run(main())
