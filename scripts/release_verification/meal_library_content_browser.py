"""Fixed content qualification/rendering diagnostic; not free menu economics.

Accept any already imported content pack. Ordinary owned async jobs, saved GETs
and the actual personal page render the exact issued recipes. No menu mocks.
"""
import argparse
import hashlib
import json
import time
import uuid
from collections import Counter
from pathlib import Path

from app.models import PlanRequest
from app.services.meal_library_content import validate_pack
from app.services.recipe_library import _scaled
from playwright.sync_api import expect, sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',required=True)
parser.add_argument('--pack',type=Path,required=True)
parser.add_argument('--request',type=Path,required=True)
parser.add_argument('--browser',choices=['chromium','webkit'],required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--take-per-type',type=int,default=7,choices=range(1,8))
args=parser.parse_args()
assert args.base=='http://127.0.0.1:18128', 'Only the owned isolated app'
args.output.mkdir(parents=True,exist_ok=False)
checked=validate_pack(args.pack)
assert not checked['rejections'],checked['rejections']
recipes=[];selection_counts=Counter()
for recipe in checked['recipes']:
    category=recipe.design.meal_types[0]
    if selection_counts[category]<args.take_per_type:
        recipes.append(recipe);selection_counts[category]+=1
counts=Counter();slots=[]
for recipe in recipes:
    category=recipe.design.meal_types[0];counts[category]+=1
    servings=2 if category=='dinner' else 1
    slots.append({'id':f'{category}-{counts[category]}','day':counts[category],
        'meal_type':category,'recipe':_scaled(recipe,servings).model_dump(mode='json')})
request=json.loads(args.request.read_text(encoding='utf8'))
request['recipes']=counts['dinner'];request['recipe_preferences'].update(cuisines=[],min_ingredients=3,max_ingredients=20,min_protein_g=None,cuisine_distribution='free',min_distinct_cuisines=None,max_same_main_protein_dinners=None)
request['personal'].update(slots=slots,use_pantry=False,pantry_revision=0)
for meal in request['personal']['meals']:
    category=meal['meal_type'];meal.update(count=counts[category],servings=2 if category=='dinner' else 1,
        limits={'min_protein_g':0,'max_kcal':4000},max_same_base_meals=None,
        recipe_choices={'dinner_level':'simple'} if category=='dinner' else {})
request=PlanRequest.model_validate(request).model_dump(mode='json')
errors=[]
def fp(saved):return hashlib.sha256(json.dumps({'request':saved['request'],'plan':saved['plan']},sort_keys=True).encode()).hexdigest()
with sync_playwright() as pw:
    browser=getattr(pw,args.browser).launch()
    context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    context.expose_binding('__smakoUnhandled',lambda source,data:errors.append('unhandledrejection: '+data['message']))
    context.add_init_script("window.addEventListener('unhandledrejection',e=>{window.__smakoUnhandled({message:String(e.reason?.message||e.reason)}).catch(()=>{});});")
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(args.base+'/personal');page.wait_for_load_state('networkidle')
    reference=str(uuid.uuid4());headers={'Prefer':'respond-async','X-Request-ID':reference,'Origin':args.base}
    started=time.monotonic()
    response=context.request.post(args.base+'/api/plans',data=request,headers=headers,timeout=60000)
    assert response.status==202,response.text()
    status_url=response.json()['status_url']
    (args.output/'job.json').write_text(json.dumps({'request_id':reference,'status_url':status_url,'accepted':response.json()},indent=2),encoding='utf8')
    duplicate=context.request.post(args.base+'/api/plans',data=request,headers=headers,timeout=60000)
    assert duplicate.status in {201,202} and (duplicate.status==201 or duplicate.json()['status_url']==status_url)
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        status=context.request.get(args.base+status_url,timeout=60000)
        assert status.status in {201,202},status.text()
        if status.status==201:break
        page.wait_for_timeout(1000)
    else:raise TimeoutError('Original job did not finish; no new generation')
    saved=status.json();plan=saved['plan'];plan_id=saved['plan_id']
    assert {(s['recipe']['design']['base_id'],s['recipe']['design']['version']) for s in plan['personal']['slots']}=={(r.design.base_id,r.design.version) for r in recipes}
    assert len(plan['recipes'])==len(recipes) and plan['optimized_basket']['store_count']<=request['max_stores']
    assert len(plan['personal']['checks']['nutrition'])==len(recipes)
    assert plan['personal']['checks']['checkout_audit']['status'] in {'PASS','passed','VERIFIED'}
    (args.output/'saved.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf8')
    read=context.request.get(args.base+f'/api/plans/{plan_id}?revision={saved["revision"]}')
    assert read.status==200 and fp(read.json())==fp(saved)
    page.goto(args.base+'/personal#plan='+plan_id)
    page.reload()  # A fragment-only goto does not run document initialization.
    expect(page.locator('#plan-content h1')).to_have_text('Din plan',timeout=60000)
    summaries=page.locator('#plan-content details > summary').filter(has_text='Öppna recept')
    assert summaries.count()==len(recipes)
    for summary in summaries.all():
        if summary.evaluate('el=>!el.parentElement.open'):summary.click()
    for recipe in recipes:expect(page.locator('#plan-content')).to_contain_text(recipe.name)
    assert page.locator('#shopping-content').inner_text().strip()
    page.screenshot(path=str(args.output/'result.png'))
    (args.output/'rendered.txt').write_text(page.locator('#plan-content').inner_text(),encoding='utf8')
    other=browser.new_context();other.request.get(args.base+'/')
    denied=other.request.get(args.base+'/api/plans/'+plan_id)
    assert denied.status in {403,404}
    assert not errors,errors
    (args.output/'report.json').write_text(json.dumps({'outcome':'PASS','browser':args.browser,'mobile_emulation':True,
        'fixed_content_diagnostic':True,'free_selection':False,'request_id':reference,'status_url':status_url,
        'same_idempotent_job':True,'recipe_count':len(recipes),'paid':plan['optimized_basket']['total'],
        'seconds':time.monotonic()-started,'saved_hash':fp(saved),'separate_owner_status':denied.status,
        'pageerrors':errors,'cookies_recorded':False},ensure_ascii=False,indent=2),encoding='utf8')
    browser.close()
