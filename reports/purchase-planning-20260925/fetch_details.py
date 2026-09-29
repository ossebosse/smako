import httpx,json,hashlib
from pathlib import Path
from datetime import datetime,UTC
r=Path('reports/purchase-planning-20260925/sources')
with httpx.Client(timeout=30,follow_redirects=True) as c:
 for name,url in [('arla-hushallsost','https://www.arla.se/produkter/arla-brand/hushallsost-2200g-793680/'),('slv-persika','https://dataportal.livsmedelsverket.se/livsmedel/api/v1/livsmedel/580?sprak=1')]:
  x=c.get(url);x.raise_for_status();suffix='.html' if name.startswith('arla') else '.json'
  (r/(name+suffix)).write_bytes(x.content);(r/(name+'-acquisition.json')).write_text(json.dumps({'url':str(x.url),'status':x.status_code,'sha256':hashlib.sha256(x.content).hexdigest(),'observed_at':datetime.now(UTC).isoformat()},ensure_ascii=False),encoding='utf-8')
  if name.startswith('slv'):
   food=x.json();print(food);link=next(z['href'] for z in food['links'] if z['rel']=='naringvarden')
   n=c.get('https://dataportal.livsmedelsverket.se/livsmedel'+link);n.raise_for_status()
   (r/'slv-persika-nutrients.json').write_bytes(n.content)
   (r/'slv-persika-nutrients-acquisition.json').write_text(json.dumps({'url':str(n.url),'status':n.status_code,'sha256':hashlib.sha256(n.content).hexdigest(),'observed_at':datetime.now(UTC).isoformat()}),encoding='utf-8')
  else:
   from bs4 import BeautifulSoup
   soup=BeautifulSoup(x.text,'html.parser');print('H1',soup.h1.get_text(' ',strip=True))
   for tag in soup.select('script[type="application/ld+json"]'):print(tag.get_text()[:2000])
   (r/'arla-text.txt').write_text(soup.get_text(' ',strip=True),encoding='utf-8')
