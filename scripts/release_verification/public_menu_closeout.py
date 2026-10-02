"""Capture allowlisted closeout evidence, matched to the actual browser IDs."""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--browser-output',type=Path,required=True,action='append')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--personal-output',type=Path)
parser.add_argument('--release',default='HEAD')
args=parser.parse_args()
cases=[json.loads(p.read_bytes()) for directory in args.browser_output for p in directory.glob('*.json') if not p.name.endswith('-network-failure.json')]
cases=[c for c in cases if 'case' in c]
ids=[]
for case in cases:
 ids += [r['request_id'] for r in case.get('transport',[]) if r.get('request_id')]
 ids += [case['headers']['x-request-id']]
 if case.get('initial_rejection'):
  ids += [case['initial_rejection']['headers']['x-request-id']]
if args.personal_output:
 ids += [c['request_id'] for c in json.loads(args.personal_output.read_bytes())['cases']]
ids=list(dict.fromkeys(ids))
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
 probe_id=next(c['body']['plan_id'] for c in cases if c['status']==201)
 report['stranger_read_status']=client.get('/api/plans/'+probe_id).status_code
 assert report['stranger_read_status']==403
 for path in ['/health','/ready','/api/price-universe/status']:
  response=client.get(path)
  report['public'][path]={'status':response.status_code,'body':response.json()}
 for name in ['app.js','index.html','personal.js','service-worker.js']:
  path='/' if name=='index.html' else '/service-worker.js' if name=='service-worker.js' else '/static/'+name
  response=client.get(path)
  relative='backend/app/static/'+name
  expected=subprocess.check_output(['git','show',args.release+':'+relative])
  report['public'][name]={'status':response.status_code,'sha256':hashlib.sha256(response.content).hexdigest(),
                          'matches_release':response.content==expected,'cache_control':response.headers.get('cache-control')}
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'matched_requests':len(report['metrics']),'expected':len(ids),'statuses':dict(Counter(r['status_code'] for r in report['metrics']))}))
assert len(report['metrics'])==len(ids)
