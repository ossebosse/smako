"""Separate OWN-only independence probe, NEVER the complete Lund candidate."""
import asyncio,os,json,time,hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from job import configure,save
configure();P=Path('/work');root=P/'physical-probe';root.mkdir(exist_ok=True)
from grocery_data.app.services.ica_offer_job import structured_source_inputs
from grocery_data.app.services import coop_offer_job,citygross_municipal_job,lidl_municipal_job,willys_flyer_job
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore,validate_backend_prepared_universe_artifact
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
from app.services.production_price_universe_build import build_city_price_universe
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from deploy.scripts.backup_sqlite import _backup_database
async def main():
 before=(P/'price-universes/active/city-lund.json');before_hash=hashlib.sha256(before.read_bytes()).hexdigest() if before.exists() else None
 options=structured_source_inputs(city='Lund',root=P/'ica-structured')
 for module in [coop_offer_job,citygross_municipal_job,lidl_municipal_job,willys_flyer_job]:options.update(module.source_inputs(city='Lund'))
 candidate=root/'candidate.json';start=time.monotonic()
 with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')):
  with TemporaryDirectory(dir=root) as temp:
   closed=Path(temp)/'grocery.sqlite';_backup_database(P/'grocery.sqlite',closed)
   result=await build_city_price_universe(closed,'Lund','22350',None,candidate,48,**options)
  artifact=PreparedPriceUniverseArtifact.model_validate_json(candidate.read_bytes())
  required=tuple(s.store_id for s in artifact.stores if s.source_provenance and s.source_provenance.source_channel=='catalog')
  store=PreparedUniverseArtifactStore(root/'price-universes')
  activation=store.activate(candidate,city='Lund',validator=lambda data,city:validate_backend_prepared_universe_artifact(data,city,required_context_ids=required,max_price_age_hours=48))
  rows=[p.model_dump(mode='json') for p in artifact.universe.products]
  proof={'scope':'INDEPENDENT OWN-ONLY PROBE. Missing mandatory Primat context is not waived for the full Lund candidate. HTTP requests restrict to verified physical offers.','build':result,'activation':str(activation),'seconds':time.monotonic()-start,'required_own_contexts':required,'products_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'products':len(rows),'full_candidate_manifest_unchanged':before_hash==(hashlib.sha256(before.read_bytes()).hexdigest() if before.exists() else None),'external_requests':0}
  (root/('build-'+str(time.time_ns())+'.json')).write_text(json.dumps(proof,ensure_ascii=False,indent=2,default=str))
  (root/'scope-settings.json').write_text(json.dumps({'required_context_ids':required,'scope':proof['scope']}))
  print(result.get('status'),len(rows),activation.status)
asyncio.run(main())
