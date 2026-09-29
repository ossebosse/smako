import asyncio,json,re,hashlib
from pathlib import Path
import httpx
async def main():
 async with httpx.AsyncClient(timeout=30,follow_redirects=True) as c:
  out=[]
  for url in ['https://www.hemkop.se/erbjudanden/4517','https://www.hemkop.se/butik/4517']:
   r=await c.get(url); scripts=re.findall(r'<script[^>]*src=["\']([^"\']+)',r.text);links=re.findall(r'href=["\']([^"\']+)',r.text)
   row={'url':url,'status':r.status_code,'sha256':hashlib.sha256(r.content).hexdigest(),'scripts':scripts,'links':[x for x in links if any(k in x for k in ['erbjud','4517','eo.se'])]}
   out.append(row)
  scripts=['/_next/static/chunks/2469.905b737145b55a59.js']
  for s in scripts[:2]:
   r=await c.get(s if s.startswith('https:') else 'https://www.hemkop.se'+s)
   patterns=sorted(set(re.findall(r'.{0,200}(?:storeId|store:|q:|offline|sort:).{0,450}',r.text)))
   out.append({'script':s,'status':r.status_code,'patterns':patterns[:40]})
  Path('/work/hemkop-public-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out[2:],ensure_ascii=True))
asyncio.run(main())
