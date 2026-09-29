"""Actual publisher rejection of missing usable mandatory base; separate empty root."""
import json,hashlib
from pathlib import Path
from datetime import datetime,UTC,timedelta
from job import configure,save
configure();P=Path('/work')
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore,validate_backend_prepared_universe_artifact
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
source=PreparedUniverseArtifactStore(P/'price-universes')
f=source.resolve_active_artifact('Lund',verify_hash=True);raw=f.read_bytes()
policy=json.loads((P/'policy.json').read_bytes());required=tuple(policy['required_context_ids'])
base=required[0];payload=json.loads(raw);count=0
for product in payload['universe']['products']:
 if product['store_id']==base:
  product['source_provenance']['source_observed_at']=(datetime.now(UTC)-timedelta(hours=49)).isoformat();count+=1
assert count>0
from app.models.product import Product
from app.services.price_universe import _products_digest
payload['universe']['products_digest']=_products_digest([Product.model_validate(x) for x in payload['universe']['products']])
root=P/('mandatory-fault-'+datetime.now(UTC).strftime('%H%M%S'));root.mkdir(exist_ok=False)
candidate=root/'candidate.json';candidate.write_text(json.dumps(payload))
store=PreparedUniverseArtifactStore(root/'price-universes')
assert store.active_manifest_bytes('Lund') is None
try:
 store.activate(candidate,city='Lund',validator=lambda p,c:validate_backend_prepared_universe_artifact(p,c,required_context_ids=required,max_price_age_hours=48))
except Exception as exc:
 result={'error':type(exc).__name__,'reason':str(exc)}
else:raise AssertionError('mandatory invalid base accepted')
print(result,flush=True)
save('mandatory-fault-attempt',result)
assert 'required usable contexts' in result['reason'] and base in result['reason']
assert store.active_manifest_bytes('Lund') is None and f.read_bytes()==raw
save('mandatory-fault',{'scope':'Actual atomic publisher/authoritative validation, fresh copied artifact with injected 49h-old mandatory Coop observations; no LKG, no source fetch, no change to main candidate. This is admission fault injection, not a live retailer outage.','required_context':base,'injected_rows':count,'result':result,'active_manifest_absent':True,'main_artifact_unchanged':True,'external_requests':0})
print('mandatory base rejected',result)
