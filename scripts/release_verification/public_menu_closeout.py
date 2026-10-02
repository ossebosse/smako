"""Capture allowlisted closeout evidence, matched to the actual browser IDs."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--browser-output',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--personal-output',type=Path)
args=parser.parse_args()
cases=[json.loads(p.read_bytes()) for p in args.browser_output.glob('*.json') if not p.name.endswith('-network-failure.json')]
ids=[c['headers']['x-request-id'] for c in cases]
if args.personal_output:
 ids += [c['request_id'] for c in json.loads(args.personal_output.read_bytes())['cases']]
assert ids and all(len(value)<=128 and all(c.isalnum() or c=='-' for c in value) for value in ids)
code='''import json,os,sqlite3
from sqlalchemy.engine import make_url
from app.config import get_settings
s=get_settings()
with sqlite3.connect('file:'+make_url(os.environ['GROCERY_DATABASE_URL']).database+'?mode=ro',uri=True) as c:
 c.row_factory=sqlite3.Row
 ids=IDS
 rows=[dict(r) for r in c.execute('SELECT created_at,request_id,endpoint,method,duration_ms,status_code,error_code,build_id FROM beta_request_metrics WHERE request_id IN ('+','.join('?' for _ in ids)+')',ids)]
print(json.dumps({'metrics':rows,'settings':{k:getattr(s,k) for k in ['build_id','own_sources_only','price_provider','price_universe_required','price_universe_required_context_ids','max_price_age_hours','price_age_warning_hours']}}))
'''.replace('IDS',repr(ids))
result=subprocess.run(['ssh','-o','BatchMode=yes','smako','docker exec -i smako-app-1 python -'],input=code,capture_output=True,text=True,check=True)
report=json.loads(result.stdout)
report['public']={}
with httpx.Client(base_url='https://beta.smako.nu',timeout=40) as client:
 probe_id=cases[0]['body']['plan_id']
 report['stranger_read_status']=client.get('/api/plans/'+probe_id).status_code
 assert report['stranger_read_status']==403
 for path in ['/health','/ready','/api/price-universe/status']:
  response=client.get(path)
  report['public'][path]={'status':response.status_code,'body':response.json()}
 for name in ['app.js','index.html','personal.js','service-worker.js']:
  path='/' if name=='index.html' else '/service-worker.js' if name=='service-worker.js' else '/static/'+name
  response=client.get(path)
  relative='backend/app/static/'+name
  expected=subprocess.check_output(['git','show','14cc716ae54e2bb09ceaed5c4e3c2159e3a9c97d:'+relative])
  report['public'][name]={'status':response.status_code,'sha256':hashlib.sha256(response.content).hexdigest(),
                          'matches_release':response.content==expected,'cache_control':response.headers.get('cache-control')}
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'matched_requests':len(report['metrics']),'expected':len(ids),'statuses':[r['status_code'] for r in report['metrics']]}))
assert len(report['metrics'])==len(ids)
