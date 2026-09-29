import httpx,json,hashlib
from pathlib import Path
from datetime import datetime,UTC
r=Path('reports/purchase-planning-20260925/sources');r.mkdir(exist_ok=True)
with httpx.Client(timeout=25,follow_redirects=True) as c:
 for term in ['persika','hårdost']:
  x=c.get('https://soknaringsinnehall.livsmedelsverket.se/Home/HamtaLivsmedelTillAutoComplete',params={'sokOrd':term,'soktyp':'1'});x.raise_for_status()
  (r/(term+'-search.json')).write_bytes(x.content)
  (r/(term+'-search-acquisition.json')).write_text(json.dumps({'url':str(x.url),'observed_at':datetime.now(UTC).isoformat(),'sha256':hashlib.sha256(x.content).hexdigest()},ensure_ascii=False),encoding='utf-8')
  print(term,x.json())
