"""Run on server: isolate app state and use read-only production prices, no collectors."""
import json
import subprocess
from pathlib import Path

root = Path('/opt/smako/evidence/public-menu-20261002')
root.mkdir(parents=True, exist_ok=True)
def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)
app = json.loads(run('docker','inspect','smako-app-1'))[0]
env = dict(v.split('=',1) for v in app['Config']['Env'])
env.update(PLAN_STORE_PATH='/probe/plans.sqlite3', GROCERY_DATABASE_URL='sqlite:////probe/grocery.sqlite',
           BUILD_ID='public-menu-isolated-probe')
private=root/'probe.private.env'
private.write_text(''.join(k+'='+v+'\n' for k,v in env.items()))
private.chmod(0o600)
state=root/'state'
state.mkdir(exist_ok=True)
mounts={m['Destination']:m['Source'] for m in app['Mounts']}
source=mounts['/srv/app/var/grocery']
backup_code="""
import sqlite3,os
from pathlib import Path
target=Path('/probe/grocery.sqlite')
assert not target.exists()
source=next(p for p in Path('/source').glob('*.sqlite') if p.name=='grocery_data.sqlite')
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as a, sqlite3.connect(target) as b: a.backup(b)
os.chown('/probe',10001,10001)
os.chown(target,10001,10001)
print('Consistent isolated database copied')
"""
if not (state/'grocery.sqlite').exists():
    print(run('docker','run','--rm','-i','--network','none','--user','0',
              '-v',source+':/source:ro','-v',str(state)+':/probe',app['Image'],'python','-',input=backup_code))
launcher=root/'probe_launcher.py'
launcher.write_text('''import faulthandler
faulthandler.enable()
faulthandler.dump_traceback_later(30, repeat=True)
from app.services.basket_optimizer import BasketOptimizer
original = BasketOptimizer._eligible_store_subsets
def observe(self, stores, limit):
    if limit > 3:
        print("PROBE_SUBSETS stores="+str(len(stores))+" limit="+str(limit), flush=True)
    return original(self, stores, limit)
BasketOptimizer._eligible_store_subsets = observe
from app.services.meal_plan_optimizer import MealPlanService
create = MealPlanService.create_plan
async def diagnostic_create(self, request):
    try:
        return await create(self, request)
    except ValueError as exc:
        import json, traceback
        traceback.print_tb(exc.__traceback__)
        print("PROBE_ERROR "+type(exc).__name__, flush=True)
        if hasattr(exc, "errors"):
            print(json.dumps(exc.errors(include_input=False, include_context=False, include_url=False)), flush=True)
        raise
MealPlanService.create_plan = diagnostic_create
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, access_log=False)
''')
command=['docker','run','-d','--name','smako-public-menu-probe5','--env-file',str(private),
         '--cpus','2','--memory','3g','-p','127.0.0.1:18082:8000','-v',str(state)+':/probe']
for target,source in mounts.items():
    if target in {'/srv/app/var/price_universes','/srv/app/var/raw_snapshots','/srv/app/var/grocery'}:
        command+=['-v',source+':'+target+':ro']
for path in ['backend/app/services/meal_plan_optimizer.py','backend/app/services/user_pricing.py',
             'backend/app/api/plan.py','backend/app/static/app.js']:
    command+=['-v',str(root/path)+':/srv/app/'+path+':ro']
command += ['-v',str(launcher)+':/probe_launcher.py:ro',app['Image'],'python','/probe_launcher.py']
print(run(*command).strip())
