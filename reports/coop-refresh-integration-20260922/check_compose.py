"""Parse only the prepared overlay with synthetic configuration; never up/run."""
import json
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
payload = {p.name: p.read_text(encoding='utf8') for p in [ROOT/'deploy/compose.yaml', ROOT/'deploy/coop-runtime.override.yaml']}
program = '''import json,sys,os,pathlib,subprocess
root=pathlib.Path('/var/tmp/smako-coop-refresh-integration-20260922')
assert (root/'.owner').read_text()=='coop-refresh-integration-20260922'
target=root/'compose-review';target.mkdir(exist_ok=True)
for name,content in json.load(sys.stdin).items():
 assert name in ['compose.yaml','coop-runtime.override.yaml']
 (target/name).write_text(content)
env={**os.environ,'ACME_EMAIL':'validation@example.invalid','BUILD_ID':'isolated-compose-check','PUBLIC_BASE_URL':'http://127.0.0.1:8000',
 'SECRET_KEY':'configuration-validation-only-'+('a'*32),'BETA_ADMIN_TOKEN':'configuration-validation-only-'+('b'*32),
 'GROCERY_DATABASE_URL':'sqlite:////work/grocery.sqlite','PLAN_STORE_PATH':'/work/plans.sqlite',
 'GROCERY_RAW_SNAPSHOT_ROOT':'/work/raw','PRICE_UNIVERSE_CACHE_ROOT':'/work/pu',
 'COOP_ALLOW_FULL_CRAWL':'true','COOP_ONLINE_CONTEXT_IDS':'730400','COOP_MUNICIPALITY_CODE':'1281',
 'COOP_MUNICIPAL_OFFERS_ENABLED':'true','COOP_XTRA_OFFERS_ENABLED':'false',
 'COOP_RELEASE_IMAGE':'smako-coop-candidate:refresh-integration-20260922'}
cmd=['docker','compose','-f',str(target/'compose.yaml'),'-f',str(target/'coop-runtime.override.yaml'),'--profile','ops','config','--format','json']
checked=subprocess.run(cmd,env=env,capture_output=True)
if checked.returncode:print(checked.stderr.decode(),file=sys.stderr);raise SystemExit(checked.returncode)
value=json.loads(checked.stdout)
result={}
for name in ['app','scheduler','refresh-once']:
 service=value['services'][name]
 assert service.get('entrypoint')==[]
 assert service['image']==env['COOP_RELEASE_IMAGE']
 assert service['environment']['COOP_MUNICIPALITY_CODE']=='1281'
 result[name]={k:service.get(k) for k in ['image','entrypoint','command','user','tmpfs','cpus','mem_limit']}
print(json.dumps({'status':'PASS','operation':'config only; no containers started','services':result}))
'''
completed = subprocess.run(['ssh','-o','BatchMode=yes','smako','python3 -c '+shlex.quote(program)],
    input=json.dumps(payload).encode(),capture_output=True,check=False)
if completed.returncode:
    print(completed.stderr.decode(errors="replace")[-1800:]);raise SystemExit(completed.returncode)
data = json.loads(completed.stdout)
(HERE/'compose-check.json').write_text(json.dumps(data,indent=2),encoding='utf8')
print(json.dumps(data))
