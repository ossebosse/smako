import asyncio,json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
R=Path('reports/coop-physical-fix-20260921')
async def main():
 tasks=[];rows=[]
 async def capture(response):
  path=urlsplit(response.url).path
  if response.request.resource_type not in {'xhr','fetch'}:return
  if not (urlsplit(response.url).hostname or '').endswith('.coop.se') or path != '/dke/offers/sorting-groups/106445':return
  record={'host':urlsplit(response.url).hostname,'path':path,'status':response.status}
  try:
   obj=await response.json()
   (R/'public-structured-inspection.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
   record['keys']=list(obj)[:50] if isinstance(obj,dict) else 'list'
   # Keys only at this stage; no credentials or runtime config are saved.
   def scan(v):
    keys=set()
    if isinstance(v,dict):
     keys.update(v)
     for child in v.values():keys.update(scan(child))
    elif isinstance(v,list):
     for child in v[:3]:keys.update(scan(child))
    return keys
   record['nested_keys']=sorted(scan(obj))[:250]
  except Exception:record['json']=False
  rows.append(record)
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True);page=await b.new_page()
  page.on('response',lambda response:tasks.append(asyncio.create_task(capture(response))))
  await page.goto('https://www.coop.se/butiker-erbjudanden/coop/coop-flojtvagen/',wait_until='domcontentloaded')
  await page.wait_for_selector('article button[aria-label]')
  await page.wait_for_timeout(2000)
  await asyncio.gather(*tasks)
  await b.close()
 (R/'public-response-shapes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 for row in rows: print(row,flush=True)
asyncio.run(main())
