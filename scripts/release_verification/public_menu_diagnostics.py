"""Read-only, allowlisted production evidence. No credentials or identities exported."""
import hashlib
import json
import subprocess
from pathlib import Path

import httpx

OUT = Path('.local/public-menu-20261002')
OUT.mkdir(parents=True, exist_ok=True)
code = r'''
import json, os, sqlite3
from datetime import datetime, timezone
from app.config import get_settings
s=get_settings()
out={'checked_utc':datetime.now(timezone.utc).isoformat(), 'settings':{k:getattr(s,k) for k in ['app_env','build_id','price_provider','own_sources_only','price_universe_required','max_price_age_hours','price_age_warning_hours','price_universe_required_context_ids']},'own_base_configured':bool(s.own_grocery_base_url)}
from sqlalchemy.engine import make_url
path=make_url(os.environ['GROCERY_DATABASE_URL']).database
db=sqlite3.connect('file:'+path+'?mode=ro',uri=True)
db.row_factory=sqlite3.Row
out['morning_requests']=[dict(r) for r in db.execute("SELECT created_at,request_id,endpoint,method,duration_ms,status_code,error_code,build_id FROM beta_request_metrics WHERE created_at >= '2026-10-02T05:15:00' AND created_at < '2026-10-02T05:30:00' ORDER BY created_at")]
out['reproductions']=[dict(r) for r in db.execute("SELECT created_at,request_id,endpoint,method,duration_ms,status_code,error_code,build_id FROM beta_request_metrics WHERE request_id IN ('4f363c813de649f384b20d86a693f491','61721907c2cb4401a6554207e13be720','03548dcd1ee04ccaadb49d91f3c77015')")]
print(json.dumps(out))
'''
result = subprocess.run(['ssh','-o','BatchMode=yes','smako','docker exec -i smako-app-1 python -'],input=code,capture_output=True,text=True,check=True)
out = json.loads(result.stdout)
out['public']={}
with httpx.Client(base_url='https://beta.smako.nu', timeout=40) as client:
    for path in ['/health','/ready','/api/price-universe/status']:
        r=client.get(path)
        out['public'][path]={'status':r.status_code,'body':r.json()}
    for file in ['app.js','index.html','personal.js']:
        r=client.get('/' if file=='index.html' else '/static/'+file)
        local=Path('backend/app/static')/file
        out['public'][file]={'status':r.status_code,'sha256':hashlib.sha256(r.content).hexdigest(),'local_sha256':hashlib.sha256(local.read_bytes()).hexdigest(),'cache_control':r.headers.get('cache-control')}
(OUT/'diagnostics-before.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='public'},ensure_ascii=False,indent=2))
print(json.dumps({k:{'status':v['status'],'body':v.get('body',{}).get('status'),'matches':v.get('sha256')==v.get('local_sha256')} for k,v in out['public'].items()}))
