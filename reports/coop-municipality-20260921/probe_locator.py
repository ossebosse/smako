import asyncio,json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

R=Path(__file__).parent
async def main():
 tasks=[];rows=[]
 async def capture(response):
  u=urlsplit(response.url)
  if u.hostname!='external.api.coop.se' or not any(x in u.path.lower() for x in ['store','butik']):return
  if any(x in u.path.lower() for x in ['cart','customer','member']):return
  row={'url':'https://'+u.hostname+u.path,'status':response.status}
  try:
   data=await response.json();row['shape']=list(data)[:15] if isinstance(data,dict) else 'list'
   # Store response inspection only; no headers, cookies or runtime settings.
   row['sample']=str(data)[:1000]
   (R/'public-store-response.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
  except Exception:pass
  rows.append(row)
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True);page=await b.new_page()
  page.on('response',lambda resp:tasks.append(asyncio.create_task(capture(resp))))
  await page.goto('https://www.coop.se/butiker-erbjudanden/',wait_until='domcontentloaded')
  try:await page.get_by_role('button',name='Endast nödvändiga cookies',exact=True).click(timeout=5000)
  except Exception:pass
  await page.get_by_placeholder('Sök butik',exact=True).fill('Lund')
  await page.wait_for_timeout(2000)
  await asyncio.gather(*tasks)
  await b.close()
 (R/'locator-probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(rows,ensure_ascii=False))
asyncio.run(main())
