"""Real loopback HTTP, native private process, saved source replay. No price network."""
import os, json, secrets, time, hashlib, sys, subprocess
from pathlib import Path
from datetime import datetime, UTC
from functools import partial

arm=sys.argv[1]
if '--serve' not in sys.argv:
    os.environ.update(APP_ENV='development', BUILD_ID='recipe-resolution-isolated-20260926',
        SECRET_KEY=secrets.token_hex(32), BETA_ADMIN_TOKEN=secrets.token_hex(32),
        PUBLIC_BASE_URL='http://127.0.0.1:8765',
        GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite', GROCERY_RAW_SNAPSHOT_ROOT='/work/raw',
        PLAN_STORE_PATH='/work/http-meal-'+arm+'-'+secrets.token_hex(6)+'.sqlite', PRICE_UNIVERSE_REQUIRED='true',
        PRICE_UNIVERSE_CACHE_ROOT='/work/http-universes', PRICE_UNIVERSE_CITY='Lund',
        PLAN_PREWARM_ENABLED='false')
CLOCK=datetime.fromisoformat('2026-09-24T21:16:35.494010+00:00')
class ReplayClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return CLOCK.astimezone(tz) if tz else CLOCK.replace(tzinfo=None)

# Only business clocks are frozen. Observation timestamps/artifact bytes remain original.
import app.services.personal_planner as personal
import app.api.plan as plan_api
import app.services.price_universe_runtime as runtime
import grocery_data.app.services.prepared_universe_activation as activation
personal.datetime=plan_api.datetime=runtime.datetime=activation.datetime=ReplayClock
from app.config import get_settings
from app.main import app
import uvicorn, httpx

if '--serve' in sys.argv:
    uvicorn.run(app,host='127.0.0.1',port=8765,log_level='warning',access_log=False)
    raise SystemExit(0)

out=Path('/work/profile');out.mkdir(exist_ok=True)
source=Path('/work/universe.json')
settings=get_settings()
publication=activation.PreparedUniverseArtifactStore(settings.price_universe_cache_root).activate(
    source, city='Lund', activated_at=CLOCK,
    validator=partial(activation.validate_backend_prepared_universe_artifact,
                      required_context_ids=settings.price_universe_required_context_ids))
assert publication.status == 'active_from_prebuilt_artifact', publication

cases=json.loads((out/'all-84.json').read_bytes())
selected=[c for c in cases if c['adapted']['name'] in {
 'Mustig gryta på kyckling med potatis och rödlök',
 'Potatisgratäng med kyckling och gul lök','Äggsmörgås med tomat'}]
assert len(selected)==3 and all(c.get('nutrition_basket_passed') for c in selected)
request={'postal_code':'22350','recipes':1,'max_stores':2,
 'purchase_planning_mode':'estimated','memberships':{'willys':True,'lidl':True},
 'personal':{'allow_nutrition_estimates':True,
 'meals':[{'meal_type':'dinner','count':1,'servings':2,'limits':{'min_protein_g':40}}]}}
report={'kind':'ordinary HTTP PersonalPlanner, isolated historical price replay with newly acquired facts',
 'clock':CLOCK.isoformat(),'actual_started_at':datetime.now(UTC).isoformat(),
 'price_source_requests':0,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'arm':arm,'cases':[],'scope':'Three previously blocked v1 recipes, unchanged amounts, original 40/30 g protein targets, ordinary area, max two stores. No product lock, extras or candidate mutation.'}

def start(rollback=False):
    env=dict(os.environ)
    if rollback: env["PYTHONPATH"]="/evaluation:/rollback/backend:/rollback"
    process=subprocess.Popen([sys.executable,__file__,arm,"--serve"],env=env)
    for _ in range(1800):
        if process.poll() is not None: raise RuntimeError('server stopped during startup')
        try:
            httpx.get('http://127.0.0.1:8765/api/health',timeout=.5)
            return process
        except httpx.TransportError:
            time.sleep(.1)
    process.terminate();process.wait(30)
    raise RuntimeError('server startup timed out')

def stop(process):
    process.terminate();process.wait(30)


def save():
    (out/('http-new-recipes-'+arm+'-integration.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str))

server=start()
try:
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=180) as client:
        saved_plans=[]
        for case in selected:
          for mode in ('exact','estimated'):
            value=json.loads(json.dumps({**request,'purchase_planning_mode':mode}))
            value['recipes']=1 if case['meal_type']=='dinner' else 0
            value['personal']['meals']=[{'meal_type':case['meal_type'],'count':1,'servings':case['adapted']['servings'],'limits':{'min_protein_g':40 if case['meal_type']=='dinner' else 30}}]
            value['personal']['slots']=[{'id':case['meal_type']+'-1','day':1,'meal_type':case['meal_type'],'recipe':case['adapted']}]
            value['personal']['pantry_revision']=client.get('/api/personal/state').json()['revision']
            began=time.perf_counter();response=client.post('/api/plans',json=value)
            result=response.json();record={'recipe':case['adapted']['name'],'request':value,'mode':mode,'seconds':round(time.perf_counter()-began,3),'http_status':response.status_code,'response':result}
            report['cases'].append(record);save()
            print(json.dumps({'recipe':record['recipe'],'mode':mode,'status':response.status_code,'seconds':record['seconds']}),flush=True)
            if mode=='exact' and case['meal_type']=='breakfast':
                assert response.status_code==422,result
                continue
            assert response.status_code==201,result
            plan_id=result.get('id',result.get('plan_id'))
            reread=client.get('/api/plans/'+plan_id)
            record['roundtrip_identical']=reread.status_code==200 and reread.json()==result
            assert record['roundtrip_identical']
            saved_plans.append((plan_id,result))
        # Stop and restart the ordinary lifespan: reload hash-verified artifact and PlanStore.
        stop(server)
        server=start()
        report['restart']=[]
        for plan_id,saved in saved_plans:
            response=client.get('/api/plans/'+plan_id)
            check={'plan_id':plan_id,'http_status':response.status_code,'saved_plan_identical':response.json()==saved}
            assert response.status_code==200 and check['saved_plan_identical']
            report['restart'].append(check)
        report['ui_state']=client.get('/api/personal/state').json()
        stop(server);server=start(rollback=True)
        report['rollback']=[]
        for plan_id,saved in saved_plans:
            response=client.get('/api/plans/'+plan_id)
            check={'plan_id':plan_id,'get_status':response.status_code,'saved_plan_identical':response.json()==saved}
            assert response.status_code==200 and check['saved_plan_identical']
            mutation={'action':'recalculate','revision':saved['revision'],
                      'pantry_revision':client.get('/api/personal/state').json()['revision']}
            response=client.post('/api/personal/plans/'+plan_id+'/change',json=mutation)
            check.update(recalculate_status=response.status_code,recalculate_response=response.json())
            # The old implementation cannot resolve these recipes. It must preserve the saved plan.
            assert response.status_code==422,response.text
            check['preserved_after_failed_recalculate']=client.get('/api/plans/'+plan_id).json()==saved
            assert check['preserved_after_failed_recalculate']
            report['rollback'].append(check)
        save()

finally:
    stop(server);save()

