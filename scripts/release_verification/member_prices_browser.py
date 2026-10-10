"""Real mobile browser checks against the isolated conditional membership candidate."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

from complete_recipe_browser import record_response, wait_operation
from playwright.sync_api import expect, sync_playwright

p = argparse.ArgumentParser()
p.add_argument('--base', default='http://127.0.0.1:18132')
p.add_argument('--output', type=Path, required=True)
p.add_argument('--expected-build', required=True)
a = p.parse_args()
assert a.base.startswith('http://127.0.0.1:')
a.output.mkdir(parents=True, exist_ok=False)
for _ in range(180):
    try:
        with urllib.request.urlopen(a.base+'/ready', timeout=3) as response:
            ready = json.load(response)
        if ready['build_id'] == a.expected_build and ready['status'] == 'ready':
            break
    except OSError:
        pass
    time.sleep(1)
else:
    raise TimeoutError('Isolated packaged application not ready')

with sync_playwright() as pw:
    for engine in ('chromium', 'webkit'):
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={'width':390,'height':844})
        page = context.new_page()
        errors, failures, observed = [], [], []
        page.on('pageerror', lambda e, errors=errors: errors.append(str(e)))
        page.on('requestfailed', lambda r, failures=failures: failures.append({'url':r.url,'error':r.failure}))
        page.on('response', lambda r, observed=observed: record_response(r, observed))
        try:
            page.goto(a.base+'/personal#choices')
            expect(page.locator('input[name="membership"][value="COOP_MEMBER"]')).to_be_enabled(timeout=120000)
            page.get_by_role('button', name='Mina val', exact=True).click()
            assert page.locator('input[name="membership"]:checked').count()==0
            page.get_by_role('button',name='Sök varor',exact=True).click()
            page.locator('#product-query').fill('Satsumas')
            page.locator('#product-query').press('Enter')
            card=page.locator('#product-search-results article').filter(has=page.get_by_role('heading',name='Satsumas',exact=True)).filter(has_text='Coop Online Syd')
            expect(card.locator('.product-result-price')).to_have_text('20,00 kr/kg',timeout=30000)
            card.locator('details').first.locator(':scope > summary').click()
            expect(card).to_contain_text('slutbeloppet beror på faktisk vikt')
            page.screenshot(path=str(a.output/(engine+'-comparison.png')))
            page.get_by_role('button',name='Inköpslista',exact=True).click()
            page.get_by_role('button',name='Lägg till vara',exact=True).click()
            with page.expect_response(lambda r:'/shopping-suggestions?' in r.url):
                page.locator('#shopping-query').fill('Satsumas')
            page.locator('#shopping-generic-results button').first.click()
            page.get_by_label('Önskad mängd',exact=True).fill('1000')
            page.get_by_role('button',name='Bekräfta och lägg till',exact=True).click()
            expect(page.locator('#shopping-estimated-purchases')).not_to_be_checked()
            page.locator('#calculate-own-list').click()
            expect(page.locator('#personal-status')).to_contain_text('Tillåt uppskattad vikt',timeout=120000)
            expect(page.locator('#calculate-own-list')).to_be_enabled(timeout=10000)
            page.locator('#shopping-estimated-purchases').check()
            begin=len(observed)
            page.locator('#calculate-own-list').dblclick()
            operation,_=wait_operation(page,observed,begin,timeout=180)
            expect(page.locator('#shopping-content .personal-total')).to_be_visible(timeout=180000)
            starts=[r for r in observed[begin:] if r.request.method=='POST' and r.url.endswith('/api/plans')]
            assert len(starts)==1
            terminals=[r.captured_body for r in observed[begin:] if r.status==201 and r.captured_body]
            saved=terminals[-1].get('saved',terminals[-1])
            assert saved['plan']['optimized_basket']['total']==22.4
            assert saved['plan']['personal']['checks']['checkout_audit']['passed']
            assert saved['request']['purchase_planning_mode']=='estimated'
            assert saved['request']['membership_price_policy']=='all_advertised'
            assert not saved['request']['membership_programs']
            assert not any(saved['request']['memberships'].values())
            expect(page.locator('#shopping-content .membership-plan-summary')).to_contain_text('Totalsumman kräver Coop medlem')
            plan_id=saved['plan_id']
            assert page.request.get(a.base+'/api/plans/'+plan_id).json()['plan']==saved['plan']
            page.wait_for_load_state('networkidle')
            page.reload()
            expect(page.locator('#plan-content .personal-total')).to_be_visible(timeout=30000)
            expect(page.locator('#shopping-estimated-purchases')).to_be_checked()
            page.get_by_role('button',name='Inköpslista',exact=True).click()
            page.screenshot(path=str(a.output/(engine+'-basket.png')))
            page.get_by_role('button',name='Min plan',exact=True).click()
            begin=len(observed)
            page.get_by_role('button',name='Räkna om med aktuellt skafferi/pris',exact=True).click()
            wait_operation(page,observed,begin,timeout=180)
            latest=page.request.get(a.base+'/api/plans/'+plan_id).json()
            assert latest['revision']==saved['revision']+1
            assert latest['plan']['optimized_basket']==saved['plan']['optimized_basket']
            assert page.request.get(a.base+'/api/plans/'+plan_id+'?revision=1').json()['plan']==saved['plan']
            # Tightening the mode must fail without replacing the saved basket.
            page.get_by_role('button',name='Inköpslista',exact=True).click()
            page.locator('#shopping-estimated-purchases').uncheck()
            page.locator('#calculate-extras').click()
            expect(page.locator('#personal-status')).to_contain_text('Tillåt uppskattad vikt',timeout=120000)
            expect(page.locator('#calculate-extras')).to_be_enabled(timeout=10000)
            unchanged=page.request.get(a.base+'/api/plans/'+plan_id).json()
            assert unchanged['revision']==latest['revision']
            assert unchanged['plan']==latest['plan']
            page.locator('#shopping-estimated-purchases').check()
            other=browser.new_context()
            assert other.request.get(a.base+'/api/plans/'+plan_id).status==403
            other.close()
            assert not errors and not failures,(errors,failures)
            assert not [r.status for r in observed if r.status>=500]
            report={'status':'PASS','engine':engine,'build':a.expected_build,'purchase_mode':'estimated',
                'total':22.4,'member_rate_per_kg':20,'start_posts':len(starts),'checkout_audit':True,'no_memberships_selected':True,'conditional_summary_visible':True,
                'saved_get_equal':True,'reload':True,'recalculated_revision':latest['revision'],
                'failed_exact_mutation_preserved_revision':True,'old_revision_equal':True,
                'owner_isolation':403,'errors':errors,'failed_requests':failures,'operation':operation}
            print(engine,'PASS',flush=True)
        except Exception as exc:
            report={'status':'FAIL','engine':engine,'error':repr(exc),'page_errors':errors,'failed_requests':failures}
            page.screenshot(path=str(a.output/(engine+'-failure.png')))
            raise
        finally:
            (a.output/(engine+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            browser.close()
