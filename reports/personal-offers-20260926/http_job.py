"""Real loopback HTTP, native private process, saved source replay. No price network."""
import os, json, secrets, time, hashlib, sys, subprocess
from pathlib import Path
from datetime import datetime, UTC
from functools import partial

arm=sys.argv[1]
if '--serve' not in sys.argv:
    os.environ.update(APP_ENV='development', BUILD_ID='personal-offers-isolated-20260926',
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

recipe={'name':'Ostsmörgås', 'servings':1,
        'ingredients':[{'name':'bröd','quantity':100,'unit':'g'},{'name':'ost','quantity':100,'unit':'g'}],
        'instructions':['Servera tillsammans.']}
# Store identity discovered from the immutable official municipality-built artifact.
prepared=runtime.PreparedPriceUniverseArtifact.model_validate_json(source.read_bytes()).restore()
p=next(p for p in prepared.universe.products if p.name=='Hushållsost' and p.chain=='lidl')
request={'postal_code':'22350','recipes':0,'max_stores':1,
         'allowed_store_ids':[p.store_id], 'purchase_planning_mode':'estimated',
         'memberships':{'willys':False,'lidl':True},
         'personal':{'allow_nutrition_estimates':True,
                     'meals':[{'meal_type':'breakfast','count':1,'servings':1,
                               'limits':{'min_protein_g':30}}],
                     'slots':[{'id':'breakfast-1','day':1,'meal_type':'breakfast','recipe':recipe}]}}
report={'kind':'real-source HTTP PersonalPlanner meal, isolated historical replay',
        'clock':CLOCK.isoformat(),'actual_started_at':datetime.now(UTC).isoformat(),
        'source_requests':0, 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'request':request, 'arm':arm, 'cases':[], 'scope':'One ordinary cold bread/cheese recipe, explicit one official Lidl price context; no product lock, candidate mutation or extra purchase.'}

def start():
    process=subprocess.Popen([sys.executable,__file__,arm,'--serve'])
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
    (out/('http-'+arm+'-integration.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str))

server=start()
try:
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=180) as client:
        for mode in ('exact','estimated'):
            value=json.loads(json.dumps({**request,'purchase_planning_mode':mode}))
            value['personal']['pantry_revision']=client.get('/api/personal/state').json()['revision']
            began=time.perf_counter();response=client.post('/api/plans',json=value)
            result=response.json();record={'mode':mode,'seconds':round(time.perf_counter()-began,3),'http_status':response.status_code,'response':result}
            report['cases'].append(record);save()
            print(json.dumps({'mode':mode,'status':response.status_code,'seconds':record['seconds']}),flush=True)
            if response.status_code==201:
                plan_id=result['id'] if 'id' in result else result['plan_id']
                reread=client.get('/api/plans/'+plan_id);record['get_status']=reread.status_code
                record['roundtrip_identical']=reread.json()==result
                assert reread.status_code==200 and record['roundtrip_identical']
                if mode=='estimated':
                    saved_id=plan_id; saved=result
        # Stop and restart the ordinary lifespan: reload hash-verified artifact and PlanStore.
        stop(server)
        server=start()
        if 'saved_id' not in locals():
            report['restart']={'not_run':'estimated meal did not succeed'}
            save();raise SystemExit(1)
        response=client.get('/api/plans/'+saved_id)
        report['restart']={'http_status':response.status_code,'saved_plan_identical':response.json()==saved,
                           'artifact_reloaded':True, 'process_restarted':True}
        assert response.status_code==200 and report['restart']['saved_plan_identical']
        save()
finally:
    stop(server);save()

