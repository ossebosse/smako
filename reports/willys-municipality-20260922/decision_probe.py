"""Read only current clocks/manifests in isolated and live runtimes."""
import json
import shlex
import subprocess
from pathlib import Path

HERE=Path(__file__).parent
IMAGE='smako-willys-candidate:municipality-20260922'
STAGE='/var/tmp/smako-willys-municipality-20260922'
program="""import json
from pathlib import Path
from datetime import datetime,UTC
from collections import Counter
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
root=Path('/work/lifecycle');now=datetime.now(UTC)
store=PreparedUniverseArtifactStore(root/'price-universes')
result={'checked_at':now.isoformat(),'test_data_only':True,'production_activation':False,'universes':{}}
for name,path in [('Lund',store.resolve_active_artifact('Lund',verify_hash=True)),('Malmo',root/'malmo.json')]:
 p=PreparedPriceUniverseArtifact.model_validate_json(path.read_bytes()).restore()
 result['universes'][name]=p.status(now=now).model_dump(mode='json')
 counts=Counter(x.store_id for x in p.universe.products if x.chain=='willys')
 result['universes'][name]['willys_by_source_store']={s.source_store_id:counts[s.store_id] for s in p.stores if s.chain=='willys'}
print(json.dumps(result))
"""
cmd=['docker','run','--rm','--network','none','--user','10001:10001','--read-only','--cpus','1','--memory','2g','-e','PYTHONPATH=/srv/app/backend:/srv/app','-v',STAGE+'/data:/work:ro','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',program]
code='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
result=json.loads(r.stdout)
(HERE/'decision-current.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps({name:{k:s[k] for k in ['status','oldest_price_age_hours','usable_context_count','excluded_stale_context_count']} for name,s in result['universes'].items()}))

live="""import json,hashlib
from pathlib import Path
p=Path('/srv/app/var/price_universes/active/city-lund.json')
b=p.read_bytes();m=json.loads(b)
print(json.dumps({'manifest_sha256':hashlib.sha256(b).hexdigest(),'universe_id':m['universe_id'],'activated_at':m['activated_at']}))
"""
cmd=['docker','exec','--user','10001:10001','smako-app-1','python','-c',live]
code='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],capture_output=True)
if r.returncode==0:
 result=json.loads(r.stdout)
 (HERE/'production-readonly-final.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps({'production_manifest':result}))
else:
 print(json.dumps({'production_readonly_check':'unavailable','exit':r.returncode}))
