"""Inspect only the isolated runtime and hash the actual immutable serving rows."""
import os,json,sys,sqlite3,hashlib,subprocess
from pathlib import Path
from datetime import datetime,UTC
from collections import Counter
from job import configure,save
configure();P=Path('/work')
r={'checked_at':datetime.now(UTC),'production_activation':False}
with sqlite3.connect(P/'grocery.sqlite') as db:
 db.row_factory=sqlite3.Row
 r['active_snapshots']=[dict(x) for x in db.execute('select id,chain,scope_key,coverage,created_at,metrics,state from catalog_snapshots where is_active=1')]
 r['schema']={t:[x[1] for x in db.execute('pragma table_info('+t+')')] for t in ['products','catalog_snapshots','collection_errors']}
manifest=P/'price-universes/active/city-lund.json'
if manifest.exists():
 m=json.loads(manifest.read_bytes());f=P/'price-universes'/m['artifact_file'];assert hashlib.sha256(f.read_bytes()).hexdigest()==m['artifact_sha256'];r['manifest']=m
 from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
 p=PreparedPriceUniverseArtifact.model_validate_json(f.read_bytes()).restore()
 r['products']=len(p.universe.products);r['stores']=[s.model_dump(mode='json') for s in p.stores]
 r['counts']={str(k):v for k,v in Counter((x.chain,x.store_id,str(x.price_context_type),str(x.coverage)) for x in p.universe.products).items()}
 r['status']=p.status(now=datetime.now(UTC)).model_dump(mode='json')
else:r['publication']='absent; no served active artifact or complete current base can be asserted'
save('inspection',r);print(json.dumps({k:v for k,v in r.items() if k not in ['schema','stores','active_snapshots']},default=str)[:2500])
