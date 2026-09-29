"""One read-only store-resolution request to explain the failed identity gate."""
import asyncio
from dataclasses import asdict
from pathlib import Path
from job import configure,save
configure()
from app.services.production_primat_refresh import _primat_primary_contexts
from app.services.primat_frozen_cache_collect import revalidate_primat_contexts
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from scripts.benchmark_lund_phase_c import _BoundedPrimatProvider
async def main():
 eligible=_primat_primary_contexts(Path('/work/grocery.sqlite'),city='Lund',max_age_hours=48)
 provider=_BoundedPrimatProvider.load(exact_contexts=frozenset((r.chain.value,r.provider_context_id) for r in eligible),max_requests=1,context_bootstrap=True)
 try:
  resolution=await provider.resolve_store_candidates('22350');discovery=primat_store_discovery_bundle(resolution);save('primat-current-store-discovery',discovery.model_dump(mode='json'));rows=[]
  for old in eligible:
   current=[r for r in discovery.items if r.provider_context_id==old.provider_context_id]
   try:revalidate_primat_contexts(resolution,(old,),city='Lund');reason=None
   except ValueError as exc:reason=str(exc)
   rows.append({'persisted':old.model_dump(mode='json'),'current':[r.model_dump(mode='json') for r in current],'accepted':reason is None,'reason':reason})
  save('primat-identity-check',{'scope':'one real stores/resolve request; no price requests or identity writes','transport':provider.transport_report,'resolution_city':resolution.place_city,'resolution_hash':resolution.response_sha256,'observed_at':resolution.observed_at,'rows':rows});print([(r['persisted']['provider_context_id'],r['accepted'],r['reason']) for r in rows])
 finally:await provider.aclose()
asyncio.run(main())
