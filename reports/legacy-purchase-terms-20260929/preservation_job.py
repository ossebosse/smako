"""Read-only comparison to the preserved prior candidate; no consumer identifiers emitted."""
import json,hashlib,sqlite3
from pathlib import Path
from job import configure,save
configure()
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
def prepared(root):
 file=PreparedUniverseArtifactStore(Path(root)/'price-universes').resolve_active_artifact('Lund',verify_hash=True)
 return PreparedPriceUniverseArtifact.model_validate_json(file.read_bytes()).restore()
before=prepared('/prior');after=prepared('/work')
policy=json.loads(Path('/work/policy.json').read_bytes())
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
report={'mandatory_contexts':{},'policy_sha256':hashlib.sha256(Path('/work/policy.json').read_bytes()).hexdigest()}
for context in policy['required_context_ids']:
 old=sorted((p.model_dump(mode='json') for p in before.universe.products if p.store_id==context),key=lambda p:p['product_id'])
 new=sorted((p.model_dump(mode='json') for p in after.universe.products if p.store_id==context),key=lambda p:p['product_id'])
 report['mandatory_contexts'][context]={'before':len(old),'after':len(new),'identical':old==new,'before_sha256':digest(old),'after_sha256':digest(new)}
 assert old==new,context
with sqlite3.connect('file:/prior/plans.sqlite?mode=ro',uri=True) as prior,sqlite3.connect('file:/work/plans.sqlite?mode=ro',uri=True) as current:
 for table,key in [('consumer_plan_revisions','plan_id,revision'),('personal_private_state','id')]:
  columns=[r[1] for r in prior.execute(f'pragma table_info({table})')]
  keys=[columns.index(k) for k in key.split(',')]
  old=prior.execute(f'select * from {table}').fetchall()
  now={tuple(r[i] for i in keys):r for r in current.execute(f'select * from {table}')}
  unchanged=all(now.get(tuple(r[i] for i in keys))==r for r in old)
  report[table]={'retained_records':len(old),'unchanged':unchanged}
  assert unchanged,table
save('preservation-result',report)
print('five mandatory bases and all prior saved records unchanged')
