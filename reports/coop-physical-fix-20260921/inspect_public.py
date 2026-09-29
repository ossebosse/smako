import asyncio,json
from pathlib import Path
from grocery_data.app.domain import SourceStore
from grocery_data.app.connectors.coop.browser import CoopBrowserOffersTransport
R=Path('reports/coop-physical-fix-20260921')
class Inspect(CoopBrowserOffersTransport):
 async def _stable_cards(self,page,selector,*,declared_total):
  cards=await super()._stable_cards(page,selector,declared_total=declared_total)
  observed=await page.locator(selector).evaluate_all('''els => els.filter(e => /pris|kronor|öre/i.test(e.getAttribute('aria-label')||'')).map(e=>({label:e.getAttribute('aria-label'),article:e.closest('article').innerText,html:e.closest('article').outerHTML}))''')
  (R/'inspect-cards.json').write_text(json.dumps(observed,ensure_ascii=False,indent=2),encoding='utf-8')
  print('cards',len(cards),'first',observed[0]['article'],flush=True)
  # One ordinary public card action to inspect the product/condition dialog.
  consent=page.get_by_role('button',name='Endast nödvändiga cookies',exact=True)
  if await consent.count():await consent.click(timeout=5000)
  await page.locator(selector).first.click(timeout=5000)
  await page.wait_for_timeout(1500)
  dialogs=await page.locator('[role=dialog]').evaluate_all('''els=>els.map(e=>({text:e.innerText,html:e.outerHTML}))''')
  (R/'inspect-dialog.json').write_text(json.dumps(dialogs,ensure_ascii=False,indent=2),encoding='utf-8')
  print('dialogs',[(x['text'][:3500]) for x in dialogs],flush=True)
  return cards
async def main():
 a=json.loads(Path('reports/municipality-offers-20260920/coop-audit.json').read_bytes())
 s=next(SourceStore(**x['store']) for x in a['stores'] if x['store']['external_id']=='3839')
 raw=await Inspect().fetch(s)
 (R/'inspect-source.json').write_bytes(raw.payload)
 print(raw.fetched_at,flush=True)
asyncio.run(main())
