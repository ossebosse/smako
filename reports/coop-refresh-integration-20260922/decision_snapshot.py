"""Read final private deadlines and production identities, never refresh/activate."""
import json
import shlex
import subprocess
from pathlib import Path

STAGE="/var/tmp/smako-coop-refresh-integration-20260922"
program="""import json,hashlib,os,sys
sys.path.insert(0,"/evaluation")
from datetime import UTC,datetime
from pathlib import Path
from lifecycle import configure, ROOT
configure()
from deploy.scripts.run_daily_refresh import demand_refresh_plan
from grocery_data.app.services.coop_offer_job import configuration, location, read
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
plan=demand_refresh_plan(now=datetime.now(UTC));plan.pop('state',None);plan.pop('state_path',None)
root,config=configuration()
manifest=PreparedUniverseArtifactStore(ROOT/'price-universes').read_active('Lund')
state=read(location(root,config))
prod=Path('/srv/app/var/price_universes/active/city-lund.json')
print(json.dumps({'at':datetime.now(UTC).isoformat(),'schedule':plan,'configuration':config,
 'publication':state.get('publication'),'source_approval':state.get('last_source_approval_at'),
 'active_private':manifest.model_dump(mode='json'),'production_manifest_sha256':hashlib.sha256(prod.read_bytes()).hexdigest()},default=str))
"""
cmd=['docker','run','--rm','-i','--read-only','--network','none','--user','10001:10001','--memory','512m','--cpus','1',
 '--tmpfs','/tmp:rw,size=16m,mode=1777','-e','PYTHONPATH=/evaluation:/srv/app/backend:/srv/app',
 '--mount',f'type=bind,source={STAGE}/evaluation,target=/evaluation,readonly',
 '--mount',f'type=bind,source={STAGE}/data,target=/work,readonly',
 '--mount','type=bind,source=/srv/smako/data/price_universes,target=/srv/app/var/price_universes,readonly',
 '--entrypoint','/bin/sh','smako-coop-candidate:refresh-integration-20260922','-c',
 'f=$(mktemp); cat > "$f"; set -a; . "$f"; set +a; rm "$f"; exec /opt/ica-venv/bin/python -c '+shlex.quote(program)]
code="import subprocess,sys; env=subprocess.check_output(['docker','exec','-u','0','smako-scheduler-1','cat','/run/grocery-beta-environment']); r=subprocess.run("+repr(cmd)+",input=env,capture_output=True); del env; sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)"
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True)
if r.returncode:print(r.stderr.decode(errors='replace')[-1600:]);raise SystemExit(r.returncode)
d=json.loads(r.stdout);Path(__file__).with_name('decision-state.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'at':d['at'],'production_manifest_sha256':d['production_manifest_sha256'],'private_id':d['active_private']['universe_id'],'next_base':d['schedule']['sources'],'publication_status':d['publication']['status']},ensure_ascii=False))
